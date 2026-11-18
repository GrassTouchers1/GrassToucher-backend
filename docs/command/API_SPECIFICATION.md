# ĐẶC TẢ GIAO DIỆN LẬP TRÌNH ỨNG DỤNG (API SPECIFICATION)
## RESTful Endpoints & WebSocket Protocol – NORTHSTAR COMMAND
**Chuẩn kỹ thuật:** OpenAPI 3.1, JSON / GeoJSON, Bearer JWT Authentication, HTTP Status Codes RFC 9110

---

## 1. NHÓM XÁC THỰC & PHÂN QUYỀN (AUTH & IDENTITY)

### `POST /api/v1/auth/login`
- **Mô tả:** Đăng nhập nhân sự điều hành, trả về Access Token & Refresh Token kèm danh sách quyền và phạm vi địa lý.
- **Request Body:**
  ```json
  { "username": "dispatcher_hanoi_01", "password": "SecurePassword123!" }
  ```
- **Response 200 OK:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "a1b2c3d4-...",
      "username": "dispatcher_hanoi_01",
      "full_name": "Nguyễn Văn A",
      "role": "DISPATCHER",
      "geo_scope": "HANOI",
      "permissions": ["SOS_VIEW", "SOS_VERIFY", "TASK_ASSIGN", "TEAM_VIEW"]
    }
  }
  ```

---

## 2. BẢNG ĐIỀU KHIỂN TÁC CHIẾN TỔNG THỂ (COMMAND DASHBOARD & COP)

### `GET /api/v1/command/dashboard/overview`
- **Mô tả:** Cung cấp chỉ số tổng hợp thời gian thực cho màn hình trung tâm COP.
- **Header:** `Authorization: Bearer <token>` (Yêu cầu vai trò COMMAND).
- **Query Params:** `province` (tùy chọn).
- **Response 200 OK:**
  ```json
  {
    "timestamp": "2026-11-18T05:45:00Z",
    "geo_scope": "HANOI",
    "kpi_counters": {
      "sos_total_active": 42,
      "sos_critical_p1": 7,
      "sos_verifying": 12,
      "rescue_teams_deployed": 15,
      "rescue_teams_available": 8,
      "people_rescued_today": 128,
      "safe_zones_open": 24,
      "safe_zones_capacity_percent": 68.5
    },
    "weather_summary": {
      "rain_max_province": "Mê Linh (85mm/h)",
      "storm_alert_level": "Cấp 2 - Mưa rất to",
      "river_highest_alarm": "Sông Hồng: Báo động 1 (+0.35m)"
    }
  }
  ```

---

## 3. TIẾP NHẬN & THẨM ĐỊNH THÔNG TIN (INFORMATION HUB & SOS)

### `GET /api/v1/command/sos/incoming`
- **Mô tả:** Lấy danh sách các cuộc gọi/báo cáo SOS đang chờ xử lý, sắp xếp theo độ ưu tiên Triage (P1 $\rightarrow$ P4).
- **Header:** `Authorization: Bearer <token>` (`INFORMATION_VERIFIER`, `DISPATCHER`, `COMMAND_DIRECTOR`).
- **Response 200 OK:**
  ```json
  [
    {
      "id": "8f9a2b1c-...",
      "tracking_code": "SOS-2026-9182",
      "contact_name": "Trần Thị B",
      "phone": "0987***321", // Đã che mờ nếu không bấm nút Mở PII
      "location": { "lat": 21.0315, "lng": 105.8421, "address": "Số 15 ngõ 42 Phúc Xá, Ba Đình" },
      "people_count": 3,
      "vulnerable": { "elderly": 1, "children": 1, "injured": false },
      "water_depth_cm": 140,
      "urgency_level": "P1_CRITICAL",
      "verification_status": "RECEIVED",
      "duplicates_count": 2,
      "created_at": "2026-11-18T05:40:12Z"
    }
  ]
  ```

### `POST /api/v1/command/sos/{id}/verify`
- **Mô tả:** Thẩm định viên cập nhật kết quả xác minh cuộc gọi cứu hộ.
- **Request Body:**
  ```json
  {
    "status": "VERIFIED", // hoặc 'REJECTED' nếu là báo cáo ảo
    "verified_phone": "0987654321",
    "verified_people_count": 3,
    "urgency_level": "P1_CRITICAL",
    "verification_notes": "Đã gọi điện cho gia đình, nước ngập đến cổ, có cháu nhỏ 2 tuổi đang trên gác xép."
  }
  ```
- **Response 200 OK:** Cập nhật trạng thái và tự động phát WebSocket thông báo cho Dispatcher.

---

## 4. BẢN ĐỒ THIÊN TAI TỔNG HỢP (GIS DISASTER MAP)

### `GET /api/v1/command/disaster-map/layers`
- **Mô tả:** Lấy dữ liệu không gian tổng hợp dạng FeatureCollection (GeoJSON) phục vụ vẽ bản đồ Leaflet/Mapbox.
- **Query Params:** `bbox` (minLng,minLat,maxLng,maxLat), `layers` (`sos,stations,shelters,hazard_zones,teams`).
- **Response 200 OK:**
  ```json
  {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [105.8421, 21.0315] },
        "properties": {
          "layer": "sos",
          "id": "8f9a2b1c-...",
          "code": "SOS-2026-9182",
          "urgency": "P1_CRITICAL",
          "status": "VERIFIED"
        }
      },
      {
        "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [105.8512, 21.0450] },
        "properties": {
          "layer": "stations",
          "station_name": "Long Biên - Sông Hồng",
          "water_level_m": 9.85,
          "alarm_state": "ALARM_1"
        }
      }
    ]
  }
  ```

---

## 5. ĐIỀU ĐỘNG CỨU HỘ & CỨU TRỢ (DISPATCH & TASK EXECUTION)

### `POST /api/v1/command/tasks/dispatch-rescue`
- **Mô tả:** Chỉ huy trưởng / Điều phối viên phát lệnh điều động Đội cứu hộ chuyên môn tới hiện trường.
- **Request Body:**
  ```json
  {
    "sos_id": "8f9a2b1c-...",
    "team_id": "c4d5e6f7-...",
    "priority": "P1_CRITICAL",
    "destination_safe_zone_id": "e9f0a1b2-...",
    "suggested_vehicle": "RUBBER_BOAT",
    "command_orders": "Tiếp cận ngõ 42 Phúc Xá bằng xuồng cứu sinh; ưu tiên bế cháu nhỏ và cụ già trước."
  }
  ```
- **Response 201 Created:**
  ```json
  {
    "task_id": "7a8b9c0d-...",
    "task_code": "TASK-2026-0812",
    "status": "ASSIGNED",
    "dispatched_at": "2026-11-18T05:48:30Z"
  }
  ```

### `POST /api/v1/command/tasks/dispatch-relief`
- **Mô tả:** Điều phối viên kết nối Đội thiện nguyện vận chuyển lương thực/thuốc men tới điểm sơ tán hoặc điểm tiếp nhận an toàn.
- **Request Body:**
  ```json
  {
    "volunteer_org_id": "b2c3d4e5-...",
    "destination_safe_zone_id": "e9f0a1b2-...",
    "supplies_requested": [
      { "item_category": "FOOD", "item_name": "Mì tôm", "quantity": 100, "unit": "thùng" },
      { "item_category": "WATER", "item_name": "Nước uống 5L", "quantity": 200, "unit": "chai" }
    ],
    "notes": "Tập kết hàng tại cổng Trường THCS Yên Hòa trước 16h00."
  }
  ```
- **Response 201 Created:** Ghi nhận lệnh cứu trợ, tự động trừ số lượng khả dụng trong `relief_inventory`.

---

## 6. NHẬT KÝ AN NINH & KIỂM TOÁN (AUDIT LOGS)

### `GET /api/v1/command/audit-logs`
- **Mô tả:** Tra cứu nhật ký kiểm toán hệ thống.
- **Header:** `Authorization: Bearer <token>` (Chỉ `SUPER_ADMIN` và `COMMAND_DIRECTOR`).
- **Query Params:** `user_id`, `action_type`, `from_date`, `to_date`, `limit`.
- **Response 200 OK:**
  ```json
  [
    {
      "id": 10842,
      "user_name": "dispatcher_hanoi_01",
      "user_role": "DISPATCHER",
      "action_type": "VIEW_PII_DATA",
      "resource_type": "SOS",
      "resource_id": "8f9a2b1c-...",
      "client_ip": "14.225.21.84",
      "timestamp": "2026-11-18T05:42:01Z"
    }
  ]
  ```
