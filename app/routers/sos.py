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
Router Phát Tín Hiệu Cứu Hộ Khẩn Cấp (1-Click Community SOS).
Cho phép người dân gửi vị trí ngập sâu bị cô lập, số người cần cứu hộ và ưu tiên trợ giúp.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..db import get_db_connection
from ..schemas import SOSCreate, SOSStatusUpdate
from ..fallback_storage import get_fallback_sos, save_fallback_sos, update_fallback_sos_status

log = logging.getLogger("northstar.sos")
router = APIRouter(prefix="/api/sos", tags=["Cứu hộ khẩn cấp SOS"])


def _to_feature(r: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(r["lng"]), float(r["lat"])]
        },
        "properties": {
            "id": r["id"],
            "contact_name": r["contact_name"],
            "phone": r["phone"],
            "people_count": int(r["people_count"]),
            "has_elderly_or_children": bool(r["has_elderly_or_children"]),
            "water_level_cm": float(r.get("water_level_cm") or 0.0),
            "priority": r["priority"],
            "status": r["status"],
            "notes": r.get("notes"),
            "created_at": str(r.get("created_at")),
            "updated_at": str(r.get("updated_at")),
        }
    }


@router.get("")
def list_sos_beacons(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: pending, acknowledged, dispatched, rescued")
):
    """Danh sách các tín hiệu SOS kêu cứu từ người dân."""
    if not isinstance(status, str):
        status = None
    try:
        with get_db_connection() as conn:
            sql = """
                SELECT id, contact_name, phone, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                       people_count, has_elderly_or_children, water_level_cm,
                       priority, status, notes, created_at, updated_at
                FROM community_sos
            """
            params = []
            if status:
                sql += " WHERE status = %s::sos_status"
                params.append(status)
            sql += " ORDER BY id DESC"

            rows = conn.execute(sql, tuple(params)).fetchall()
            return {
                "type": "FeatureCollection",
                "features": [_to_feature(r) for r in rows]
            }
    except Exception as e:
        log.warning("DB query failed in list_sos_beacons, using fallback: %s", e)
        fb_rows = get_fallback_sos(status=status)
        return {
            "type": "FeatureCollection",
            "features": [_to_feature(r) for r in fb_rows]
        }


@router.post("", status_code=201)
def create_sos_beacon(body: SOSCreate):
    """Gửi tín hiệu kêu cứu khẩn cấp SOS kèm toạ độ và số người mắc kẹt."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                INSERT INTO community_sos (contact_name, phone, geom, people_count, has_elderly_or_children, water_level_cm, priority, notes)
                VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s::sos_priority, %s)
                RETURNING id, contact_name, phone, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                          people_count, has_elderly_or_children, water_level_cm,
                          priority, status, notes, created_at, updated_at
            """, (
                body.contact_name, body.phone, body.lng, body.lat, body.people_count,
                body.has_elderly_or_children, body.water_level_cm, body.priority, body.notes
            )).fetchone()
            return _to_feature(row)
    except Exception as e:
        log.warning("DB query failed in create_sos_beacon, using fallback: %s", e)
        saved = save_fallback_sos(body.model_dump())
        return _to_feature(saved)


@router.patch("/{sos_id}/status")
def update_sos_status(sos_id: int, body: SOSStatusUpdate):
    """Cập nhật trạng thái xử lý cứu hộ (điều phối đội cứu hộ, xác nhận đã an toàn)."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                UPDATE community_sos
                SET status = %s::sos_status, updated_at = now()
                WHERE id = %s
                RETURNING id, contact_name, phone, ST_X(geom) AS lng, ST_Y(geom) AS lat,
                          people_count, has_elderly_or_children, water_level_cm,
                          priority, status, notes, created_at, updated_at
            """, (body.status, sos_id)).fetchone()
            if row:
                return _to_feature(row)
    except Exception as e:
        log.warning("DB query failed in update_sos_status, using fallback: %s", e)

    updated = update_fallback_sos_status(sos_id, body.status)
    if updated:
        return _to_feature(updated)

    raise HTTPException(404, f"Không tìm thấy yêu cầu cứu hộ SOS id={sos_id}")
