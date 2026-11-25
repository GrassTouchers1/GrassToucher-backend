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
Router Xac thuc, Phien dang nhap & Quan tri RBAC (Auth & Admin RBAC).
"""
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..auth import (
    AuthUser,
    VALID_ROLES,
    authenticate_user,
    create_user_account,
    get_audit_logs,
    get_current_user,
    init_auth_tables,
    issue_access_token,
    list_all_users,
    record_audit_event,
    require_roles,
    revoke_access_token,
    update_user_role,
)

auth_router = APIRouter(prefix="/api/auth", tags=["Xac thuc & Phien dang nhap"])
admin_router = APIRouter(prefix="/api/admin", tags=["Quan tri RBAC & Audit Log"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    role: Optional[str] = None


class RoleUpdateRequest(BaseModel):
    role: Literal["citizen", "rescue", "coordinator", "admin"]


@auth_router.post("/login")
def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        record_audit_event(
            action="login_failed",
            resource_type="auth",
            resource_id=body.username,
            outcome="denied_401",
            detail="Invalid username or password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai ten dang nhap hoac mat khau.",
        )
    token, expires_at = issue_access_token(user)
    record_audit_event(
        action="login_success",
        resource_type="auth",
        resource_id=user.username,
        outcome="success",
        actor=user,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
        },
    }


@auth_router.post("/register", status_code=201)
def register(body: RegisterRequest):
    """Dang ky tai khoan Dan su moi. Luon ep vai tro 'citizen' va chan leo thang dac quyen."""
    if body.role is not None and body.role != "citizen":
        record_audit_event(
            action="privilege_escalation_attempt",
            resource_type="auth_register",
            resource_id=body.username,
            outcome="denied_403",
            detail=f"Attempted self-assign role '{body.role}'",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Khong duoc phep tu gan vai tro dac quyen khi dang ky. Tai khoan moi mac dinh la 'citizen'.",
        )
    try:
        user = create_user_account(body.username, body.password, body.full_name, role="citizen")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    token, expires_at = issue_access_token(user)
    record_audit_event(
        action="register_citizen",
        resource_type="auth_users",
        resource_id=str(user.id),
        outcome="success",
        actor=user,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
        },
    }


@auth_router.post("/logout")
def logout(user: AuthUser = Depends(get_current_user)):
    if user.jti:
        revoke_access_token(user.jti)
    record_audit_event(
        action="logout",
        resource_type="auth",
        resource_id=user.username,
        outcome="success",
        actor=user,
    )
    return {"logged_out": True}


@auth_router.get("/me")
def get_me(user: AuthUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
    }


@auth_router.get("/demo-accounts")
def get_demo_account_directory():
    """Tra ve danh sach dinh danh tai khoan Demo (khong tra mat khau)."""
    init_auth_tables()
    return {
        "accounts": [
            {"username": u["username"], "role": u["role"], "full_name": u["full_name"]}
            for u in list_all_users()
            if u.get("is_demo")
        ]
    }


@admin_router.get("/users")
def admin_list_users(user: AuthUser = Depends(require_roles("admin"))):
    return {"users": list_all_users()}


@admin_router.patch("/users/{user_id}/role")
def admin_update_user_role(
    user_id: int,
    body: RoleUpdateRequest,
    user: AuthUser = Depends(require_roles("admin")),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(422, "Vai tro khong hop le.")
    updated = update_user_role(user_id, body.role)
    if not updated:
        raise HTTPException(404, f"Khong tim thay tai khoan id={user_id}")
    record_audit_event(
        action="admin_change_role",
        resource_type="auth_users",
        resource_id=str(user_id),
        outcome="success",
        detail=f"Set role -> {body.role}",
        actor=user,
    )
    return {"updated": True, "user": updated}


@admin_router.get("/audit-logs")
def admin_get_audit_logs(
    limit: int = 100,
    user: AuthUser = Depends(require_roles("admin")),
):
    return {"logs": get_audit_logs(limit=limit)}
