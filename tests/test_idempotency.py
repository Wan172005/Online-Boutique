"""Run real Ansible tasks locally with isolated files and fake cluster binaries.

Requires the roles/collections from requirements.yml and /usr/bin/python3-yaml.
No VM, package manager, system service, or real Kubernetes API is contacted.
Run from the repository root: /usr/bin/python3 -m unittest discover -s tests -v
"""

import copy
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml


REPO = Path(__file__).resolve().parents[1]


def read_yaml(path):
    return yaml.safe_load((REPO / path).read_text())


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="boutique-idempotency-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.admin = self.work / "admin.conf"
        self.worker_config = self.work / "kubelet.conf"
        self.events = self.work / "events.jsonl"
        self.releases = self.work / "releases.json"
        self.releases.write_text("[]")
        self.inventory = self.work / "inventory.ini"
        self.inventory.write_text(
            "[k8s_control_plane]\n"
            "localhost ansible_connection=local ansible_host=127.0.0.1 kubernetes_node_ip=10.0.0.1\n"
            "[k8s_workers]\n"
            "worker ansible_connection=local ansible_host=203.0.113.20 kubernetes_node_ip=10.0.0.2\n"
            "[k8s:children]\nk8s_control_plane\nk8s_workers\n"
        )
        fixture = self.bin / "fixture.py"
        fixture.write_text('''#!/usr/bin/python3
import json
import pathlib
import sys
work = pathlib.Path(__file__).resolve().parents[1]
binary = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
def event():
    with (work / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps([binary] + args) + '\\n')
if binary == 'kubeadm':
    event()
    if args[:2] == ['token', 'create']:
        print(str(work / 'bin/kubeadm') + ' join 10.0.0.1:6443 --token fixture-token\\n')
    elif args[0] == 'join':
        (work / 'kubelet.conf').write_text('joined')
    elif args[0] == 'init':
        (work / 'admin.conf').write_text('fixture admin kubeconfig')
    else:
        sys.exit('Unexpected kubeadm invocation: ' + repr(args))
elif binary == 'kubectl':
    if 'apply' in args:
        marker = work / 'flannel'
        result = marker.read_text() if marker.exists() else 'created'
        print('daemonset.apps/kube-flannel-ds ' + result)
        marker.write_text('unchanged')
    elif 'rollout' in args:
        print('successfully rolled out')
    elif 'json' in args:
        resource = args[args.index('get') + 1]
        print((work / (resource + '.json')).read_text())
    elif 'nodes' in args:
        print('localhost Ready\\nworker Ready')
    else:
        sys.exit('Unexpected kubectl invocation: ' + repr(args))
elif binary == 'helm':
    releases = json.loads((work / 'releases.json').read_text())
    if args[0] == 'version':
        print('version.BuildInfo{Version:"v3.21.4", GitCommit:"fixture"}')
    elif args[0] == 'list':
        name = args[args.index('--filter') + 1]
        print(json.dumps([dict(name=r['name'], status=r['status']) for r in releases if r['name'] == name]))
    elif args[:2] == ['get', 'values']:
        print('{}')
    elif args[0] == 'uninstall':
        event()
        (work / 'releases.json').write_text(json.dumps([r for r in releases if r['name'] != args[-1]]))
    else:
        sys.exit('Unexpected Helm invocation: ' + repr(args))
else:
    sys.exit('Unknown fixture binary: ' + binary)
''')
        fixture.chmod(0o755)
        for name in ("kubeadm", "kubectl", "helm"):
            (self.bin / name).symlink_to(fixture)

    def run_tasks(self, tasks, variables=None, expected_changed=0, check=False):
        variables = dict(variables or {})
        variables.update(
            ansible_python_interpreter=sys.executable,
            ansible_remote_tmp=str(self.work / "remote-tmp"),
        )
        play = dict(
            name="Isolated idempotency regression",
            hosts="localhost",
            gather_facts=False,
            vars=variables,
            tasks=copy.deepcopy(tasks),
        )
        playbook = self.work / "check.yml"
        playbook.write_text(yaml.safe_dump([play], sort_keys=False))
        env = dict(
            os.environ,
            ANSIBLE_CONFIG=str(REPO / "ansible.cfg"),
            ANSIBLE_LOCAL_TEMP=str(self.work / "local-tmp"),
            ANSIBLE_NOCOLOR="1",
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
        )
        command = ["ansible-playbook", "-i", str(self.inventory), str(playbook)]
        if check:
            command.append("--check")
        result = subprocess.run(
            command, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertRegex(result.stdout, rf"changed={expected_changed}\s", result.stdout)

    def mutations(self):
        if not self.events.exists():
            return []
        return [json.loads(line) for line in self.events.read_text().splitlines()]

    def rewrite_paths(self, value):
        if isinstance(value, str):
            return (value.replace("/etc/kubernetes/admin.conf", str(self.admin))
                    .replace("/etc/kubernetes/kubelet.conf", str(self.worker_config))
                    .replace("/root/.kube", str(self.work / "root/.kube")))
        if isinstance(value, list):
            return [self.rewrite_paths(item) for item in value]
        if isinstance(value, dict):
            return {key: (str(os.getuid()) if key == "owner" else
                          str(os.getgid()) if key == "group" else
                          self.rewrite_paths(item)) for key, item in value.items()}
        return value

    def test_export_writes_final_endpoint_once_and_preserves_credentials(self):
        tasks = read_yaml("tasks/verify.yml")
        tasks = tasks[next(i for i, t in enumerate(tasks) if t["name"].startswith("Create a private local")):]
        tasks = self.rewrite_paths(tasks[:3])
        original = "clusters:\n- cluster:\n    certificate-authority-data: fixture-cert\n    server: https://10.0.0.1:6443\nusers:\n- name: admin\n  user:\n    client-key-data: fixture-key\n"
        self.admin.write_text(original)
        destination = self.work / "artifacts/admin.conf"
        variables = dict(kubernetes_kubeconfig_local_path=str(destination),
                         kubernetes_kubeconfig_server="https://127.0.0.1:6443")
        self.run_tasks(tasks, variables, expected_changed=2)
        self.run_tasks(tasks, variables)
        exported = yaml.safe_load(destination.read_text())
        self.assertEqual(exported["clusters"][0]["cluster"]["server"], variables["kubernetes_kubeconfig_server"])
        self.assertEqual(exported["users"][0]["user"]["client-key-data"], "fixture-key")
        self.assertEqual(self.admin.read_text(), original)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        variables["kubernetes_kubeconfig_server"] = "https://vpn.example.test:6443"
        self.run_tasks(tasks, variables, expected_changed=1)
        self.run_tasks(tasks, variables)

    def test_kubeconfig_permissions_do_not_oscillate(self):
        tasks = [task for task in read_yaml("tasks/kubeconfig.yml") if "ansible.builtin.getent" not in task]
        tasks = self.rewrite_paths(tasks)
        self.admin.write_text("fixture kubeconfig")
        self.admin.chmod(0o600)
        variables = dict(ansible_user=getpass.getuser(), ansible_facts=dict(
            getent_passwd={getpass.getuser(): ["x", "0", "0", "", str(self.work / "ssh-user")]}
        ))
        self.run_tasks(tasks, variables, expected_changed=3)
        self.run_tasks(tasks, variables)
        root_config = self.work / "root/.kube/config"
        self.assertTrue(root_config.is_symlink())
        self.assertEqual(root_config.resolve(), self.admin)
        self.admin.chmod(0o644)
        (self.work / "root/.kube").chmod(0o755)
        self.run_tasks(tasks, variables, expected_changed=2)
        self.run_tasks(tasks, variables)

    def test_worker_rerun_does_not_create_a_token_or_rejoin(self):
        tasks = [task for task in read_yaml("tasks/workers.yml")
                 if not any(module in task for module in ("ansible.builtin.wait_for", "ansible.builtin.systemd_service"))]
        tasks = self.rewrite_paths(tasks)
        variables = dict(kubernetes_control_plane_host="localhost",
                         kubernetes_join_command_extra_opts="--cri-socket unix:///run/containerd/containerd.sock")
        self.run_tasks(tasks, variables, expected_changed=2)
        self.assertTrue(self.worker_config.exists())
        mutations = self.mutations()
        self.assertEqual(len(mutations), 2)
        self.assertEqual(mutations[0][1:3], ["token", "create"])
        self.assertEqual(mutations[1][-2:], ["--node-name", "localhost"])
        self.run_tasks(tasks, variables)
        self.assertEqual(self.mutations(), mutations)
        self.worker_config.unlink()
        self.run_tasks(tasks, variables, expected_changed=2)
        self.assertEqual(len(self.mutations()), 4)

    def test_control_plane_skips_init_and_reports_flannel_drift(self):
        tasks = self.rewrite_paths(read_yaml("tasks/kubernetes-init.yml"))
        tasks[1]["ansible.builtin.template"]["src"] = str(REPO / "templates/kubeadm-config.yml.j2")
        variables = read_yaml("roles/geerlingguy.kubernetes/defaults/main.yml")
        variables.update(read_yaml("vars/main.yml"))
        variables.update(kubernetes_kubeadm_kubelet_config_file_path=str(self.work / "kubeadm.yml"))
        self.run_tasks(tasks, variables, expected_changed=4)
        rendered = list(yaml.safe_load_all((self.work / "kubeadm.yml").read_text()))
        self.assertEqual([doc["kind"] for doc in rendered], ["InitConfiguration", "ClusterConfiguration", "KubeletConfiguration"])
        self.assertEqual(rendered[1]["kubernetesVersion"], "1.35.9")
        self.run_tasks(tasks, variables)
        self.assertEqual(len(self.mutations()), 1)
        (self.work / "flannel").write_text("configured")
        self.run_tasks(tasks, variables, expected_changed=1)
        self.run_tasks(tasks, variables)
        self.assertEqual(len(self.mutations()), 1)

    def test_teardown_repeats_without_uninstalling_again(self):
        self.admin.write_text("apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n")
        variables = read_yaml("vars/microservices.yml")
        variables.update(boutique_helm_binary=str(self.bin / "helm"), boutique_kubeconfig=str(self.admin))
        releases = [dict(name=item["name"], status="pending-install" if index == 0 else "deployed")
                    for index, item in enumerate(variables["boutique_releases"])]
        self.releases.write_text(json.dumps(releases))
        tasks = read_yaml("tasks/boutique-teardown.yml")
        self.run_tasks(tasks, variables, expected_changed=1, check=True)
        self.assertEqual(json.loads(self.releases.read_text()), releases)
        self.assertEqual(self.mutations(), [])
        self.run_tasks(tasks, variables, expected_changed=1)
        mutations = self.mutations()
        self.assertEqual([event[-1] for event in mutations], [item["name"] for item in reversed(variables["boutique_releases"])])
        self.assertEqual(json.loads(self.releases.read_text()), [])
        self.run_tasks(tasks, variables)
        self.assertEqual(self.mutations(), mutations)

    def test_application_verification_is_read_only_on_repeated_runs(self):
        variables = read_yaml("vars/microservices.yml")
        nodes = [dict(metadata=dict(name=name), status=dict(
            conditions=[dict(type="Ready", status="True")],
            addresses=[dict(type="InternalIP", address=address)]
        )) for name, address in (("localhost", "10.0.0.1"), ("worker", "10.0.0.2"))]
        deployments = [dict(metadata=dict(name=name, generation=2), spec=dict(replicas=1),
                            status=dict(observedGeneration=2, updatedReplicas=1, readyReplicas=1, availableReplicas=1))
                       for name in variables["boutique_expected_deployments"]]
        services = [dict(metadata=dict(name="checkoutservice"), spec=dict(ports=[dict(port=5050)])),
                    dict(metadata=dict(name="frontend"), spec=dict(type="NodePort", ports=[dict(port=80, nodePort=30080)]))]
        for name, items in (("nodes", nodes), ("deployments", deployments), ("services", services)):
            (self.work / (name + ".json")).write_text(json.dumps(dict(items=items)))

        class Storefront(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html>Online Boutique</html>")

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Storefront)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        variables["boutique_verify_url"] = f"http://127.0.0.1:{server.server_port}/"
        tasks = read_yaml("tasks/boutique-verify.yml")
        self.run_tasks(tasks, variables)
        self.run_tasks(tasks, variables, check=True)
        self.assertEqual(self.mutations(), [])


if __name__ == "__main__":
    unittest.main()
