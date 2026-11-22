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
Pydantic Schemas cho AI Provider Layer.
Định nghĩa cấu trúc dữ liệu đầu vào và đầu ra chuẩn hóa cho toàn bộ chức năng AI.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# 1. Schemas cho Phân tích Báo cáo Thiên tai (Disaster Report Analysis)
# ==============================================================================

class ReportAnalysisRequest(BaseModel):
    content: str = Field(..., min_length=3, description="Nội dung báo cáo thiên tai từ cộng đồng hoặc truyền thông")
    source: Optional[str] = Field("community", description="Nguồn tin: community, social_media, field_worker, news")
    reporter: Optional[str] = Field(None, description="Tên hoặc định danh người gửi")


class LocationExtracted(BaseModel):
    province: Optional[str] = Field(None, description="Tỉnh/Thành phố")
    district: Optional[str] = Field(None, description="Quận/Huyện/Thị xã")
    ward_or_street: Optional[str] = Field(None, description="Phường/Xã hoặc tên tuyến đường/thôn xóm")
    lat: Optional[float] = Field(None, description="Vĩ độ dự đoán nếu có")
    lng: Optional[float] = Field(None, description="Kinh độ dự đoán nếu có")


class ReportAnalysisResult(BaseModel):
    disaster_type: str = Field(..., description="Loại thiên tai: ngập lụt, lũ quét, sạt lở, bão, triều cường, khác")
    location: LocationExtracted = Field(..., description="Địa điểm trích xuất được")
    time_occurred: Optional[str] = Field(None, description="Thời gian xảy ra trích xuất được từ báo cáo")
    missing_info: list[str] = Field(default_factory=list, description="Các thông tin quan trọng còn thiếu (độ sâu, số người, v.v.)")
    urgency_level: str = Field("medium", description="Mức độ khẩn cấp sơ bộ: low, medium, high, critical")
    raw_summary: str = Field(..., description="Tóm tắt ngắn gọn nội dung báo cáo trong 1-2 câu")
    confidence_score: float = Field(0.85, description="Độ tin cậy của phân tích (0.0 đến 1.0)")
    provider_used: str = Field("mock", description="AI Provider đã thực thi: groq hoặc mock_offline")
    is_fallback: bool = Field(False, description="Cờ đánh dấu có phải kết quả từ fallback ngoại tuyến không")


# ==============================================================================
# 2. Schemas cho Tổng hợp Thông tin Thiên tai (Disaster Info Summarization)
# ==============================================================================

class DisasterSummaryRequest(BaseModel):
    region: Optional[str] = Field(None, description="Khu vực hoặc tỉnh thành cần tổng hợp (ví dụ: 'Thái Nguyên', 'Toàn Miền Bắc')")
    reports: Optional[list[dict[str, Any]]] = Field(None, description="Danh sách báo cáo đầu vào (nếu không có sẽ lấy từ hệ thống)")
    time_window_hours: int = Field(24, ge=1, le=168, description="Cửa sổ thời gian tổng hợp (giờ)")


class GroupedDisasterCategory(BaseModel):
    category_name: str = Field(..., description="Nhóm thiên tai (ví dụ: Ngập úng đô thị, Lũ quét vùng cao, Sự cố giao thông)")
    count: int = Field(..., description="Số lượng báo cáo thuộc nhóm")
    hotspots: list[str] = Field(default_factory=list, description="Các địa danh điểm nóng tiêu biểu")


class DisasterSummaryResult(BaseModel):
    region: str = Field(..., description="Khu vực tổng hợp")
    time_window_str: str = Field(..., description="Khoảng thời gian tổng hợp")
    summary: str = Field(..., description="Tóm tắt tổng quan diễn biến thiên tai")
    progression_trend: str = Field(..., description="Xu thế diễn biến (đang tăng nhanh, đạt đỉnh, đang rút chậm, v.v.)")
    grouped_reports: list[GroupedDisasterCategory] = Field(default_factory=list, description="Phân nhóm báo cáo có nội dung tương đồng")
    conflicts_or_unverified: list[str] = Field(default_factory=list, description="Các thông tin mâu thuẫn hoặc chưa được xác minh")
    overall_risk_level: str = Field("medium", description="Mức độ rủi ro tổng thể: low, medium, high, critical")
    provider_used: str = Field("mock")
    is_fallback: bool = Field(False)


# ==============================================================================
# 3. Schemas cho Phân loại Yêu cầu Cứu trợ (Rescue Information Classification)
# ==============================================================================

class EmergencyClassificationRequest(BaseModel):
    message: str = Field(..., min_length=3, description="Nội dung lời kêu cứu / tin nhắn SOS từ người dân")
    contact_phone: Optional[str] = Field(None, description="Số điện thoại liên hệ")
    location_text: Optional[str] = Field(None, description="Địa chỉ hoặc mô tả vị trí người gặp nạn")


class EmergencyClassificationResult(BaseModel):
    needs: list[str] = Field(
        default_factory=list,
        description="Các nhu cầu nhận diện được: sơ tán, thực phẩm, nước sạch, y tế khẩn cấp, xuồng cứu hộ, an toàn điện, phao cứu sinh"
    )
    people_affected: int = Field(1, description="Số người bị ảnh hưởng / mắc kẹt ước tính")
    vulnerable_groups: list[str] = Field(
        default_factory=list,
        description="Nhóm đối tượng dễ bị tổn thương: trẻ nhỏ, người già, phụ nữ mang thai, người khuyết tật/ốm đau"
    )
    urgency: str = Field("high", description="Mức độ ưu tiên điều phối: low, medium, high, critical")
    recommended_action: str = Field(..., description="Đề xuất hành động tức thời cho đội cứu hộ phản ứng nhanh")
    structured_json: dict[str, Any] = Field(default_factory=dict, description="Bản ghi có cấu trúc phục vụ lưu trữ CSDL")
    provider_used: str = Field("mock")
    is_fallback: bool = Field(False)


# ==============================================================================
# 4. Schemas cho Trợ lý Trực ban Cứu hộ (Emergency Assistant Chat)
# ==============================================================================

class AIChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Câu hỏi hoặc yêu cầu cứu nạn của người dùng")
    conversation_history: Optional[list[dict[str, str]]] = Field(None, description="Lịch sử hội thoại trước đó (nếu có)")
    lat: Optional[float] = Field(None, description="Vĩ độ hiện tại của người dùng")
    lng: Optional[float] = Field(None, description="Kinh độ hiện tại của người dùng")
    include_live_context: bool = Field(True, description="Đính kèm dữ liệu trạm đo, trạm sơ tán thời gian thực từ Backend")


class SuggestedAction(BaseModel):
    label: str = Field(..., description="Nhãn hiển thị trên nút bấm")
    action: str = Field(..., description="Hành động kích hoạt: switch_tab, open_sos, zoom_to, call_hotline")
    tab: Optional[str] = Field(None, description="Tab cần chuyển nếu action=switch_tab")
    phone: Optional[str] = Field(None, description="Số điện thoại gọi nếu action=call_hotline")


class AIChatResult(BaseModel):
    reply: str = Field(..., description="Câu trả lời tự nhiên, chính xác, dựa trên dữ liệu thật của Backend")
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, description="Các nút tương tác nhanh gợi ý cho người dùng")
    sources_consulted: list[str] = Field(default_factory=list, description="Danh mục nguồn dữ liệu backend đã đối chiếu")
    provider_used: str = Field("mock")
    is_fallback: bool = Field(False)


# ==============================================================================
# 5. Schema cho Trạng thái AI Provider (Status)
# ==============================================================================

class ProviderStatusResult(BaseModel):
    enabled: bool = Field(..., description="Trạng thái bật/tắt toàn hệ thống AI")
    configured_provider: str = Field(..., description="Provider được cấu hình trong biến môi trường (groq, mock, v.v.)")
    active_provider: str = Field(..., description="Provider đang hoạt động thực tế")
    model: str = Field(..., description="Tên mô hình đang sử dụng")
    status: str = Field(..., description="Trạng thái: online, offline_fallback, disabled")
    is_fallback_active: bool = Field(..., description="Có đang trong trạng thái fallback ngoại tuyến không")
    capabilities: list[str] = Field(default_factory=list, description="Danh sách năng lực AI đang hỗ trợ")
    message: str = Field(..., description="Thông báo chi tiết về tình trạng hoạt động")


# ==============================================================================
# 6. Schemas cho Phân loại & Điều phối Yêu cầu Cứu trợ (Relief Request Triage - Qwen3-8B)
# ==============================================================================

class ReliefRequestCreate(BaseModel):
    """Đầu vào yêu cầu cứu trợ từ người dân (tin nhắn, transcript cuộc gọi, form SOS)."""
    message: str = Field(..., min_length=2, description="Nội dung người dân cung cấp hoặc bản ghi âm chuyển chữ")
    contact_name: Optional[str] = Field(None, description="Tên người liên hệ nếu có")
    phone: Optional[str] = Field(None, description="Số điện thoại liên hệ nếu có")
    location_text: Optional[str] = Field(None, description="Mô tả địa chỉ/vị trí người dân cung cấp")
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Vĩ độ nếu có GPS")
    lng: Optional[float] = Field(None, ge=-180, le=180, description="Kinh độ nếu có GPS")
    source: Optional[str] = Field("community", description="Nguồn: community, hotline_114, sms_sos, citizen_app")
    request_id: Optional[str] = Field(None, description="Mã yêu cầu (nếu đã có)")


class ReliefExtractedData(BaseModel):
    """Dữ liệu có cấu trúc do AI trích xuất (phân biệt rõ sự thật người dân cấp và AI suy luận)."""
    request_id: str = Field(..., description="Mã định danh yêu cầu cứu trợ")
    location_text: Optional[str] = Field(None, description="Địa chỉ nhận diện được")
    lat: Optional[float] = Field(None, description="Vĩ độ")
    lng: Optional[float] = Field(None, description="Kinh độ")
    province: Optional[str] = Field(None, description="Tỉnh/Thành phố")
    district: Optional[str] = Field(None, description="Quận/Huyện")
    ward: Optional[str] = Field(None, description="Phường/Xã/Thôn xóm")
    timestamp: Optional[str] = Field(None, description="Thời gian gửi hoặc thời điểm sự cố")
    people_count: Optional[int] = Field(None, description="Số người gặp nạn (chính xác hoặc ước tính)")
    water_level_m: Optional[float] = Field(None, description="Mực nước hiện tại theo mét (VD: 1.5)")
    water_trend: str = Field("unknown", description="Xu hướng mực nước: rising (đang dâng), stable (ổn định), receding (đang rút), unknown")
    vulnerable_people: list[str] = Field(
        default_factory=list,
        description="Người cần hỗ trợ đặc biệt: children, elderly, disabled, pregnant, medical_patient, infant"
    )
    medical_emergency: bool = Field(False, description="Tình trạng cấp cứu y tế hoặc chấn thương nghiêm trọng")
    immediate_danger: bool = Field(False, description="Nguy hiểm tức thời đe dọa tính mạng (sắp chìm, sập nhà, lũ xiết)")
    mobility_status: str = Field("unknown", description="Khả năng tự thoát hiểm: trapped_roof, trapped_attic, isolated, cannot_move, can_walk, unknown")
    relief_needs: list[str] = Field(
        default_factory=list,
        description="Nhu cầu: boat_evacuation, food_water, medical_kit, lifejacket, rope, shelter"
    )
    contact_name: Optional[str] = Field(None, description="Tên người báo")
    contact_phone: Optional[str] = Field(None, description="Số điện thoại")
    citizen_reported_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Thông tin tường minh do người dân trực tiếp cung cấp"
    )
    ai_inferred_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Thông tin do AI suy luận/ước tính dựa trên ngữ cảnh"
    )
    raw_ai_priority: str = Field("P3", description="Mức ưu tiên ban đầu do AI đề xuất: P1, P2, P3, P4")
    ai_priority_reasons: list[str] = Field(default_factory=list, description="Lý do AI đề xuất mức ưu tiên")
    missing_information: list[str] = Field(default_factory=list, description="Các trường quan trọng còn thiếu")
    conflicting_information: list[str] = Field(default_factory=list, description="Mâu thuẫn phát hiện trong nội dung")


class ReliefVerificationResult(BaseModel):
    """Kết quả kiểm tra dữ liệu và phân biệt cấp độ xác minh."""
    is_structurally_valid: bool = Field(True, description="Hợp lệ về cấu trúc JSON và kiểu dữ liệu")
    has_valid_coords: bool = Field(False, description="Toạ độ hợp lệ trong phạm vi địa lý")
    has_valid_people_count: bool = Field(False, description="Số lượng người hợp lệ (> 0)")
    has_valid_water_level: bool = Field(False, description="Mực nước hợp lệ về kiểu dữ liệu và đơn vị mét")
    has_valid_timestamp: bool = Field(True, description="Thời gian hợp lệ")
    is_duplicate: bool = Field(False, description="Phát hiện trùng lặp với yêu cầu khác")
    duplicate_of_id: Optional[str] = Field(None, description="ID của yêu cầu trùng lặp nếu có")
    conflicts_detected: list[str] = Field(default_factory=list, description="Danh sách mâu thuẫn được xác định")
    verification_status: str = Field(
        "needs_verification",
        description="Cấp độ xác minh: structurally_valid, source_verified, content_verified, needs_verification, unverified"
    )
    verification_notes: list[str] = Field(default_factory=list, description="Ghi chú xác minh từ hệ thống")


class ReliefAuditEntry(BaseModel):
    """Nhật ký thay đổi mức ưu tiên phục vụ truy vết điều phối."""
    timestamp: str
    actor: str = Field(..., description="Người thực hiện: ai_engine, business_guardrails, hoặc tên điều phối viên")
    action: str = Field(..., description="Hành động: created, rule_override, dispatcher_override, status_change")
    old_priority: Optional[str] = None
    new_priority: Optional[str] = None
    reason: Optional[str] = None


class ReliefTriageResult(BaseModel):
    """Kết quả phân loại toàn diện kết hợp AI, Guardrails nghiệp vụ và Kiểm tra xác minh."""
    request_id: str = Field(..., description="Mã yêu cầu cứu trợ")
    extracted: ReliefExtractedData = Field(..., description="Dữ liệu trích xuất chuẩn hóa")
    verification: ReliefVerificationResult = Field(..., description="Đánh giá xác minh dữ liệu")
    final_priority: str = Field("P3", description="Mức ưu tiên cuối cùng: P1 (Nguy hiểm tức thời), P2 (Nguy cơ cao), P3 (Cần cứu trợ), P4 (Theo dõi)")
    priority_reasons: list[str] = Field(default_factory=list, description="Các lý do dẫn đến mức ưu tiên cuối cùng")
    guardrails_applied: list[str] = Field(default_factory=list, description="Bộ quy tắc nghiệp vụ đã kích hoạt")
    was_downgrade_prevented: bool = Field(False, description="Đã kích hoạt cơ chế chống hạ mức ưu tiên sai")
    requires_human_review: bool = Field(True, description="Yêu cầu người điều phối kiểm tra trước khi xuất quân")
    confidence_score: float = Field(0.85, description="Độ tin cậy tổng hợp")
    status: str = Field("awaiting_dispatch", description="Trạng thái: awaiting_dispatch, dispatched, on_scene, rescued, needs_verification, cancelled")
    created_at: str = Field(..., description="Thời điểm tiếp nhận")
    updated_at: str = Field(..., description="Thời điểm cập nhật gần nhất")
    override_history: list[ReliefAuditEntry] = Field(default_factory=list, description="Lịch sử điều chỉnh mức ưu tiên")
    provider_used: str = Field("qwen3-8b", description="AI Provider thực thi: qwen3-8b hoặc mock_offline")
    is_fallback: bool = Field(False, description="Kết quả có chạy qua fallback ngoại tuyến không")


class ReliefPriorityOverrideRequest(BaseModel):
    """Yêu cầu người điều phối thay đổi mức ưu tiên."""
    new_priority: str = Field(..., description="Mức ưu tiên mới: P1, P2, P3, P4")
    dispatcher_name: str = Field(..., min_length=2, description="Tên hoặc mã định danh của người điều phối")
    reason: str = Field(..., min_length=3, description="Lý do xác nhận hoặc điều chỉnh mức ưu tiên")

