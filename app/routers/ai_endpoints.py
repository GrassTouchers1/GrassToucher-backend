"""
Router API Trí tuệ Nhân tạo NorthStar AI Ecosystem.
Cung cấp các endpoint RESTful thống nhất kết nối với AI Provider Layer:
- POST /api/ai/analyze-report: Phân tích báo cáo thiên tai cộng đồng
- POST /api/ai/summarize-disaster: Tổng hợp diễn biến & đối chiếu tin đồn
- POST /api/ai/classify-emergency: Phân loại yêu cầu cứu trợ SOS khẩn cấp
- POST /api/ai/chat: Trợ lý hỏi đáp trực ban dựa trên dữ liệu thật
- GET  /api/ai/status: Kiểm tra trạng thái và năng lực AI Provider
"""

import logging
from typing import Any, Optional
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field

from .. import config
from ..schemas import SOSCreate
from .sos import create_sos_beacon
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


# ==============================================================================
# 6. Cấp cứu Bằng Giọng nói AI Đa phương thức (AI Voice Emergency SOS)
# ==============================================================================
async def transcribe_audio_groq(audio_bytes: bytes, content_type: str = "audio/webm") -> Optional[str]:
    """Chuyển âm thanh giọng nói tiếng Việt thành văn bản bằng Groq Whisper LPU."""
    api_key = config.GROQ_API_KEY
    if not api_key:
        return None

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    ext = "webm"
    if "wav" in content_type:
        ext = "wav"
    elif "mp4" in content_type or "m4a" in content_type:
        ext = "m4a"
    elif "ogg" in content_type:
        ext = "ogg"

    files = {"file": (f"emergency_voice.{ext}", audio_bytes, content_type or "audio/webm")}
    data = {"model": "whisper-large-v3-turbo", "language": "vi", "response_format": "json"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, headers=headers, files=files, data=data)
            if res.status_code == 200:
                data_json = res.json()
                return data_json.get("text", "").strip()
            else:
                logging.getLogger("northstar.ai.whisper").warning("Whisper API error: %s - %s", res.status_code, res.text[:200])
    except Exception as e:
        logging.getLogger("northstar.ai.whisper").error("Whisper transcription failed: %s", e)
    return None


VIETNAM_LOCATION_COORDS = {
    "thái nguyên": (21.5928, 105.8442, "TP. Thái Nguyên"),
    "hoàng văn thụ": (21.5928, 105.8442, "Đường Hoàng Văn Thụ, Thái Nguyên"),
    "quang vinh": (21.6020, 105.8350, "Phường Quang Vinh, Thái Nguyên"),
    "chùa hang": (21.6150, 105.8650, "Phường Chùa Hang, Thái Nguyên"),
    "gia bẩy": (21.5980, 105.8500, "Cầu Gia Bảy, Thái Nguyên"),
    "sông cầu": (21.5928, 105.8442, "Lưu vực Sông Cầu, Thái Nguyên"),
    "làng nủ": (22.3167, 104.3833, "Thôn Làng Nủ, Bảo Yên, Lào Cai"),
    "bảo yên": (22.2850, 104.3420, "Huyện Bảo Yên, Lào Cai"),
    "phố ràng": (22.2850, 104.3420, "TT. Phố Ràng, Lào Cai"),
    "lào cai": (22.4856, 103.9707, "TP. Lào Cai"),
    "yên bái": (21.7167, 104.8833, "TP. Yên Bái"),
    "hồng hà": (21.7167, 104.8833, "Phường Hồng Hà, Yên Bái"),
    "sông thao": (21.7167, 104.8833, "Ven sông Thao, Yên Bái"),
    "cầu giấy": (21.0370, 105.7800, "Quận Cầu Giấy, Hà Nội"),
    "hoa bằng": (21.0220, 105.7950, "Phố Hoa Bằng, Cầu Giấy"),
    "yên hòa": (21.0210, 105.7940, "Phường Yên Hòa, Cầu Giấy"),
    "chương mỹ": (20.8920, 105.6580, "Huyện Chương Mỹ, Hà Nội"),
    "nam phương tiến": (20.8920, 105.6580, "Xã Nam Phương Tiến, Chương Mỹ"),
    "sông bùi": (20.8920, 105.6580, "Ven Sông Bùi, Chương Mỹ"),
    "nam từ liêm": (21.0120, 105.7650, "Quận Nam Từ Liêm, Hà Nội"),
    "bắc từ liêm": (21.0650, 105.7550, "Quận Bắc Từ Liêm, Hà Nội"),
    "ba đình": (21.0340, 105.8250, "Quận Ba Đình, Hà Nội"),
    "đống đa": (21.0180, 105.8280, "Quận Đống Đa, Hà Nội"),
    "hoàn kiếm": (21.0285, 105.8542, "Quận Hoàn Kiếm, Hà Nội"),
    "phong châu": (21.3117, 105.2890, "Cầu Phong Châu, Phú Thọ"),
    "phú thọ": (21.3117, 105.2890, "Tỉnh Phú Thọ"),
    "tam nông": (21.3117, 105.2890, "Huyện Tam Nông, Phú Thọ"),
    "tuyên quang": (21.8200, 105.2200, "TP. Tuyên Quang"),
    "chiêm hóa": (22.1500, 105.2600, "Huyện Chiêm Hóa, Tuyên Quang"),
    "hạ long": (20.9500, 107.0800, "TP. Hạ Long, Quảng Ninh"),
    "cát hải": (20.8000, 106.9100, "Huyện Cát Hải, Hải Phòng"),
    "hiệp hòa": (21.3200, 106.0500, "Huyện Hiệp Hòa, Bắc Giang"),
    "nguyên bình": (22.6100, 105.9700, "Huyện Nguyên Bình, Cao Bằng")
}

def resolve_sos_coordinates(transcript: str, client_lat: float, client_lng: float) -> tuple[float, float, Optional[str]]:
    """Tự động nhận diện và nắn chỉnh tọa độ chính xác dựa theo lời kêu cứu giọng nói."""
    t_lower = (transcript or "").lower()
    for name, (target_lat, target_lng, label) in VIETNAM_LOCATION_COORDS.items():
        if name in t_lower:
            return target_lat, target_lng, label
    return client_lat, client_lng, None


class VoiceTextSOSRequest(BaseModel):
    transcript: str = Field(..., min_length=2, description="Nội dung lời kêu cứu đã được nhận diện từ giọng nói")
    lat: float = Field(21.0285, description="Vĩ độ GPS người kêu cứu")
    lng: float = Field(105.8542, description="Kinh độ GPS người kêu cứu")
    contact_name: Optional[str] = Field("Nạn nhân Voice SOS", description="Tên liên hệ nếu có")
    contact_phone: Optional[str] = Field("0999999999", description="Số điện thoại liên hệ")
    auto_create_beacon: bool = Field(True, description="Tự động ghim điểm SOS lên bản đồ tác chiến")


@router.post(
    "/voice-sos/transcribe",
    summary="Chuyển giọng nói sang văn bản siêu tốc (Groq Whisper LPU)",
    description="Nhận tệp âm thanh tiếng Việt và trả về văn bản để nạn nhân xem lại và chỉnh sửa trước khi bấm gửi cứu hộ."
)
async def transcribe_emergency_audio(request: Request) -> dict[str, Any]:
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Tệp âm thanh trống hoặc không hợp lệ")

    content_type = request.headers.get("content-type", "audio/webm")
    transcript = await transcribe_audio_groq(audio_bytes, content_type)
    if not transcript:
        return {
            "status": "warning",
            "message": "Không nhận diện được giọng nói qua Whisper. Bạn có thể tự gõ nội dung vào ô văn bản bên dưới.",
            "transcript": ""
        }

    return {
        "status": "success",
        "transcript": transcript,
        "provider_used": "groq (whisper-large-v3-turbo)"
    }


@router.post(
    "/voice-sos",
    summary="Cấp cứu khẩn cấp bằng giọng nói trực tiếp (Groq Whisper + LLM Auto-Dispatch)",
    description="Nhận tệp âm thanh tiếng Việt, chuyển âm thanh sang văn bản siêu tốc bằng Whisper LPU, bóc tách thực thể và tự động cắm mốc cứu hộ trên bản đồ."
)
async def process_voice_sos_audio(
    request: Request,
    lat: float = Query(21.0285),
    lng: float = Query(105.8542),
    contact_name: Optional[str] = Query("Nạn nhân Voice SOS"),
    contact_phone: Optional[str] = Query("0999999999"),
    auto_create_beacon: bool = Query(True),
    ai: AIProvider = Depends(get_ai_provider)
) -> dict[str, Any]:
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Tệp âm thanh trống hoặc không hợp lệ")

    content_type = request.headers.get("content-type", "audio/webm")
    transcript = await transcribe_audio_groq(audio_bytes, content_type)

    provider_used = "groq (whisper-large-v3-turbo)"
    if not transcript:
        return {
            "status": "warning",
            "message": "Không thể giải mã giọng nói qua Whisper Cloud. Vui lòng thử lại hoặc sử dụng nhận diện cục bộ.",
            "transcript": "",
            "provider_used": "offline_fallback"
        }

    # Bóc tách ngữ nghĩa cứu hộ bằng LLM
    resolved_lat, resolved_lng, loc_label = resolve_sos_coordinates(transcript, lat, lng)
    loc_desc = loc_label if loc_label else f"Tọa độ GPS ({resolved_lat:.4f}, {resolved_lng:.4f})"
    classification = await ai.classify_emergency(
        message=transcript,
        contact_phone=contact_phone,
        location_text=loc_desc
    )

    created_beacon = None
    if auto_create_beacon:
        has_vulnerable = bool(len(classification.vulnerable_groups) > 0)
        prio = classification.urgency.lower()
        if prio not in ["low", "medium", "high", "critical"]:
            prio = "high"

        sos_body = SOSCreate(
            contact_name=(contact_name or "Nạn nhân Voice SOS")[:50],
            phone=(contact_phone or "0999999999")[:20],
            lat=resolved_lat,
            lng=resolved_lng,
            people_count=max(1, min(100, classification.people_affected or 1)),
            has_elderly_or_children=has_vulnerable,
            water_level_cm=45.0 if prio in ["high", "critical"] else 20.0,
            priority=prio,
            notes=f"🎙️ [Voice SOS - {loc_desc}]: {transcript}"[:480]
        )
        created_beacon = create_sos_beacon(sos_body)

    return {
        "status": "success",
        "transcript": transcript,
        "resolved_lat": resolved_lat,
        "resolved_lng": resolved_lng,
        "location_label": loc_label,
        "classification": classification.model_dump(),
        "beacon": created_beacon,
        "provider_used": f"{provider_used} + {classification.provider_used}",
        "emergency_hotlines": [
            {"name": "Tổng đài Cứu nạn PCTT", "phone": "114", "label": "Gọi 114"},
            {"name": "Cấp cứu Y tế", "phone": "115", "label": "Gọi 115"},
            {"name": "Tìm kiếm Cứu nạn Quốc gia", "phone": "112", "label": "Gọi 112"}
        ]
    }


@router.post(
    "/voice-sos/text",
    summary="Cấp cứu khẩn cấp từ văn bản giọng nói (Web Speech API Client-side)",
    description="Dành cho chế độ nhận diện giọng nói trực tiếp trên trình duyệt hoặc khi mạng yếu."
)
async def process_voice_sos_text(
    req: VoiceTextSOSRequest,
    ai: AIProvider = Depends(get_ai_provider)
) -> dict[str, Any]:
    resolved_lat, resolved_lng, loc_label = resolve_sos_coordinates(req.transcript, req.lat, req.lng)
    loc_desc = loc_label if loc_label else f"Tọa độ GPS ({resolved_lat:.4f}, {resolved_lng:.4f})"
    classification = await ai.classify_emergency(
        message=req.transcript,
        contact_phone=req.contact_phone,
        location_text=loc_desc
    )

    created_beacon = None
    if req.auto_create_beacon:
        has_vulnerable = bool(len(classification.vulnerable_groups) > 0)
        prio = classification.urgency.lower()
        if prio not in ["low", "medium", "high", "critical"]:
            prio = "high"

        sos_body = SOSCreate(
            contact_name=(req.contact_name or "Nạn nhân Voice SOS")[:50],
            phone=(req.contact_phone or "0999999999")[:20],
            lat=resolved_lat,
            lng=resolved_lng,
            people_count=max(1, min(100, classification.people_affected or 1)),
            has_elderly_or_children=has_vulnerable,
            water_level_cm=45.0 if prio in ["high", "critical"] else 20.0,
            priority=prio,
            notes=f"🎙️ [Voice SOS - {loc_desc}]: {req.transcript}"[:480]
        )
        created_beacon = create_sos_beacon(sos_body)

    return {
        "status": "success",
        "transcript": req.transcript,
        "resolved_lat": resolved_lat,
        "resolved_lng": resolved_lng,
        "location_label": loc_label,
        "classification": classification.model_dump(),
        "beacon": created_beacon,
        "provider_used": f"WebSpeech + {classification.provider_used}",
        "emergency_hotlines": [
            {"name": "Tổng đài Cứu nạn PCTT", "phone": "114", "label": "Gọi 114"},
            {"name": "Cấp cứu Y tế", "phone": "115", "label": "Gọi 115"},
            {"name": "Tìm kiếm Cứu nạn Quốc gia", "phone": "112", "label": "Gọi 112"}
        ]
    }
