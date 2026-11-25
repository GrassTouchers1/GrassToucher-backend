# Quy định Đóng góp Mã Nguồn Mở (Contributing Guidelines)

Dự án **GrassToucher Backend** là dịch vụ API & xử lý dữ liệu địa lý không gian mã nguồn mở, được phát hành theo giấy phép **Apache License 2.0 (OSI-Approved)**.

---

## 📜 1. Tiêu chí Mã Nguồn Mở
- 100% sử dụng thư viện mở chuẩn (FastAPI, SQLAlchemy, GeoPandas, Pydantic).
- Toàn bộ tham số cấu hình được đưa ra biến môi trường (`.env`), không sửa mã nguồn để cấu hình.
- Luôn cung cấp và duy trì cơ chế Fallback (SQLite WAL) khi các dịch vụ bên ngoài ngắt kết nối.

---

## 🛠️ 2. Quy trình Phát triển
1. **Fork & Clone:**
   ```bash
   git clone https://github.com/GrassTouchers1/GrassToucher-backend.git
   cd GrassToucher-backend
   ```
2. **Khởi tạo môi trường ảo & cài đặt:**
   ```bash
   python -m venv venv
   source venv/bin/activate # hoặc venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Chạy kiểm thử trước khi commit:**
   ```bash
   pytest tests/
   ```

---

## 🐛 3. Hệ thống Quản lý Lỗi Phần mềm (Bug Tracker)
Dự án sử dụng chính thức **GitHub Issues** làm hệ thống tiếp nhận và quản lý lỗi phần mềm (Bug Tracker):
- 🔗 **Kho quản lý lỗi:** [https://github.com/GrassTouchers1/GrassToucher-backend/issues](https://github.com/GrassTouchers1/GrassToucher-backend/issues)
- Khi phát hiện lỗi API, lỗi dữ liệu hoặc crash server, hãy tạo Issue kèm theo log lỗi và các bước tái hiện.
- Mẫu Issue chuẩn được cung cấp tại `.github/ISSUE_TEMPLATE/bug_report.md`.
