# BẢN THIẾT KẾ CƠ SỞ DỮ LIỆU TOÀN DIỆN (DATABASE DESIGN)
## Cấu trúc Schema PostgreSQL 16 + PostGIS & SQLite Fallback cho NORTHSTAR COMMAND

---

## 1. NGUYÊN TẮC THIẾT KẾ DỮ LIỆU
1. **Chuẩn hóa & Toàn vẹn tham chiếu:** Sử dụng UUID v4 cho các bản ghi giao dịch phân tán (SOS, Tasks, Logs) để tránh xung đột mã định danh khi đồng bộ ngoại tuyến.
2. **Không gian địa lý PostGIS (SRID 4326):** Mọi tọa độ vị trí được lưu trữ ở kiểu dữ liệu `GEOMETRY(Point, 4326)` hoặc `GEOMETRY(Polygon, 4326)`, tối ưu hóa truy vấn vùng lân cận bằng chỉ mục GiST (`idx_..._geom USING GIST`).
3. **Phân vùng dữ liệu chuỗi thời gian (Timescale / Partitioning ready):** Các bảng có tần suất ghi cao (`water_level_observations`, `weather_observations`, `data_ingestion_logs`, `audit_logs`) được thiết kế trường thời gian `recorded_at` với chỉ mục B-Tree giảm dần (`DESC`).
4. **Mô hình Dự phòng Tương thích Kép (Dual-mode Schema):** Schema tương thích hoàn toàn để khi chuyển sang SQLite Circuit Breaker, các trường hình học tự động chuyển thành cặp số thực `(latitude, longitude)`.

---

## 2. ĐẶC TẢ CHI TIẾT 14 NHÓM BẢNG DỮ LIỆU (DDL)

```sql
-- Kích hoạt extension PostGIS & sinh UUID
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================================
-- NHÓM 1: TÀI KHOẢN, VAI TRÒ & PHÂN QUYỀN (USERS & RBAC)
-- ========================================================
CREATE TYPE user_role_enum AS ENUM (
    'SUPER_ADMIN', 'COMMAND_DIRECTOR', 'DISPATCHER', 
    'DATA_ANALYST', 'INFORMATION_VERIFIER', 'RESCUE_COORDINATOR', 
    'RELIEF_COORDINATOR', 'RESCUER', 'VOLUNTEER', 'CITIZEN'
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    role user_role_enum NOT NULL DEFAULT 'CITIZEN',
    geo_scope VARCHAR(100) DEFAULT 'ALL', -- ALL hoặc mã tỉnh 'HANOI', 'THAI_NGUYEN', 'LAO_CAI'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- NHÓM 2: TỔ CHỨC & LIÊN MINH CỨU NẠN (ORGANIZATIONS)
-- ========================================================
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    org_type VARCHAR(50) NOT NULL, -- 'GOVERNMENT', 'MILITARY', 'POLICE', 'NGO', 'CHARITY'
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    operating_area VARCHAR(255),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    position VARCHAR(100) NOT NULL DEFAULT 'Thành viên',
    is_lead BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id, user_id)
);

-- ========================================================
-- NHÓM 3: BÁO CÁO DÂN SỰ & YÊU CẦU SOS (CITIZEN REPORTS & SOS)
-- ========================================================
CREATE TYPE verification_status_enum AS ENUM ('RECEIVED', 'VERIFYING', 'VERIFIED', 'REJECTED', 'EXPIRED');
CREATE TYPE urgency_level_enum AS ENUM ('P1_CRITICAL', 'P2_HIGH', 'P3_MEDIUM', 'P4_LOW');

CREATE TABLE sos_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tracking_code VARCHAR(20) UNIQUE NOT NULL, -- Sinh ngẫu nhiên ví dụ 'SOS-2026-9812'
    contact_name VARCHAR(100),
    phone_encrypted TEXT, -- Lưu trữ mã hóa AES-256
    geom geometry(Point, 4326) NOT NULL,
    address_text TEXT,
    people_count INT NOT NULL DEFAULT 1,
    has_elderly BOOLEAN NOT NULL DEFAULT FALSE,
    has_children BOOLEAN NOT NULL DEFAULT FALSE,
    has_injured BOOLEAN NOT NULL DEFAULT FALSE,
    water_depth_cm NUMERIC(6,1),
    situation_notes TEXT,
    audio_recording_url TEXT,
    urgency_level urgency_level_enum NOT NULL DEFAULT 'P2_HIGH',
    verification_status verification_status_enum NOT NULL DEFAULT 'RECEIVED',
    verified_by UUID REFERENCES users(id),
    verification_notes TEXT,
    is_duplicate_of UUID REFERENCES sos_requests(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sos_requests_geom ON sos_requests USING GIST (geom);
CREATE INDEX idx_sos_requests_status ON sos_requests (verification_status, urgency_level);
CREATE INDEX idx_sos_tracking_code ON sos_requests (tracking_code);

CREATE TABLE citizen_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    hazard_type VARCHAR(50) NOT NULL, -- 'FLOOD', 'LANDSLIDE', 'DAMAGED_BRIDGE', 'DOWNED_WIRE'
    geom geometry(Point, 4326) NOT NULL,
    description TEXT,
    photo_url TEXT,
    verification_status verification_status_enum NOT NULL DEFAULT 'RECEIVED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_citizen_reports_geom ON citizen_reports USING GIST (geom);

-- ========================================================
-- NHÓM 4: NGUỒN TIẾP NHẬN DỮ LIỆU (INGESTION SOURCES)
-- ========================================================
CREATE TABLE information_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- 'OPEN_METEO', 'NASA_GPM', 'GLOFAS', 'SENTINEL_SAR', 'CITIZEN'
    endpoint_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    poll_interval_seconds INT NOT NULL DEFAULT 600,
    last_ingested_at TIMESTAMPTZ,
    last_status VARCHAR(50) DEFAULT 'HEALTHY'
);

CREATE TABLE data_ingestion_logs (
    id BIGSERIAL PRIMARY KEY,
    source_id UUID REFERENCES information_sources(id) ON DELETE CASCADE,
    records_fetched INT NOT NULL DEFAULT 0,
    records_valid INT NOT NULL DEFAULT 0,
    records_rejected INT NOT NULL DEFAULT 0,
    error_message TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ingestion_logs_time ON data_ingestion_logs (created_at DESC);

-- ========================================================
-- NHÓM 5: DỮ LIỆU KHÍ TƯỢNG THỜI TIẾT (WEATHER)
-- ========================================================
CREATE TABLE weather_observations (
    id BIGSERIAL PRIMARY KEY,
    location_name VARCHAR(100) NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    temp_c NUMERIC(4,1),
    precipitation_1h_mm NUMERIC(6,1) NOT NULL DEFAULT 0.0,
    precipitation_24h_mm NUMERIC(6,1) NOT NULL DEFAULT 0.0,
    wind_speed_kmh NUMERIC(5,1),
    wind_direction_deg INT,
    source VARCHAR(50) NOT NULL DEFAULT 'Open-Meteo',
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_weather_geom_time ON weather_observations USING GIST (geom);
CREATE INDEX idx_weather_recorded_at ON weather_observations (recorded_at DESC);

-- ========================================================
-- NHÓM 6: TRẠM THỦY VĂN & MỰC NƯỚC SÔNG (RIVER STATIONS)
-- ========================================================
CREATE TABLE river_stations (
    id VARCHAR(50) PRIMARY KEY, -- e.g., 'ST_SONGHONG_HANOI'
    name VARCHAR(255) NOT NULL,
    river_name VARCHAR(100) NOT NULL,
    basin_name VARCHAR(100) NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    alarm_level_1_m NUMERIC(5,2) NOT NULL,
    alarm_level_2_m NUMERIC(5,2) NOT NULL,
    alarm_level_3_m NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_river_stations_geom ON river_stations USING GIST (geom);

CREATE TABLE water_level_observations (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(50) NOT NULL REFERENCES river_stations(id) ON DELETE CASCADE,
    water_level_m NUMERIC(5,2) NOT NULL,
    flow_discharge_m3s NUMERIC(8,2),
    alarm_state VARCHAR(20) NOT NULL DEFAULT 'NORMAL', -- 'NORMAL', 'ALARM_1', 'ALARM_2', 'ALARM_3'
    source VARCHAR(50) NOT NULL DEFAULT 'GloFAS',
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_water_level_station_time ON water_level_observations (station_id, recorded_at DESC);

-- ========================================================
-- NHÓM 7: VÙNG NGUY HIỂM & VÙNG NGẬP (HAZARDS & FLOOD ZONES)
-- ========================================================
CREATE TABLE hazard_zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    hazard_type VARCHAR(50) NOT NULL, -- 'FLOOD', 'LANDSLIDE', 'FLASH_FLOOD'
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    geom geometry(Polygon, 4326) NOT NULL,
    water_depth_cm NUMERIC(6,1),
    flow_velocity_ms NUMERIC(4,2),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    verified_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_hazard_zones_geom ON hazard_zones USING GIST (geom);

-- ========================================================
-- NHÓM 8: ĐỘI CỨU HỘ & PHƯƠNG TIỆN (RESCUE TEAMS & ASSETS)
-- ========================================================
CREATE TYPE team_status_enum AS ENUM ('AVAILABLE', 'ASSIGNED', 'ON_MISSION', 'RESTING', 'OFFLINE');

CREATE TABLE rescue_teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    leader_name VARCHAR(100) NOT NULL,
    leader_phone VARCHAR(20) NOT NULL,
    total_members INT NOT NULL DEFAULT 4,
    skills TEXT[], -- ARRAY['WATER_RESCUE', 'FIRST_AID', 'DIVING', 'BOAT_OPERATOR']
    current_geom geometry(Point, 4326),
    location_updated_at TIMESTAMPTZ,
    status team_status_enum NOT NULL DEFAULT 'AVAILABLE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rescue_teams_geom ON rescue_teams USING GIST (current_geom);

CREATE TABLE resources_vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID REFERENCES rescue_teams(id) ON DELETE SET NULL,
    vehicle_type VARCHAR(50) NOT NULL, -- 'RUBBER_BOAT', 'CANOE', 'HIGH_CLEARANCE_TRUCK', 'AMBULANCE'
    plate_or_reg_number VARCHAR(50),
    max_payload_kg INT,
    seat_capacity INT NOT NULL DEFAULT 6,
    fuel_level_percent INT NOT NULL DEFAULT 100,
    status VARCHAR(50) NOT NULL DEFAULT 'OPERATIONAL',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- NHÓM 9: ĐỘI THIỆN NGUYỆN & KHO VẬT TƯ (VOLUNTEERS & RELIEF)
-- ========================================================
CREATE TABLE volunteer_organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_name VARCHAR(255) NOT NULL,
    representative_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    vehicle_count INT DEFAULT 1,
    operational_province VARCHAR(100),
    verified_by_command BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE relief_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    volunteer_org_id UUID REFERENCES volunteer_organizations(id) ON DELETE CASCADE,
    item_category VARCHAR(50) NOT NULL, -- 'FOOD', 'WATER', 'MEDICINE', 'CLOTHING', 'EQUIPMENT'
    item_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(10,2) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL, -- 'kg', 'thùng', 'chai', 'viên', 'bộ'
    storage_location_text TEXT,
    allocated_quantity NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- NHÓM 10: ĐIỂM SƠ TÁN AN TOÀN (SAFE ZONES)
-- ========================================================
CREATE TABLE safe_zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(100) NOT NULL, -- 'SCHOOL', 'COMMUNITY_CENTER', 'GOVERNMENT_OFFICE', 'STADIUM'
    geom geometry(Point, 4326) NOT NULL,
    address TEXT,
    max_capacity INT NOT NULL DEFAULT 200,
    current_occupants INT NOT NULL DEFAULT 0,
    has_backup_power BOOLEAN NOT NULL DEFAULT TRUE,
    water_reserve_days INT NOT NULL DEFAULT 3,
    medical_staff_on_duty BOOLEAN NOT NULL DEFAULT FALSE,
    contact_phone VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'FULL', 'TEMPORARILY_CLOSED', 'UNVERIFIED'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_safe_zones_geom ON safe_zones USING GIST (geom);

-- ========================================================
-- NHÓM 11: NHIỆM VỤ ĐIỀU PHỐI (RESCUE & RELIEF TASKS)
-- ========================================================
CREATE TYPE task_type_enum AS ENUM ('RESCUE_MISSION', 'RELIEF_DELIVERY', 'EVACUATION_ESCORT', 'VERIFICATION');
CREATE TYPE task_status_enum AS ENUM ('PENDING', 'ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'COMPLETED', 'ABORTED');

CREATE TABLE rescue_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_code VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'TASK-2026-0812'
    task_type task_type_enum NOT NULL DEFAULT 'RESCUE_MISSION',
    sos_id UUID REFERENCES sos_requests(id) ON DELETE SET NULL,
    assigned_team_id UUID REFERENCES rescue_teams(id) ON DELETE SET NULL,
    assigned_volunteer_id UUID REFERENCES volunteer_organizations(id) ON DELETE SET NULL,
    target_geom geometry(Point, 4326) NOT NULL,
    target_address TEXT,
    priority urgency_level_enum NOT NULL DEFAULT 'P2_HIGH',
    destination_safe_zone_id UUID REFERENCES safe_zones(id) ON DELETE SET NULL,
    status task_status_enum NOT NULL DEFAULT 'PENDING',
    dispatched_by UUID REFERENCES users(id),
    dispatched_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rescue_tasks_geom ON rescue_tasks USING GIST (target_geom);
CREATE INDEX idx_rescue_tasks_status ON rescue_tasks (status, priority);

CREATE TABLE task_updates (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES rescue_tasks(id) ON DELETE CASCADE,
    updated_by UUID REFERENCES users(id),
    previous_status task_status_enum,
    new_status task_status_enum NOT NULL,
    people_rescued INT DEFAULT 0,
    current_location geometry(Point, 4326),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- NHÓM 12: THÔNG BÁO TÁC CHIẾN (NOTIFICATIONS)
-- ========================================================
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipient_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    recipient_role user_role_enum,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'ALARM_DISASTER', 'NEW_TASK', 'TASK_COMPLETED'
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_recipient ON notifications (recipient_user_id, is_read);

-- ========================================================
-- NHÓM 13: NHẬT KÝ KIỂM TOÁN AN NINH (AUDIT LOGS)
-- ========================================================
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_role user_role_enum,
    action_type VARCHAR(100) NOT NULL, -- 'VIEW_PII_DATA', 'VERIFY_SOS', 'DISPATCH_TASK', 'CHANGE_USER_ROLE'
    resource_type VARCHAR(50) NOT NULL, -- 'SOS', 'RESCUE_TASK', 'USER', 'INVENTORY'
    resource_id VARCHAR(100),
    client_ip VARCHAR(50),
    user_agent TEXT,
    previous_state JSONB,
    new_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_user_action ON audit_logs (user_id, action_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at DESC);

-- ========================================================
-- NHÓM 14: ĐỒNG BỘ NGOẠI TUYẾN & XỬ LÝ XUNG ĐỘT (OFFLINE SYNC)
-- ========================================================
CREATE TABLE sync_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(100) NOT NULL,
    client_tx_uuid UUID NOT NULL,
    entity_name VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    operation VARCHAR(10) NOT NULL, -- 'INSERT', 'UPDATE'
    payload JSONB NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(device_id, client_tx_uuid)
);

CREATE TABLE sync_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_op_id UUID REFERENCES sync_operations(id) ON DELETE CASCADE,
    conflict_reason TEXT NOT NULL,
    resolution_strategy VARCHAR(50) DEFAULT 'LAST_WRITE_WINS',
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
