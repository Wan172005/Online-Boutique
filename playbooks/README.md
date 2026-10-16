# Playbook verification

## verify.yml — Kiểm tra node và ứng dụng

Playbook có hai play: play đầu thu thập network facts trên `k8s`, xác nhận inventory đầy đủ, chọn `kubernetes_private_ip` hoặc IP NIC mặc định và kiểm tra IP thuộc VM. Play thứ hai chạy trên master, nạp `vars/main.yml`, `vars/microservices.yml` và import `tasks/boutique-verify.yml`.

Các assertion kiểm tra node Ready/đúng InternalIP, đủ 11 Deployment với replica khả dụng thuộc revision hiện tại, tên checkoutservice/port 5050, không còn tài nguyên `servicename`, frontend NodePort và HTTP 200 có nội dung storefront. HTTP chạy từ master tới IP private worker; playbook in URL public để người dùng thử trên trình duyệt.

Playbook dùng kubectl và module built-in, không cần cài Python Kubernetes client. Các thao tác kiểm tra chỉ đọc, không cài package hay thay đổi tài nguyên; command và HTTP GET vẫn chạy khi dùng `--check`. Chạy từ root sau khi triển khai ứng dụng, không dùng `--limit`:

```bash
ansible-playbook playbooks/verify.yml --syntax-check
ansible-playbook playbooks/verify.yml
```

Nếu kiểm tra thất bại, play dừng với node/tài nguyên hoặc phản hồi HTTP liên quan. Cần kiểm tra truy cập public và thử checkout riêng; HTTP nội bộ không chứng minh máy demo đi qua được NSG.
