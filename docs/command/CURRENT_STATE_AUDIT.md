# BÁO CÁO KIỂM TOÁN HIỆN TRẠNG 3 REPOSITORIES (CURRENT STATE AUDIT)
## Đánh giá Nền tảng Kỹ thuật NORTHSTAR & Tính sẵn sàng cho Phân hệ COMMAND

---

## 1. TỔNG QUAN TÀI NGUYÊN KIỂM TOÁN

| Repository | Công nghệ chủ đạo | Trạng thái Git / Branch | Bộ kiểm thử (Tests) | Đánh giá tổng quan |
| :--- | :--- | :--- | :--- | :--- |
| **`GrassToucher-core`** | Python 3.12, NetworkX, OSMnx, Scikit-learn, GeoJSON | `dev` (clean, in-sync) | 2 test suites (`test_core.py`, `test_multi_hazard.py`) | Đồ thị mạng lưới đường bộ, thuật toán tìm đường A* và Dijkstra đa nguồn ổn định. |
| **`GrassToucher-backend`** | FastAPI 0.115, PostGIS (Circuit Breaker SQLite), Uvicorn | `dev` (clean, in-sync) | 28 Unit Tests (Pass 100%, 31.2s) | API RESTful phong phú, có sẵn router SOS, Shelter, Disaster, AI Voice Whisper. Chưa có hệ thống RBAC hoàn chỉnh. |
| **`GrassTouchers-Frontend`** | Vanilla JS (ES6+), Leaflet.js, Tailwind CSS, Lucide | `dev` (clean, in-sync) | PWA Service Worker, Toast Suite | Bản đồ tương tác mượt mà, hỗ trợ Voice SOS, đa lớp thiên tai. Chưa tách cổng điều phối COMMAND độc lập. |

---

## 2. CHI TIẾT HIỆN TRẠNG TỪNG REPOSITORY

### A. Repository `GrassToucher-core`
- **Mã nguồn:**
  - `grasstoucher_core/graph.py`: Xây dựng đồ thị NetworkX từ file `.graphml` (Hà Nội & các phân vùng Miền Bắc).
  - `grasstoucher_core/routing.py`: Hiện thực thuật toán A* né ngập có trọng số rủi ro (`risk_cost_function`) và Dijkstra đa nguồn tìm điểm sơ tán gần nhất.
  - `grasstoucher_core/weather.py`: Thu thập dữ liệu thời tiết cơ bản.
  - `grasstoucher_core/ai/prediction_engine.py`: Chạy mô hình Scikit-learn (RandomForest, GradientBoosting) dự báo ngập 30 phút và 60 phút.
- **Điểm mạnh:** Xử lý đồ thị nhanh (benchmark 2.200 nút giao thông chỉ mất ~318 ms), tách biệt logic toán học độc lập với hạ tầng web.
- **Khoảng trống:** Chưa có module tính toán phạm vi tiếp cận cứu hộ (isochrone mapping / reachability analysis) kết hợp đặc tính phương tiện lội nước (cano, xuồng).

### B. Repository `GrassToucher-backend`
- **Mô hình Dữ liệu (Database & ORM):**
  - Đã có PostgreSQL/PostGIS baseline (`db/init/01_schema.sql`) và migration Alembic `0002_multi_hazard_schema.py` định nghĩa các bảng: `disaster_events`, `evacuation_shelters`, `community_sos`.
  - Cơ chế **Circuit Breaker** thông minh trong `app/db.py` và `app/fallback_storage.py`: Tự động chuyển hướng sang SQLite in-memory khi mất kết nối PostGIS, bảo đảm hệ thống không bao giờ bị sập.
- **Endpoints hiện có:**
  - `/api/v1/sos`: Tạo yêu cầu cứu hộ, lấy danh sách, cập nhật trạng thái.
  - `/api/v1/shelters`: Quản lý điểm sơ tán, tìm điểm sơ tán gần nhất.
  - `/api/v1/disasters`: Quản lý vùng thiên tai, sạt lở, ngập lụt.
  - `/api/v1/weather`: Lấy thông tin thời tiết Open-Meteo và kịch bản mưa mô phỏng.
  - `/api/v1/sitrep`: Sinh báo cáo tình hình cứu hộ theo chuẩn QĐ 18/2021/QĐ-TTg.
  - `/api/v1/ai/voice-emergency-parse`: Bóc tách giọng nói khẩn cấp qua Groq Whisper LPU.
- **Khoảng trống nghiêm trọng cho phân hệ COMMAND:**
  - Chưa có bảng dữ liệu quản lý tài khoản và phân quyền: `users`, `roles`, `permissions`, `organizations`.
  - Chưa có bảng quản lý đội thiện nguyện (`volunteer_organizations`, `relief_inventory`).
  - Chưa có bảng kiểm toán hoạt động (`audit_logs`) ghi nhận ai đã truy cập/thay đổi thông tin nhạy cảm.
  - Chưa có dịch vụ xử lý dữ liệu đầu vào tập trung (Information Ingestion Engine) với bộ lọc trùng lặp tự động (Deduplication).

### C. Repository `GrassTouchers-Frontend`
- **Cấu trúc:** Một Single Page Application (SPA) trên nền `index.html` với các module JS: `map_core.js`, `rescue_manager.js`, `voice_sos.js`, `dashboard.js`.
- **Điểm mạnh:** Giao diện bản đồ tải nhanh, phản hồi linh hoạt trên di động, hỗ trợ đa lớp bản đồ thiên tai (thủy văn, ngập lụt, cứu hộ, sơ tán, ảnh vệ tinh Sentinel-1 SAR).
- **Khoảng trống:** Tất cả tính năng hiện đang nằm chung trên một màn hình của người dân. Chưa có màn hình Dashboard tác chiến đa phân luồng (Common Operating Picture) dành riêng cho Dispatcher và Commander.

---

## 3. PHÂN LOẠI TÁI SỬ DỤNG VÀ NÂNG CẤP (TAXONOMY)

| Phân loại | Thành phần / Module | Đánh giá kỹ thuật & Giải pháp triển khai |
| :--- | :--- | :--- |
| **KEEP (Giữ nguyên)** | • Lõi đồ thị NetworkX & A* né ngập (`core`)<br>• Cơ chế Circuit Breaker PostgreSQL / SQLite (`backend`)<br>• Engine bóc tách âm thanh Groq Whisper (`backend`)<br>• Bộ icon Lucide & Leaflet Base Layer mapping (`frontend`) | Giữ vững tính ổn định, độ tin cậy cao và tốc độ phản hồi sub-second đã được kiểm nghiệm thực tế. |
| **IMPROVE (Cải tiến)** | • Module `sitrep.py`: Nâng cấp xuất dữ liệu JSON/Markdown/PDF kèm chữ ký số điều phối viên.<br>• Module `shelters.py`: Bổ sung thông tin chi tiết về tải trọng, y tế, nguồn nước và năng lượng dự phòng.<br>• Bộ lọc lớp bản đồ Leaflet: Tối ưu hóa gom cụm điểm (MarkerCluster) cho >10.000 đối tượng. | Giúp các module đáp ứng đầy đủ yêu cầu khắt khe của trung tâm điều hành cấp tỉnh/thành phố. |
| **REFACTOR (Tái cấu trúc)**| • Tách biệt logic phân quyền Backend: Xây dựng middleware xác thực JWT và Role/Scope Guard (`require_permission`) thay vì kiểm tra đơn lẻ.<br>• Chuẩn hóa mô hình dữ liệu DDL: Thống nhất khóa ngoại giữa `users`, `organizations`, `sos_requests` và `rescue_tasks`. | Loại bỏ rủi ro rò rỉ dữ liệu cá nhân nạn nhân sang các phân hệ không có thẩm quyền. |
| **REPLACE (Thay thế)** | • Loại bỏ toàn bộ cơ chế cào HTML (Scraping): Thay thế bằng API dữ liệu mở chính thức có bản quyền (Open-Meteo, GloFAS, NASA GPM).<br>• Thay thế việc hiển thị gộp chung người dùng: Tách biệt trang đăng nhập và giao diện riêng biệt cho COMMAND. | Tuân thủ 100% chuẩn mã nguồn mở OSI và chuẩn mực bảo mật dữ liệu PII. |
| **NEW (Xây dựng mới)** | • **Information Hub Engine:** Module tiếp nhận dữ liệu đa luồng, làm sạch, gắn nhãn độ tin cậy và phát hiện trùng lặp.<br>• **Volunteer Management Module:** Quản lý tổ chức thiện nguyện, kho hàng cứu trợ và phân phối nhu yếu phẩm.<br>• **Command & Dispatch Workflow:** Quy trình điều động 12 bước, phân luồng nhiệm vụ cứu nạn vs cứu trợ.<br>• **Audit Log System:** Lưu vết lịch sử truy cập và can thiệp dữ liệu bất biến.<br>• **Frontend Portal COMMAND:** Giao diện tác chiến độc lập (`portal-command.html`). | Đây là các thành phần cốt lõi tạo nên phân hệ NORTHSTAR COMMAND toàn diện. |
