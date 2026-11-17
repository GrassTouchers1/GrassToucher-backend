# BÁO CÁO KHẢO SÁT & ĐÁNH GIÁ TOÀN DIỆN HIỆN TRẠNG MÃ NGUỒN
## CURRENT STATE AUDIT REPORT – NORTHSTAR PROJECT

> **Ngày thực hiện:** 18/11/2026  
> **Phạm vi khảo sát:** Cả 3 repositories (`GrassToucher-core`, `GrassToucher-backend`, `GrassTouchers-Frontend`) và cấu trúc điều hành chung.  
> **Phương pháp:** Kiểm tra mã nguồn trực tiếp (Source Code Static Analysis), đo đạc hiệu năng (Benchmark Run), kiểm thử tự động (Unit Test Suite), phân tích phụ thuộc (Dependency Audit).  

---

## 1. TỔNG QUAN HỆ THỐNG REPOSITORIES HIỆN TẠI

Hệ sinh thái dự án hiện được phân chia thành 3 kho mã nguồn độc lập trên GitHub Organization `GrassTouchers1`:

```
c:\Users\ASUS\Downloads\floodnav-main\
├── GrassToucher-core/          # [CORE] Thuật toán GIS, đồ thị NetworkX, A*, Dijkstra, AI Scikit-learn, Thủy văn
├── GrassToucher-backend/       # [BACKEND] Máy chủ FastAPI, PostGIS, SQLite Circuit Breaker, AI Groq Provider, WebSockets
└── GrassTouchers-Frontend/     # [FRONTEND] Ứng dụng Web SPA, Leaflet GIS, Tailwind CSS, PWA Offline Service Worker
```

Toàn bộ 3 kho mã nguồn hiện đang hoạt động thống nhất trên nhánh **`dev`** và đã được đồng bộ sạch sẽ với máy chủ từ xa (`origin/dev`).

---

## 2. KHẢO SÁT CHI TIẾT TỪNG REPOSITORY

### 2.1. Kho mã nguồn `GrassToucher-core` (Lõi Thuật toán & Dữ liệu Không gian)

- **Mục đích:** Thư viện Python đóng gói (`grasstoucher_core`) chứa toàn bộ thuật toán toán học, đồ thị đường bộ và xử lý dữ liệu địa lý không gian.
- **Ngôn ngữ & Thư viện:** Python 3.12, `networkx`, `osmnx`, `scikit-learn`, `joblib`, `urllib` (chuẩn thư viện chuẩn, không phụ thuộc bên ngoài cồng kềnh).
- **Cấu trúc tệp tin:**
  - `grasstoucher_core/config.py`: Tham số chuẩn hóa (`METRIC_CRS = 3857`, `FLOOD_RADIUS_M = 150.0`, `PENALTY_ALPHA = 20.0`).
  - `grasstoucher_core/graph.py`: Đọc và nạp tệp đồ thị `hanoi_drive.graphml` (2,235 nút, 5,502 cạnh đường bộ), hỗ trợ hàm chụp tọa độ nút gần nhất `get_nearest_node()`.
  - `grasstoucher_core/routing.py`:
    - Thuật toán $A^*$ tìm đường né ngập theo hàm trọng số đa thiên tai `multi_hazard_edge_cost()`:
      $$Cost(e) = \text{length}(e) \times (1 + \alpha \times \text{penalty}_{flood} + \beta \times \text{penalty}_{landslide} + \gamma \times \text{penalty}_{storm})$$
    - Thuật toán Dijkstra đa nguồn `find_evacuation_route()` tìm trạm sơ tán an toàn tối ưu từ điểm ngập.
  - `grasstoucher_core/weather.py`:
    - Tích hợp Open-Meteo Weather API (dự báo mưa theo giờ, TTL cache 5 phút).
    - Tích hợp Open-Meteo Flood API (Copernicus GloFAS) dự báo lưu lượng dòng chảy sông ngòi ($m^3/s$).
    - Tích hợp chuẩn đo mưa vệ tinh không gian NASA GPM IMERG.
    - Danh mục chứng thực bản quyền chuẩn mở OSI.
  - `grasstoucher_core/ai/prediction_engine.py`: Động cơ Machine Learning Scikit-learn (Gradient Boosting Regressor) dự báo mực nước dâng sau 30 phút và 60 phút.

#### Đánh giá Kỹ thuật:
- **Ưu điểm:**
  - Tách bạch hoàn toàn logic toán học khỏi web framework (FastAPI).
  - Thuật toán $A^*$ có hiệu năng cao: thời gian tìm đường né ngập trung bình chỉ từ **300ms đến 400ms** trên đồ thị hơn 2,200 nút.
  - Không có bất kỳ phụ thuộc nào vào dịch vụ đóng hoặc cào dữ liệu trái phép.
- **Tồn tại & Hạn chế:**
  - Đồ thị đường bộ GraphML hiện tại mới chỉ đóng gói cho khu vực Hà Nội (`hanoi_drive.graphml`). Khi mở rộng ra các tỉnh miền núi phía Bắc (Thái Nguyên, Yên Bái, Lào Cai), hệ thống đang fallback sang đồ thị lưới toán học (Grid Graph) hoặc cần cơ chế nạp động nhiều đồ thị theo tỉnh thành.

---

### 2.2. Kho mã nguồn `GrassToucher-backend` (Máy chủ Dịch vụ & Cơ sở Dữ liệu)

- **Mục đích:** RESTful API Gateway, WebSocket Server, Quản lý CSDL PostGIS và Cầu nối AI Provider Layer.
- **Ngôn ngữ & Thư viện:** Python 3.12, FastAPI 0.115, Uvicorn, Pydantic v2, SQLAlchemy / Psycopg, SQLite3, Groq Python SDK.
- **Cấu trúc tệp tin:**
  - `app/main.py`: Khởi động ứng dụng, nạp CORS, cấu hình router và xử lý lifecycle.
  - `app/db.py`: Quản lý kết nối PostgreSQL / PostGIS.
  - `app/fallback_storage.py`: **Kiến trúc Circuit Breaker độc đáo:** Khi CSDL PostgreSQL ngoại tuyến hoặc rớt kết nối, hệ thống tự động chuyển vùng sang SQLite In-Memory cục bộ không để gián đoạn bất kỳ request nào.
  - `app/ai/`: Lớp trung gian quản lý AI Provider Layer:
    - `base.py`: Abstract Base Class `AIProvider`.
    - `groq_provider.py`: Tích hợp Groq API LPU siêu tốc (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, Whisper `whisper-large-v3-turbo`).
    - `mock_provider.py`: Bộ dự phòng Offline hoàn toàn khi mất internet.
    - `factory.py`: Cơ chế Factory chuyển đổi tự động nhà cung cấp AI qua biến môi trường `.env`.
  - `app/routers/`: 15 modules RESTful API:
    - `ai_endpoints.py`: Phân tích báo cáo thiên tai, tóm tắt diễn biến, phân loại cấp cứu, cấp cứu bằng giọng nói Voice SOS (kèm tự động nắn tọa độ địa danh).
    - `sos.py`: Quản lý tín hiệu cứu nạn cộng đồng (`GET /api/sos`, `POST /api/sos`, `PATCH /api/sos/{id}/status`).
    - `disasters.py`: Quản lý các sự cố đa thiên tai (Lũ lụt, sạt lở, vỡ đê, bão).
    - `shelters.py`: Quản lý trạm sơ tán và tìm trạm an toàn gần nhất.
    - `weather.py`: Các API dữ liệu mở Open-Meteo, GloFAS, NASA GPM.
    - `websocket_nav.py`: Kênh WebSocket phát sóng thời gian thực tín hiệu SOS và cảnh báo nguy hiểm phía trước.
    - `sitrep.py`: Báo cáo tác chiến theo chuẩn Quyết định số 18/2021/QĐ-TTg.

#### Đánh giá Kỹ thuật:
- **Ưu điểm:**
  - Hệ thống kiểm thử tự động đạt **28/28 unit tests thành công 100%** (`Ran 28 tests in 28.268s, OK`).
  - Khả năng sống sót khi rớt database (Zero Downtime nhờ SQLite Circuit Breaker).
  - Tích hợp AI LPU có tốc độ suy luận cực nhanh (< 1 giây cho phản hồi cấp cứu).
- **Tồn tại & Hạn chế:**
  - **Chưa có hệ thống Xác thực & Phân quyền (Authentication & Authorization):** Chưa có bảng `users`, chưa có JWT token, bất kỳ ai cũng có thể gọi endpoint cập nhật trạng thái SOS.
  - **Chưa có mô hình Thực thể Đội cứu hộ (Rescue Teams):** Chưa quản lý danh sách đội cứu hộ, năng lực phương tiện (xuồng máy, xe tải) và quy trình giao việc (Task Assignment).
  - **Mô hình dữ liệu phẳng:** Các báo cáo SOS hiện chỉ là bản ghi độc lập, chưa liên kết với sự kiện thiên tai cha (Disaster Incident).

---

### 2.3. Kho mã nguồn `GrassTouchers-Frontend` (Giao diện Tác chiến & PWA)

- **Mục đích:** Giao diện tương tác người dùng, hiển thị bản đồ số GIS, điều phối cứu nạn và hỗ trợ PWA ngoại tuyến.
- **Công nghệ:** HTML5, Tailwind CSS, Leaflet.js, Lucide Icons, Vanilla JavaScript hiện đại (Module Pattern).
- **Cấu trúc tệp tin:**
  - `index.html`: Khung giao diện chính tích hợp bản đồ Leaflet toàn màn hình, thanh bên điều khiển đa tab (Tìm đường, Trạm sơ tán, Cứu hộ SOS, Báo cáo thiên tai, Phân tích AI).
  - `js/map_core.js`: Quản lý vòng đời bản đồ Leaflet, hiển thị lớp ngập lụt, chọn điểm xuất phát/đích, GPS người dùng.
  - `js/rescue_manager.js`: Tải và hiển thị mốc cờ đỏ SOS, vòng bán kính thiên tai, trạm sơ tán, kết nối WebSocket.
  - `js/voice_sos.js`: Phân hệ cấp cứu bằng giọng nói:
    - Thu âm MediaRecorder + Web Speech API thời gian thực.
    - Ô văn bản `<textarea>` cho phép xem và sửa chữ trực tiếp.
    - Bộ bóc tách địa danh tự động (Auto Speech Geocoding) chống lệch vị trí.
    - Chế độ chấm vị trí cứu hộ trực tiếp trên bản đồ Leaflet.
  - `js/ai_assistant.js`: Widget Trợ lý AI Trực ban cứu hộ nổi góc phải màn hình.
  - `js/advanced_modules.js`: Modal báo cáo tình huống SitRep chuẩn QĐ 18/2021/QĐ-TTg.
  - `js/demo_suite.js`: Bộ kịch bản trình diễn 4 tình huống thực tế cho Ban giám khảo (phím tắt `D`, `V`, `1`, `2`, `3`, `4`).
  - `sw.js` & `manifest.json`: Đăng ký Service Worker lưu trữ đệm tài nguyên tĩnh (CSS, JS, Icon) phục vụ truy cập PWA khi rớt mạng.

#### Đánh giá Kỹ thuật:
- **Ưu điểm:**
  - Giao diện trực quan, tốc độ tải nhanh, tương thích tốt trên cả máy tính và màn hình điện thoại di động.
  - Giao diện Voice SOS vừa được nâng cấp hoạt động mượt mà, giải quyết trọn vẹn phản hồi của người dùng về việc xem lại nội dung và chống sai lệch tọa độ.
  - Có đầy đủ các công cụ demo tình huống phục vụ chấm thi và đánh giá.
- **Tồn tại & Hạn chế:**
  - **Gộp chung tất cả vai trò vào một màn hình duy nhất:** Người dân, Đội cứu hộ và Ban điều phối hiện đang nhìn chung một giao diện, chưa có các Portal chuyên biệt hóa theo chức năng nghiệp vụ.
  - **Bản đồ ngoại tuyến chưa lưu trữ Tile đệm sâu:** Service Worker mới lưu mã nguồn tĩnh (HTML/CSS/JS), chưa có bộ đệm lưu trước mảnh bản đồ ngoại tuyến (Offline Map Tiles IndexedDB) cho khu vực mất sóng hoàn toàn.

---

## 3. BẢNG TỔNG HỢP NĂNG LỰC HIỆN TẠI (SYSTEM CAPABILITIES MATRIX)

| Thành phần Nghiệp vụ | Trạng thái Hiện tại | Mức độ Hoàn thiện | Đánh giá Kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Tìm đường né ngập ($A^*$)** | Hoạt động tốt | 90% | Chạy mượt trên Hà Nội, tính toán theo độ sâu ngập và loại phương tiện. |
| **Tìm trạm sơ tán (Dijkstra)** | Hoạt động tốt | 85% | Tìm trạm gần nhất còn chỗ, né vùng ngập nguy hiểm. |
| **Cứu nạn 1-Click SOS** | Hoạt động tốt | 85% | Gửi tọa độ, số người, phân loại ưu tiên, WebSocket phát sóng tức thời. |
| **Voice SOS AI (Whisper)** | Hoạt động tốt | 95% | Có ô sửa chữ, tự động nắn địa danh tiếng Việt, cho phép chấm bản đồ. |
| **Trợ lý AI Trực ban** | Hoạt động tốt | 90% | Hỏi đáp kỹ năng sinh tồn, an toàn điện, tra cứu dữ liệu thời gian thực. |
| **Báo cáo SitRep QĐ 18** | Hoạt động tốt | 90% | Xuất bảng thống kê tác chiến, mực nước, điều tiết giao thông tự động. |
| **Dữ liệu Mở Quốc tế** | Hoạt động tốt | 95% | Tích hợp Open-Meteo, GloFAS, NASA GPM, OSM. Không cào dữ liệu đóng. |
| **Phân quyền Đội Cứu hộ** | Chưa có | 10% | Cần thiết kế Portal riêng cho lực lượng 114 / Đội cứu hộ hiện trường. |
| **Quản lý Phương tiện / Kho** | Chưa có | 0% | Cần bổ sung bảng quản lý tài sản, xuồng máy, áo phao, lương thực. |
| **Đồng bộ Ngoại tuyến P2P** | Sơ khai | 25% | Đã có Service Worker PWA, cần bổ sung hàng đợi đồng bộ SyncQueue. |
