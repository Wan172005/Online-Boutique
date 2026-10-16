# Kubernetes và Online Boutique bằng Ansible trên Azure

Project dựng Kubernetes bằng `kubeadm` trên hai VM **Ubuntu 24.04** có sẵn trong Azure: một control plane và một worker. Ansible cấu hình containerd, Flannel, Kubernetes, Helm 3, sau đó triển khai Online Boutique qua `kubernetes.core.helm`.

Yêu cầu tham khảo: [Project01_Ansible.pdf](Project01_Ansible.pdf). Inventory thật được giữ ở local; dùng [inventory.ini.example](inventory.ini.example) làm mẫu.

## Part 1 — Create the Virtual Machines

Tự chuẩn bị **hai VM Azure Ubuntu 24.04**: một master và một worker; cài Python 3, cấu hình SSH key, quyền sudo cho `azureuser` và sao chép `inventory.ini.example` thành `inventory.ini` rồi cập nhật IP public, SSH user và đường dẫn key. File inventory thật không được commit. Máy điều khiển cần Ansible core từ 2.16.

Master có ít nhất 2 vCPU/2 GB RAM; worker nên có ít nhất 2 vCPU/4 GB RAM. Hai VM có IP private khác nhau, kết nối được với nhau; mạng VM không chồng Pod CIDR `10.244.0.0/16` hoặc Service CIDR `10.96.0.0/12`. Cho phép SSH, Kubernetes API, kubelet, Flannel VXLAN, NodePort frontend và outbound tải dependency/image theo cấu hình lab.

**Minh chứng báo cáo:** thông tin hai VM, mạng private và inventory. Repository sử dụng VM có sẵn, không tự tạo VM.

## Nguồn gốc

Dựa trên ví dụ Kubernetes trong Ansible for DevOps của Jeff Geerling, điều chỉnh cho hai VM Azure có sẵn. Yêu cầu đối chiếu lấy từ [Project01_Ansible.pdf](Project01_Ansible.pdf).
