# ĐẶC TẢ GIAO DIỆN LẬP TRÌNH ỨNG DỤNG
## API ARCHITECTURE & SPECIFICATION (OPENAPI 3.1 COMPLIANT)

> **Dự án:** NORTHSTAR – Open-source Emergency Response OS  
> **Kiến trúc API:** RESTful JSON API + Real-time Bi-directional WebSockets  
> **Tiêu chuẩn dữ liệu:** GeoJSON (RFC 7946), ISO 8601 Timestamps, HTTP/1.1 & HTTP/2.  

---

## 1. QUY CHUẨN CẤU TRÚC PHẢN HỒI (STANDARD JSON ENVELOPE)

Tất cả các API của NORTHSTAR đều trả về cấu trúc JSON đồng nhất:

```json
{
  "status": "success | error | warning",
  "data": { ... },
  "message": "Thông điệp mô tả kết quả xử lý bằng tiếng Việt",
  "meta": {
    "timestamp": "2026-11-18T00:30:00Z",
    "provider_used": "groq (openai/gpt-oss-120b) | postgresql | offline_cache",
    "is_offline": false,
    "version": "1.0.0"
  }
}
```

---

## 2. DANH MỤC API ENDPOINTS THEO TỪNG PHÂN HỆ

### 2.1. Phân hệ Xác thực & Phân quyền (Authentication & RBAC)

| Method | Endpoint | Quyền hạn (Role) | Mô tả nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Đăng nhập tài khoản điều phối viên / đội cứu hộ (nhận JWT Token). |
| `POST` | `/api/auth/refresh` | Rescuer, Commander | Làm mới phiên đăng nhập (Refresh Token). |
| `GET` | `/api/auth/me` | Authenticated | Lấy thông tin tài khoản hiện tại, vai trò và đội được phân công. |
| `POST` | `/api/auth/register-team` | Admin, Commander | Cấp phép và đăng ký đội cứu hộ tình nguyện mới. |

---

### 2.2. Phân hệ Citizen Portal (Giao diện Người Dân)

Không bắt buộc người dân phải đăng nhập để gửi yêu cầu cứu hộ khẩn cấp.

#### 1. Phát Tín hiệu Cứu hộ SOS 1 Chạm
- **Endpoint:** `POST /api/citizen/sos`
- **Request Body:**
```json
{
  "reporter_name": "Nguyễn Văn A",
  "reporter_phone": "0912345678",
  "lat": 21.5928,
  "lng": 105.8442,
  "address_description": "Số 15 đường Hoàng Văn Thụ, TP. Thái Nguyên",
  "people_count": 3,
  "has_elderly": true,
  "has_children": true,
  "has_injured": false,
  "water_level_cm": 150.0,
  "danger_description": "Nước dâng lên gác xép, sắp cạn pin điện thoại",
  "required_needs": ["xuồng cứu hộ", "sơ tán", "nước uống"]
}
```
- **Response (201 Created):**
```json
{
  "status": "success",
  "data": {
    "tracking_code": "SOS-2026-7821",
    "status": "pending",
    "priority": "critical",
    "assigned_team": null,
    "created_at": "2026-11-18T00:30:15Z"
  },
  "message": "Đã tiếp nhận yêu cầu cứu hộ. Lực lượng cứu nạn đang phân công đội tiếp cận!"
}
```

#### 2. Cấp Cứu Bằng Giọng Nói AI (Voice SOS)
- **Endpoint:** `POST /api/ai/voice-sos/text` (Nhận diện văn bản Web Speech)
- **Endpoint:** `POST /api/ai/voice-sos` (Tải tệp âm thanh trực tiếp lên Groq Whisper LPU)
- **Năng lực đặc biệt:** Tự động phát hiện địa danh tiếng Việt trong câu nói và nắn chỉnh tọa độ chính xác.

#### 3. Tra Cứu Trạng Thái Cứu Hộ (SOS Tracking)
- **Endpoint:** `GET /api/citizen/sos/track/{tracking_code}`
- **Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "tracking_code": "SOS-2026-7821",
    "status": "dispatched",
    "status_label": "Đội cứu hộ đang trên đường tới",
    "assigned_team": {
      "team_name": "Đội Xuồng Máy Số 3 - PCCC Thái Nguyên",
      "hotline": "0208-3855-114",
      "vehicle": "Xuồng hơi cứu nạn Yamaha 40HP"
    },
    "estimated_arrival_minutes": 15,
    "safety_instructions": "Di chuyển lên vị trí cao nhất có thể, giữ ấm cơ thể, vẫy áo màu sáng khi nghe tiếng động cơ xuồng."
  }
}
```

#### 4. Báo Cáo Hiện Trường Thiên Tai (Citizen Report)
- **Endpoint:** `POST /api/citizen/report`
- **Request Body (Multipart Form):** `phone`, `lat`, `lng`, `hazard_type`, `water_depth_cm`, `description`, `images` (tệp ảnh hiện trường).

---

### 2.3. Phân hệ Rescue Operations (Cổng Đội Cứu Hộ Hiện Trường)

Yêu cầu xác thực `Bearer JWT Token` với vai trò `rescuer` hoặc `team_leader`.

#### 1. Lấy Danh Sách Nhiệm Vụ Được Phân Công
- **Endpoint:** `GET /api/rescue/tasks`
- **Query Params:** `status=dispatched&limit=20`
- **Response:** Danh sách các ca SOS được Ban chỉ huy giao cho đội kèm tọa độ, số người, nhu cầu đặc biệt và số điện thoại liên lạc.

#### 2. Cập Nhật Tiến Độ Nhiệm Vụ Hiện Trường
- **Endpoint:** `PATCH /api/rescue/tasks/{task_id}/status`
- **Request Body:**
```json
{
  "status": "in_progress | transporting | resolved | unreachable",
  "rescued_count": 4,
  "safe_zone_delivered_id": 3,
  "field_notes": "Đã đưa 2 người già và 2 trẻ nhỏ lên xuồng an toàn, đang di chuyển về trường THPT Chu Văn An."
}
```

#### 3. Cập Nhật Vị Trí & Trạng Thái Trực Chiến của Đội
- **Endpoint:** `POST /api/rescue/team/telemetry`
- **Request Body:** `lat`, `lng`, `team_status` ('standby', 'deployed', 'resting'), `fuel_level_percent`.

#### 4. Đồng Bộ Hàng Đợi Ngoại Tuyến (Offline Batch Sync)
- **Endpoint:** `POST /api/rescue/sync`
- **Mô tả:** Gửi một batch các hành động ngoại tuyến từ `IndexedDB` khi thiết bị vừa bắt lại sóng di động.

---

### 2.4. Phân hệ NorthStar Command (Trung tâm Chỉ huy Điều hành)

Yêu cầu quyền `dispatcher`, `commander` hoặc `sys_admin`.

#### 1. Bản Đồ Tình Huống Toàn Cảnh (Common Operating Picture - COP)
- **Endpoint:** `GET /api/command/cop-overview`
- **Response:** Thống kê tổng hợp: Tổng số ca SOS, số ca nguy cấp chưa giao việc, số đội đang cơ động, bản đồ nhiệt các điểm ngập sâu và cảnh báo lũ sông ngòi.

#### 2. Lệnh Điều Phân Công Đội Cứu Hộ (Dispatch Task)
- **Endpoint:** `POST /api/command/dispatch`
- **Request Body:**
```json
{
  "sos_request_id": 7821,
  "team_id": 3,
  "priority": "critical",
  "operational_order": "Điều động xuồng số 3 tiếp cận ngay số 15 Hoàng Văn Thụ, ưu tiên 2 người già."
}
```

#### 3. Quản Lý Kho Vận & Tiếp Tế Nhu Yếu Phẩm
- **Endpoint:** `GET /api/command/inventory`
- **Endpoint:** `POST /api/command/inventory/transfer` (Chuyển 500 áo phao và 1,000 thùng nước sạch từ Kho Dự Trữ Tỉnh sang Trạm sơ tán Làng Nủ).

#### 4. Xuất Báo Cáo Tác Chiến SitRep QĐ 18/2021/QĐ-TTg
- **Endpoint:** `GET /api/sitrep/generate` (Tạo bảng báo cáo trực ban theo định dạng chuẩn).

---

### 2.5. Phân hệ GIS, Định Tuyến & Dữ Liệu Mở Toàn Cầu

| Method | Endpoint | Mô tả nghiệp vụ |
| :--- | :--- | :--- |
| `POST` | `/api/route` | Thuật toán $A^*$ tìm đường né ngập, né sạt lở theo phương tiện. |
| `POST` | `/api/evacuation/nearest-shelter` | Thuật toán Dijkstra đa nguồn tìm điểm sơ tán còn chỗ gần nhất. |
| `GET` | `/api/weather/flood-forecast` | Dữ liệu mở Open-Meteo Flood API / Copernicus GloFAS ($m^3/s$). |
| `GET` | `/api/weather/glofas-basins` | Báo cáo thủy văn các lưu vực sông trọng điểm Bắc Bộ. |
| `GET` | `/api/weather/nasa-gpm` | Quan trắc mưa bão vệ tinh NASA GPM IMERG. |
| `GET` | `/api/weather/open-data-licenses` | Danh mục giấy phép mở OSI & tuyên bố Zero Scraping. |

---

### 2.6. Hệ Thống WebSockets Phát Sóng Thời Gian Thực

- **Kênh `/ws/nav`:** Truyền tọa độ di chuyển và cảnh báo ngập nước tức thời cho phương tiện đang tìm đường.
- **Kênh `/ws/sos`:** Phát sóng mốc cờ đỏ SOS cho toàn bộ bản đồ khi có người dân gửi tín hiệu khẩn cấp.
- **Kênh `/ws/command`:** Kênh mã hóa hai chiều dành riêng cho Trung tâm Chỉ huy và Đội trưởng Đội Cứu hộ để trao đổi mệnh lệnh điều động khẩn cấp.
