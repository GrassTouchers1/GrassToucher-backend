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
