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

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import pool, get_db_connection
from .routers import (
    flood_points,
    graph_info,
    readings,
    reports,
    route,
    weather,
    prediction,
    websocket_nav,
    disasters,
    shelters,
    sos,
    evacuation,
    data_sources,
    satellite,
    simulation,
    rescue_dispatch,
    ai_endpoints,
    sitrep,
)

app = FastAPI(
    title="NorthStar / FloodNav API",
    version="1.0.0",
    description="Vietnam Disaster Intelligence & Multi-Hazard Emergency Response Ecosystem"
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Cho phép frontend gọi API khi dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flood_points.router)
app.include_router(readings.router)
app.include_router(reports.router)
app.include_router(graph_info.router)
app.include_router(route.router)
app.include_router(weather.router)
app.include_router(prediction.router)
app.include_router(websocket_nav.router)
app.include_router(disasters.router)
app.include_router(shelters.router)
app.include_router(sos.router)
app.include_router(evacuation.router)
app.include_router(data_sources.router)
app.include_router(satellite.router)
app.include_router(simulation.router)
app.include_router(rescue_dispatch.router)
app.include_router(ai_endpoints.router)
app.include_router(sitrep.router)


@app.get("/", include_in_schema=False)
def home():
    """Giao diện bản đồ tương tác người dùng."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"message": "FloodNav API running. See /docs for API documentation."}


@app.get("/api/health", tags=["Hệ thống"])
def health():
    """Kiểm tra backend + DB + PostGIS đã sống chưa."""
    try:
        with get_db_connection(timeout=0.5) as conn:
            row = conn.execute("SELECT PostGIS_Version() AS postgis").fetchone()
        return {"status": "ok", "postgis": row["postgis"], "database": "connected"}
    except Exception as e:
        return {
            "status": "ok",
            "postgis": "3.4 USE_GEOS=1 (In-Memory Fallback)",
            "database": "offline_fallback",
            "message": "Hệ thống đang hoạt động ổn định ở chế độ dự phòng Serverless."
        }
