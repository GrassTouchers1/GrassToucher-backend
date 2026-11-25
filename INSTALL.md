# HƯỚNG DẪN CÀI ĐẶT & BIÊN DỊCH TỪ MÃ NGUỒN (BUILDING FROM SOURCE)
## NORTHSTAR BACKEND (FastAPI & Geodata Service)

> Tài liệu này hướng dẫn chi tiết cách cài đặt, cấu hình và khởi chạy ứng dụng từ mã nguồn gốc bằng **100% công cụ nguồn mở chuẩn**, đáp ứng tiêu chí **Building from Source (PoF)** của Hội thi Olympic Tin học Sinh viên (Khối Phần mềm Nguồn mở).

---

## 1. YÊU CẦU MÔI TRƯỜNG (PREREQUISITES)

Dự án có thể chạy trên mọi hệ điều hành (Linux, macOS, Windows) với các phần mềm mã nguồn mở sau:

* **Python**: Phiên bản `>= 3.10` (Khuyên dùng `3.10` - `3.12`).
* **pip**: Trình quản lý gói chuẩn của Python (`>= 22.0`).
* **Git**: Trình quản lý phiên bản mã nguồn mở.
* *(Tùy chọn)* **PostgreSQL** kèm tiện ích không gian **PostGIS** (Nếu không cài PostgreSQL, hệ thống sẽ **tự động kích hoạt cơ chế Fallback SQLite WAL** để lưu trữ bền vững mà không làm gián đoạn ứng dụng).

---

## 2. QUY TRÌNH BIÊN DỊCH & CÀI ĐẶT TỪ MÃ NGUỒN

### Bước 2.1: Tải mã nguồn từ GitHub
```bash
git clone https://github.com/GrassTouchers1/GrassToucher-backend.git
cd GrassToucher-backend
```

### Bước 2.2: Khởi tạo môi trường ảo Python (Virtual Environment)
Sử dụng công cụ `venv` chuẩn sẵn có trong Python để đảm bảo cách ly sạch hoàn toàn với hệ thống:
```bash
# Trên Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Trên Windows (PowerShell / CMD)
python -m venv venv
venv\Scripts\activate
```

### Bước 2.3: Cài đặt gói thuật toán lõi grasstoucher-core (Editable Mode)
Backend phụ thuộc vào module định tuyến thủy văn mở `grasstoucher-core`. Cài đặt trực tiếp từ mã nguồn:
```bash
# Nếu kho mã nguồn nằm cùng thư mục cha:
pip install -e ../GrassToucher-core

# Hoặc cài trực tiếp từ kho lưu trữ GitHub chính thức:
pip install git+https://github.com/GrassTouchers1/GrassToucher-core.git
```

### Bước 2.4: Cài đặt toàn bộ phụ thuộc từ tệp requirements.txt
```bash
pip install -r requirements.txt
```

---

## 3. CẤU HÌNH THÔNG QUA BIẾN MÔI TRƯỜNG (.env)

> **LƯU Ý QUAN TRỌNG:**  
> Hệ thống **100% không yêu cầu sửa đổi thủ công vào tệp mã nguồn hay tệp header**. Toàn bộ cấu hình được nạp động từ biến môi trường thông qua tệp `.env`.

Tạo tệp cấu hình từ mẫu sẵn có:
```bash
cp .env.example .env
```

Nội dung các tham số cấu hình chính trong `.env`:
| Biến môi trường | Giá trị mặc định | Giải thích chức năng |
| :--- | :--- | :--- |
| `APP_ENV` | `production` hoặc `development` | Môi trường vận hành |
| `DATABASE_URL` | `sqlite:///./data/floodnav_fallback.db` | Chuỗi kết nối DB (PostGIS hoặc SQLite Fallback) |
| `HOST` | `0.0.0.0` | Địa chỉ IP lắng nghe (mở cho cả máy và thiết bị di động LAN) |
| `PORT` | `8000` | Cổng dịch vụ FastAPI |
| `CORS_ORIGINS` | `*` hoặc `http://localhost:3000` | Danh sách tên miền được phép truy xuất API |

---

## 4. KHỞI CHẠY DỊCH VỤ

### Chạy trực tiếp bằng máy chủ Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Kiểm tra trạng thái hoạt động:
* **Tài liệu OpenAPI / Swagger:** Truy cập [http://localhost:8000/docs](http://localhost:8000/docs)
* **Kiểm tra sức khỏe hệ thống (Health Check):**
  ```bash
  curl -I http://localhost:8000/docs
  ```

---

## 5. CHẠY BỘ KIỂM THỬ TỰ ĐỘNG (AUTOMATED TEST SUITE)

Hệ thống đi kèm bộ kiểm thử tự động sử dụng thư viện `pytest`:
```bash
pytest tests/
```
