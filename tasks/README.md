# Task files dựng và kiểm tra Kubernetes/Online Boutique

Các file được playbook cha import.

## preflight.yml — Kiểm tra trước khi cấu hình VM

[preflight.yml](preflight.yml) kiểm tra Ubuntu 24.04, systemd, RAM theo facts ít nhất 1700 MB, control plane có ít nhất 2 vCPU và alias host hợp lệ làm tên node Kubernetes.

File đặt fact `kubernetes_node_ip` từ `kubernetes_private_ip` nếu được khai báo, nếu không lấy địa chỉ IPv4 trên NIC mặc định. Sau đó kiểm tra IP có trên NIC, không phải loopback `127.0.0.1`, không trùng giữa các node; in địa chỉ/interface được chọn. Python `ipaddress` kiểm tra Pod CIDR và Service CIDR không chồng nhau, IP node không nằm trong hai dải đó.

File không xác nhận toàn bộ dải VNet/VPN hay khả năng kết nối hai chiều giữa VM. Kiểm tra số lượng control plane/worker và yêu cầu chạy đủ host nằm trong `main.yml`. Fact IP được các task kubelet, Flannel và kubeadm sử dụng ở bước sau.

## prepare.yml — Chuẩn bị hệ điều hành và tắt swap

[prepare.yml](prepare.yml) chạy `swapoff -a` khi đang có swap, làm mới memory facts trước khi role swap chạy, comment dòng swap trong `/etc/fstab` và đặt `ResourceDisk.EnableSwap=n` nếu tồn tại `/etc/waagent.conf`.

File cài `ca-certificates`, `python3-debian`, `iproute2`, `iptables`, `conntrack`, `socat`, với APT cache hợp lệ trong 3600 giây. Role `geerlingguy.swap` chạy sau đó để xử lý swapfile theo `swap_file_path`; việc xóa swapfile không nằm trực tiếp trong task file này.

## containerd.yml — Cấu hình container runtime

[containerd.yml](containerd.yml) lưu module `overlay` vào `/etc/modules-load.d/kubernetes.conf`, nạp nếu chưa có, ghi `net.ipv4.ip_forward = 1` vào `/etc/sysctl.d/99-kubernetes.conf` và áp dụng sysctl.

Sau khi role Docker cài `containerd.io`, file lấy cấu hình từ `containerd config default`, đổi `SystemdCgroup = false` thành `true`, ghi `/etc/containerd/config.toml` và gọi handler `Restart containerd` khi nội dung thay đổi. Cấu hình mặc định này được dùng để bật CRI. Cuối cùng, dịch vụ containerd được bật và chạy. Cấu hình bridged traffic do role Kubernetes đảm nhiệm.

## control-plane-bootstrap.yml — Chuẩn bị kubelet trước kubeadm init

[control-plane-bootstrap.yml](control-plane-bootstrap.yml) kiểm tra `/etc/kubernetes/admin.conf`. Nếu chưa có, file tạo systemd drop-in cho kubelet với `ConditionPathExists=/etc/kubernetes/admin.conf`, reload systemd khi cần và dừng kubelet đã cài.

Sau đó, `ss` kiểm tra không còn listener TCP 10250; assertion dừng play nếu cổng vẫn bị chiếm. Điều kiện tạm ngăn role bật kubelet quá sớm khi chạy lại một lần init chưa hoàn tất. Khi kubeadm ghi admin kubeconfig trong bootstrap, điều kiện cho phép kubelet chạy. `main.yml` gỡ drop-in sau khi role hoàn tất. File này chỉ áp dụng trên control plane.

## control-plane.yml — Chuẩn bị manifest Flannel

[control-plane.yml](control-plane.yml) tạo `/etc/kubernetes`, tải manifest theo `kubernetes_flannel_manifest_url` vào `kube-flannel-upstream.yml`, đọc nội dung rồi render [../templates/kube-flannel.yml.j2](../templates/kube-flannel.yml.j2) ra `/etc/kubernetes/kube-flannel.yml`.

Template thay Pod CIDR và thêm `NODE_IP` từ `status.hostIP` cùng `--iface=$(NODE_IP)` cho Flannel. Task file này **không chạy kubeadm init và không apply Flannel**; role `geerlingguy.kubernetes` thực hiện hai thao tác đó sau khi manifest đã sẵn sàng.

## kubelet.yml — Ghim địa chỉ IP node

[kubelet.yml](kubelet.yml) ghi `KUBELET_EXTRA_ARGS=--node-ip={{ kubernetes_node_ip }}` vào `/etc/default/kubelet`, trước khi role bật kubelet trên master hoặc worker.

Kết quả được lưu vào `kubernetes_kubelet_address`; `packages.yml` dựa vào trạng thái thay đổi này để restart kubelet. Mục đích là để node đăng ký địa chỉ mạng cluster đã chọn thay vì một địa chỉ trên NIC khác.

## packages.yml — Giữ phiên bản package và áp dụng IP kubelet

[packages.yml](packages.yml) đặt trạng thái `hold` cho `kubelet`, `kubeadm`, `kubectl` bằng `dpkg_selections`, tránh tự nâng phiên bản qua APT. Nếu `kubelet.yml` vừa đổi cấu hình IP, file reload systemd và restart kubelet.

Package và repository được role Kubernetes cài trước đó; task file này không tự cài package Kubernetes.

## workers.yml — Chuẩn bị join command cho worker

[workers.yml](workers.yml) kiểm tra `/etc/kubernetes/kubelet.conf`. Nếu worker chưa join, file đợi master private IP mở TCP 6443 và assert role control plane đã cung cấp join command.

Join command được chuẩn hóa whitespace thành một dòng, thêm `--node-name` theo alias inventory và đặt `systemctl stop kubelet &&` ở đầu. Role Kubernetes chạy command này sau bước bật dịch vụ kubelet, giúp giải phóng cổng 10250 ngay trước join. Fact chứa command được che bằng `no_log: true` ở task chuẩn bị.

Task file không tự thực thi join. Task của role dùng guard `creates=/etc/kubernetes/kubelet.conf` để bỏ qua command khi worker đã join. Cần chạy toàn bộ `main.yml` để có facts và join command từ master.

## kubeconfig.yml — Cấp kubeconfig cho SSH user

[kubeconfig.yml](kubeconfig.yml) đặt `/etc/kubernetes/admin.conf` thành `root:root`, mode `0600`; tra home của `ansible_user` qua `getent`; đặt thư mục `.kube` của root và SSH user thành `0700`.

Role Kubernetes đã cấu hình kubeconfig của root. File này sao chép admin kubeconfig sang `<home-của-ansible_user>/.kube/config`, owner là SSH user, mode `0600`, với `no_log: true`. Nhờ đó `azureuser` sử dụng được quyền quản trị cluster trên master. Việc tải kubeconfig về máy Ansible nằm trong `verify.yml`.

## helm.yml — Cài Helm 3 trên control plane

[helm.yml](helm.yml) xác nhận `helm_version` có dạng `v3.x.y` và kiến trúc VM là `x86_64` hoặc `aarch64`. File tải archive theo phiên bản/kiến trúc, kiểm tra SHA256 từ URL checksum, giải nén rồi chép binary vào `/usr/local/bin/helm` với mode `0755`.

Bước cuối chạy `helm version --short` và assert phiên bản khớp `helm_version`. Có thể gọi riêng qua playbook cha:

```bash
ansible-playbook main.yml --tags helm --limit k8s_control_plane
```

## verify.yml — Đợi cluster sẵn sàng và xuất kubeconfig

[verify.yml](verify.yml) đợi từng node trong inventory đăng ký và có condition Ready, đợi rollout DaemonSet Flannel trong `kube-flannel`, Deployment CoreDNS và tất cả Pod trong `kube-system` có condition Ready. Các lệnh đợi dùng `kubernetes_ready_timeout` (mặc định `300s`).

File tạo thư mục kubeconfig local với mode `0700`, fetch `/etc/kubernetes/admin.conf`, thay server endpoint theo `kubernetes_kubeconfig_server` và đặt file thành `0600`. Mặc định lưu tại `artifacts/admin.conf`, trỏ `https://127.0.0.1:6443`; khi truy cập từ local cần SSH tunnel. Cuối cùng in node/private IP và vị trí kubeconfig.

Đây là kiểm tra **cluster** ở Part 2. Việc kiểm tra ứng dụng Part 4 nằm trong `boutique-verify.yml`, được playbook riêng gọi.

## boutique-verify.yml — Xác nhận Online Boutique theo Part 4

[boutique-verify.yml](boutique-verify.yml) được [../playbooks/verify.yml](../playbooks/verify.yml) gọi sau khi playbook thu thập IP NIC từ tất cả node. File chỉ dùng command đọc/đợi tài nguyên, facts, assertion và HTTP GET; không cài dependency hoặc sửa ứng dụng.

File assert node Ready và InternalIP khớp `hostvars[node].kubernetes_node_ip`; đợi rollout của 11 Deployment trong `boutique_expected_deployments`, rồi kiểm tra generation và số replica cập nhật/Ready/available, không cho replica yêu cầu bằng 0. File kiểm tra Service checkoutservice port 5050, không còn Deployment/Service `servicename`, frontend là NodePort với HTTP port 80 và NodePort hợp lệ.

Cuối cùng, `uri` gọi storefront qua IP private worker từ master, yêu cầu HTTP 200 và nội dung khớp `boutique_storefront_pattern`. URL có thể override bằng `boutique_verify_url`; số lần thử lại/thời gian chờ giữa các lần lấy từ `boutique_verify_retries`/`boutique_verify_delay`. Kết quả in cả URL kiểm tra nội bộ và URL public cho trình duyệt. Các thao tác chỉ đọc vẫn chạy trong check mode, vì vậy `--check` vẫn kiểm tra cluster thật.

Chạy từ root bằng `ansible-playbook playbooks/verify.yml`, không dùng `--limit`. Verification không thay thế thử giỏ hàng/đặt hàng bằng trình duyệt.
