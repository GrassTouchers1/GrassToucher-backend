"""
Cơ chế lưu trữ bền vững dự phòng (Persistent Fallback Storage) khi PostgreSQL không hoạt động.
Sử dụng SQLite với cơ chế khoá file và WAL để đảm bảo:
- Đồng bộ dữ liệu quan trắc giữa nhiều tiến trình (workers) và các phiên Serverless
- Dữ liệu số đo (readings) và báo cáo (reports) được lưu bền vững vào đĩa thay vì chỉ lưu tạm trên RAM
- Tách biệt hoàn toàn số đo quan trắc khỏi danh mục trạm ngập mặc định (DEFAULT_FLOOD_POINTS)
"""
import sqlite3
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import tempfile

log = logging.getLogger("floodnav.fallback_storage")
_FALLBACK_WRITE_LOCK = threading.Lock()


class IdempotencyConflictError(Exception):
    """Ngoại lệ khi cùng client_event_id nhưng nội dung payload xung đột."""
    pass

ROOT = Path(__file__).resolve().parents[2]


def _get_db_path() -> Path:
    """Xác định đường dẫn file SQLite an toàn (ưu tiên thư mục data/ của dự án, fallback sang tempdir nếu read-only)."""
    data_dir = ROOT / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return data_dir / "fallback_storage.db"
    except Exception:
        pass
    temp_dir = Path(tempfile.gettempdir()) / "floodnav"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / "fallback_storage.db"


DB_PATH = _get_db_path()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except Exception:
        pass
    return conn


def init_fallback_db():
    """Khởi tạo bảng lưu trữ bền vững nếu chưa tồn tại."""
    try:
        with _get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS fallback_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    point_id INTEGER NOT NULL,
                    sensor_id TEXT,
                    depth_cm REAL NOT NULL,
                    source TEXT DEFAULT 'sensor',
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fb_readings_point ON fallback_readings(point_id, id DESC);

                CREATE TABLE IF NOT EXISTS fallback_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    lng REAL NOT NULL,
                    lat REAL NOT NULL,
                    level TEXT NOT NULL,
                    photo_url TEXT,
                    confirmed INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fb_reports_exp ON fallback_reports(expires_at);

                CREATE TABLE IF NOT EXISTS fallback_disasters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    hazard_type TEXT NOT NULL DEFAULT 'flood',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'active',
                    description TEXT,
                    lng REAL NOT NULL,
                    lat REAL NOT NULL,
                    radius_m REAL DEFAULT 150.0,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fallback_shelters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT,
                    lng REAL NOT NULL,
                    lat REAL NOT NULL,
                    capacity INTEGER DEFAULT 200,
                    current_occupancy INTEGER DEFAULT 0,
                    contact_phone TEXT,
                    supplies_status TEXT DEFAULT 'Sẵn sàng (Lương thực & Y tế)',
                    status TEXT DEFAULT 'open',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fallback_sos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    lng REAL,
                    lat REAL,
                    location_source TEXT DEFAULT 'manual',
                    location_accuracy_m REAL,
                    location_captured_at TEXT,
                    location_confirmed INTEGER DEFAULT 0,
                    location_description TEXT,
                    location_landmark TEXT,
                    people_count INTEGER DEFAULT 1,
                    has_elderly_or_children INTEGER DEFAULT 0,
                    water_level_cm REAL DEFAULT 0.0,
                    priority TEXT DEFAULT 'high',
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # Di trú an toàn bảng fallback_sos cũ nếu thiếu các cột vị trí mở rộng hoặc lng/lat vẫn NOT NULL
            table_info = conn.execute("PRAGMA table_info(fallback_sos)").fetchall()
            existing_sos_cols = {row[1] for row in table_info}
            lng_notnull = any(row[1] == "lng" and row[3] == 1 for row in table_info)
            sos_migrations = [
                ("location_source", "TEXT DEFAULT 'manual'"),
                ("location_accuracy_m", "REAL"),
                ("location_captured_at", "TEXT"),
                ("location_confirmed", "INTEGER DEFAULT 0"),
                ("location_description", "TEXT"),
                ("location_landmark", "TEXT"),
                ("client_event_id", "TEXT"),
                ("payload_hash", "TEXT"),
                ("tracking_token_hash", "TEXT"),
                ("tracking_token_expires_at", "TEXT"),
                ("tracking_token_revoked", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_def in sos_migrations:
                if col_name not in existing_sos_cols:
                    conn.execute(f"ALTER TABLE fallback_sos ADD COLUMN {col_name} {col_def}")
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_fb_sos_client_event_id
                ON fallback_sos(client_event_id) WHERE client_event_id IS NOT NULL
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_fb_sos_tracking_token_hash
                ON fallback_sos(tracking_token_hash) WHERE tracking_token_hash IS NOT NULL
            """)

            existing_rep_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(fallback_reports)").fetchall()
            }
            for col_name, col_def in [("client_event_id", "TEXT"), ("payload_hash", "TEXT")]:
                if col_name not in existing_rep_cols:
                    conn.execute(f"ALTER TABLE fallback_reports ADD COLUMN {col_name} {col_def}")
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_fb_reports_client_event_id
                ON fallback_reports(client_event_id) WHERE client_event_id IS NOT NULL
            """)
            if lng_notnull:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS fallback_sos_v2 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        contact_name TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        lng REAL,
                        lat REAL,
                        location_source TEXT DEFAULT 'manual',
                        location_accuracy_m REAL,
                        location_captured_at TEXT,
                        location_confirmed INTEGER DEFAULT 0,
                        location_description TEXT,
                        location_landmark TEXT,
                        people_count INTEGER DEFAULT 1,
                        has_elderly_or_children INTEGER DEFAULT 0,
                        water_level_cm REAL DEFAULT 0.0,
                        priority TEXT DEFAULT 'high',
                        status TEXT DEFAULT 'pending',
                        notes TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    INSERT INTO fallback_sos_v2 (
                        id, contact_name, phone, lng, lat,
                        location_source, location_accuracy_m, location_captured_at,
                        location_confirmed, location_description, location_landmark,
                        people_count, has_elderly_or_children, water_level_cm,
                        priority, status, notes, created_at, updated_at
                    )
                    SELECT id, contact_name, phone, lng, lat,
                           location_source, location_accuracy_m, location_captured_at,
                           location_confirmed, location_description, location_landmark,
                           people_count, has_elderly_or_children, water_level_cm,
                           priority, status, notes, created_at, updated_at
                    FROM fallback_sos;
                    DROP TABLE fallback_sos;
                    ALTER TABLE fallback_sos_v2 RENAME TO fallback_sos;
                """)

            # Seed default disasters if empty
            count = conn.execute("SELECT COUNT(*) FROM fallback_disasters").fetchone()[0]
            if count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany("""
                    INSERT INTO fallback_disasters (title, hazard_type, severity, status, description, lng, lat, radius_m, start_time, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ("Lũ bùn quét & sạt lở núi kinh hoàng (Thôn Làng Nủ, Bảo Yên, Lào Cai)", "landslide", "critical", "active", "Dòng lũ bùn đá kinh hoàng từ núi Voi tràn qua bản làng, chia cắt toàn bộ lối vào, nhiều điểm ngập sâu và bùn lầy nguy hiểm.", 104.3833, 22.3167, 2500.0, now_iso, now_iso),
                    ("Lũ đặc biệt lớn trên BĐ3 sông Thao (TP Yên Bái)", "flood", "critical", "active", "Mực nước sông Thao vượt đỉnh lũ lịch sử 1968, ngập lụt diện rộng toàn bộ phường Hồng Hà, Yên Ninh, Đồng Tâm (sâu 1.5m - 3.2m).", 104.8833, 21.7167, 3000.0, now_iso, now_iso),
                    ("Lũ khẩn cấp sông Cầu - Ngập lụt nghiêm trọng TP Thái Nguyên", "flood", "critical", "active", "Mực nước dâng vượt đê Chã và cầu Gia Bảy, ngập sâu toàn diện các phường Quang Vinh, Chùa Hang, Hoàng Văn Thụ.", 105.8442, 21.5928, 2500.0, now_iso, now_iso),
                    ("Tràn đê bối sông Cầu & nguy cơ vỡ đê Tả Cầu (Hiệp Hòa, Bắc Giang)", "flood", "high", "active", "Mực nước lũ sông Cầu dâng cao tràn các bờ bao, đê bối xã Hợp Thịnh và Mai Đình, uy hiếp 4 xã ven sông.", 106.0500, 21.3200, 2000.0, now_iso, now_iso),
                    ("Sạt lở vách núi taluy dương chia cắt QL34 (Nguyên Bình, Cao Bằng)", "landslide", "critical", "active", "Sạt trượt đất đá khối lượng lớn tại đèo Pia Oắc vùi lấp mặt đường, phong tỏa tuyệt đối lưu thông.", 105.9700, 22.6100, 1500.0, now_iso, now_iso),
                    ("Sự cố sập mố nhịp cầu Phong Châu trên sông Thao (Tam Nông, Phú Thọ)", "landslide", "critical", "active", "Lũ xiết gây sập 2 nhịp giàn thép cầu Phong Châu trên QL32C, cấm mọi phương tiện và người dân tiếp cận.", 105.2890, 21.3117, 1200.0, now_iso, now_iso),
                    ("Tâm bão đổ bộ gió giật cấp 14 & sóng biển dâng cao (Vịnh Hạ Long)", "storm", "critical", "active", "Gió bão cực mạnh làm tốc mái, đổ gãy cây xanh, sạt trượt đất đồi và chìm tàu tại Bãi Cháy, Hòn Gai.", 107.0800, 20.9500, 3500.0, now_iso, now_iso),
                    ("Triều cường cực hạn kết hợp sóng bão phá vỡ kè biển (Cát Hải, Hải Phòng)", "storm", "high", "active", "Nước biển dâng tràn qua thân kè vào khu dân cư thị trấn Cát Hải, ngập sâu 1m - 1.5m.", 106.9100, 20.8000, 2500.0, now_iso, now_iso),
                    ("Xả lũ khẩn cấp hồ Tuyên Quang - Ngập úng hạ lưu sông Gâm & Lô", "flood", "high", "active", "Thủy điện mở 8 cửa xả đáy, dòng chảy xiết ngập bãi ven sông TP Tuyên Quang và huyện Chiêm Hóa.", 105.2200, 21.8200, 2200.0, now_iso, now_iso),
                    ("Cảnh báo ngập bãi bồi hạ lưu khi Thủy điện Hòa Bình mở cửa xả đáy", "flood", "medium", "active", "Lưu lượng xả lớn làm dâng cao mực nước sông Đà, ngập tràn các vùng bãi trũng TP Hòa Bình và Kỳ Sơn.", 105.3333, 20.8167, 2000.0, now_iso, now_iso),
                    ("Lũ báo động 3 sông Bùi - Ngập úng sâu xã Nam Phương Tiến (Chương Mỹ)", "flood", "high", "active", "Nước lũ dâng ngập trắng các thôn Nhân Lý, Nam Hài, sâu từ 1m đến 2m, kéo dài nhiều ngày.", 105.6580, 20.8920, 1500.0, now_iso, now_iso),
                    ("Điểm ngập úng đô thị Cầu Giấy - Hoa Bằng", "flood", "medium", "active", "Mực nước ngập 35cm sau cơn mưa lớn kéo dài, các phương tiện xe máy di chuyển khó khăn.", 105.7950, 21.0220, 300.0, now_iso, now_iso)
                ])

            # Seed default shelters if empty
            s_count = conn.execute("SELECT COUNT(*) FROM fallback_shelters").fetchone()[0]
            if s_count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany("""
                    INSERT INTO fallback_shelters (name, address, lng, lat, capacity, current_occupancy, contact_phone, supplies_status, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ("Trung tâm Chỉ huy Quân sự Huyện Bảo Yên (Sơ tán Làng Nủ)", "Khu 3B, TT. Phố Ràng, Bảo Yên, Lào Cai", 104.3420, 22.2850, 600, 180, "0214-3876-114", "Trạm chỉ huy dã chiến, 500 suất lương khô và thuốc men", "open", now_iso),
                    ("Nhà thi đấu Đa năng Tỉnh Lào Cai", "Đại lộ Trần Hưng Đạo, P. Bắc Lệnh, TP Lào Cai", 103.9780, 22.4510, 1500, 320, "0214-3840-234", "Máy phát điện công suất lớn, trạm lọc nước sạch dã chiến", "open", now_iso),
                    ("Trường THPT Chuyên Nguyễn Tất Thành (Điểm tránh lũ TP Yên Bái)", "Tổ 2, P. Đồng Tâm, TP Yên Bái", 104.8720, 21.7250, 1000, 450, "0216-3852-368", "1000 chăn ấm, bình nước 20L và mì ăn liền tiếp tế", "open", now_iso),
                    ("Trường Tiểu học & THCS Trần Phú (Trạm sơ tán Lục Yên)", "TT. Yên Thế, Huyện Lục Yên, Yên Bái", 104.7200, 22.1150, 500, 110, "0216-3845-122", "Khu nhà 3 tầng kiên cố, sẵn sàng pin sạc dự phòng", "open", now_iso),
                    ("Cung Văn hóa Lao động Tỉnh Thái Nguyên (Bến Đoan)", "Số 6 Đội Cấn, P. Trưng Vương, TP Thái Nguyên", 105.8360, 21.5870, 1400, 680, "0208-3855-432", "Điểm tập kết ca nô cứu hộ, phát cơm nóng và nước ngọt 24/7", "open", now_iso),
                    ("Trường THPT Trần Quốc Tuấn (Trạm an toàn Sông Cầu)", "TT. Hóa Thượng, Huyện Đồng Hỷ, Thái Nguyên", 105.8750, 21.6320, 600, 95, "0208-3820-115", "Đầy đủ vật tư y tế, chăn màn và lương thực khô", "open", now_iso),
                    ("Trung tâm Hội nghị Triển lãm Tỉnh Bắc Giang", "Quảng trường 3/2, Đường Hoàng Văn Thụ, TP Bắc Giang", 106.1980, 21.2760, 1200, 210, "0204-3854-222", "Hội trường rộng, máy phát điện liên tục, đội y tế túc trực", "open", now_iso),
                    ("Nhà thi đấu Thể dục Thể thao Tỉnh Phú Thọ", "Đường Hùng Vương, P. Thọ Sơn, TP Việt Trì, Phú Thọ", 105.3950, 21.3220, 1600, 290, "0210-3846-555", "Khu vực ngã ba sông cao ráo, trạm quân y lưu động", "open", now_iso),
                    ("Trung tâm Y tế Huyện Nguyên Bình (Trạm cấp cứu sạt trượt)", "Khu phố 1, TT. Nguyên Bình, Cao Bằng", 105.9820, 22.5830, 400, 145, "0206-3872-115", "Xe cấp cứu túc trực, cơ số thuốc và máu dự phòng đầy đủ", "open", now_iso),
                    ("Cung Quy hoạch, Hội chợ & Triển lãm Quảng Ninh (Cung Cá Heo)", "Đường Trần Quốc Nghiễn, P. Hồng Hải, TP Hạ Long", 107.0980, 20.9410, 2500, 620, "0203-3835-678", "Kết cấu thép kiên cố chịu bão cấp 17, bếp ăn dã chiến", "open", now_iso),
                    ("Cung Văn hóa Lao động Hữu nghị Việt Tiệp Hải Phòng", "Số 53 Lạch Tray, Quận Ngô Quyền, Hải Phòng", 106.6870, 20.8540, 2000, 410, "0225-3847-195", "Trạm trú bão an toàn, kho lương thực dự phòng 10 ngày", "open", now_iso),
                    ("Trung tâm Văn hóa Thể thao Thanh thiếu nhi Tuyên Quang", "Đường Bình Thuận, P. Tân Quang, TP Tuyên Quang", 105.2150, 21.8230, 900, 170, "0207-3822-456", "Phòng ốc rộng rãi, sẵn sàng quần áo khô và nước đóng chai", "open", now_iso),
                    ("Trường Cao đẳng Sư phạm Hòa Bình", "Phường Dân Chủ, TP Hòa Bình", 105.3470, 20.8260, 800, 190, "0218-3854-123", "Ký túc xá cao ráo an toàn tránh ngập xả lũ sông Đà", "open", now_iso),
                    ("Trường THPT Yên Hòa (Điểm sơ tán Cầu Giấy)", "Ngõ 251 Nguyễn Khang, Yên Hòa, Cầu Giấy, Hà Nội", 105.7940, 21.0210, 600, 85, "024-3833-1122", "Đầy đủ nước sạch, lương thực và chăn ấm", "open", now_iso),
                    ("Trường Tiểu học Nam Phương Tiến A (Điểm tránh lũ Chương Mỹ)", "Xã Nam Phương Tiến, Chương Mỹ, Hà Nội", 105.6620, 20.8960, 500, 210, "024-3386-7788", "Đã tiếp nhận lương khô, áo phao và thuốc men", "open", now_iso)
                ])

            # Seed default SOS requests if empty
            sos_count = conn.execute("SELECT COUNT(*) FROM fallback_sos").fetchone()[0]
            if sos_count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany("""
                    INSERT INTO fallback_sos (contact_name, phone, lng, lat, people_count, has_elderly_or_children, water_level_cm, priority, status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ("Hoàng Văn Tuấn", "0982341992", 104.3780, 22.3120, 5, 1, 0.0, "critical", "pending", "Đồi sạt cô lập 5 người có 2 cháu nhỏ 3 tuổi và 5 tuổi, cạn kiệt sữa và nước uống, đường sạt không đi bộ ra được!", now_iso, now_iso),
                    ("Sùng A Páo", "0971452881", 103.7450, 22.5480, 7, 1, 30.0, "high", "pending", "Nước suối dâng tràn qua nóc bếp, 1 cụ già 82 tuổi liệt giường cần chuyển cáng cứu hộ gấp!", now_iso, now_iso),
                    ("Nguyễn Thị Mai Lan", "0915678234", 104.8825, 21.7145, 4, 1, 180.0, "critical", "pending", "Nước sông Thao dâng ngập hết tầng 1 ngõ 84 Kim Đồng, trèo lên mái tôn chờ ca nô, pin sắp cạn!", now_iso, now_iso),
                    ("Vũ Đình Cường", "0944123890", 104.8320, 21.6850, 3, 0, 120.0, "high", "pending", "Thôn ngập sâu tứ bề tại Trấn Yên, cần viện trợ phao cứu sinh và nước sạch.", now_iso, now_iso),
                    ("Lê Văn Hùng", "0988776655", 105.8385, 21.5975, 6, 1, 160.0, "critical", "pending", "Ngập nóc nhà cấp 4 tổ 8 Quang Vinh, có phụ nữ mang thai tháng thứ 8 và trẻ em, đề nghị đội xuồng hỗ trợ khẩn!", now_iso, now_iso),
                    ("Trần Thị Ánh Tuyết", "0963214589", 105.8480, 21.6020, 4, 1, 90.0, "high", "pending", "Nước ngập ngang ngực gần cầu Gia Bảy, gia đình cần di tản tới điểm sơ tán Cung Văn hóa.", now_iso, now_iso),
                    ("Nguyễn Văn Đạt", "0977889900", 106.0380, 21.3180, 8, 1, 80.0, "high", "pending", "Nước sông Cầu tràn đê bối cô lập xóm ven sông Hiệp Hòa, cần 50 áo phao và lương khô.", now_iso, now_iso),
                    ("Đội Tuần tra Giao thông", "0206-3871-999", 105.9660, 22.6120, 12, 0, 0.0, "critical", "pending", "Đất đá vùi lấp xe chở khách trên đèo Pia Oắc km180 QL34, cần máy xúc chuyên dụng và đội tìm kiếm cứu nạn!", now_iso, now_iso),
                    ("Bùi Đình Trọng", "0934567112", 105.2860, 21.3080, 4, 1, 40.0, "high", "pending", "Bãi bồi sông Thao sát mố cầu Phong Châu nứt toác nguy cơ sập nhà, xin hỗ trợ sơ tán khẩn cấp người và gia súc.", now_iso, now_iso),
                    ("Đỗ Thành Trung", "0912456789", 107.0920, 20.9750, 5, 1, 70.0, "high", "pending", "Bão tốc toàn bộ mái tôn tại Hà Khánh - Hạ Long, nước dâng ngập, có cháu nhỏ sốt cao cần hỗ trợ y tế khẩn cấp.", now_iso, now_iso),
                    ("Vũ Hải Nam", "0904321987", 106.7920, 20.7020, 3, 0, 85.0, "medium", "pending", "Sóng biển đánh tràn kè Đồ Sơn, ghe xuồng đứt dây, đang trú tầng 2.", now_iso, now_iso),
                    ("Lý A Dũng", "0986543210", 105.2500, 22.1200, 6, 1, 110.0, "high", "pending", "Thủy điện xả lũ dòng nước xiết cô lập nhà ở Yên Nguyên - Chiêm Hóa, cần ca nô cứu nạn.", now_iso, now_iso),
                    ("Trần Văn Cường", "0983112233", 105.6590, 20.8930, 5, 1, 135.0, "critical", "pending", "Nước sông Bùi tràn đê ngập 1.35m xóm Bến Nam Phương Tiến, mất điện 4 ngày, cần tiếp tế khẩn cấp đồ ăn.", now_iso, now_iso),
                    ("Phạm Thị Hương", "0912987654", 105.7948, 21.0225, 2, 0, 38.0, "medium", "pending", "Ngập sâu 38cm ngõ Hoa Bằng xe máy chết máy, xin xe cứu hộ kéo xe khỏi điểm ngập.", now_iso, now_iso)
                ])

            conn.commit()
    except Exception as e:
        log.warning("Không thể khởi tạo fallback database SQLite: %s", e)


init_fallback_db()


def save_fallback_reading(
    point_id: int,
    sensor_id: Optional[str],
    depth_cm: float,
    source: str = "sensor",
    threshold_cm: float = 20.0
) -> dict:
    """Lưu số đo mới vào cơ chế lưu trữ bền vững thay vì gán trực tiếp vào DEFAULT_FLOOD_POINTS."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO fallback_readings (point_id, sensor_id, depth_cm, source, recorded_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (point_id, sensor_id, float(depth_cm), source, now_iso)
            )
            rec_id = cursor.lastrowid
            conn.commit()
    except Exception as e:
        log.warning("Lỗi ghi fallback_readings: %s", e)
        rec_id = int(datetime.now().timestamp() * 1000)

    return {
        "id": rec_id,
        "point_id": point_id,
        "depth_cm": float(depth_cm),
        "source": source,
        "recorded_at": now_iso,
        "exceeds_threshold": float(depth_cm) >= float(threshold_cm)
    }


def get_fallback_readings(point_id: Optional[int] = None, limit: int = 50) -> List[dict]:
    """Truy vấn lịch sử số đo từ bộ nhớ lưu trữ bền vững."""
    try:
        with _get_connection() as conn:
            if point_id is not None:
                rows = conn.execute(
                    """SELECT id, point_id, depth_cm, source, recorded_at
                       FROM fallback_readings
                       WHERE point_id = ?
                       ORDER BY id DESC LIMIT ?""",
                    (point_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, point_id, depth_cm, source, recorded_at
                       FROM fallback_readings
                       ORDER BY id DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "point_id": r["point_id"],
                    "depth_cm": float(r["depth_cm"]),
                    "source": r["source"],
                    "recorded_at": r["recorded_at"]
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("Lỗi đọc fallback_readings: %s", e)
        return []


def get_latest_readings_map() -> Dict[int, dict]:
    """
    Trả về dictionary {point_id: {"depth_cm": float, "recorded_at": str, "source": str}}
    chứa số đo quan trắc mới nhất của từng trạm đo.
    """
    try:
        with _get_connection() as conn:
            rows = conn.execute("""
                SELECT point_id, depth_cm, source, recorded_at
                FROM fallback_readings
                WHERE id IN (
                    SELECT MAX(id) FROM fallback_readings GROUP BY point_id
                )
            """).fetchall()
            return {
                r["point_id"]: {
                    "depth_cm": float(r["depth_cm"]),
                    "source": r["source"],
                    "recorded_at": r["recorded_at"]
                }
                for r in rows
            }
    except Exception as e:
        log.warning("Lỗi đọc latest readings map: %s", e)
        return {}


def save_fallback_report(
    user_id: Optional[int],
    lng: float,
    lat: float,
    level: str,
    photo_url: Optional[str],
    client_event_id: Optional[str] = None,
    payload_hash: Optional[str] = None,
) -> dict:
    """Lưu báo cáo ngập từ người dân vào bộ nhớ bền vững (hỗ trợ idempotency qua client_event_id)."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=45)
    now_iso = now.isoformat()
    exp_iso = exp.isoformat()
    idempotent_replay = False
    with _FALLBACK_WRITE_LOCK:
        try:
            with _get_connection() as conn:
                if client_event_id:
                    existing = conn.execute(
                        "SELECT id, level, confirmed, expires_at, payload_hash FROM fallback_reports WHERE client_event_id = ?",
                        (client_event_id,)
                    ).fetchone()
                    if existing:
                        if existing["payload_hash"] and payload_hash and existing["payload_hash"] != payload_hash:
                            raise IdempotencyConflictError("Xung đột payload cho client_event_id báo cáo ngập.")
                        return {
                            "id": existing["id"],
                            "level": existing["level"],
                            "confirmed": bool(existing["confirmed"]),
                            "nearby_reports": 1,
                            "need_more": 0,
                            "expires_at": existing["expires_at"],
                            "client_event_id": client_event_id,
                            "idempotent_replay": True,
                        }
                cursor = conn.execute(
                    """INSERT INTO fallback_reports (user_id, lng, lat, level, photo_url, confirmed, created_at, expires_at, client_event_id, payload_hash)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                    (user_id, lng, lat, level, photo_url, now_iso, exp_iso, client_event_id, payload_hash)
                )
                rep_id = cursor.lastrowid
                conn.commit()
        except IdempotencyConflictError:
            raise
        except sqlite3.IntegrityError:
            with _get_connection() as conn:
                existing = conn.execute(
                    "SELECT id, level, confirmed, expires_at, payload_hash FROM fallback_reports WHERE client_event_id = ?",
                    (client_event_id,)
                ).fetchone()
                if existing:
                    if existing["payload_hash"] and payload_hash and existing["payload_hash"] != payload_hash:
                        raise IdempotencyConflictError("Xung đột payload cho client_event_id báo cáo ngập.")
                    return {
                        "id": existing["id"],
                        "level": existing["level"],
                        "confirmed": bool(existing["confirmed"]),
                        "nearby_reports": 1,
                        "need_more": 0,
                        "expires_at": existing["expires_at"],
                        "client_event_id": client_event_id,
                        "idempotent_replay": True,
                    }
            rep_id = int(datetime.now().timestamp() * 1000)
        except Exception as e:
            log.warning("Lỗi ghi fallback_reports: %s", e)
            rep_id = int(datetime.now().timestamp() * 1000)

    return {
        "id": rep_id,
        "level": level,
        "confirmed": True,
        "nearby_reports": 1,
        "need_more": 0,
        "expires_at": exp_iso,
        "client_event_id": client_event_id,
        "idempotent_replay": idempotent_replay,
    }


def get_fallback_reports(only_confirmed: bool = False) -> List[dict]:
    """Lấy danh sách các báo cáo ngập còn hiệu lực từ bộ nhớ bền vững."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            sql = "SELECT id, level, confirmed, created_at, expires_at, lng, lat FROM fallback_reports WHERE expires_at > ?"
            params = [now_iso]
            if only_confirmed:
                sql += " AND confirmed = 1"
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "level": r["level"],
                    "confirmed": bool(r["confirmed"]),
                    "created_at": r["created_at"],
                    "expires_at": r["expires_at"],
                    "lng": float(r["lng"]),
                    "lat": float(r["lat"])
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("Lỗi đọc fallback_reports: %s", e)
        return []


def clear_fallback_reports() -> int:
    """Xóa tất cả các báo cáo ngập tạm thời."""
    try:
        with _get_connection() as conn:
            res = conn.execute("DELETE FROM fallback_reports")
            conn.commit()
            return res.rowcount
    except Exception as e:
        log.warning("Lỗi clear fallback_reports: %s", e)
        return 0


def delete_fallback_report(report_id: int) -> bool:
    """Xóa một báo cáo ngập theo id."""
    try:
        with _get_connection() as conn:
            res = conn.execute("DELETE FROM fallback_reports WHERE id = ?", (report_id,))
            conn.commit()
            return res.rowcount > 0
    except Exception as e:
        log.warning("Lỗi delete fallback_report: %s", e)
        return False


# ==========================================
# DISASTERS FALLBACK STORAGE
# ==========================================

def get_fallback_disasters(hazard_type: Optional[str] = None, active_only: bool = True) -> List[dict]:
    try:
        with _get_connection() as conn:
            sql = "SELECT id, title, hazard_type, severity, status, description, lng, lat, radius_m, start_time, end_time, created_at FROM fallback_disasters"
            clauses = []
            params = []
            if active_only:
                clauses.append("status IN ('warning', 'active')")
            if hazard_type and hazard_type != "all":
                clauses.append("hazard_type = ?")
                params.append(hazard_type)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.warning("Lỗi get_fallback_disasters: %s", e)
        return []


def save_fallback_disaster(data: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO fallback_disasters (title, hazard_type, severity, status, description, lng, lat, radius_m, start_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["title"], data.get("hazard_type", "flood"), data.get("severity", "medium"),
                data.get("status", "active"), data.get("description"), float(data["lng"]),
                float(data["lat"]), float(data.get("radius_m", 150.0)),
                data.get("start_time") or now_iso, now_iso
            ))
            conn.commit()
            new_id = cursor.lastrowid
            res = dict(data)
            res["id"] = new_id
            res["created_at"] = now_iso
            return res
    except Exception as e:
        log.warning("Lỗi save_fallback_disaster: %s", e)
        res = dict(data)
        res["id"] = int(datetime.now().timestamp() * 1000)
        return res


# ==========================================
# SHELTERS FALLBACK STORAGE
# ==========================================

def get_fallback_shelters(status: Optional[str] = None) -> List[dict]:
    try:
        with _get_connection() as conn:
            sql = "SELECT id, name, address, lng, lat, capacity, current_occupancy, contact_phone, supplies_status, status, created_at FROM fallback_shelters"
            params = []
            if status:
                sql += " WHERE status = ?"
                params.append(status)
            sql += " ORDER BY id ASC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.warning("Lỗi get_fallback_shelters: %s", e)
        return []


def save_fallback_shelter(data: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO fallback_shelters (name, address, lng, lat, capacity, current_occupancy, contact_phone, supplies_status, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["name"], data.get("address"), float(data["lng"]), float(data["lat"]),
                int(data.get("capacity", 200)), int(data.get("current_occupancy", 0)),
                data.get("contact_phone"), data.get("supplies_status", "Sẵn sàng"),
                data.get("status", "open"), now_iso
            ))
            conn.commit()
            res = dict(data)
            res["id"] = cursor.lastrowid
            res["created_at"] = now_iso
            return res
    except Exception as e:
        log.warning("Lỗi save_fallback_shelter: %s", e)
        res = dict(data)
        res["id"] = int(datetime.now().timestamp() * 1000)
        return res


# ==========================================
# COMMUNITY SOS FALLBACK STORAGE
# ==========================================

def get_fallback_sos(status: Optional[str] = None) -> List[dict]:
    try:
        with _get_connection() as conn:
            sql = """
                SELECT id, contact_name, phone, lng, lat,
                       location_source, location_accuracy_m, location_captured_at,
                       location_confirmed, location_description, location_landmark,
                       people_count, has_elderly_or_children, water_level_cm,
                       priority, status, notes, created_at, updated_at
                FROM fallback_sos
            """
            params = []
            if status:
                sql += " WHERE status = ?"
                params.append(status)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    **dict(r),
                    "has_elderly_or_children": bool(r["has_elderly_or_children"]),
                    "location_confirmed": bool(r["location_confirmed"]),
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("Lỗi get_fallback_sos: %s", e)
        return []


def save_fallback_sos(data: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    lng_val = float(data["lng"]) if data.get("lng") is not None else None
    lat_val = float(data["lat"]) if data.get("lat") is not None else None
    acc_val = float(data["location_accuracy_m"]) if data.get("location_accuracy_m") is not None else None
    client_event_id = data.get("client_event_id")
    payload_hash = data.get("payload_hash")

    with _FALLBACK_WRITE_LOCK:
        try:
            with _get_connection() as conn:
                if client_event_id:
                    existing = conn.execute(
                        "SELECT * FROM fallback_sos WHERE client_event_id = ?",
                        (client_event_id,)
                    ).fetchone()
                    if existing:
                        if existing["payload_hash"] and payload_hash and existing["payload_hash"] != payload_hash:
                            raise IdempotencyConflictError("Xung đột payload cho client_event_id SOS.")
                        d = dict(existing)
                        d["has_elderly_or_children"] = bool(d["has_elderly_or_children"])
                        d["location_confirmed"] = bool(d["location_confirmed"])
                        d["idempotent_replay"] = True
                        return d

                cursor = conn.execute("""
                    INSERT INTO fallback_sos (
                        contact_name, phone, lng, lat,
                        location_source, location_accuracy_m, location_captured_at,
                        location_confirmed, location_description, location_landmark,
                        people_count, has_elderly_or_children, water_level_cm,
                        priority, status, notes, created_at, updated_at,
                        client_event_id, payload_hash,
                        tracking_token_hash, tracking_token_expires_at, tracking_token_revoked
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["contact_name"], data["phone"], lng_val, lat_val,
                    data.get("location_source", "manual"), acc_val, data.get("location_captured_at"),
                    1 if data.get("location_confirmed") else 0,
                    data.get("location_description"), data.get("location_landmark"),
                    int(data.get("people_count", 1)), 1 if data.get("has_elderly_or_children") else 0,
                    float(data.get("water_level_cm", 0.0)), data.get("priority", "high"),
                    data.get("status", "pending"), data.get("notes"), now_iso, now_iso,
                    client_event_id, payload_hash,
                    data.get("tracking_token_hash"), data.get("tracking_token_expires_at"),
                    1 if data.get("tracking_token_revoked") else 0
                ))
                conn.commit()
                res = dict(data)
                res["id"] = cursor.lastrowid
                res["lng"] = lng_val
                res["lat"] = lat_val
                res["status"] = data.get("status", "pending")
                res["created_at"] = now_iso
                res["updated_at"] = now_iso
                res["idempotent_replay"] = False
                return res
        except IdempotencyConflictError:
            raise
        except sqlite3.IntegrityError:
            with _get_connection() as conn:
                existing = conn.execute(
                    "SELECT * FROM fallback_sos WHERE client_event_id = ?",
                    (client_event_id,)
                ).fetchone()
                if existing:
                    if existing["payload_hash"] and payload_hash and existing["payload_hash"] != payload_hash:
                        raise IdempotencyConflictError("Xung đột payload cho client_event_id SOS.")
                    d = dict(existing)
                    d["has_elderly_or_children"] = bool(d["has_elderly_or_children"])
                    d["location_confirmed"] = bool(d["location_confirmed"])
                    d["idempotent_replay"] = True
                    return d
        except Exception as e:
            log.warning("Lỗi save_fallback_sos: %s", e)
            res = dict(data)
            res["id"] = None
            res["status"] = data.get("status", "pending")
            return res


def get_fallback_sos_by_token_hash(token_hash: str) -> Optional[dict]:
    if not token_hash:
        return None
    try:
        init_fallback_db()
        with _get_connection() as conn:
            row = conn.execute(
                """SELECT id, status, created_at, updated_at,
                          tracking_token_expires_at, tracking_token_revoked
                   FROM fallback_sos WHERE tracking_token_hash = ?""",
                (token_hash,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        log.warning("Lỗi get_fallback_sos_by_token_hash: %s", e)
        return None


def revoke_fallback_sos_token(token_hash: str) -> bool:
    if not token_hash:
        return False
    try:
        init_fallback_db()
        with _FALLBACK_WRITE_LOCK:
            with _get_connection() as conn:
                cur = conn.execute(
                    "UPDATE fallback_sos SET tracking_token_revoked = 1 WHERE tracking_token_hash = ?",
                    (token_hash,),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        log.warning("Lỗi revoke_fallback_sos_token: %s", e)
        return False


def update_fallback_sos_status(sos_id: int, new_status: str) -> Optional[dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            conn.execute("UPDATE fallback_sos SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_iso, sos_id))
            conn.commit()
            row = conn.execute("SELECT * FROM fallback_sos WHERE id = ?", (sos_id,)).fetchone()
            if row:
                d = dict(row)
                d["has_elderly_or_children"] = bool(d["has_elderly_or_children"])
                return d
    except Exception as e:
        log.warning("Lỗi update_fallback_sos_status: %s", e)
    return None

