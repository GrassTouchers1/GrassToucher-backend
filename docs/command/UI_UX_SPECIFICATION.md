# ĐẶC TẢ GIAO DIỆN VÀ TRẢI NGHIỆM NGƯỜI DÙNG (UI/UX SPECIFICATION)
## Thiết kế Bảng Điều Hành Tác Chiến NORTHSTAR COMMAND – Trung tâm Điều phối

---

## 1. TRIẾT LÝ THIẾT KẾ VÀ PHONG CÁCH GIAO DIỆN

1. **Bản đồ là trung tâm (GIS-Centric Operation):** Bản đồ không gian chiếm tối thiểu $65\%$ diện tích hiển thị trên màn hình tác chiến để người điều phối luôn nắm trọn ngữ cảnh thực địa.
2. **Mật độ thông tin cao nhưng phân cấp thị giác rõ ràng (High Data Density & Clear Visual Hierarchy):** Phù hợp với nhân viên trực ban liên tục 8-12 tiếng trong đợt thiên tai, mọi thông số khẩn cấp phải nhận biết được trong vòng 3 giây.
3. **Chế độ Tối Tác chiến (Tactical Dark Mode):** Sử dụng bảng màu Dark Navy / Slate (`#0f172a`, `#1e293b`) làm chủ đạo để giảm mỏi mắt, làm nổi bật các tín hiệu khẩn cấp màu Đỏ (P1), Cam (P2), Vàng (P3) và Xanh lục (An toàn).
4. **Tuyệt đối không lạm dụng hiệu ứng thừa:** Loại bỏ các chuyển động trang trí rườm rà gây tốn CPU hoặc làm chậm thao tác điều động khẩn cấp.
5. **Minh bạch nhãn dữ liệu:** Nếu sử dụng dữ liệu mô phỏng để tập huấn, bắt buộc phải có huy hiệu `[DEMO / TẬP HUẤN]` màu tím nổi bật ở góc màn hình.

---

## 2. CƠ CẤU ĐIỀU HƯỚNG 12 MỤC NGHIỆP VỤ (NAVIGATION STRUCTURE)

Thanh điều hướng Sidebar (bên trái) hiển thị 12 phân hệ tác chiến chuyên biệt:

```
[🧭 NORTHSTAR COMMAND]
├── 1. Tổng quan Tác chiến (Overview / COP)
├── 2. Trung tâm Tiếp nhận (Information Hub)
├── 3. Giám sát Thời tiết (Weather Monitoring)
├── 4. Thủy văn & Ngập lụt (Flood Intelligence)
├── 5. Bản đồ Thiên tai GIS (Disaster Map)
├── 6. Quản lý Đội Cứu Hộ (Rescue Management)
├── 7. Quản lý Đội Thiện Nguyện (Volunteer Management)
├── 8. Quản lý Điểm Sơ Tán (Safe Zone Management)
├── 9. Điều Phối Tác Chiến (Command & Dispatch)
├── 10. Báo cáo & Thống kê (Reports & SitRep)
├── 11. Nguồn Dữ liệu Mở (Data Sources Registry)
└── 12. Cấu hình Hệ thống (System Settings & RBAC)
```

---

## 3. BỐ CỤC CHI TIẾT TRANG TỔNG QUAN TÁC CHIẾN (OVERVIEW PAGE WIREFRAME)

```
+---------------------------------------------------------------------------------------------------------+
| [LOGO] NORTHSTAR COMMAND | Khu vực: [Hà Nội & Phụ cận v] | 🔴 CẤP 2 BÃO LŨ | 🟢 PostGIS Online | 2026-11-18 12:45 | [User: Dispatcher_01] |
+--------------------------------------------------------------------+------------------------------------+
|                                                                    | CỘT TÁC CHIẾN THỜI GIAN THỰC       |
|                                                                    | ---------------------------------- |
|                       BẢN ĐỒ TÁC CHIẾN (GIS COP)                    | 🚨 YÊU CẦU SOS KHẨN CẤP (P1) [7]   |
|                                                                    | [!] SOS-9182 - 3 người (Trẻ nhỏ)  |
|  - Hiển thị lớp ngập lụt, ranh giới hành chính, trạm đo mực nước   |     Ngập 1.4m - Phúc Xá, Ba Đình   |
|  - Vị trí các ca SOS (P1: Chấm đỏ nhấp nháy, P2: Chấm cam)         |     [Xác minh ngay] [Điều động]    |
|  - Vị trí các Đội Cứu hộ đang trực ban (Icon xuồng xanh lá)        | ---------------------------------- |
|  - Vị trí các Điểm sơ tán an toàn (Icon khiên xanh dương)          | ⚠️ CHỜ XÁC MINH (VERIFYING) [12]  |
|                                                                    | [?] Báo cáo sạt lở taluy QL4D      |
|  [Bộ lọc lớp bản đồ v]  [Công cụ đo đạc]  [Bản đồ nhiệt ngập]      | [?] Nước tràn đê Bùi 2 (Chương Mỹ) |
|                                                                    | ---------------------------------- |
|                                                                    | 🌧️ CẢNH BÁO THỜI TIẾT MỚI NHẤT    |
|                                                                    | Mưa lớn: Mê Linh (85mm/h)          |
|                                                                    | Sông Hồng: Báo động 1 (+0.35m)     |
+--------------------------------------------------------------------+------------------------------------+
| CHỈ SỐ NHANH:  [SOS Hoạt động: 42]  |  [Đội đã điều động: 15/23]  |  [Đã giải cứu: 128]  |  [Sơ tán: 68.5% Sức chứa]    |
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. QUY CHUẨN HIỂN THỊ TRẠNG THÁI XÁC MINH TRÊN BẢN ĐỒ

| Trạng thái Dữ liệu | Ký hiệu & Màu sắc trực quan | Quy cách tương tác |
| :--- | :--- | :--- |
| **Mới tiếp nhận (`RECEIVED`)** | Vòng tròn viền đứt nét màu vàng, có dấu chấm hỏi `?`. | Bấm vào để mở bảng điều tra, phân công cho Verifier gọi điện thoại đối soát. |
| **Đang xác minh (`VERIFYING`)** | Biểu tượng xoay nhẹ màu xanh dương nhạt. | Hiển thị tên nhân viên đang thực hiện thẩm định để tránh 2 người cùng gọi một nạn nhân. |
| **Đã xác minh (`VERIFIED`)** | Khối biểu tượng đặc, màu Đỏ tươi (P1) hoặc Cam (P2). | Sẵn sàng để Dispatcher kéo thả hoặc click chọn phân công cho Đội cứu hộ. |
| **Bị từ chối (`REJECTED`)** | Biểu tượng xám mờ có gạch chéo `✕`. | Ẩn khỏi bản đồ tác chiến chính, chỉ lưu trong tab Kiểm tra chất lượng dữ liệu. |
| **Đã giải cứu (`RESOLVED`)** | Biểu tượng hình chiếc khiên màu xanh lá cây đậm. | Hiển thị trong vòng 2 giờ rồi tự động lưu trữ vào lớp dữ liệu lịch sử. |
