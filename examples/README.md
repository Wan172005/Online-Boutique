# Triển khai Online Boutique bằng Ansible

Tài liệu này chỉ mô tả [online-boutique.yml](online-boutique.yml), phục vụ Part 3 của [../Project01_Ansible.pdf](../Project01_Ansible.pdf).

## Mục đích và cấu hình

Playbook chạy trên `k8s_control_plane` với `become: true`, triển khai Online Boutique bằng `kubernetes.core.helm`. Tài nguyên ứng dụng được tạo qua Helm module; không cần tự chạy `kubectl apply` để deploy.

Các biến lấy từ [../vars/microservices.yml](../vars/microservices.yml):

| Biến | Giá trị hiện tại / ý nghĩa |
| --- | --- |
| `boutique_repo` | `https://github.com/iankisali/microservice-deployment.git`, nguồn chart upstream. |
| `boutique_revision` | `main`, nhánh được clone; chưa ghim commit cố định. |
| `boutique_src` | `/opt/online-boutique-charts`, đường dẫn clone trên master. |
| `boutique_namespace` | `microservice`, namespace triển khai các release. |
| `boutique_helm_binary` | `/usr/local/bin/helm`. |
| `boutique_kubeconfig` | `/etc/kubernetes/admin.conf`, quyền truy cập API cluster. |
| `boutique_timeout` | `10m`, timeout cho mỗi lần cài/nâng cấp release. |
| `boutique_common` | Cấu hình chung `appReplicas: 1`. |
| `boutique_releases` | Danh sách 11 release, chart, values file và override riêng. |

## Trình tự trong online-boutique.yml

1. **Cài Git:** dùng APT, update cache với thời gian hiệu lực 3600 giây.
2. **Chuẩn bị Python client:** import `tasks/client.yml`, cài `python3-venv`; tạo venv `/opt/kubernetes-client` với `kubernetes>=24.2.0,<36.0.0`, PyYAML và jsonpatch; chọn interpreter trong venv cho module Ansible tiếp theo.
3. **Clone chart upstream:** module Git lấy `boutique_revision` vào `boutique_src` với `update: true`. Playbook không có task chỉnh trực tiếp nội dung clone.
4. **Triển khai từng release:** lặp `boutique_releases`, dùng `chart/redis` nếu release chọn chart Redis, mặc định `chart/microservice`; nạp values file trong `<boutique_src>/values/`, hợp nhất cấu hình chung và override riêng bằng `combine(..., recursive=true)`, truyền vào Helm.
5. **Đợi release:** mỗi lần dùng `state: present`, `create_namespace: true`, `wait: true`, timeout `10m`. Nếu một lần triển khai thất bại, play dừng; các release đã triển khai trước đó không được tự rollback toàn bộ.
6. **In địa chỉ ứng dụng:** dùng `kubernetes.core.k8s_info` đọc Service `frontend`, lấy NodePort ở phần tử port đầu tiên và in URL với IP public của worker đầu tiên trong inventory.

Helm có thể cài mới hoặc nâng cấp release theo trạng thái/cấu hình. `wait: true` hỗ trợ đợi tài nguyên sẵn sàng, chưa thay thế assertion ứng dụng và thử luồng mua hàng của Part 4.

## 11 release được triển khai

Thứ tự từ `vars/microservices.yml`; đường dẫn values dưới đây tương đối với folder `values/` trong clone:

| Thứ tự | Helm release | Chart | Values file |
| --- | --- | --- | --- |
| 1 | `rediscart` | `redis` | `redis-values.yaml` |
| 2 | `emailservice` | `microservice` | `email-service-values.yaml` |
| 3 | `currencyservice` | `microservice` | `currency-service-values.yaml` |
| 4 | `paymentservice` | `microservice` | `payment-service-values.yaml` |
| 5 | `productcatalogservice` | `microservice` | `productcatalog-service-values.yaml` |
| 6 | `shippingservice` | `microservice` | `shipping-service-values.yaml` |
| 7 | `adservice` | `microservice` | `ad-service-values.yaml` |
| 8 | `cartservice` | `microservice` | `cart-service-values.yaml` |
| 9 | `recommendationservice` | `microservice` | `recommendation-service-values.yaml` |
| 10 | `checkoutservice` | `microservice` | `checkout-service-values.yaml` |
| 11 | `frontendservice` | `microservice` | `frontend-values.yaml` |

Tên Helm release khác tên tài nguyên do chart tạo: playbook tìm Service `frontend` dù release là `frontendservice`. Theo kiến trúc trong PDF, Redis Service có tên `redis-cart` dù release là `rediscart`.

## Ba override theo PDF

| Cấu hình | Áp dụng | Lý do |
| --- | --- | --- |
| `appReplicas: 1` | Cấu hình chung các release | Giảm số bản chạy trên worker của lab; tác dụng cuối cùng phụ thuộc chart sử dụng giá trị này. |
| `serviceType: NodePort` | `frontendservice` | Thay kiểu LoadBalancer upstream để truy cập ứng dụng bằng địa chỉ node và NodePort. |
| `appName: checkoutservice` | `checkoutservice` | Đặt đúng tên Service/Deployment mà frontend gọi tại `checkoutservice:5050`. |

PDF mô tả values upstream của checkout có hai khóa `appImage` thay vì khai báo `appName`, làm chart dùng tên mặc định `servicename`. Override sửa lỗi mà không sửa repository upstream. Mô tả lỗi dựa vào PDF; chưa tái hiện và thu log lỗi trong lần rà soát này.

`values_files` giữ cấu hình upstream; `values` chứa override có ưu tiên cao hơn. Cách phân tách này giúp chỉ rõ các thay đổi của project khi viết báo cáo.

## Cách chạy và kết quả cần ghi lại

Chạy từ thư mục gốc project sau khi cluster và Helm đã được dựng bằng `main.yml`:

```bash
ansible-galaxy collection install -r requirements.yml
ansible-playbook examples/online-boutique.yml --syntax-check
ansible-playbook examples/online-boutique.yml
```

Master cần outbound tới GitHub, package mirrors/PyPI; các node chạy workload cần tải được image ứng dụng. Máy demo cần truy cập được NodePort worker qua NSG/firewall.

Với inventory hiện tại, URL in ra có dạng:

```text
Online Boutique: http://20.2.248.1:<NODE_PORT>/
```

Lấy cổng thật từ output; không nhập nguyên `<NODE_PORT>`. Mở URL, thử xem sản phẩm, thêm giỏ hàng và hoàn tất đơn hàng. Ghi lại PLAY RECAP, 11 release, giá trị override và ảnh storefront/đơn hàng. Ghim `boutique_revision` vào commit cố định là cải tiến nên cân nhắc để lần demo dùng đúng phiên bản chart đã kiểm chứng; hiện chưa thay biến này.

Để đọc release và effective values phục vụ báo cáo:

```bash
ansible k8s_control_plane -b -m ansible.builtin.command \
  -a 'helm --kubeconfig=/etc/kubernetes/admin.conf -n microservice list'
ansible k8s_control_plane -b -m ansible.builtin.command \
  -a 'helm --kubeconfig=/etc/kubernetes/admin.conf -n microservice get values frontendservice'
ansible k8s_control_plane -b -m ansible.builtin.command \
  -a 'helm --kubeconfig=/etc/kubernetes/admin.conf -n microservice get values checkoutservice'
```

Sau triển khai, chạy `ansible-playbook playbooks/verify.yml` từ root để assert node/private IP, 11 Deployment, Service checkout/frontend và HTTP storefront theo Part 4. Xem [../playbooks/README.md](../playbooks/README.md). Kết quả trên VM và luồng mua hàng cần xác nhận bằng lần chạy/demo thực tế.
