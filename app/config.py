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

"""
GrassToucher Backend - Cấu hình hệ thống.
Kế thừa trực tiếp từ grasstoucher_core.config để tránh trùng lặp dữ liệu (DRY).
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import grasstoucher_core.config as core_config

ROOT = Path(__file__).resolve().parents[1]

# Nạp file .env nếu có (không ghi đè biến môi trường hệ thống đã set)
load_dotenv(ROOT / ".env")

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

# Cấu hình AI Provider (Groq / Qwen / Local / Mock fallback)
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower().strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower().strip() in ("true", "1", "yes", "on")
AI_TIMEOUT_SEC = float(os.getenv("AI_TIMEOUT_SEC", "12.0"))

# Cấu hình Mô hình Qwen3-8B (HuggingFace: Qwen/Qwen3-8B)
# Tương thích chuẩn OpenAI API (vLLM, Ollama, LM Studio, TGI)
QWEN_API_BASE = os.getenv("QWEN_API_BASE", "http://localhost:8000/v1").rstrip("/")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "EMPTY").strip()
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-8B").strip()
QWEN_TIMEOUT_SEC = float(os.getenv("QWEN_TIMEOUT_SEC", "15.0"))


