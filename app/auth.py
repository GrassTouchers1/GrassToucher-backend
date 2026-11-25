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
He thong Xac thuc & Phan quyen RBAC phia May chu (NorthStar Backend Auth & RBAC).
- Mat khau bam PBKDF2-HMAC-SHA256 voi salt ngau nhien tung tai khoan.
- Token ky HMAC-SHA256 co thoi han (exp), dinh danh phien (jti) va ho tro thu hoi (logout).
- Ho tro 5 vai tro: guest (chua dang nhap), citizen, rescue, coordinator, admin.
- Ghi nhat ky Audit Trail cho moi hanh dong nhay cam va vi pham truy cap.
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
from typing import Callable, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status

from . import fallback_storage

log = logging.getLogger("northstar.auth")

VALID_ROLES = ("citizen", "rescue", "coordinator", "admin")
TOKEN_TTL_HOURS = int(os.getenv("NORTHSTAR_TOKEN_TTL_HOURS", "12"))

# Ephemeral runtime CSPRNG key when NORTHSTAR_AUTH_SECRET is not set in environment.
_RUNTIME_EPHEMERAL_SECRET = secrets.token_urlsafe(32)


def _get_signing_secret() -> bytes:
    env_secret = os.getenv("NORTHSTAR_AUTH_SECRET", "").strip()
    secret = env_secret if env_secret else _RUNTIME_EPHEMERAL_SECRET
    return secret.encode("utf-8")


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    role: str
    full_name: str
    jti: Optional[str] = None
    is_active: bool = True


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Bam mat khau bang PBKDF2-HMAC-SHA256 voi 120,000 vong."""
    salt_val = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_val.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt_val}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        alg, salt_val, expected_hex = encoded.split("$", 2)
        if alg != "pbkdf2_sha256":
            return False
        candidate = hash_password(password, salt=salt_val)
        return hmac.compare_digest(candidate, encoded)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(val: str) -> bytes:
    pad = "=" * ((4 - len(val) % 4) % 4)
    return base64.urlsafe_b64decode((val + pad).encode("ascii"))


def init_auth_tables() -> None:
    """Khoi tao bang nguoi dung RBAC, bang thu hoi token va nhat ky kiem toan (Audit Log)."""
    demo_pw = os.getenv("NORTHSTAR_DEMO_PASSWORD", "NorthStarDemo@2026")
    now_iso = datetime.now(timezone.utc).isoformat()
    with fallback_storage._FALLBACK_WRITE_LOCK:
        with fallback_storage._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'citizen',
                    full_name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    is_demo INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_revoked_tokens (
                    jti TEXT PRIMARY KEY,
                    revoked_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS security_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor_id INTEGER,
                    actor_username TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    outcome TEXT NOT NULL,
                    detail TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON security_audit_logs(id DESC);
            """)

            demo_accounts = [
                ("citizen_demo", "citizen", "Nguyễn Văn An (Dân sự - Demo)"),
                ("citizen_demo2", "citizen", "Trần Thị Bình (Dân sự - Demo)"),
                ("rescue_demo", "rescue", "Đội PCCC & CNCH 114 (Cứu hộ - Demo)"),
                ("coordinator_demo", "coordinator", "Trực ban Chỉ huy PCTT (Điều phối - Demo)"),
                ("admin_demo", "admin", "Quản trị viên Hệ thống (Admin - Demo)"),
            ]
            for uname, role, fname in demo_accounts:
                existing = conn.execute("SELECT id FROM auth_users WHERE username = ?", (uname,)).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO auth_users (username, password_hash, role, full_name, is_active, is_demo, created_at)
                           VALUES (?, ?, ?, ?, 1, 1, ?)""",
                        (uname, hash_password(demo_pw), role, fname, now_iso),
                    )
            conn.commit()


def record_audit_event(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    outcome: str = "success",
    detail: Optional[str] = None,
    actor: Optional[AuthUser] = None,
) -> None:
    try:
        init_auth_tables()
        now_iso = datetime.now(timezone.utc).isoformat()
        with fallback_storage._FALLBACK_WRITE_LOCK:
            with fallback_storage._get_connection() as conn:
                conn.execute(
                    """INSERT INTO security_audit_logs
                       (timestamp, actor_id, actor_username, actor_role, action, resource_type, resource_id, outcome, detail)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        now_iso,
                        actor.id if actor else None,
                        actor.username if actor else "guest",
                        actor.role if actor else "guest",
                        action,
                        resource_type,
                        str(resource_id) if resource_id is not None else None,
                        outcome,
                        detail,
                    ),
                )
                conn.commit()
    except Exception as exc:
        log.warning("Khong the ghi audit log: %s", exc)


def get_audit_logs(limit: int = 100) -> list[dict]:
    init_auth_tables()
    with fallback_storage._get_connection() as conn:
        rows = conn.execute(
            """SELECT id, timestamp, actor_id, actor_username, actor_role,
                      action, resource_type, resource_id, outcome, detail
               FROM security_audit_logs ORDER BY id DESC LIMIT ?""",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        return [dict(r) for r in rows]


def authenticate_user(username: str, password: str) -> Optional[AuthUser]:
    init_auth_tables()
    uname = (username or "").strip().lower()
    if not uname or not password:
        return None
    with fallback_storage._get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, full_name, is_active FROM auth_users WHERE lower(username) = ?",
            (uname,),
        ).fetchone()
    if not row or not int(row["is_active"] or 0):
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return AuthUser(
        id=int(row["id"]),
        username=row["username"],
        role=row["role"],
        full_name=row["full_name"],
        is_active=True,
    )


def create_user_account(username: str, password: str, full_name: str, role: str = "citizen") -> AuthUser:
    init_auth_tables()
    if role not in VALID_ROLES:
        raise ValueError("Vai tro khong hop le.")
    uname = username.strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    with fallback_storage._FALLBACK_WRITE_LOCK:
        with fallback_storage._get_connection() as conn:
            try:
                cur = conn.execute(
                    """INSERT INTO auth_users (username, password_hash, role, full_name, is_active, is_demo, created_at)
                       VALUES (?, ?, ?, ?, 1, 0, ?)""",
                    (uname, hash_password(password), role, full_name.strip(), now_iso),
                )
                conn.commit()
                uid = int(cur.lastrowid)
            except sqlite3.IntegrityError:
                raise ValueError(f"Tai khoan '{uname}' da ton tai.")
    return AuthUser(id=uid, username=uname, role=role, full_name=full_name.strip(), is_active=True)


def list_all_users() -> list[dict]:
    init_auth_tables()
    with fallback_storage._get_connection() as conn:
        rows = conn.execute(
            "SELECT id, username, role, full_name, is_active, is_demo, created_at FROM auth_users ORDER BY id ASC"
        ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "username": r["username"],
                "role": r["role"],
                "full_name": r["full_name"],
                "is_active": bool(r["is_active"]),
                "is_demo": bool(r["is_demo"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def update_user_role(user_id: int, new_role: str) -> Optional[dict]:
    if new_role not in VALID_ROLES:
        raise ValueError(f"Vai tro khong hop le: {new_role}")
    init_auth_tables()
    with fallback_storage._FALLBACK_WRITE_LOCK:
        with fallback_storage._get_connection() as conn:
            cur = conn.execute(
                "UPDATE auth_users SET role = ? WHERE id = ?",
                (new_role, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT id, username, role, full_name, is_active, is_demo, created_at FROM auth_users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None


def issue_access_token(user: AuthUser) -> tuple[str, str]:
    now_dt = datetime.now(timezone.utc)
    exp_dt = now_dt + timedelta(hours=TOKEN_TTL_HOURS)
    jti = secrets.token_hex(16)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "jti": jti,
        "iat": int(now_dt.timestamp()),
        "exp": int(exp_dt.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(_get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    token = f"{payload_b64}.{_b64url_encode(sig)}"
    return token, exp_dt.isoformat()


def revoke_access_token(jti: str, exp_ts: Optional[int] = None) -> None:
    if not jti:
        return
    init_auth_tables()
    now_iso = datetime.now(timezone.utc).isoformat()
    exp_iso = (
        datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()
        if exp_ts
        else (datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    )
    with fallback_storage._FALLBACK_WRITE_LOCK:
        with fallback_storage._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO auth_revoked_tokens (jti, revoked_at, expires_at) VALUES (?, ?, ?)",
                (jti, now_iso, exp_iso),
            )
            conn.commit()


def decode_and_verify_token(token: str) -> AuthUser:
    try:
        payload_b64, sig_b64 = token.strip().split(".", 1)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token xac thuc khong dung dinh dang.")

    expected_sig = hmac.new(_get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chu ky token khong hop le.")

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token xac thuc khong hop le hoac da bi gia mao.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Noi dung token khong hop le.")

    if int(payload.get("exp") or 0) <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phien dang nhap da het han.")

    jti = payload.get("jti")
    init_auth_tables()
    with fallback_storage._get_connection() as conn:
        rev = conn.execute("SELECT jti FROM auth_revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        if rev:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token da bi thu hoi (da dang xuat).")
        db_user = conn.execute(
            "SELECT id, username, role, full_name, is_active FROM auth_users WHERE id = ?",
            (int(payload["sub"]),),
        ).fetchone()
    if not db_user or not int(db_user["is_active"] or 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tai khoan khong ton tai hoac da bi khoa.")

    return AuthUser(
        id=int(db_user["id"]),
        username=db_user["username"],
        role=db_user["role"],
        full_name=db_user["full_name"],
        jti=jti,
        is_active=True,
    )


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth_hdr = request.headers.get("Authorization") or ""
    if auth_hdr.lower().startswith("bearer "):
        tok = auth_hdr[7:].strip()
        if tok:
            return tok
    return None


def get_current_user_optional(request: Request) -> Optional[AuthUser]:
    """Tra ve AuthUser neu co Bearer token hop le; None neu la Guest; nem 401 neu token sai/het han."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    return decode_and_verify_token(token)


def get_current_user(request: Request) -> AuthUser:
    user = get_current_user_optional(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yeu cau dang nhap (thieu Bearer token).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[[Request], AuthUser]:
    allowed = tuple(allowed_roles)

    def _dependency(request: Request) -> AuthUser:
        user = get_current_user_optional(request)
        if user is None:
            record_audit_event(
                action="auth_required_denied",
                resource_type="endpoint",
                resource_id=request.url.path,
                outcome="denied_401",
                detail="Unauthenticated request to protected endpoint",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Yeu cau dang nhap de truy cap tai nguyen nay.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.role not in allowed:
            record_audit_event(
                action="rbac_forbidden",
                resource_type="endpoint",
                resource_id=request.url.path,
                outcome="denied_403",
                detail=f"Role '{user.role}' not in {allowed}",
                actor=user,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vai tro '{user.role}' khong co quyen thuc hien thao tac nay.",
            )
        return user

    return _dependency
