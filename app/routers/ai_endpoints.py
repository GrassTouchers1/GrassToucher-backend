"""
Router API Trí tuệ Nhân tạo NorthStar AI Ecosystem.
Cung cấp các endpoint RESTful thống nhất kết nối với AI Provider Layer:
- POST /api/ai/analyze-report: Phân tích báo cáo thiên tai cộng đồng
- POST /api/ai/summarize-disaster: Tổng hợp diễn biến & đối chiếu tin đồn
- POST /api/ai/classify-emergency: Phân loại yêu cầu cứu trợ SOS khẩn cấp
- POST /api/ai/chat: Trợ lý hỏi đáp trực ban dựa trên dữ liệu thật
- GET  /api/ai/status: Kiểm tra trạng thái và năng lực AI Provider
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..ai.base import AIProvider
from ..ai.factory import get_ai_provider
from ..ai.schemas import (
    ReportAnalysisRequest,
    ReportAnalysisResult,
    DisasterSummaryRequest,
    DisasterSummaryResult,
    EmergencyClassificationRequest,
    EmergencyClassificationResult,
    AIChatRequest,
    AIChatResult,
    ProviderStatusResult,
)
from .flood_points import DEFAULT_FLOOD_POINTS
from .shelters import list_shelters
from ..fallback_storage import get_fallback_reports

router = APIRouter(prefix="/api/ai", tags=["Trí tuệ Nhân tạo (NorthStar AI Provider)"])


def get_backend_live_context() -> dict[str, Any]:
    """Tổng hợp dữ liệu trạm đo và trạm sơ tán thời gian thực làm context cho AI."""
    shelters_data = list_shelters()
    shelter_features = shelters_data.get("features", []) if isinstance(shelters_data, dict) else []
    return {
        "flood_points": DEFAULT_FLOOD_POINTS,
        "shelters": shelter_features,
    }


# ==============================================================================
# 1. Phân tích báo cáo thiên tai (Disaster Report Analysis)
# ==============================================================================
@router.post(
    "/analyze-report",
    response_model=ReportAnalysisResult,
    summary="Phân tích ngữ nghĩa báo cáo thiên tai và trích xuất thực thể",
    description="Nhận diện loại thiên tai, địa bàn, thời gian, mức độ khẩn cấp và thông tin còn thiếu."
)
async def analyze_disaster_report(
    req: ReportAnalysisRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> ReportAnalysisResult:
    try:
        return await ai.analyze_report(
            content=req.content,
            source=req.source,
            reporter=req.reporter
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi phân tích báo cáo: {str(e)}")


# ==============================================================================
# 2. Tổng hợp thông tin thiên tai (Disaster Information Summarization)
# ==============================================================================
@router.post(
    "/summarize-disaster",
    response_model=DisasterSummaryResult,
    summary="Tổng hợp diễn biến thiên tai và đối chiếu thông tin đa nguồn",
    description="Tổng hợp các báo cáo hiện trường, tóm tắt xu thế đỉnh lũ và lọc tin đồn chưa kiểm chứng."
)
async def summarize_disaster_info(
    req: DisasterSummaryRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> DisasterSummaryResult:
    try:
        reports = req.reports
        if not reports:
            # Lấy báo cáo thực tế từ fallback storage nếu không truyền vào
            reports = get_fallback_reports()

        return await ai.summarize_disaster(
            region=req.region,
            reports=reports,
            time_window_hours=req.time_window_hours
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tổng hợp thông tin thiên tai: {str(e)}")


# ==============================================================================
# 3. Phân loại yêu cầu cứu trợ khẩn cấp (Rescue Information Classification)
# ==============================================================================
@router.post(
    "/classify-emergency",
    response_model=EmergencyClassificationResult,
    summary="Phân loại yêu cầu cứu hộ và bóc tách nhu cầu nạn nhân",
    description="Nhận diện các nhu cầu cấp thiết (sơ tán, lương thực, nước sạch, y tế, xuồng máy) và nhóm dễ tổn thương."
)
async def classify_emergency_request(
    req: EmergencyClassificationRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> EmergencyClassificationResult:
    try:
        return await ai.classify_emergency(
            message=req.message,
            contact_phone=req.contact_phone,
            location_text=req.location_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi phân loại yêu cầu cứu trợ: {str(e)}")


# ==============================================================================
# 4. Trợ lý Trực ban Cứu hộ Thời gian thực (Emergency Assistant Chat)
# ==============================================================================
@router.post(
    "/chat",
    response_model=AIChatResult,
    summary="Hỏi đáp thời gian thực với Trợ lý Trực ban Thiên tai",
    description="Tư vấn lộ trình an toàn, trạm sơ tán và kỹ năng sinh tồn dựa trên dữ liệu thật."
)
async def chat_with_ai(
    req: AIChatRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> AIChatResult:
    try:
        context = get_backend_live_context() if req.include_live_context else {}
        return await ai.chat(
            query=req.query,
            conversation_history=req.conversation_history,
            context=context,
            lat=req.lat,
            lng=req.lng
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi trao đổi với trợ lý AI: {str(e)}")


# ==============================================================================
# 5. Kiểm tra Trạng thái AI Provider (Status)
# ==============================================================================
@router.get(
    "/status",
    response_model=ProviderStatusResult,
    summary="Kiểm tra trạng thái kết nối và khả năng phục vụ của AI Provider",
    description="Báo cáo tình trạng Groq Cloud API, mô hình LLaMA, hoặc chế độ ngoại tuyến Fallback."
)
async def check_ai_status(
    ai: AIProvider = Depends(get_ai_provider)
) -> ProviderStatusResult:
    return await ai.get_status()


# ==============================================================================
# Tương thích ngược: POST /api/ai/assistant
# ==============================================================================
class LegacyChatRequest(BaseModel):
    message: str = Field(..., description="Câu hỏi hoặc yêu cầu cứu hộ")
    lat: Optional[float] = None
    lng: Optional[float] = None

@router.post("/assistant", summary="Hỏi đáp trợ lý AI (Endpoint tương thích ngược)")
async def legacy_assistant_chat(
    req: LegacyChatRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> dict[str, Any]:
    context = get_backend_live_context()
    res = await ai.chat(query=req.message, context=context, lat=req.lat, lng=req.lng)
    return {
        "status": "success",
        "reply": res.reply,
        "suggested_actions": [a.model_dump() for a in res.suggested_actions],
        "provider_used": res.provider_used,
        "is_fallback": res.is_fallback
    }
