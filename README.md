# Kubernetes và Online Boutique bằng Ansible trên Azure

Project dựng Kubernetes bằng `kubeadm` trên hai VM **Ubuntu 24.04** có sẵn trong Azure: một control plane và một worker. Ansible cấu hình containerd, Flannel, Kubernetes, Helm 3, sau đó triển khai Online Boutique qua `kubernetes.core.helm`.

Yêu cầu tham khảo: [Project01_Ansible.pdf](Project01_Ansible.pdf). Inventory thật được giữ ở local; dùng [inventory.ini.example](inventory.ini.example) làm mẫu.

## Part 1 — Create the Virtual Machines

Tự chuẩn bị **hai VM Azure Ubuntu 24.04**: một master và một worker; cài Python 3, cấu hình SSH key, quyền sudo cho `azureuser` và sao chép `inventory.ini.example` thành `inventory.ini` rồi cập nhật IP public, SSH user và đường dẫn key. File inventory thật không được commit. Máy điều khiển cần Ansible core từ 2.16.

Master có ít nhất 2 vCPU/2 GB RAM; worker nên có ít nhất 2 vCPU/4 GB RAM. Hai VM có IP private khác nhau, kết nối được với nhau; mạng VM không chồng Pod CIDR `10.244.0.0/16` hoặc Service CIDR `10.96.0.0/12`. Cho phép SSH, Kubernetes API, kubelet, Flannel VXLAN, NodePort frontend và outbound tải dependency/image theo cấu hình lab.

**Minh chứng báo cáo:** thông tin hai VM, mạng private và inventory. Repository sử dụng VM có sẵn, không tự tạo VM.

## Part 2 — Build the Kubernetes Cluster

Theo PDF trang 3–4, Ansible dựng cluster, cấu hình mạng và đợi cluster sẵn sàng. Entry point thực tế là `main.yml`; folder không có `playbooks/cluster.yml` nêu làm ví dụ trong PDF.

Cài dependency trên máy điều khiển trước khi dựng cluster (role đã có trong `roles/` thì không cần tải lại):

```bash
ansible-galaxy role install -r requirements.yml --roles-path ./roles
ansible-galaxy collection install -r requirements.yml
ansible-playbook main.yml --syntax-check
ansible-playbook main.yml --tags preflight
ansible-playbook main.yml
```

Không dùng `--limit` khi dựng cluster: playbook cần facts cả hai node và IP private master trước khi join worker. `--tags preflight` chỉ kiểm tra inventory, OS, tài nguyên và mạng.

Luồng thực hiện:

1. Kiểm tra inventory, Ubuntu 24.04, RAM/CPU, IP/CIDR; tắt swap hiện tại, trong fstab và Azure Linux Agent.
2. Role swap xử lý swapfile; role Docker chỉ cài `containerd.io`. Task bổ sung bật overlay, IPv4 forwarding, CRI và systemd cgroups.
3. Trên master, chuẩn bị bootstrap kubelet, render Flannel và ghi IP private cho kubelet. Role Kubernetes cài package, chạy `kubeadm init` và áp dụng CNI.
4. Hold package, cài kubeconfig cho SSH user và cài Helm 3 bằng task riêng. Project không dùng hai role `geerlingguy.containerd`/`geerlingguy.helm` nêu trong PDF; chức năng tương ứng được thực hiện bằng cách trên.
5. Worker nhận join command từ role trên master, đợi API private và join với tên node theo inventory.
6. Đợi từng node Ready, rollout Flannel/CoreDNS, toàn bộ Pod `kube-system` Ready và lấy kubeconfig về `artifacts/admin.conf`.

Flannel dùng `--iface=$(NODE_IP)`, với `NODE_IP` từ `status.hostIP`; kubelet đăng ký IP private qua `/etc/default/kubelet`. Cách này chọn interface theo địa chỉ node thực tế thay cho hard-code `enp0s8` trong Vagrant.

Để kiểm tra cluster và lấy thông tin báo cáo, **hãy vào trực tiếp VM master**, rồi chạy các lệnh `kubectl` bằng `azureuser` (đã được cấp kubeconfig):

```bash
ssh -i ~/.ssh/OpenStack-VM_key.pem azureuser@20.255.48.151
kubectl get nodes -o wide
kubectl -n kube-system get pods -o wide
kubectl -n kube-flannel get pods -o wide
helm version --short
```

Kubeconfig xuất về `artifacts/admin.conf` trỏ `https://127.0.0.1:6443` mặc định; truy cập từ máy local cần SSH tunnel. Các bước kiểm tra thủ công trong tài liệu dùng trực tiếp VM master.

**Minh chứng báo cáo:** PLAY RECAP, hai node Ready với INTERNAL-IP đúng, tất cả Pod `kube-system` Ready và phiên bản Helm.

## Nguồn gốc

Dựa trên ví dụ Kubernetes trong Ansible for DevOps của Jeff Geerling, điều chỉnh cho hai VM Azure có sẵn. Yêu cầu đối chiếu lấy từ [Project01_Ansible.pdf](Project01_Ansible.pdf).
