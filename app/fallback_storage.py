"""
Cơ chế lưu trữ bền vững dự phòng (Persistent Fallback Storage) khi PostgreSQL không hoạt động.
Sử dụng SQLite với cơ chế khoá file và WAL để đảm bảo:
- Đồng bộ dữ liệu quan trắc giữa nhiều tiến trình (workers) và các phiên Serverless
- Dữ liệu số đo (readings) và báo cáo (reports) được lưu bền vững vào đĩa thay vì chỉ lưu tạm trên RAM
- Tách biệt hoàn toàn số đo quan trắc khỏi danh mục trạm ngập mặc định (DEFAULT_FLOOD_POINTS)
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import tempfile

log = logging.getLogger("floodnav.fallback_storage")

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
                    lng REAL NOT NULL,
                    lat REAL NOT NULL,
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

            # Seed default disasters if empty
            count = conn.execute("SELECT COUNT(*) FROM fallback_disasters").fetchone()[0]
            if count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany("""
                    INSERT INTO fallback_disasters (title, hazard_type, severity, status, description, lng, lat, radius_m, start_time, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ("Cảnh báo Lũ báo động 2 sông Tích - sông Đáy", "flood", "high", "active", "Mực nước lũ dâng cao gây ngập tràn đê bối tại Quốc Oai và Thạch Thất.", 105.6100, 20.9800, 1200.0, now_iso, now_iso),
                    ("Nguy cơ sạt trượt đất bờ đê Tả Bùi", "landslide", "critical", "active", "Đoạn đê qua Nam Phương Tiến có hiện tượng sạt trượt đất, cấm phương tiện trọng tải lớn.", 105.6580, 20.8920, 500.0, now_iso, now_iso),
                    ("Cây đổ chắn ngang đường do bão (Đại lộ Thăng Long)", "storm", "high", "active", "Cây cổ thụ bật gốc tại hầm chui số 3 An Khánh, lực lượng chức năng đang giải tỏa.", 105.7480, 21.0010, 300.0, now_iso, now_iso),
                    ("Điểm đen ngập sâu đô thị Cầu Giấy (Hoa Bằng)", "flood", "medium", "active", "Mực nước dâng 27cm sau cơn mưa lớn, hạn chế xe máy qua lại.", 105.7950, 21.0220, 250.0, now_iso, now_iso),
                    ("Cảnh báo ngập hầm chui & ngã ba Giải Phóng - Pháp Vân", "flood", "high", "active", "Khu vực trũng cửa ngõ phía Nam ngập 28cm.", 105.8465, 20.9625, 350.0, now_iso, now_iso)
                ])

            # Seed default shelters if empty
            s_count = conn.execute("SELECT COUNT(*) FROM fallback_shelters").fetchone()[0]
            if s_count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany("""
                    INSERT INTO fallback_shelters (name, address, lng, lat, capacity, current_occupancy, contact_phone, supplies_status, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ("Trường THPT Yên Hòa (Điểm sơ tán Cầu Giấy)", "Ngõ 251 Nguyễn Khang, Yên Hòa, Cầu Giấy", 105.7940, 21.0210, 600, 45, "024-3833-1122", "Đầy đủ nước sạch, lương thực và chăn ấm", "open", now_iso),
                    ("Nhà thi đấu quận Hoàng Mai (Trạm cứu trợ Đền Lừ)", "Đường Tam Trinh, Hoàng Mai, Hà Nội", 105.8610, 20.9850, 1200, 110, "024-3864-4455", "Sẵn sàng trạm y tế dã chiến và ca nô cứu nạn", "open", now_iso),
                    ("Trường Tiểu học Nam Phương Tiến A (Điểm tránh lũ Chương Mỹ)", "Xã Nam Phương Tiến, Chương Mỹ, Hà Nội", 105.6620, 20.8960, 500, 160, "024-3386-7788", "Đã tiếp nhận lương khô, áo phao và thuốc men", "open", now_iso),
                    ("Cung Thiếu nhi Hà Nội mới (Điểm tập kết Nam Từ Liêm)", "Đường Phạm Hùng, Mỹ Đình, Nam Từ Liêm", 105.7820, 21.0180, 1500, 80, "024-3936-2244", "Sẵn sàng hội trường lớn và điện máy phát", "open", now_iso),
                    ("Trụ sở UBND xã Cấn Hữu (Điểm an toàn Quốc Oai)", "Xã Cấn Hữu, Quốc Oai, Hà Nội", 105.6150, 20.9450, 400, 75, "024-3384-3311", "Túc trực cứu hộ 24/7", "open", now_iso),
                    ("Trung tâm Huấn luyện & Sơ tán Thanh Trì", "Đường 70, Tả Thanh Oai, Thanh Trì", 105.8450, 20.9420, 800, 95, "024-3861-5566", "Sẵn sàng lương thực 7 ngày cho 500 người", "open", now_iso)
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
    photo_url: Optional[str]
) -> dict:
    """Lưu báo cáo ngập từ người dân vào bộ nhớ bền vững."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=45)
    now_iso = now.isoformat()
    exp_iso = exp.isoformat()
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO fallback_reports (user_id, lng, lat, level, photo_url, confirmed, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (user_id, lng, lat, level, photo_url, now_iso, exp_iso)
            )
            rep_id = cursor.lastrowid
            conn.commit()
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
            sql = "SELECT id, contact_name, phone, lng, lat, people_count, has_elderly_or_children, water_level_cm, priority, status, notes, created_at, updated_at FROM fallback_sos"
            params = []
            if status:
                sql += " WHERE status = ?"
                params.append(status)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    **dict(r),
                    "has_elderly_or_children": bool(r["has_elderly_or_children"])
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("Lỗi get_fallback_sos: %s", e)
        return []


def save_fallback_sos(data: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO fallback_sos (contact_name, phone, lng, lat, people_count, has_elderly_or_children, water_level_cm, priority, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["contact_name"], data["phone"], float(data["lng"]), float(data["lat"]),
                int(data.get("people_count", 1)), 1 if data.get("has_elderly_or_children") else 0,
                float(data.get("water_level_cm", 0.0)), data.get("priority", "high"),
                data.get("status", "pending"), data.get("notes"), now_iso, now_iso
            ))
            conn.commit()
            res = dict(data)
            res["id"] = cursor.lastrowid
            res["status"] = data.get("status", "pending")
            res["created_at"] = now_iso
            res["updated_at"] = now_iso
            return res
    except Exception as e:
        log.warning("Lỗi save_fallback_sos: %s", e)
        res = dict(data)
        res["id"] = int(datetime.now().timestamp() * 1000)
        res["status"] = data.get("status", "pending")
        return res


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

