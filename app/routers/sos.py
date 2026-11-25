"""
Router Phát Tín Hiệu Cứu Hộ Khẩn Cấp (1-Click Community SOS).
Cho phép người dân gửi vị trí ngập sâu bị cô lập, số người cần cứu hộ và ưu tiên trợ giúp.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import secrets
import time
from typing import Dict, List, Optional
import psycopg
from fastapi import APIRouter, HTTPException, Query, Request

from ..db import get_db_connection
from ..schemas import SOSCreate, SOSStatusUpdate
from ..fallback_storage import (
    IdempotencyConflictError,
    get_fallback_sos,
    get_fallback_sos_by_token_hash,
    revoke_fallback_sos_token,
    save_fallback_sos,
    update_fallback_sos_status,
)

log = logging.getLogger("northstar.sos")
router = APIRouter(prefix="/api/sos", tags=["Cứu hộ khẩn cấp SOS"])

TRACKING_TOKEN_TTL_DAYS = 7
_TRACK_RATE_LIMIT_MAX = 20
_TRACK_RATE_LIMIT_WINDOW_S = 60.0
_TRACK_RATE_BUCKETS: Dict[str, List[float]] = {}

_CITIZEN_STATUS_MAP = {
    "pending": ("RECEIVED", "Đã tiếp nhận yêu cầu SOS, đang chờ cán bộ xác minh."),
    "acknowledged": ("VERIFIED", "Trung tâm Chỉ huy đã xác nhận hồ sơ, đang chuẩn bị điều phối."),
    "dispatched": ("DISPATCHED", "Đội cứu hộ đang trên đường tiếp cận vị trí của bạn."),
    "rescued": ("RESCUED", "Đã hoàn tất cứu hộ an toàn."),
    "cancelled": ("CANCELLED", "Hồ sơ SOS đã được hủy."),
}


def _hash_tracking_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _check_track_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    bucket = _TRACK_RATE_BUCKETS.setdefault(client_key, [])
    cutoff = now - _TRACK_RATE_LIMIT_WINDOW_S
    bucket[:] = [t for t in bucket if t > cutoff]
    if len(bucket) >= _TRACK_RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Vượt quá giới hạn tần suất tra cứu. Vui lòng thử lại sau.",
            headers={"Retry-After": str(int(_TRACK_RATE_LIMIT_WINDOW_S))},
        )
    bucket.append(now)


def _format_public_track_response(row: dict) -> dict:
    raw_status = str(row.get("status") or "pending").lower()
    citizen_status, guidance = _CITIZEN_STATUS_MAP.get(
        raw_status, ("RECEIVED", "Đã tiếp nhận yêu cầu SOS.")
    )
    sos_id = int(row["id"])
    return {
        "ticket_code": f"#SOS-2026-{sos_id:04d}",
        "status": citizen_status,
        "raw_status": raw_status,
        "guidance": guidance,
        "progress_confirmed": raw_status in ("dispatched", "rescued"),
        "received_at": str(row.get("created_at")),
        "updated_at": str(row.get("updated_at")),
        "source": "NORTHSTAR Command",
    }


def compute_sos_payload_hash(body: SOSCreate) -> str:
    """Tính SHA-256 chuẩn tắc của payload SOS để phát hiện xung đột khi trùng client_event_id."""
    canonical = {
        "contact_name": body.contact_name,
        "phone": body.phone,
        "lng": body.lng,
        "lat": body.lat,
        "location_source": body.location_source,
        "location_description": body.location_description,
        "location_landmark": body.location_landmark,
        "people_count": body.people_count,
        "has_elderly_or_children": body.has_elderly_or_children,
        "water_level_cm": body.water_level_cm,
        "priority": body.priority,
        "notes": body.notes,
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_feature(r: dict) -> dict:
    has_coords = r.get("lng") is not None and r.get("lat") is not None
    geometry = (
        {
            "type": "Point",
            "coordinates": [float(r["lng"]), float(r["lat"])]
        }
        if has_coords
        else None
    )
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "id": r["id"],
            "contact_name": r["contact_name"],
            "phone": r["phone"],
            "location_source": r.get("location_source") or ("manual" if has_coords else "unknown"),
            "location_accuracy_m": float(r["location_accuracy_m"]) if r.get("location_accuracy_m") is not None else None,
            "location_captured_at": r.get("location_captured_at"),
            "location_confirmed": bool(r.get("location_confirmed", False)),
            "location_description": r.get("location_description"),
            "location_landmark": r.get("location_landmark"),
            "people_count": int(r["people_count"]),
            "has_elderly_or_children": bool(r["has_elderly_or_children"]),
            "water_level_cm": float(r.get("water_level_cm") or 0.0),
            "priority": r["priority"],
            "status": r["status"],
            "notes": r.get("notes"),
            "client_event_id": r.get("client_event_id"),
            "idempotent_replay": bool(r.get("idempotent_replay", False)),
            **({"tracking_token": r["tracking_token"]} if r.get("tracking_token") else {}),
            "created_at": str(r.get("created_at")),
            "updated_at": str(r.get("updated_at")),
        }
    }


@router.get("")
def list_sos_beacons(
    request: Request,
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: pending, acknowledged, dispatched, rescued")
):
    """Danh sách các tín hiệu SOS kêu cứu từ người dân (Chỉ dành cho Command, chặn Citizen)."""
    if (request.headers.get("x-northstar-client") or "").strip().lower() == "citizen":
        raise HTTPException(
            status_code=403,
            detail="Phân hệ Citizen không được phép truy cập danh sách SOS nội bộ. Hãy dùng /api/sos/track/{tracking_token}.",
        )
    if not isinstance(status, str):
        status = None
    try:
        with get_db_connection() as conn:
            sql = """
                SELECT id, contact_name, phone,
                       CASE WHEN geom IS NOT NULL THEN ST_X(geom) ELSE NULL END AS lng,
                       CASE WHEN geom IS NOT NULL THEN ST_Y(geom) ELSE NULL END AS lat,
                       location_source, location_accuracy_m, location_captured_at,
                       location_confirmed, location_description, location_landmark,
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
    """Gửi tín hiệu kêu cứu khẩn cấp SOS kèm toạ độ (hoặc mô tả địa điểm khi mất GPS) và idempotency."""
    has_coords = (body.lng is not None) and (body.lat is not None)
    payload_hash = compute_sos_payload_hash(body) if body.client_event_id else None
    raw_tracking_token = secrets.token_urlsafe(24)
    token_hash = _hash_tracking_token(raw_tracking_token)
    token_expires_dt = datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)
    token_expires_iso = token_expires_dt.isoformat()

    try:
        with get_db_connection() as conn:
            try:
                if has_coords:
                    row = conn.execute("""
                        INSERT INTO community_sos (
                            contact_name, phone, geom,
                            location_source, location_accuracy_m, location_captured_at,
                            location_confirmed, location_description, location_landmark,
                            people_count, has_elderly_or_children, water_level_cm, priority, notes,
                            client_event_id, payload_hash,
                            tracking_token_hash, tracking_token_expires_at, tracking_token_revoked
                        )
                        VALUES (
                            %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s::sos_priority, %s,
                            %s, %s, %s, %s, 0
                        )
                        RETURNING id, contact_name, phone,
                                  ST_X(geom) AS lng, ST_Y(geom) AS lat,
                                  location_source, location_accuracy_m, location_captured_at,
                                  location_confirmed, location_description, location_landmark,
                                  people_count, has_elderly_or_children, water_level_cm,
                                  priority, status, notes, client_event_id, created_at, updated_at
                    """, (
                        body.contact_name, body.phone, body.lng, body.lat,
                        body.location_source, body.location_accuracy_m, body.location_captured_at,
                        body.location_confirmed, body.location_description, body.location_landmark,
                        body.people_count, body.has_elderly_or_children, body.water_level_cm,
                        body.priority, body.notes, body.client_event_id, payload_hash,
                        token_hash, token_expires_dt
                    )).fetchone()
                else:
                    row = conn.execute("""
                        INSERT INTO community_sos (
                            contact_name, phone, geom,
                            location_source, location_accuracy_m, location_captured_at,
                            location_confirmed, location_description, location_landmark,
                            people_count, has_elderly_or_children, water_level_cm, priority, notes,
                            client_event_id, payload_hash,
                            tracking_token_hash, tracking_token_expires_at, tracking_token_revoked
                        )
                        VALUES (
                            %s, %s, NULL,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s::sos_priority, %s,
                            %s, %s, %s, %s, 0
                        )
                        RETURNING id, contact_name, phone,
                                  NULL::double precision AS lng, NULL::double precision AS lat,
                                  location_source, location_accuracy_m, location_captured_at,
                                  location_confirmed, location_description, location_landmark,
                                  people_count, has_elderly_or_children, water_level_cm,
                                  priority, status, notes, client_event_id, created_at, updated_at
                    """, (
                        body.contact_name, body.phone,
                        body.location_source, body.location_accuracy_m, body.location_captured_at,
                        body.location_confirmed, body.location_description, body.location_landmark,
                        body.people_count, body.has_elderly_or_children, body.water_level_cm,
                        body.priority, body.notes, body.client_event_id, payload_hash,
                        token_hash, token_expires_dt
                    )).fetchone()
                d = dict(row)
                d["tracking_token"] = raw_tracking_token
                return _to_feature(d)
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                if not body.client_event_id:
                    raise
                existing = conn.execute("""
                    SELECT id, contact_name, phone,
                           CASE WHEN geom IS NOT NULL THEN ST_X(geom) ELSE NULL END AS lng,
                           CASE WHEN geom IS NOT NULL THEN ST_Y(geom) ELSE NULL END AS lat,
                           location_source, location_accuracy_m, location_captured_at,
                           location_confirmed, location_description, location_landmark,
                           people_count, has_elderly_or_children, water_level_cm,
                           priority, status, notes, client_event_id, payload_hash, created_at, updated_at
                    FROM community_sos
                    WHERE client_event_id = %s
                """, (body.client_event_id,)).fetchone()
                if existing:
                    if existing.get("payload_hash") and payload_hash and existing["payload_hash"] != payload_hash:
                        log.warning("Idempotency conflict on SOS client_event_id=%s", body.client_event_id)
                        raise HTTPException(409, "Xung đột dữ liệu: client_event_id đã tồn tại với nội dung khác.")
                    d = dict(existing)
                    d["idempotent_replay"] = True
                    return _to_feature(d)
                raise
    except HTTPException:
        raise
    except Exception as e:
        log.warning("DB query failed in create_sos_beacon, using fallback: %s", e)

    try:
        fb_data = body.model_dump()
        if payload_hash:
            fb_data["payload_hash"] = payload_hash
        fb_data["tracking_token_hash"] = token_hash
        fb_data["tracking_token_expires_at"] = token_expires_iso
        fb_data["tracking_token_revoked"] = 0
        saved = save_fallback_sos(fb_data)
    except IdempotencyConflictError:
        log.warning("Idempotency conflict (fallback) on SOS client_event_id=%s", body.client_event_id)
        raise HTTPException(409, "Xung đột dữ liệu: client_event_id đã tồn tại với nội dung khác.")

    if saved.get("id") is None:
        raise HTTPException(500, "Không thể lưu hồ sơ cứu hộ SOS trên máy chủ.")
    if not saved.get("idempotent_replay"):
        saved["tracking_token"] = raw_tracking_token
    return _to_feature(saved)


@router.get("/track/{tracking_token}")
def track_sos_by_token(tracking_token: str, request: Request):
    """Tra cứu riêng tư tiến độ SOS bằng tracking_token mật mã (không trả PII)."""
    client_host = request.client.host if request.client else "unknown"
    _check_track_rate_limit(client_host)

    if not tracking_token or len(tracking_token) < 16:
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc token tra cứu không hợp lệ.")

    token_hash = _hash_tracking_token(tracking_token)
    row = None
    try:
        with get_db_connection() as conn:
            r = conn.execute("""
                SELECT id, status, created_at, updated_at,
                       tracking_token_expires_at, tracking_token_revoked
                FROM community_sos
                WHERE tracking_token_hash = %s
            """, (token_hash,)).fetchone()
            row = dict(r) if r else None
    except Exception as e:
        log.warning("DB query failed in track_sos_by_token, using fallback: %s", e)
        row = get_fallback_sos_by_token_hash(token_hash)

    if not row or int(row.get("tracking_token_revoked") or 0) == 1:
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc token tra cứu không hợp lệ.")

    exp_raw = row.get("tracking_token_expires_at")
    if exp_raw:
        exp_dt = exp_raw if isinstance(exp_raw, datetime) else datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt <= datetime.now(timezone.utc):
            raise HTTPException(410, "Token tra cứu đã hết hạn.")

    return _format_public_track_response(row)


@router.post("/track/{tracking_token}/revoke")
def revoke_sos_tracking_token(tracking_token: str):
    """Thu hồi tracking_token để vô hiệu hóa quyền tra cứu sau khi hoàn tất."""
    if not tracking_token or len(tracking_token) < 16:
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc token tra cứu không hợp lệ.")

    token_hash = _hash_tracking_token(tracking_token)
    revoked = False
    try:
        with get_db_connection() as conn:
            r = conn.execute(
                "UPDATE community_sos SET tracking_token_revoked = 1 WHERE tracking_token_hash = %s RETURNING id",
                (token_hash,),
            ).fetchone()
            revoked = bool(r)
    except Exception as e:
        log.warning("DB query failed in revoke_sos_tracking_token, using fallback: %s", e)
        revoked = revoke_fallback_sos_token(token_hash)

    if not revoked:
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc token tra cứu không hợp lệ.")
    return {"revoked": True}


@router.post("/relay", status_code=201)
def receive_relayed_sos(packet: dict):
    """Tiếp nhận gói SOS chuyển tiếp thủ công từ thiết bị trung gian và chống trùng theo client_event_id."""
    if not isinstance(packet, dict):
        raise HTTPException(400, "Gói tin Relay không hợp lệ.")
    client_event_id = packet.get("client_event_id")
    if not client_event_id or len(str(client_event_id)) < 8:
        raise HTTPException(422, "Gói tin Relay thiếu client_event_id hợp lệ.")

    exp_raw = packet.get("expires_at")
    if exp_raw:
        try:
            exp_dt = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt <= datetime.now(timezone.utc):
                raise HTTPException(410, "Gói tin Relay đã hết hạn.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "Định dạng expires_at không hợp lệ.")

    hop = int(packet.get("hop_count") or 0)
    max_hops = int(packet.get("max_hops") or 3)
    if hop > max_hops:
        raise HTTPException(422, "Gói tin Relay vượt quá số lần chuyển tiếp cho phép.")

    loc = packet.get("location") or {}
    pl = packet.get("payload") or {}
    body = SOSCreate(
        contact_name=f"Relay ({packet.get('origin_device_id', 'unknown')})",
        phone="0000000000",
        lng=loc.get("lng"),
        lat=loc.get("lat"),
        location_source=packet.get("location_source") or "unknown",
        location_confirmed=False,
        location_description=loc.get("location_description") or "SOS chuyển tiếp qua thiết bị trung gian",
        location_landmark=loc.get("location_landmark"),
        people_count=int(pl.get("people_count") or 1),
        has_elderly_or_children=bool(pl.get("has_elderly_or_children")),
        water_level_cm=float(pl.get("water_level_cm") or 0),
        priority=pl.get("priority") or "high",
        notes=pl.get("notes") or f"Relayed hop={hop}",
        client_event_id=str(client_event_id),
    )
    return create_sos_beacon(body)


@router.patch("/{sos_id}/status")
def update_sos_status(sos_id: int, body: SOSStatusUpdate):
    """Cập nhật trạng thái xử lý cứu hộ (điều phối đội cứu hộ, xác nhận đã an toàn)."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("""
                UPDATE community_sos
                SET status = %s::sos_status, updated_at = now()
                WHERE id = %s
                RETURNING id, contact_name, phone,
                          CASE WHEN geom IS NOT NULL THEN ST_X(geom) ELSE NULL END AS lng,
                          CASE WHEN geom IS NOT NULL THEN ST_Y(geom) ELSE NULL END AS lat,
                          location_source, location_accuracy_m, location_captured_at,
                          location_confirmed, location_description, location_landmark,
                          people_count, has_elderly_or_children, water_level_cm,
                          priority, status, notes, created_at, updated_at
            """, (body.status, sos_id)).fetchone()
            if row:
                return _to_feature(dict(row))
    except Exception as e:
        log.warning("DB query failed in update_sos_status, using fallback: %s", e)

    updated = update_fallback_sos_status(sos_id, body.status)
    if updated:
        return _to_feature(updated)

    raise HTTPException(404, f"Không tìm thấy yêu cầu cứu hộ SOS id={sos_id}")
