# Quy định Đóng góp Mã Nguồn Mở (Contributing Guidelines)

Dự án **GrassToucher Backend** là dịch vụ API & WebSocket mã nguồn mở được phát hành theo giấy phép **Apache License 2.0 (OSI-Approved)**.

---

## 📜 1. Tiêu chí Mã Nguồn Mở (FOSS)
- Mọi đóng góp phải đảm bảo tính mở, không thêm các gói phụ thuộc có giấy phép thương mại hoặc API yêu cầu token độc quyền.
- Hệ thống hỗ trợ chế độ dự phòng In-Memory / SQLite để các lập trình viên có thể kiểm thử và phát triển tính năng mà không bắt buộc phải cài đặt PostgreSQL + PostGIS cục bộ.

---

## 🛠️ 2. Quy trình Phát triển (Development Workflow)

1. **Fork & Clone:**
   ```bash
   git clone https://github.com/GrassTouchers1/GrassToucher-backend.git
   cd GrassToucher-backend
   ```
2. **Cài đặt môi trường:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Chạy server phát triển:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. **Kiểm thử tự động:**
   ```bash
   python -m unittest discover -s tests
   ```
5. **Gửi Pull Request:** Đặt tiêu đề rõ ràng, mô tả mục đích thay đổi và đính kèm kết quả test.
