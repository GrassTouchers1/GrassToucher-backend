# Changelog

Tất cả các thay đổi đáng chú ý của dự án **NORTHSTAR Backend (GrassToucher-backend)** sẽ được ghi lại trong tệp này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
và dự án này tuân thủ [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-19 (Bản nộp chính thức Olympic Tin học Sinh viên - PMNM)

### Đã thêm (Added)
- **RESTful API Contract cho Ứng dụng Di động Nạn nhân**: Cung cấp đầy đủ các đầu mút chuẩn OpenAPI:
  - `POST /api/sos`: Tiếp nhận tín hiệu cấp cứu thời gian thực kèm tọa độ GPS và thông tin nhân khẩu.
  - `POST /api/reports`: Tiếp nhận báo cáo ngập lụt, hình ảnh hiện trường từ người dân.
  - `GET /api/shelters`: Truy vấn trạm trú ẩn an toàn còn chỗ lân cận.
  - `POST /api/route`: Tính toán lộ trình thoát hiểm tránh ngập thích ứng theo phương tiện (đi bộ, xe máy, ô tô gầm cao, xuồng cứu hộ).
- **Fallback Persistent SQLite Storage with WAL**: Cơ chế dự phòng bền vững tự động chuyển hướng lưu trữ SQLite khi cơ sở dữ liệu PostgreSQL/PostGIS gặp sự cố, đảm bảo hệ thống không bao giờ mất dữ liệu trong bão lũ.
- **Dynamic Routing Bridge**: Cầu nối tích hợp thuật toán định tuyến thủy văn thích ứng A* từ gói `grasstoucher-core`.
- **Open-Meteo & US-EPA AQI Sync**: Bộ đồng bộ dữ liệu khí tượng vi mô và chất lượng không khí vệ tinh tự động nạp cache định kỳ.
- **Administrative Sitrep Exporter**: API tạo báo cáo tác chiến tình hình khẩn cấp định dạng chuẩn hành chính.

### Đã thay đổi (Changed)
- **Thống nhất bản quyền**: 100% mã nguồn được bảo hộ và cấp phép theo **Apache License 2.0 (OSI Approved)**.
- **Cấu hình môi trường 100% qua biến môi trường (.env)**: Không ghi cứng tham số kết nối hay cấu hình vào mã nguồn, đảm bảo tuân thủ tiêu chí Building from Source của OLP PMNM.
- Bật cơ chế CORS toàn diện và hỗ trợ lắng nghe trên `0.0.0.0:8000` để các thiết bị di động trong mạng nội bộ dễ dàng kết nối thử nghiệm.

### Đã sửa (Fixed)
- Sửa lỗi tương thích đường dẫn tuyệt đối khi chạy trên hệ điều hành Windows/Linux.
- Tối ưu hóa truy vấn điểm ngập lụt theo không gian (Spatial Bounding Box).

---

## [0.4.0] - 2026-11-15

### Đã thêm (Added)
- Tích hợp mô hình AI Machine Learning dự báo mực nước dâng do mưa lớn từ dữ liệu cảm biến.
- Thêm các endpoint quản lý danh bạ trạm quan trắc thủy văn và trạm cứu nạn.

---

## [0.1.0] - 2026-10-20

### Đã thêm (Added)
- Khởi tạo kiến trúc FastAPI ban đầu với các router điểm ngập lụt và chỉ đường sơ bộ.
