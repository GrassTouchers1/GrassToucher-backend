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
Router Phat Tin Hieu Cuu Ho Khan Cap (1-Click Community SOS) & DTN Relay / Satellite Gateway.
Tich hop phan quyen RBAC phia may chu, ownership cho Citizen va nhat ky Audit Trail.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import logging
import re
import secrets
import time
from typing import Dict, List, Optional

import psycopg
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth import (
    AuthUser,
    get_current_user,
    get_current_user_optional,
    record_audit_event,
)
from ..db import get_db_connection
from ..fallback_storage import (
    IdempotencyConflictError,
    get_fallback_sos,
    get_fallback_sos_by_id,
    get_fallback_sos_by_token_hash,
    revoke_fallback_sos_token,
    save_fallback_sos,
    update_fallback_sos_status,
)
from ..schemas import SOSCreate, SOSStatusUpdate

log = logging.getLogger("northstar.sos")
router = APIRouter(prefix="/api/sos", tags=["Cuu ho khan cap SOS"])

TRACKING_TOKEN_TTL_DAYS = 7
_TRACK_RATE_LIMIT_MAX = 20
_TRACK_RATE_LIMIT_WINDOW_S = 60.0
_TRACK_RATE_BUCKETS: Dict[str, List[float]] = {}

_CITIZEN_STATUS_MAP = {
    "pending": ("RECEIVED", "Đã tiếp nhận yêu cầu SOS, đang chờ cán bộ xác minh."),
    "verified": ("VERIFIED", "Trung tâm Chỉ huy đã xác minh thực địa hồ sơ SOS."),
    "acknowledged": ("VERIFIED", "Trung tâm Chỉ huy đã xác nhận hồ sơ, đang chuẩn bị điều phối."),
    "dispatched": ("DISPATCHED", "Đội cứu hộ đang trên đường tiếp cận vị trí của bạn."),
    "on_scene": ("DISPATCHED", "Đội cứu hộ đã có mặt tại hiện trường tiếp cận nạn nhân."),
    "rescued": ("RESCUED", "Đã hoàn tất cứu hộ an toàn."),
    "cancelled": ("CANCELLED", "Hồ sơ SOS đã được hủy."),
}

RESCUE_ALLOWED_STATUSES = {"acknowledged", "on_scene", "rescued"}
COORDINATOR_ALLOWED_STATUSES = {"pending", "verified", "acknowledged", "dispatched", "on_scene", "rescued", "cancelled"}


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
        "progress_confirmed": raw_status in ("dispatched", "on_scene", "rescued"),
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
            "coordinates": [float(r["lng"]), float(r["lat"])],
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
            "owner_user_id": r.get("owner_user_id"),
            "client_event_id": r.get("client_event_id"),
            "idempotent_replay": bool(r.get("idempotent_replay", False)),
            "deduplicated": bool(r.get("deduplicated", r.get("idempotent_replay", False))),
            "ingest_channel": r.get("ingest_channel") or "direct_online",
            "hop_count": int(r.get("hop_count") or 0),
            "signature_verified": bool(r.get("signature_verified", False)),
            "origin_created_at": r.get("origin_created_at"),
            "relayed_at": r.get("relayed_at"),
            **({"tracking_token": r["tracking_token"]} if r.get("tracking_token") else {}),
            "created_at": str(r.get("created_at")),
            "updated_at": str(r.get("updated_at")),
        },
    }


def _fetch_sos_collection(status_filter: Optional[str] = None, owner_user_id: Optional[int] = None) -> dict:
    """Ham noi bo truy van danh sach SOS cho cac router tac chien (rescue_dispatch, sitrep)."""
    if not isinstance(status_filter, str):
        status_filter = None
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
            if status_filter:
                sql += " WHERE status = %s::sos_status"
                params.append(status_filter)
            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, tuple(params)).fetchall()
            if owner_user_id is None:
                return {"type": "FeatureCollection", "features": [_to_feature(dict(r)) for r in rows]}
    except Exception as e:
        log.warning("DB query failed in _fetch_sos_collection, using fallback: %s", e)

    fb_rows = get_fallback_sos(status=status_filter, owner_user_id=owner_user_id)
    return {"type": "FeatureCollection", "features": [_to_feature(r) for r in fb_rows]}


@router.get("")
def list_sos_beacons(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái: pending, acknowledged, dispatched, rescued"),
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Danh sách các tín hiệu SOS kêu cứu (Chỉ dành cho Rescue, Coordinator, Admin)."""
    if (request.headers.get("x-northstar-client") or "").strip().lower() == "citizen" and (not user or user.role == "citizen"):
        record_audit_event("sos_list_forbidden_citizen", "sos", None, "denied_403", "Citizen client header blocked", actor=user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phân hệ Citizen không được phép truy cập danh sách SOS nội bộ. Hãy dùng /api/sos/track/{tracking_token} hoặc /api/sos/mine.",
        )
    if user is None:
        record_audit_event("sos_list_unauthorized", "sos", None, "denied_401", "Unauthenticated GET /api/sos")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập vai trò Cứu hộ hoặc Điều phối để xem danh sách SOS.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role not in ("rescue", "coordinator", "admin"):
        record_audit_event("sos_list_forbidden_role", "sos", None, "denied_403", f"Role '{user.role}' forbidden", actor=user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vai trò '{user.role}' không có quyền truy cập danh sách SOS toàn hệ thống.",
        )
    return _fetch_sos_collection(status_filter=status_filter)


@router.get("/mine")
def list_my_sos_beacons(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: AuthUser = Depends(get_current_user),
):
    """Nguoi dan chi xem duoc cac ho so SOS do chinh tai khoan minh tao."""
    return _fetch_sos_collection(status_filter=status_filter, owner_user_id=user.id)


@router.post("", status_code=201)
def create_sos_beacon(
    body: SOSCreate,
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Gửi tín hiệu kêu cứu khẩn cấp SOS kèm toạ độ (hoặc mô tả địa điểm khi mất GPS) và idempotency."""
    has_coords = (body.lng is not None) and (body.lat is not None)
    payload_hash = compute_sos_payload_hash(body) if body.client_event_id else None
    raw_tracking_token = secrets.token_urlsafe(24)
    token_hash = _hash_tracking_token(raw_tracking_token)
    token_expires_dt = datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)
    token_expires_iso = token_expires_dt.isoformat()
    owner_user_id = user.id if isinstance(user, AuthUser) else None

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
                d["owner_user_id"] = owner_user_id
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
        fb_data["owner_user_id"] = owner_user_id
        saved = save_fallback_sos(fb_data)
    except IdempotencyConflictError:
        log.warning("Idempotency conflict (fallback) on SOS client_event_id=%s", body.client_event_id)
        raise HTTPException(409, "Xung đột dữ liệu: client_event_id đã tồn tại với nội dung khác.")

    if saved.get("id") is None:
        raise HTTPException(500, "Không thể lưu hồ sơ cứu hộ SOS trên máy chủ.")
    if not saved.get("idempotent_replay"):
        saved["tracking_token"] = raw_tracking_token
    record_audit_event("sos_created", "sos", str(saved.get("id")), "success", f"priority={body.priority}", actor=user if isinstance(user, AuthUser) else None)
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


def _b64url_to_int(val: str) -> int:
    padded = val + "=" * ((4 - len(val) % 4) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(padded.encode("ascii")), "big")


def _verify_relay_integrity_and_signature(packet: dict) -> bool:
    """Xác thực SHA-256 và chữ ký ECDSA-P256 nếu gói tin có kèm metadata bảo mật."""
    integ = packet.get("integrity_metadata") or {}
    provided_hash = packet.get("payload_sha256") or integ.get("content_hash")
    if provided_hash:
        if integ.get("content_hash"):
            core_obj = {
                "message_id": packet.get("message_id"),
                "client_event_id": packet.get("client_event_id"),
                "origin_device_id": packet.get("origin_device_id"),
                "created_at": packet.get("created_at"),
                "expires_at": packet.get("expires_at"),
                "location": packet.get("location"),
                "location_source": packet.get("location_source"),
                "payload": packet.get("payload"),
            }
            expected = hashlib.sha256(
                json.dumps(core_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
        else:
            expected = hashlib.sha256(
                json.dumps(packet.get("payload"), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
        if str(provided_hash).lower() != expected.lower():
            raise HTTPException(422, "Gói tin Relay không khớp mã băm toàn vẹn SHA-256.")

    auth_meta = packet.get("authentication_metadata") or {}
    sig_b64 = packet.get("signature") or auth_meta.get("signature")
    pub_jwk = packet.get("public_key") or auth_meta.get("public_key_jwk")
    scheme = auth_meta.get("scheme") or ("ECDSA-P256" if (sig_b64 and pub_jwk) else "NONE")
    if scheme == "ECDSA-P256" and sig_b64 and pub_jwk:
        try:
            if isinstance(pub_jwk, str):
                pub_jwk = json.loads(pub_jwk)
            x = _b64url_to_int(pub_jwk["x"])
            y = _b64url_to_int(pub_jwk["y"])
            pub_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
            sig_raw = base64.b64decode(sig_b64)
            if len(sig_raw) == 64:
                r_int = int.from_bytes(sig_raw[:32], "big")
                s_int = int.from_bytes(sig_raw[32:], "big")
                der_sig = encode_dss_signature(r_int, s_int)
            else:
                der_sig = sig_raw
            signed_msg = str(provided_hash).encode("utf-8") if provided_hash else json.dumps(
                packet.get("payload"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            pub_key.verify(der_sig, signed_msg, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            raise HTTPException(422, "Chữ ký xác thực ECDSA-P256 của gói tin Relay không hợp lệ.")
    return bool(provided_hash)


def _create_sos_with_metadata(body: SOSCreate, extra_meta: dict) -> dict:
    payload_hash = compute_sos_payload_hash(body) if body.client_event_id else None
    raw_tracking_token = secrets.token_urlsafe(24)
    token_hash = _hash_tracking_token(raw_tracking_token)
    token_expires_iso = (datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)).isoformat()

    fb_data = body.model_dump()
    if payload_hash:
        fb_data["payload_hash"] = payload_hash
    fb_data["tracking_token_hash"] = token_hash
    fb_data["tracking_token_expires_at"] = token_expires_iso
    fb_data["tracking_token_revoked"] = False
    fb_data.update(extra_meta)

    try:
        saved = save_fallback_sos(fb_data)
    except IdempotencyConflictError as exc:
        raise HTTPException(409, str(exc))
    if not saved.get("idempotent_replay") and not saved.get("deduplicated"):
        saved["tracking_token"] = raw_tracking_token
    return _to_feature(saved)


@router.post("/relay", status_code=201)
def receive_relayed_sos(packet: dict):
    """Tiếp nhận gói SOS chuyển tiếp (DTN Relay), xác thực SHA-256/ECDSA-P256 và chống trùng client_event_id."""
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
    max_hops = int(packet.get("max_hops") or 5)
    if hop > max_hops:
        raise HTTPException(422, "Gói tin Relay vượt quá số lần chuyển tiếp cho phép.")

    sig_verified = _verify_relay_integrity_and_signature(packet)

    loc = packet.get("location") or {}
    pl = packet.get("payload") or {}
    relay_hops = packet.get("relay_hops") or packet.get("relay_history") or []
    raw_phone = str(pl.get("contact_phone_masked") or "0000000000")
    safe_phone = raw_phone if len(raw_phone) >= 8 else f"REL-{raw_phone}".ljust(8, "0")
    body = SOSCreate(
        contact_name=f"Relay ({packet.get('origin_device_id', 'unknown')})",
        phone=safe_phone,
        lng=loc.get("lng") if loc.get("lng") is not None else pl.get("lng"),
        lat=loc.get("lat") if loc.get("lat") is not None else pl.get("lat"),
        location_source=packet.get("location_source") or "unknown",
        location_confirmed=False,
        location_description=loc.get("location_description") or pl.get("location_description") or "SOS chuyển tiếp qua thiết bị trung gian",
        location_landmark=loc.get("location_landmark"),
        people_count=int(pl.get("people_count") or 1),
        has_elderly_or_children=bool(pl.get("has_elderly_or_children")),
        water_level_cm=float(pl.get("water_level_cm") or 0),
        priority=pl.get("priority") or "high",
        notes=pl.get("notes") or f"Relayed hop={hop}",
        client_event_id=str(client_event_id),
    )
    return _create_sos_with_metadata(
        body,
        {
            "ingest_channel": "dtn_relay",
            "hop_count": hop,
            "signature_verified": sig_verified,
            "origin_created_at": packet.get("created_at"),
            "relayed_at": datetime.now(timezone.utc).isoformat(),
            "relay_hops": relay_hops,
        },
    )


@router.post("/gateway/inbound", status_code=201)
def receive_gateway_inbound_sos(body: dict):
    """Tiếp nhận khung nén vệ tinh (NS1|...) hoặc tin nhắn SMS 2G chuẩn hóa kèm Auto-Triage."""
    if not isinstance(body, dict):
        raise HTTPException(400, "Dữ liệu gateway không hợp lệ.")

    compact_frame = str(body.get("compact_frame") or "").strip()
    sms_text = str(body.get("sms_text") or "").strip()
    simulated = bool(body.get("simulated", False))

    lat_val = None
    lng_val = None
    people_count = 1
    water_level_cm = 0.0
    frame_prio = "high"
    short_id = ""
    ingest_channel = "satellite_simulated" if simulated else "satellite"

    if compact_frame:
        parts = compact_frame.split("|")
        if len(parts) != 7 or parts[0] != "NS1":
            raise HTTPException(422, "Khung nén vệ tinh không đúng định dạng NS1.")
        core_body = "|".join(parts[:6])
        crc = 0
        for ch in core_body:
            crc = (crc ^ ord(ch)) & 0xFF
        expected_crc = f"{crc:02X}"
        if parts[6].upper() != expected_crc:
            raise HTTPException(422, "Sai checksum khung nén vệ tinh.")
        if parts[1] != "NOGPS" and "," in parts[1]:
            lat_s, lng_s = parts[1].split(",", 1)
            lat_val, lng_val = float(lat_s), float(lng_s)
        people_count = max(1, int(parts[2]))
        water_level_cm = max(0.0, float(parts[3]))
        prio_rev = {"C": "critical", "H": "high", "M": "medium", "L": "low"}
        frame_prio = prio_rev.get(parts[4].upper(), "high")
        short_id = parts[5]
    elif sms_text:
        ingest_channel = "sms_2g"
        m_coord = re.search(r"(-?\d+\.\d+),(-?\d+\.\d+)", sms_text)
        if m_coord:
            lat_val, lng_val = float(m_coord.group(1)), float(m_coord.group(2))
        m_ppl = re.search(r"(\d+)\s*nguoi", sms_text, re.IGNORECASE)
        if m_ppl:
            people_count = max(1, int(m_ppl.group(1)))
        m_depth = re.search(r"(\d+)\s*cm", sms_text, re.IGNORECASE)
        if m_depth:
            water_level_cm = max(0.0, float(m_depth.group(1)))
        short_id = sms_text.split()[-1] if sms_text.split() else "SMS"
    else:
        raise HTTPException(422, "Thiếu compact_frame hoặc sms_text.")

    if water_level_cm >= 200 or frame_prio == "critical":
        triaged_prio = "critical"
    elif water_level_cm >= 100 or frame_prio == "high":
        triaged_prio = "high"
    else:
        triaged_prio = "medium"

    client_event_id = str(body.get("client_event_id") or f"gw-{ingest_channel}-{short_id}-{int(time.time() * 1000)}")
    if len(client_event_id) < 8:
        client_event_id = f"gw-{client_event_id}-0000"

    sos_body = SOSCreate(
        contact_name=f"Gateway ({ingest_channel})",
        phone="0000000000",
        lng=lng_val,
        lat=lat_val,
        location_source="approximate" if lat_val is not None else "unknown",
        location_confirmed=False,
        location_description=f"Tiếp nhận qua {ingest_channel} ({short_id})" if lat_val is None else None,
        people_count=people_count,
        has_elderly_or_children=bool(body.get("has_elderly_or_children", False)),
        water_level_cm=water_level_cm,
        priority=triaged_prio,
        notes=f"[{ingest_channel.upper()}] {compact_frame or sms_text}",
        client_event_id=client_event_id,
    )
    feature = _create_sos_with_metadata(
        sos_body,
        {
            "ingest_channel": ingest_channel,
            "hop_count": 0,
            "signature_verified": bool(compact_frame),
            "relayed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    feature["gateway_ref"] = f"GW-{feature['properties']['id']}"
    feature["simulated"] = simulated
    return feature


@router.patch("/{sos_id}/status")
def update_sos_status(
    sos_id: int,
    body: SOSStatusUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Cập nhật trạng thái xử lý cứu hộ theo RBAC + kiểm tra ownership cho Citizen."""
    existing = get_fallback_sos_by_id(sos_id)

    if user.role == "citizen":
        # Citizen chỉ được phép HỦY đúng hồ sơ do chính tài khoản mình tạo (chống IDOR)
        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Không tìm thấy yêu cầu cứu hộ SOS id={sos_id}")
        if existing.get("owner_user_id") != user.id:
            record_audit_event("sos_idor_attempt", "sos", str(sos_id), "denied_403", f"Citizen {user.username} attempted modify sos {sos_id}", actor=user)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền thao tác trên hồ sơ SOS của người khác.")
        if body.status != "cancelled":
            record_audit_event("sos_privilege_denied", "sos", str(sos_id), "denied_403", f"Citizen attempted set status={body.status}", actor=user)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Người dân chỉ có thể hủy (cancelled) hồ sơ SOS của chính mình.")
    elif user.role == "rescue":
        if body.status not in RESCUE_ALLOWED_STATUSES:
            record_audit_event("sos_rescue_status_denied", "sos", str(sos_id), "denied_403", f"Rescue attempted set status={body.status}", actor=user)
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Đội cứu hộ chỉ được cập nhật trạng thái hiện trường {sorted(RESCUE_ALLOWED_STATUSES)}.",
            )
    elif user.role not in ("coordinator", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Vai trò '{user.role}' không có quyền cập nhật trạng thái SOS.")

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
                record_audit_event("sos_status_updated", "sos", str(sos_id), "success", f"status={body.status}", actor=user)
                return _to_feature(dict(row))
    except Exception as e:
        log.warning("DB query failed in update_sos_status, using fallback: %s", e)

    updated = update_fallback_sos_status(sos_id, body.status)
    if updated:
        record_audit_event("sos_status_updated", "sos", str(sos_id), "success", f"status={body.status}", actor=user)
        return _to_feature(updated)

    raise HTTPException(404, f"Không tìm thấy yêu cầu cứu hộ SOS id={sos_id}")
