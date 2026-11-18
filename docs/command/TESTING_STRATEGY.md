# CHIẾN LƯỢC KIỂM THỬ VÀ DIỄN TẬP THỰC CHIẾN (TESTING STRATEGY)
## Khung Kiểm thử Toàn diện: Unit Test, Tích hợp, An ninh PII & Kịch bản Giả định Thiên tai

---

## 1. THÁP KIỂM THỬ (TESTING PYRAMID) TRONG NORTHSTAR COMMAND

```
           / \
          /   \        E2E Disaster Drills (Kịch bản cứu nạn bão lũ khép kín)
         /-----\
        /       \      Security & PII Audits (Kiểm thử leo thang đặc quyền, rò rỉ PII)
       /---------\
      /           \    Integration Tests (PostGIS, SQLite Fallback, WebSocket Gateway)
     /-------------\
    /               \  Unit Tests (Thuật toán Triage, Deduplication, Router A*, Schemas)
   /-----------------\
```

---

## 2. CHI TIẾT CÁC TẦNG KIỂM THỬ

### 2.1. Kiểm thử Đơn vị (Unit Testing)
- **Công cụ:** `unittest`, `pytest`, `pytest-asyncio`.
- **Phạm vi kiểm tra:**
  - Logic chấm điểm khẩn cấp Triage: Bảo đảm ca có trẻ nhỏ/người già trong nước ngập $>1\text{m}$ luôn được xếp vào `P1_CRITICAL`.
  - Thuật toán Deduplication: Thử nghiệm ma trận tọa độ, bảo đảm 10 báo cáo cách nhau $<50\text{m}$ trong vòng 30 phút tự động gom thành 1 Master Record.
  - Hàm trọng số A* trong `GrassToucher-core`: Đoạn đường ngập $>20\text{cm}$ phải trả về trọng số vô cực ($\infty$) đối với xe cấp cứu.

### 2.2. Kiểm thử Tích hợp & Dự phòng (Integration & Resiliency Testing)
- **Kiểm thử Circuit Breaker:**
  - Ngắt kết nối cổng PostgreSQL (Port 5432) trong lúc hệ thống đang chạy.
  - Xác nhận API vẫn tiếp nhận SOS bình thường bằng cách chuyển hướng ghi vào SQLite dã chiến mà không làm văng ngoại lệ HTTP 500.
  - Khôi phục kết nối PostgreSQL và kiểm tra tính toàn vẹn dữ liệu được đồng bộ lại.

### 2.3. Kiểm thử An ninh & Quyền riêng tư (Security & PII Leakage Testing)
- **Thử nghiệm leo thang đặc quyền:** Đăng nhập bằng tài khoản `VOLUNTEER` hoặc `CITIZEN` rồi cố tình gọi endpoint `/api/v1/command/tasks/dispatch-rescue` $\rightarrow$ Phải nhận mã lỗi `403 Forbidden`.
- **Kiểm tra rò rỉ dữ liệu cá nhân:** Gọi endpoint danh sách SOS `/api/v1/command/sos/incoming` với tài khoản `DATA_ANALYST` $\rightarrow$ Xác nhận trường `phone` và `contact_name` bị ẩn hoặc trả về `null`.
- **Kiểm tra rào chắn địa lý (Geographic Scope Breach):** Dispatcher Hà Nội cố tình điều động ca cứu hộ tại Thái Nguyên $\rightarrow$ Bị chặn lại với mã lỗi `403 Forbidden: Ngoài địa bàn phân công`.

---

## 3. KỊCH BẢN DIỄN TẬP THỰC CHIẾN MÔ PHỎNG THIÊN TAI (E2E DISASTER DRILL)

Hệ thống được kiểm thử thông qua kịch bản tự động mô phỏng cơn bão lịch sử đổ bộ:

1. **Giai đoạn 1 (Tích tụ mưa & Báo động lũ):** Sinh dữ liệu mưa 120 mm/h từ Open-Meteo và mực nước sông vượt Báo động 2 tại trạm Long Biên. Bản đồ COP đổi màu cảnh báo vàng $\rightarrow$ cam.
2. **Giai đoạn 2 (Bão SOS tràn ngập):** Giả lập 500 yêu cầu SOS đổ về đồng thời trong 2 phút (trong đó có 200 yêu cầu trùng lặp).
3. **Giai đoạn 3 (Thẩm định & Lọc trùng):** Information Hub gom 200 báo cáo trùng vào các Master Record tương ứng. Verifier gọi điện xác nhận 5 ca P1 nguy kịch.
4. **Giai đoạn 4 (Điều động cano cứu nạn):** Dispatcher phân công 3 đội cứu hộ tiếp cận hiện trường; bản đồ vẽ lộ trình an toàn tránh các điểm ngập sâu.
5. **Giai đoạn 5 (Cứu nạn & Đưa về Safe Zone):** Đội cứu hộ cập nhật trạng thái `ON_SCENE` $\rightarrow$ `COMPLETED`; Trường THPT Yên Hòa tiếp nhận 15 nạn nhân, cập nhật tăng sĩ số lưu trú.
6. **Giai đoạn 6 (Xuất SitRep):** Hệ thống tự động xuất Báo cáo Tình hình tác chiến (SitRep) định dạng PDF đầy đủ số liệu chính xác từng phút.

---

## 4. TIÊU CHUẨN ĐẠT CHẤT LƯỢNG (QUALITY GATES)

- **Độ bao phủ mã nguồn (Code Coverage):** Đạt tối thiểu **$90\%$** đối với luồng nghiệp vụ tiếp nhận SOS, phân quyền RBAC và điều phối cứu hộ.
- **Rò rỉ dữ liệu:** **$0\%$** (Không có bất kỳ trường hợp nào lộ PII chưa được cấp phép trong log hệ thống hoặc response API).
- **Chịu tải đỉnh:** Hệ thống chịu tải tối thiểu **1.000 requests/giây** với độ trễ phản hồi $P_{95} \le 800\text{ ms}$.
