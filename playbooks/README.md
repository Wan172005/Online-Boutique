# Giải thích các playbook

Folder có [verify.yml](verify.yml) cho Part 4 và [teardown.yml](teardown.yml) cho Part 5 trong [../Project01_Ansible.pdf](../Project01_Ansible.pdf).

## verify.yml — Kiểm tra node và ứng dụng

Playbook có hai play: play đầu thu thập network facts trên `k8s`, xác nhận inventory đầy đủ, chọn `kubernetes_private_ip` hoặc IP NIC mặc định và kiểm tra IP thuộc VM. Play thứ hai chạy trên master, nạp `vars/main.yml`, `vars/microservices.yml` và import `tasks/boutique-verify.yml`.

Các assertion kiểm tra node Ready/đúng InternalIP, đủ 11 Deployment với replica khả dụng thuộc revision hiện tại, tên checkoutservice/port 5050, không còn tài nguyên `servicename`, frontend NodePort và HTTP 200 có nội dung storefront. HTTP chạy từ master tới IP private worker; playbook in URL public để người dùng thử trên trình duyệt.

Playbook dùng kubectl và module built-in, không cần cài Python Kubernetes client. Các thao tác kiểm tra chỉ đọc, không cài package hay thay đổi tài nguyên; command và HTTP GET vẫn chạy khi dùng `--check`. Chạy từ root sau khi triển khai ứng dụng, không dùng `--limit`:

```bash
ansible-playbook playbooks/verify.yml --syntax-check
ansible-playbook playbooks/verify.yml
```

Nếu kiểm tra thất bại, play dừng với node/tài nguyên hoặc phản hồi HTTP liên quan. Cần kiểm tra truy cập public và thử checkout riêng; HTTP nội bộ không chứng minh máy demo đi qua được NSG.

## teardown.yml — Gỡ Online Boutique

Playbook chạy trên nhóm `k8s_control_plane` với quyền sudo (`become: true`) và `any_errors_fatal: true`. Mục đích là gỡ các Helm release của Online Boutique, giữ Kubernetes cluster và VM để có thể triển khai lại.

| Thành phần | Cách thực hiện |
| --- | --- |
| Cấu hình dùng chung | Nạp `../vars/microservices.yml`: namespace `microservice`, danh sách 11 release, Helm binary, kubeconfig và timeout. |
| Chuẩn bị dependency | Import `../examples/tasks/client.yml`, cài hỗ trợ venv, thư viện Python Kubernetes/PyYAML/jsonpatch trong `/opt/kubernetes-client` và chọn Python interpreter của venv. |
| Gỡ ứng dụng | Import `../tasks/boutique-teardown.yml`, dùng Helm module gỡ release theo thứ tự ngược với triển khai, Redis cuối cùng. |
| Xác nhận sau gỡ | Tra các release ở mọi trạng thái, assert không còn release, gọi `kubectl get nodes -o wide` và in kết quả. |

Teardown dùng `state: absent`, `purge: true`, `wait: true`; thời gian đợi uninstall lấy từ `boutique_timeout` qua `wait_timeout`. Release chưa tồn tại được module xử lý theo trạng thái absent, nên có thể gọi lại khi ứng dụng đã gỡ hoặc triển khai dở.

Namespace `microservice`, ứng dụng khác, Helm, containerd, Kubernetes, kubeconfig và VM được giữ lại. Playbook không sao lưu dữ liệu ứng dụng và không dừng/xóa VM. Việc gọi `get nodes` xác nhận API truy cập được, chưa assert tất cả node Ready.

## Điều kiện chạy

Máy Ansible cần collection trong `requirements.yml`; master cần truy cập SSH/sudo, Helm và admin kubeconfig. Kubernetes API phải còn hoạt động để Helm xóa tài nguyên. Lần chuẩn bị Python client có thể cần truy cập Ubuntu package mirrors/PyPI; teardown không cần clone lại chart ứng dụng.

Chạy từ thư mục gốc project, dùng `inventory.ini` qua `ansible.cfg`:

```bash
ansible-playbook playbooks/teardown.yml --syntax-check
ansible-playbook playbooks/teardown.yml --check
ansible-playbook playbooks/teardown.yml
```

`--syntax-check` chỉ kiểm tra cú pháp; `--check` dự kiến thay đổi và bỏ qua block xác nhận sau gỡ. Hai chế độ này không thay thế lần chạy teardown thực tế.

Để triển khai lại ứng dụng:

```bash
ansible-playbook examples/online-boutique.yml
```

## Liên hệ với các Part của PDF

- Part 2: entry point dựng cluster hiện là `../main.yml`; không có `playbooks/cluster.yml` nêu làm ví dụ trong PDF.
- Part 4: `verify.yml` gọi `../tasks/boutique-verify.yml` để kiểm tra ứng dụng; khác với `../tasks/verify.yml` dùng khi dựng cluster ở Part 2.
- Part 5: `teardown.yml` là phần gỡ ứng dụng. Dừng và xóa hai VM Azure thực hiện riêng, không dùng lệnh Vagrant của PDF.

Để viết báo cáo Part 5, lưu PLAY RECAP chạy thật, kết quả xác nhận 11 release không còn, danh sách node sau gỡ và giải thích khác biệt giữa gỡ ứng dụng, dừng VM giữ đĩa và xóa VM. Chưa thực thi teardown trong lần cập nhật tài liệu này.
