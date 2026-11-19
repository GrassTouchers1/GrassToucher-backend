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
GrassToucher Backend - Graph Bridge & Flood Source Extractor.
Tái sử dụng RoadGraph và get_graph từ grasstoucher_core.
Chịu trách nhiệm truy vấn điểm ngập từ PostGIS và Fallback SQLite.
"""
import logging
import numpy as np

from grasstoucher_core.graph import RoadGraph, get_graph, GraphNotReady
from grasstoucher_core.ai.prediction_engine import get_prediction_engine
from . import config
from .db import get_db_connection

log = logging.getLogger("floodnav.graph")

# ---------------------------------------------------------------- nguồn ngập từ DB
POINTS_SQL = """
    SELECT fp.id, fp.name, fp.threshold_cm, ST_X(fp.geom) AS lng, ST_Y(fp.geom) AS lat, r.depth_cm
    FROM flood_points fp
    JOIN LATERAL (
        SELECT depth_cm FROM water_readings
        WHERE point_id = fp.id ORDER BY recorded_at DESC LIMIT 1
    ) r ON TRUE
"""

REPORTS_SQL = """
    SELECT id, level, ST_X(geom) AS lng, ST_Y(geom) AS lat
    FROM reports WHERE confirmed AND expires_at > now()
"""


def fetch_flood_sources(use_ai_prediction: bool = False) -> list:
    """
    Mực nước hiện tại: số đo mới nhất của mỗi điểm ngập + báo cáo đã xác nhận còn hiệu lực.
    Nếu use_ai_prediction=True, kết hợp mô hình AI Scikit-learn dự báo 30 phút để chặn đường sớm.
    Sử dụng get_db_connection an toàn (Circuit Breaker tránh chờ timeout 3s khi offline).
    """
    points, reports = [], []
    try:
        with get_db_connection(timeout=0.3) as conn:
            points = conn.execute(POINTS_SQL).fetchall()
            reports = conn.execute(REPORTS_SQL).fetchall()
    except Exception as e:
        log.warning("DB query failed in fetch_flood_sources, using fallback: %s", e)
        from .routers.flood_points import get_fallback_flood_points
        from .fallback_storage import get_fallback_reports
        points = get_fallback_flood_points()
        reports = get_fallback_reports(only_confirmed=True)

    ai_engine = None
    rain_1h, rain_3h = 0.0, 0.0
    if use_ai_prediction:
        try:
            from grasstoucher_core.weather import get_rainfall_summary
            ai_engine = get_prediction_engine()
            rain_1h, rain_3h = get_rainfall_summary()
        except Exception:
            ai_engine = None

    sources = []
    for p in points:
        if p.get("depth_cm") is None:
            continue
        d = float(p["depth_cm"])
        predicted_d = d
        if ai_engine is not None and d >= 5.0:
            try:
                res = ai_engine.predict(
                    current_depth_cm=d,
                    point_name=p.get("name", ""),
                    threshold_cm=float(p.get("threshold_cm", 20.0)),
                    rain_1h=rain_1h,
                    rain_3h=rain_3h,
                )
                predicted_d = max(d, float(res["forecast_30m"]["predicted_depth_cm"]))
            except Exception:
                predicted_d = d

        sources.append({
            "lng": p["lng"], "lat": p["lat"], "depth_cm": round(predicted_d, 1),
            "threshold_cm": p["threshold_cm"],
            "name": p["name"] + (" (Dự báo AI +30p)" if predicted_d > d else ""),
            "kind": "point", "source_id": p["id"]
        })

    sources += [
        {"lng": r["lng"], "lat": r["lat"], "depth_cm": float(config.LEVEL_DEPTH_CM[r["level"]]),
         "threshold_cm": 20, "name": "Báo cáo của người dân", "kind": "report", "source_id": r["id"]}
        for r in reports
    ]
    return sources


__all__ = ["RoadGraph", "get_graph", "GraphNotReady", "fetch_flood_sources"]
