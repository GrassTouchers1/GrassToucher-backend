# Copyright 2026 GrassTouchers Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import time
from contextlib import contextmanager
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
        with pool.connection(timeout=0.3) as conn:
            conn.execute("SELECT 1")
            _db_online_status = True
            _last_check_time = now
            return True
    except Exception:
        _db_online_status = False
        _last_check_time = now
        return False


@contextmanager
def get_db_connection(timeout: float = 0.5):
    """
    Context manager an toàn: kiểm tra circuit breaker trước khi lấy kết nối.
    Nếu DB offline, ném ConnectionError ngay lập tức (0.01ms) để kích hoạt fallback,
    không gây nghẽn 3 giây cho người dùng.
    """
    if not is_db_available():
        raise ConnectionError("PostgreSQL database is currently offline (Circuit breaker active).")
    with pool.connection(timeout=timeout) as conn:
        yield conn
