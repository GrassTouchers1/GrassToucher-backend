import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger("floodnav.db")

# Đọc file .env nằm ở thư mục gốc backend
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:floodnav_2026@localhost:5432/floodnav"
)

# Cấu hình pool tối ưu cho Serverless & Local: min_size=0, timeout=1.0s
pool = ConnectionPool(
    DATABASE_URL,
    min_size=0,
    max_size=5,
    timeout=1.0,
    kwargs={"row_factory": dict_row},
    open=True,
)

_last_check_time = 0.0
_db_online_status = None


def is_db_available() -> bool:
    """Kiểm tra nhanh kết nối DB với cơ chế Circuit Breaker (tránh chờ timeout 3s mỗi request khi offline)."""
    global _last_check_time, _db_online_status
    now = time.time()
    # Nếu DB vừa kiểm tra là offline, ghi nhớ trạng thái trong 15 giây
    if _db_online_status is False and (now - _last_check_time) < 15.0:
        return False

    try:
        with pool.connection(timeout=0.4) as conn:
            conn.execute("SELECT 1")
            _db_online_status = True
            _last_check_time = now
            return True
    except Exception:
        _db_online_status = False
        _last_check_time = now
        return False
