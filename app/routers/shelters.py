"""
Router Quản lý Điểm Sơ tán & Cứu trợ An toàn (Rescue & Shelter Management).
Hỗ trợ tìm điểm sơ tán gần nhất, kiểm tra sức chứa (capacity) và tình trạng tiếp nhận.
"""
import math
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..db import get_db_connection
from ..schemas import ShelterCreate
from ..fallback_storage import get_fallback_shelters, save_fallback_shelter

log = logging.getLogger("northstar.shelters")
router = APIRouter(prefix="/api/shelters", tags=["Điểm sơ tán & Cứu trợ"])


def _to_feature(r: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(r["lng"]), float(r["lat"])]
        },
        "properties": {
            "id": r["id"],
            "name": r["name"],
            "address": r.get("address"),
            "capacity": int(r.get("capacity") or 200),
            "current_occupancy": int(r.get("current_occupancy") or 0),
            "available_slots": max(0, int(r.get("capacity") or 200) - int(r.get("current_occupancy") or 0)),
            "contact_phone": r.get("contact_phone"),
            "supplies_status": r.get("supplies_status") or "Sẵn sàng",
            "status": r.get("status") or "open",
            "created_at": str(r.get("created_at")),
        }
    }


@router.get("")
def list_shelters(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: open, full, closed")
):
    """Lấy danh sách các điểm sơ tán và trạm cứu trợ theo chuẩn GeoJSON FeatureCollection."""
    if not isinstance(status, str):
        status = None
    try:
        with get_db_connection() as conn:
            sql = """
                SELECT id, name, address, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                       capacity, current_occupancy, contact_phone, supplies_status, status, created_at
                FROM evacuation_shelters
            """
            params = []
            if status:
                sql += " WHERE status = %s::shelter_status"
                params.append(status)
            sql += " ORDER BY id ASC"

            rows = conn.execute(sql, tuple(params)).fetchall()
            return {
                "type": "FeatureCollection",
                "features": [_to_feature(r) for r in rows]
            }
    except Exception as e:
        log.warning("DB query failed in list_shelters, using fallback storage: %s", e)
        fb_rows = get_fallback_shelters(status=status)
        return {
            "type": "FeatureCollection",
            "features": [_to_feature(r) for r in fb_rows]
        }


@router.post("", status_code=201)
def create_shelter(body: ShelterCreate):
    """Khai báo điểm sơ tán hoặc trạm cứu trợ mới."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                INSERT INTO evacuation_shelters (name, address, geom, capacity, current_occupancy, contact_phone, supplies_status, status)
                VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s::shelter_status)
                RETURNING id, name, address, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                          capacity, current_occupancy, contact_phone, supplies_status, status, created_at
            """, (
                body.name, body.address, body.lng, body.lat, body.capacity,
                body.current_occupancy, body.contact_phone, body.supplies_status, body.status
            )).fetchone()
            return _to_feature(row)
    except Exception as e:
        log.warning("DB query failed in create_shelter, using persistent fallback: %s", e)
        saved = save_fallback_shelter(body.model_dump())
        return _to_feature(saved)


@router.get("/nearest")
def get_nearest_shelter(
    lng: float = Query(..., ge=-180, le=180, description="Kinh độ hiện tại"),
    lat: float = Query(..., ge=-90, le=90, description="Vĩ độ hiện tại"),
):
    """Tìm điểm sơ tán mở cửa còn chỗ tiếp nhận gần nhất với toạ độ người dùng."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                SELECT id, name, address, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                       capacity, current_occupancy, contact_phone, supplies_status, status, created_at,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS dist_m
                FROM evacuation_shelters
                WHERE status = 'open' AND current_occupancy < capacity
                ORDER BY dist_m ASC
                LIMIT 1
            """, (lng, lat)).fetchone()
            if row:
                feat = _to_feature(row)
                feat["properties"]["distance_m"] = round(float(row["dist_m"]), 1)
                return feat
    except Exception as e:
        log.warning("DB query failed in get_nearest_shelter, calculating via fallback: %s", e)

    shelters = get_fallback_shelters(status="open")
    valid_shelters = [s for s in shelters if s.get("capacity", 200) > s.get("current_occupancy", 0)]
    if not valid_shelters:
        raise HTTPException(404, "Không có điểm sơ tán khả dụng nào còn chỗ tiếp nhận.")

    def calc_dist(s):
        # Tính khoảng cách Euclidean xấp xỉ mét
        dx = (s["lng"] - lng) * 103000
        dy = (s["lat"] - lat) * 111000
        return math.hypot(dx, dy)

    best = min(valid_shelters, key=calc_dist)
    feat = _to_feature(best)
    feat["properties"]["distance_m"] = round(calc_dist(best), 1)
    return feat


@router.get("/{shelter_id}")
def get_shelter(shelter_id: int):
    """Chi tiết điểm sơ tán theo ID."""
    shelters = get_fallback_shelters()
    for s in shelters:
        if s["id"] == shelter_id:
            return _to_feature(s)
    raise HTTPException(404, f"Không tìm thấy điểm sơ tán id={shelter_id}")
