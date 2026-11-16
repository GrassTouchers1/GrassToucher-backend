"""
Router Quản lý Giám sát Đa thiên tai (Disaster Monitoring).
Hỗ trợ các loại hình thiên tai: lũ lụt (flood), sạt lở (landslide), bão/cây đổ (storm), mưa lớn (heavy_rain).
"""
import logging
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query, Response

from ..db import get_db_connection
from ..schemas import DisasterCreate
from ..fallback_storage import get_fallback_disasters, save_fallback_disaster

log = logging.getLogger("northstar.disasters")
router = APIRouter(prefix="/api/disasters", tags=["Giám sát Đa thiên tai"])


def _to_feature(r: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(r["lng"]), float(r["lat"])]
        },
        "properties": {
            "id": r["id"],
            "title": r["title"],
            "hazard_type": r["hazard_type"],
            "severity": r["severity"],
            "status": r["status"],
            "description": r.get("description"),
            "radius_m": float(r.get("radius_m") or 150.0),
            "start_time": str(r.get("start_time")),
            "end_time": str(r.get("end_time")) if r.get("end_time") else None,
            "created_at": str(r.get("created_at")),
        }
    }


@router.get("")
def list_disasters(
    hazard_type: Optional[str] = Query(None, description="Lọc theo loại thiên tai: flood, landslide, storm, all"),
    active_only: bool = Query(True, description="Chỉ lấy các sự kiện thiên tai đang cảnh báo hoặc hoạt động")
):
    """Lấy danh sách các sự kiện thiên tai theo định dạng GeoJSON FeatureCollection."""
    if not isinstance(hazard_type, str):
        hazard_type = None
    if not isinstance(active_only, bool):
        active_only = True
    try:
        with get_db_connection() as conn:
            sql = """
                SELECT id, title, hazard_type, severity, status, description,
                       ST_X(geom) AS lng, ST_Y(geom) AS lat, radius_m,
                       start_time, end_time, created_at
                FROM disaster_events
            """
            clauses = []
            params = []
            if active_only:
                clauses.append("status IN ('warning', 'active')")
            if hazard_type and hazard_type != "all":
                clauses.append("hazard_type = %s")
                params.append(hazard_type)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY id DESC"

            rows = conn.execute(sql, tuple(params)).fetchall()
            return {
                "type": "FeatureCollection",
                "hazard_type": hazard_type or "all",
                "features": [_to_feature(r) for r in rows]
            }
    except Exception as e:
        log.warning("DB query failed in list_disasters, using fallback storage: %s", e)
        fb_rows = get_fallback_disasters(hazard_type=hazard_type, active_only=active_only)
        return {
            "type": "FeatureCollection",
            "hazard_type": hazard_type or "all",
            "features": [_to_feature(r) for r in fb_rows]
        }


@router.post("", status_code=201)
def create_disaster(body: DisasterCreate):
    """Khai báo sự kiện hoặc vùng cảnh báo thiên tai mới."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                INSERT INTO disaster_events (title, hazard_type, severity, status, description, geom, radius_m)
                VALUES (%s, %s::disaster_type, %s::disaster_severity, %s::disaster_status, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                RETURNING id, title, hazard_type, severity, status, description,
                          ST_X(geom) AS lng, ST_Y(geom) AS lat, radius_m,
                          start_time, end_time, created_at
            """, (
                body.title, body.hazard_type, body.severity, body.status, body.description,
                body.lng, body.lat, body.radius_m
            )).fetchone()
            return _to_feature(row)
    except Exception as e:
        log.warning("DB query failed in create_disaster, using persistent fallback: %s", e)
        saved = save_fallback_disaster(body.model_dump())
        return _to_feature(saved)


@router.get("/{disaster_id}")
def get_disaster(disaster_id: int):
    """Chi tiết sự kiện thiên tai theo ID."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                SELECT id, title, hazard_type, severity, status, description,
                       ST_X(geom) AS lng, ST_Y(geom) AS lat, radius_m,
                       start_time, end_time, created_at
                FROM disaster_events WHERE id = %s
            """, (disaster_id,)).fetchone()
            if row:
                return _to_feature(row)
    except Exception as e:
        log.warning("DB query failed in get_disaster: %s", e)

    fb_rows = get_fallback_disasters(active_only=False)
    for r in fb_rows:
        if r["id"] == disaster_id:
            return _to_feature(r)

    raise HTTPException(404, f"Không tìm thấy sự kiện thiên tai id={disaster_id}")
