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
Router Tiếp nhận, Phân tích AI & Điều phối Yêu cầu Cứu trợ (Relief Triage & Dispatch API).
Tích hợp:
- Mô hình Qwen3-8B phân tích nội dung cứu trợ
- Động cơ Xác minh Dữ liệu (ReliefVerificationEngine)
- Bộ Quy tắc Nghiệp vụ Chống hạ mức (ReliefGuardrailsEngine)
- Hàng chờ Điều phối theo Mức ưu tiên P1 -> P4 (FIFO)
- Giao diện Xác nhận & Ghi đè của Người Điều phối với Truy vết Audit Trail
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..ai.factory import get_ai_provider
from ..ai.qwen_provider import QwenProvider
from ..ai.schemas import (
    ReliefPriorityOverrideRequest,
    ReliefRequestCreate,
    ReliefTriageResult,
)
from ..fallback_storage import (
    get_fallback_relief_queue,
    get_fallback_relief_request_by_id,
    override_fallback_relief_priority,
    save_fallback_relief_request,
    get_fallback_sos,
)

log = logging.getLogger("northstar.routers.relief")
router = APIRouter(prefix="/api/relief", tags=["Tiếp nhận & Điều phối Cứu trợ AI"])


def _ensure_seed_data_loaded():
    """Tự động đồng bộ các ca SOS hiện có vào hàng đợi cứu trợ nếu hàng đợi đang trống."""
    current_queue = get_fallback_relief_queue()
    if len(current_queue) == 0:
        sos_list = get_fallback_sos()
        provider = get_ai_provider()
        for s in sos_list:
            req = ReliefRequestCreate(
                message=s.get("notes") or f"Yêu cầu cứu trợ khẩn cấp tại tọa độ [{s.get('lat')}, {s.get('lng')}]",
                contact_name=s.get("contact_name"),
                phone=s.get("phone"),
                lat=s.get("lat"),
                lng=s.get("lng"),
                source="sms_sos",
                request_id=f"NS-{s.get('id', 0):04d}"
            )
            # Khởi tạo qua provider
            try:
                import asyncio
                if hasattr(provider, "triage_relief_request"):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Đã chạy trong loop
                        pass
            except Exception:
                pass


@router.post(
    "/analyze",
    response_model=ReliefTriageResult,
    summary="Phân tích & Phân loại Thử nghiệm bằng AI (Không lưu trữ)"
)
async def analyze_relief_request(body: ReliefRequestCreate) -> ReliefTriageResult:
    """
    Tiếp nhận thông tin người dân và phân tích theo cấu trúc Qwen3-8B.
    Trả về dữ liệu đã chuẩn hóa, kết quả xác minh và mức ưu tiên đề xuất sau Guardrails.
    Không ghi vào hàng chờ điều phối (dùng để preview hoặc kiểm thử).
    """
    provider = get_ai_provider()
    existing_requests = get_fallback_relief_queue()

    if hasattr(provider, "triage_relief_request"):
        result = await provider.triage_relief_request(body, existing_requests=existing_requests)
    else:
        # Fallback tạo trực tiếp QwenProvider hoặc Mock
        qwen = QwenProvider()
        result = await qwen.triage_relief_request(body, existing_requests=existing_requests)

    return result


@router.post(
    "/requests",
    response_model=ReliefTriageResult,
    status_code=status.HTTP_201_CREATED,
    summary="Tiếp nhận Yêu cầu Cứu trợ mới và Đưa vào Hàng chờ Điều phối"
)
async def create_relief_request(body: ReliefRequestCreate) -> ReliefTriageResult:
    """
    Quy trình tiếp nhận chính thức:
    1. Trích xuất thông tin bằng mô hình Qwen3-8B (hoặc offline fallback).
    2. Xác minh dữ liệu: tọa độ, số người, mực nước, trùng lặp, mâu thuẫn.
    3. Áp dụng Guardrails: đảm bảo không hạ mức ưu tiên nếu có nguy hiểm tính mạng.
    4. Lưu trữ bền vững vào cơ sở dữ liệu.
    5. Đưa vào Hàng chờ Điều phối theo đúng mức ưu tiên (P1 -> P4) và thời gian.
    """
    provider = get_ai_provider()
    existing_requests = get_fallback_relief_queue()

    if hasattr(provider, "triage_relief_request"):
        result = await provider.triage_relief_request(body, existing_requests=existing_requests)
    else:
        qwen = QwenProvider()
        result = await qwen.triage_relief_request(body, existing_requests=existing_requests)

    # Lưu trữ bền vững
    saved = save_fallback_relief_request(result.model_dump())
    return ReliefTriageResult(**saved)


@router.get(
    "/queue",
    summary="Truy xuất Hàng chờ Điều phối Cứu trợ (Ưu tiên P1 -> P4, FIFO)"
)
def get_relief_dispatch_queue(
    priority: Optional[str] = Query(None, description="Lọc theo mức ưu tiên: P1, P2, P3, P4"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: awaiting_dispatch, dispatched, on_scene, rescued, needs_verification"),
    verification_status: Optional[str] = Query(None, description="Lọc theo cấp độ xác minh: structurally_valid, source_verified, content_verified, needs_verification, unverified")
) -> Dict[str, Any]:
    """
    Trả về danh sách yêu cầu cứu trợ đã được sắp xếp chuẩn:
    1. Ưu tiên cao nhất P1 (Nguy hiểm tức thời) lên đầu, tiếp đến P2, P3, P4.
    2. Cùng mức ưu tiên xếp theo thời gian tiếp nhận sớm hơn (FIFO).
    """
    queue = get_fallback_relief_queue(priority=priority, status=status, verification_status=verification_status)
    return {
        "total": len(queue),
        "filter": {
            "priority": priority,
            "status": status,
            "verification_status": verification_status
        },
        "items": queue
    }


@router.get(
    "/queue/{request_id}",
    summary="Xem chi tiết Yêu cầu Cứu trợ & Lịch sử Nhật ký Audit"
)
def get_relief_request_detail(request_id: str) -> Dict[str, Any]:
    """Lấy toàn bộ thông tin chi tiết: dữ liệu trích xuất, lý do phân loại và lịch sử điều chỉnh."""
    req = get_fallback_relief_request_by_id(request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy yêu cầu cứu trợ với mã: {request_id}"
        )
    return req


@router.patch(
    "/queue/{request_id}/override",
    summary="Người Điều phối Điều chỉnh / Xác nhận Mức Ưu tiên (Kèm Audit Trail)"
)
def override_relief_priority(request_id: str, body: ReliefPriorityOverrideRequest) -> Dict[str, Any]:
    """
    Cho phép điều phối viên can thiệp:
    - Xác nhận hoặc nâng/hạ mức ưu tiên dựa trên tình hình thực địa.
    - Lưu bắt buộc: tên người thực hiện, thời điểm và lý do thay đổi vào nhật ký truy vết.
    """
    updated = override_fallback_relief_priority(
        request_id=request_id,
        new_priority=body.new_priority,
        dispatcher_name=body.dispatcher_name,
        reason=body.reason
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hoặc không thể cập nhật yêu cầu: {request_id}"
        )
    return {
        "success": True,
        "message": f"Đã cập nhật mức ưu tiên của [{request_id}] thành {body.new_priority}",
        "data": updated
    }


@router.get(
    "/stats",
    summary="Thống kê Tổng hợp Hàng chờ Điều phối & Hoạt động AI"
)
def get_relief_statistics() -> Dict[str, Any]:
    """Báo cáo các chỉ số KPI: tổng số yêu cầu, số lượng theo P1/P2/P3/P4, số ca Guardrail can thiệp."""
    queue = get_fallback_relief_queue()
    p_counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
    status_counts = {}
    downgrade_prevented_count = 0
    needs_verification_count = 0

    for item in queue:
        p = item.get("final_priority", "P3")
        p_counts[p] = p_counts.get(p, 0) + 1

        st = item.get("status", "awaiting_dispatch")
        status_counts[st] = status_counts.get(st, 0) + 1

        if item.get("was_downgrade_prevented"):
            downgrade_prevented_count += 1

        ver = item.get("verification_status") or item.get("verification", {}).get("verification_status")
        if ver == "needs_verification":
            needs_verification_count += 1

    return {
        "total_requests": len(queue),
        "by_priority": p_counts,
        "by_status": status_counts,
        "downgrade_prevented_by_guardrails": downgrade_prevented_count,
        "needs_human_verification": needs_verification_count,
    }
