"""
GrassToucher Backend - Cấu hình hệ thống.
Kế thừa trực tiếp từ grasstoucher_core.config để tránh trùng lặp dữ liệu (DRY).
"""
from pathlib import Path
import grasstoucher_core.config as core_config

ROOT = Path(__file__).resolve().parents[1]

# Kế thừa đường dẫn đồ thị và các tham số chuẩn từ Core
GRAPH_PATH = core_config.GRAPH_PATH
METRIC_CRS = core_config.METRIC_CRS
FLOOD_RADIUS_M = core_config.FLOOD_RADIUS_M
PENALTY_START_CM = core_config.PENALTY_START_CM
PENALTY_ALPHA = core_config.PENALTY_ALPHA
CAR_LIMIT_FACTOR = core_config.CAR_LIMIT_FACTOR
LEVEL_DEPTH_CM = core_config.LEVEL_DEPTH_CM
SPEED_KMH = core_config.SPEED_KMH
MAX_SNAP_M = core_config.MAX_SNAP_M

# Tham số nghiệp vụ cảm biến Backend
SENSOR_STALE_HOURS = 24
