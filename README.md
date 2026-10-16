# Kubernetes và Online Boutique bằng Ansible trên Azure

Project dựng Kubernetes bằng `kubeadm` trên hai VM **Ubuntu 24.04** có sẵn trong Azure: một control plane và một worker. Ansible cấu hình containerd, Flannel, Kubernetes, Helm 3, sau đó triển khai Online Boutique qua `kubernetes.core.helm`.

Tài liệu đối chiếu: [Project01_Ansible.pdf](Project01_Ansible.pdf), Part 1–5 ở trang 3–6; rubric ở trang 6–7. Các lệnh Ansible chạy từ folder `online-boutique/` trên máy điều khiển; các lệnh `kubectl` chạy trực tiếp trên VM master. Mã nguồn đã bổ sung kiểm tra Part 2 và Part 4; chưa chạy xác nhận trên VM thực tế.

## Hạ tầng và cấu trúc

Inventory thật `inventory.ini` được giữ ở local và nằm trong `.gitignore`. Khi tải project, sao chép [inventory.ini.example](inventory.ini.example) thành `inventory.ini`, rồi sửa địa chỉ VM, SSH user và đường dẫn key. IP public của môi trường hiện tại:

| Node | Nhóm inventory | Vai trò | IP public/SSH |
| --- | --- | --- | --- |
| `master` | `k8s_control_plane` | Control plane | `20.255.48.151` |
| `worker` | `k8s_workers` | Worker | `20.2.248.1` |

SSH dùng `azureuser`, key `~/.ssh/OpenStack-VM_key.pem`. IP public dùng cho SSH và truy cập frontend NodePort. Playbook lấy IP trên NIC mặc định để cấu hình cluster; có thể khai báo `kubernetes_private_ip` trên từng host nếu có nhiều NIC. Hai VM cần IP private khác nhau và kết nối được với nhau.

| Đường dẫn | Nội dung |
| --- | --- |
| [main.yml](main.yml) | Chuẩn bị VM, dựng control plane, join worker và kiểm tra cluster. |
| [playbooks/verify.yml](playbooks/verify.yml) | Kiểm tra node/private IP, 11 Deployment, Service và HTTP storefront. |
| [vars/main.yml](vars/main.yml) | Phiên bản phần mềm, mạng cluster, cấu hình role và kubeconfig. |
| [vars/microservices.yml](vars/microservices.yml) | Repository chart, namespace, 11 release và ba override ứng dụng. |
| [requirements.yml](requirements.yml) | Role và collection cần cài trên máy chạy Ansible. |
| [ansible.cfg](ansible.cfg) | Inventory mặc định, đường dẫn role và tùy chọn SSH. |
| [tasks/README.md](tasks/README.md) | Giải thích từng task file `.yml`. |
| [playbooks/README.md](playbooks/README.md) | Giải thích playbook verification và teardown. |
| [examples/README.md](examples/README.md) | Giải thích riêng `online-boutique.yml`. |
| [templates/kube-flannel.yml.j2](templates/kube-flannel.yml.j2) | Render Flannel với Pod CIDR và interface theo IP node. |

Phiên bản đang khai báo: Kubernetes `1.35.9`, Flannel `v0.28.9`, Helm `v3.21.4`. Đây là giá trị cấu hình trong mã nguồn, chưa xác nhận khả năng tải package/image trong lần kiểm tra này. Đổi biến phiên bản trên cluster đang chạy không thay thế quy trình nâng cấp.

## Tình trạng 5 Part

Bảng dưới phản ánh mã nguồn hiện có. Cần chạy trên VM và thu thập bằng chứng trước khi kết luận đáp ứng toàn bộ PDF.

| Part | Đã có | Chưa đủ hoặc khác PDF |
| --- | --- | --- |
| 1 — Create the Virtual Machines | Người thực hiện tự chuẩn bị hai VM Azure và cấu hình inventory. | Khác môi trường Vagrant của PDF; lưu minh chứng VM/network. |
| 2 — Build the Kubernetes Cluster | `main.yml` dựng cluster, đợi node, Flannel/CoreDNS và toàn bộ Pod `kube-system` Ready. | Cần log dựng sạch và chạy lại trên VM. |
| 3 — Deploy the Online Boutique | `examples/online-boutique.yml` clone chart, triển khai 11 Helm release vào `microservice`; đủ ba override. | Chưa có bằng chứng storefront/checkout hoạt động. `boutique_revision: main` chưa cố định commit chart để tái lập cùng phiên bản; đây là điểm nên cải thiện, không phải yêu cầu riêng của Part 3. |
| 4 — Verify and Use the Application | `playbooks/verify.yml` assert node/private IP, 11 Deployment, checkoutservice, frontend NodePort và HTTP 200/nội dung storefront. | Cần chạy verification trên VM và chụp bằng chứng mua hàng. |
| 5 — Teardown and Low-Memory Hosts | Có playbook gỡ 11 release, xác nhận release đã mất và API còn truy cập được; giữ cluster. Đã đặt `appReplicas: 1`. | Chưa có log teardown thực tế; dừng/xóa VM Azure là thao tác riêng. Cần minh chứng tương ứng nếu Azure được chấp nhận thay Vagrant. |

Ngoài 5 Part, **rubric trang 6–7 còn yêu cầu** các nội dung chưa thấy đủ mã nguồn hoặc bằng chứng trong folder:

- Hai thí nghiệm chẩn đoán mạng, phân biệt lỗi interface Flannel với lỗi IP kubelet.
- Tái hiện lỗi checkoutservice, báo cáo điều tra và đề xuất ngăn lỗi tái diễn. Hiện chỉ có override sửa tên.
- Ingress controller cài qua Ansible, định tuyến hostname, frontend trở về ClusterIP và mở rộng verification.
- Chart mở rộng được lưu trong project, limits dựa trên đo đạc, probes cho ít nhất bốn service và minh chứng restart.
- Scaling bằng Ansible, thực hiện drain và giải thích PodDisruptionBudget.
- Bằng chứng idempotency: `changed=0` ở lần chạy thứ hai, hai log chạy lại theo yêu cầu nộp bài và giải thích task chưa idempotent nếu có. Role Kubernetes đặt mode kubeconfig/root directory rồi task bổ sung đặt lại mode chặt hơn; đây là điểm cần kiểm tra bằng PLAY RECAP. Role cũng tạo join token mới dù task khai báo `changed_when: false`, nên không chỉ dựa vào recap để giải thích hành vi.
- Bộ nộp bài: repository có `.git`, `report.pdf`, thư mục `screenshots/` và `recap.txt` từ lần dựng sạch cùng hai lần kiểm tra idempotency.

Part 2 và Part 4 đã được bổ sung trong mã nguồn. Các nội dung rubric và bằng chứng thực tế nêu trên vẫn cần hoàn thiện.

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

## Part 3 — Deploy the Online Boutique

Theo PDF trang 4–5, triển khai bằng module Helm của Ansible, không chỉnh chart upstream. File thực hiện là [examples/online-boutique.yml](examples/online-boutique.yml); xem [examples/README.md](examples/README.md) để giải thích từng bước.

```bash
ansible-playbook examples/online-boutique.yml --syntax-check
ansible-playbook examples/online-boutique.yml
```

Playbook chạy trên master, chuẩn bị Git và Python client trong `/opt/kubernetes-client`, clone repository `iankisali/microservice-deployment` vào `/opt/online-boutique-charts`, rồi cài 11 release vào namespace `microservice`. Redis dùng `chart/redis`; các release khác dùng `chart/microservice`. Mỗi release có `wait: true`, timeout `10m`.

Ba override trong `vars/microservices.yml` được truyền qua `values`, ưu tiên cao hơn values file upstream:

| Override | Phạm vi | Mục đích theo PDF |
| --- | --- | --- |
| `appReplicas: 1` | Cấu hình chung các release | Giảm replica phù hợp worker của lab. |
| `serviceType: NodePort` | Release `frontendservice` | Truy cập storefront qua IP node và NodePort. |
| `appName: checkoutservice` | Release `checkoutservice` | Tránh Service/Deployment mang tên mặc định `servicename`. |

Theo PDF, values upstream của checkout khai báo trùng khóa `appImage`, làm thiếu `appName`; frontend lại gọi `checkoutservice:5050`. Override tên giúp hai bên khớp nhau. Việc tái hiện lỗi để lấy bằng chứng chưa được thực hiện trong lần kiểm tra này.

Playbook đọc Service `frontend` và in URL `http://20.2.248.1:<NODE_PORT>/`. Mở đúng cổng được trả về trên NSG/firewall worker cho máy demo; không giả định một NodePort cố định.

**Minh chứng báo cáo:** PLAY RECAP triển khai, 11 release, effective values frontend/checkout, URL thực tế và ảnh storefront.

## Part 4 — Verify and Use the Application

Chạy verification từ máy điều khiển sau Part 3:

```bash
ansible-playbook playbooks/verify.yml --syntax-check
ansible-playbook playbooks/verify.yml
```

[playbooks/verify.yml](playbooks/verify.yml) thu thập địa chỉ mạng trên cả hai VM, sau đó gọi [tasks/boutique-verify.yml](tasks/boutique-verify.yml) trên master để kiểm tra:

1. Mỗi node trong inventory Ready và có InternalIP khớp IP trên NIC đã chọn khi dựng cluster.
2. Đủ 11 Deployment dự kiến; revision hiện tại đã được controller ghi nhận, số replica cập nhật/Ready/available đáp ứng số replica yêu cầu và không scale về 0.
3. Deployment/Service mang tên `checkoutservice`, Service có port 5050 và không còn tài nguyên tên mặc định `servicename`.
4. Service `frontend` là NodePort, HTTP port 80 có NodePort trong khoảng 30000–32767.
5. HTTP từ master tới NodePort qua IP private worker trả `200` và chứa nội dung nhận diện Online Boutique/Hipster Shop.

Các thao tác kiểm tra chỉ đọc, không cài dependency hay chỉnh tài nguyên ứng dụng. Không dùng `--limit`, vì playbook cần địa chỉ thực tế của cả hai VM. Có thể đặt `kubernetes_private_ip` trên từng host nếu có nhiều NIC. Kết quả in URL public để demo; kiểm tra HTTP nội bộ chưa xác nhận rule NSG cho máy truy cập từ ngoài Azure.

Để tự kiểm tra cluster và ứng dụng, **hãy vào trực tiếp VM master** rồi chạy:

```bash
ssh -i ~/.ssh/OpenStack-VM_key.pem azureuser@20.255.48.151
kubectl get nodes -o wide
kubectl -n microservice get deployments,pods,services -o wide
kubectl -n microservice get deployment/checkoutservice service/checkoutservice service/frontend
helm -n microservice list
```

Mở URL public từ Part 3, xem sản phẩm, thêm vào giỏ rồi tải lại trang và hoàn tất đặt hàng. Chụp storefront, giỏ hàng và trang xác nhận đơn hàng. Theo PDF, Redis dùng `emptyDir`, nên không bảo đảm dữ liệu khi Pod Redis bị tạo lại.

**Minh chứng báo cáo:** PLAY RECAP verification, ảnh storefront/đơn hàng và kết quả từng thao tác. HTTP 200 trang chủ chưa chứng minh checkout thành công.

## Part 5 — Teardown and Low-Memory Hosts

Theo PDF trang 6, gỡ ứng dụng phải giữ cluster; dừng VM giữ đĩa khác với xóa VM. PDF không đặt thêm ngưỡng RAM riêng trong Part 5.

Các lệnh dưới gỡ ứng dụng khi bạn chủ động thực hiện:

```bash
ansible-playbook playbooks/teardown.yml --syntax-check
ansible-playbook playbooks/teardown.yml --check
ansible-playbook playbooks/teardown.yml
```

`--check` chỉ dự kiến thay đổi, bỏ qua xác nhận sau gỡ và không thay thế kết quả chạy thật. Playbook gỡ 11 release theo thứ tự ngược triển khai, đợi tài nguyên bị xóa, xác nhận không còn release và lấy danh sách node. Bước cuối xác nhận API còn truy cập được, chưa assert tất cả node Ready. Xem [playbooks/README.md](playbooks/README.md).

Namespace `microservice`, cluster, runtime, Helm, kubeconfig và VM được giữ lại. Dữ liệu gắn với tài nguyên ứng dụng bị xóa có thể mất. Triển khai lại bằng:

```bash
ansible-playbook examples/online-boutique.yml
```

Với VM ít RAM, hiện đã có `appReplicas: 1`. Vào từng VM và chạy `free -h` để xem bộ nhớ. Để kiểm tra workload, **hãy vào trực tiếp VM master** rồi chạy:

```bash
kubectl -n microservice get pods -o wide
kubectl -n microservice describe pods
```

Dựa trên kết quả để quyết định tăng RAM hoặc thêm worker.

Trong PDF, `vagrant halt` dừng VM và giữ đĩa; `vagrant destroy -f` xóa VM. Chúng không áp dụng cho inventory Azure này. Thực hiện riêng trong Azure Portal: **Stop** rồi kiểm tra trạng thái deallocated khi muốn dừng; **Delete** và kiểm tra lựa chọn disk/NIC/public IP khi muốn xóa. Teardown Ansible không thực hiện các thao tác VM.

**Minh chứng báo cáo:** PLAY RECAP teardown, 11 release không còn, danh sách node sau gỡ, phân biệt gỡ app/dừng VM/xóa VM và tác dụng của giảm replica.

## Chuẩn bị báo cáo và nộp bài

PDF yêu cầu mỗi Part một mục báo cáo; bộ nộp gồm repository có lịch sử Git, `report.pdf`, `screenshots/`, `recap.txt`. Cần ghi lại lần dựng thành công từ VM sạch và hai lần chạy lại kiểm tra idempotency. Chạy lại các playbook dựng cluster và triển khai ứng dụng theo phạm vi báo cáo; chưa có kết quả `changed=0` trong lần rà soát này.

Không đưa SSH private key, kubeconfig hoặc join token vào bài nộp. `artifacts/admin.conf` là credential quản trị; `artifacts/` đã được ignore nhưng vẫn cần loại khỏi archive nếu nén trực tiếp cả folder. Rubric về Ingress, probes/limits, scaling và chẩn đoán cần hoàn thiện bên cạnh 5 Part cơ bản.

## Nguồn gốc

Dựa trên ví dụ Kubernetes trong Ansible for DevOps của Jeff Geerling, điều chỉnh cho hai VM Azure có sẵn. Yêu cầu đối chiếu lấy từ [Project01_Ansible.pdf](Project01_Ansible.pdf).
