"""
Groq AI Provider cho Hệ sinh thái NorthStar.
Sử dụng Groq Cloud API (mô hình LLaMA 3.3 70B hoặc Mixtral) với tốc độ xử lý suy luận cực cao (LPU Inference).
Tích hợp cơ chế tự phục hồi: Tự động chuyển tiếp sang MockAIProvider khi gặp sự cố mạng, timeout hoặc hết hạn ngạch.
Tuân thủ bảo mật: Tuyệt đối không in hoặc trả API Key ra log/response.
"""

import json
import logging
from typing import Any, Optional
import httpx

from .base import AIProvider
from .mock_provider import MockAIProvider
from .schemas import (
    ReportAnalysisResult,
    LocationExtracted,
    DisasterSummaryResult,
    GroupedDisasterCategory,
    EmergencyClassificationResult,
    AIChatResult,
    SuggestedAction,
    ProviderStatusResult,
)

logger = logging.getLogger("northstar.ai.groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(AIProvider):
    """Nhà cung cấp AI qua Groq Cloud API với khả năng fallback ngoại tuyến hoàn hảo."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout_sec: float = 12.0
    ):
        self.api_key = (api_key or "").strip()
        self.model = model or "llama-3.3-70b-versatile"
        self.timeout_sec = max(2.0, timeout_sec)
        self.fallback_engine = MockAIProvider(model_name="rule-engine-offline")

    def _has_valid_key(self) -> bool:
        return bool(self.api_key and len(self.api_key) >= 10)

    async def _call_groq_api(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> Optional[str]:
        """Thực hiện gọi API Groq bất đồng bộ qua HTTPX với timeout và xử lý ngoại lệ."""
        if not self._has_valid_key():
            logger.info("Groq API Key không được cung cấp. Chuyển sang fallback ngoại tuyến.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "NorthStar-Disaster-AI/1.0"
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(GROQ_API_URL, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                elif res.status_code in (401, 403):
                    logger.warning("Groq API xác thực thất bại (HTTP %s). Vui lòng kiểm tra GROQ_API_KEY.", res.status_code)
                elif res.status_code == 429:
                    logger.warning("Groq API bị vượt hạn mức gọi (HTTP 429 - Rate limit). Tự động fallback.")
                else:
                    logger.warning("Groq API trả về mã lỗi HTTP %s: %s", res.status_code, res.text[:200])
        except (httpx.TimeoutException, httpx.ConnectTimeout):
            logger.warning("Groq API quá thời gian phản hồi (timeout %ss). Tự động fallback sang ngoại tuyến.", self.timeout_sec)
        except (httpx.ConnectError, httpx.NetworkError) as net_err:
            logger.warning("Không thể kết nối Internet tới Groq API (%s). Kích hoạt chế độ ngoại tuyến.", type(net_err).__name__)
        except Exception as e:
            logger.error("Lỗi không xác định khi giao tiếp với Groq API: %s", str(e))

        return None

    async def analyze_report(
        self,
        content: str,
        source: Optional[str] = "community",
        reporter: Optional[str] = None
    ) -> ReportAnalysisResult:
        """1. Disaster Report Analysis: Phân tích báo cáo thiên tai có cấu trúc."""
        sys_prompt = (
            "Bạn là chuyên gia thẩm tra thông tin thiên tai thuộc Ban Chỉ huy PCTT & TKCN Việt Nam. "
            "Nhiệm vụ: Phân tích nội dung báo cáo thiên tai và trả về định dạng JSON thuần túy (không kèm giải thích markdown ngoài JSON) theo cấu trúc:\n"
            "{\n"
            '  "disaster_type": "ngập lụt | lũ quét | sạt lở đất | bão | triều cường | khác",\n'
            '  "province": "tên tỉnh/thành phố hoặc null",\n'
            '  "district": "tên quận/huyện/thị xã hoặc null",\n'
            '  "ward_or_street": "tên phường/xã/tuyến đường hoặc null",\n'
            '  "time_occurred": "thời gian xảy ra hoặc null",\n'
            '  "missing_info": ["danh sách các thông tin quan trọng còn thiếu"],\n'
            '  "urgency_level": "low | medium | high | critical",\n'
            '  "raw_summary": "Tóm tắt súc tích trong 1-2 câu",\n'
            '  "confidence_score": 0.95\n'
            "}\n"
            "NGUYÊN TẮC: Không bịa đặt địa danh hoặc số liệu không có trong nội dung."
        )

        user_content = f"Nguồn tin: {source or 'Cộng đồng'}\nNgười báo: {reporter or 'Ẩn danh'}\nNội dung: {content}"
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        raw_resp = await self._call_groq_api(messages, json_mode=True)
        if raw_resp:
            try:
                parsed = json.loads(raw_resp)
                return ReportAnalysisResult(
                    disaster_type=str(parsed.get("disaster_type", "ngập lụt")),
                    location=LocationExtracted(
                        province=parsed.get("province"),
                        district=parsed.get("district"),
                        ward_or_street=parsed.get("ward_or_street")
                    ),
                    time_occurred=parsed.get("time_occurred"),
                    missing_info=parsed.get("missing_info", []),
                    urgency_level=str(parsed.get("urgency_level", "medium")).lower(),
                    raw_summary=str(parsed.get("raw_summary", content[:120])),
                    confidence_score=float(parsed.get("confidence_score", 0.9)),
                    provider_used=f"groq ({self.model})",
                    is_fallback=False
                )
            except Exception as parse_err:
                logger.warning("Không thể parse JSON từ Groq API: %s. Chuyển fallback.", parse_err)

        # Fallback ngoại tuyến
        return await self.fallback_engine.analyze_report(content, source, reporter)

    async def summarize_disaster(
        self,
        region: Optional[str] = None,
        reports: Optional[list[dict[str, Any]]] = None,
        time_window_hours: int = 24
    ) -> DisasterSummaryResult:
        """2. Disaster Information Summarization: Tổng hợp và đối chiếu báo cáo."""
        sys_prompt = (
            "Bạn là sĩ quan tác chiến tổng hợp thông tin thiên tai tại Việt Nam. "
            "Nhiệm vụ: Tổng hợp các báo cáo hiện trường, tóm tắt diễn biến, nhóm báo cáo tương đồng, "
            "và đánh dấu các thông tin mâu thuẫn/chưa kiểm chứng. Trả về đúng JSON thuần túy:\n"
            "{\n"
            '  "summary": "Tóm tắt tổng quan 2-3 câu",\n'
            '  "progression_trend": "Xu thế diễn biến (đang tăng, đạt đỉnh, đang rút)",\n'
            '  "grouped_reports": [{"category_name": "...", "count": 12, "hotspots": ["..."]}],\n'
            '  "conflicts_or_unverified": ["danh sách tin đồn hoặc báo cáo chưa kiểm chứng"],\n'
            '  "overall_risk_level": "low | medium | high | critical"\n'
            "}"
        )

        user_content = f"Khu vực: {region or 'Toàn Miền Bắc'}\nKhoảng thời gian: {time_window_hours} giờ qua\n"
        if reports:
            user_content += f"Dữ liệu báo cáo hiện trường ({len(reports)} bản ghi):\n{json.dumps(reports[:15], ensure_ascii=False)}"
        else:
            user_content += "Tổng hợp dựa trên tình hình các tỉnh miền Bắc đang chịu ảnh hưởng hoàn lưu bão và lũ sông Thao, sông Cầu, sông Hồng."

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        raw_resp = await self._call_groq_api(messages, json_mode=True)
        if raw_resp:
            try:
                p = json.loads(raw_resp)
                groups = [
                    GroupedDisasterCategory(
                        category_name=g.get("category_name", "Khác"),
                        count=int(g.get("count", 1)),
                        hotspots=g.get("hotspots", [])
                    )
                    for g in p.get("grouped_reports", [])
                ]
                return DisasterSummaryResult(
                    region=region or "Toàn Miền Bắc",
                    time_window_str=f"{time_window_hours} giờ qua",
                    summary=p.get("summary", ""),
                    progression_trend=p.get("progression_trend", ""),
                    grouped_reports=groups,
                    conflicts_or_unverified=p.get("conflicts_or_unverified", []),
                    overall_risk_level=p.get("overall_risk_level", "high"),
                    provider_used=f"groq ({self.model})",
                    is_fallback=False
                )
            except Exception as e:
                logger.warning("Lỗi parse kết quả tổng hợp từ Groq: %s", e)

        return await self.fallback_engine.summarize_disaster(region, reports, time_window_hours)

    async def classify_emergency(
        self,
        message: str,
        contact_phone: Optional[str] = None,
        location_text: Optional[str] = None
    ) -> EmergencyClassificationResult:
        """3. Rescue Information Classification: Phân loại yêu cầu cứu trợ khẩn cấp."""
        sys_prompt = (
            "Bạn là điều phối viên cứu nạn cứu hộ trực ban 114 / NorthStar. "
            "Nhiệm vụ: Phân loại lời kêu cứu của người dân, bóc tách nhu cầu (sơ tán, thực phẩm, nước sạch, y tế khẩn cấp, xuồng cứu hộ), "
            "nhận diện nhóm dễ bị tổn thương (trẻ nhỏ, người già, bệnh tật, phụ nữ mang thai) và số lượng nạn nhân. Trả về đúng JSON thuần túy:\n"
            "{\n"
            '  "needs": ["sơ tán", "thực phẩm", "nước sạch", "y tế khẩn cấp", "xuồng cứu hộ"],\n'
            '  "people_affected": 1,\n'
            '  "vulnerable_groups": ["người già", "trẻ em"],\n'
            '  "urgency": "low | medium | high | critical",\n'
            '  "recommended_action": "Mệnh lệnh tác chiến ngắn gọn cho đội cứu hộ"\n'
            "}"
        )

        user_content = f"Người gặp nạn liên hệ: {contact_phone or 'Chưa rõ'}\nVị trí: {location_text or 'Theo GPS'}\nLời kêu cứu: {message}"
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        raw_resp = await self._call_groq_api(messages, json_mode=True)
        if raw_resp:
            try:
                p = json.loads(raw_resp)
                return EmergencyClassificationResult(
                    needs=p.get("needs", ["hỗ trợ chung"]),
                    people_affected=int(p.get("people_affected", 1)),
                    vulnerable_groups=p.get("vulnerable_groups", []),
                    urgency=p.get("urgency", "high"),
                    recommended_action=p.get("recommended_action", "Cử tổ cứu hộ tiếp cận."),
                    structured_json=p,
                    provider_used=f"groq ({self.model})",
                    is_fallback=False
                )
            except Exception as e:
                logger.warning("Lỗi parse phân loại SOS từ Groq: %s", e)

        return await self.fallback_engine.classify_emergency(message, contact_phone, location_text)

    async def chat(
        self,
        query: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
        context: Optional[dict[str, Any]] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None
    ) -> AIChatResult:
        """4. Emergency Assistant Chat: Trợ lý hỏi đáp trực ban dựa trên dữ liệu thật."""
        # Chuẩn bị dữ liệu định vị và quan trắc thực tế từ backend
        live_pts = context.get("flood_points", []) if context else []
        shelters = context.get("shelters", []) if context else []
        danger_count = sum(1 for p in live_pts if (p.get("depth_cm") or 0) >= 20)

        sys_prompt = (
            "Bạn là Trợ lý AI Trực ban Thiên tai Ban Chỉ huy PCTT & TKCN Việt Nam (NorthStar). "
            "Nhiệm vụ: Hỗ trợ người dân tra cứu lộ trình né ngập, điểm sơ tán khẩn cấp và kỹ năng sinh tồn (an toàn điện, lũ quét, nước sạch). "
            "QUY TẮC BẮT BUỘC:\n"
            "1. Tuyệt đối KHÔNG tự bịa đặt mực nước hoặc số liệu quan trắc giả mạo. Chỉ căn cứ vào dữ liệu backend cung cấp bên dưới.\n"
            "2. Trả lời bằng tiếng Việt lịch sự, điềm tĩnh, súc tích, dứt khoát.\n"
            "3. Nếu người dùng hỏi địa bàn không có trong dữ liệu, hãy nói rõ hệ thống chưa ghi nhận trạm quan trắc tại đó và khuyến cáo liên hệ chính quyền địa phương.\n"
            f"DỮ LIỆU HIỆN HÀNH: Hệ thống có {len(live_pts)} trạm quan trắc ({danger_count} điểm ngập nguy cấp ≥20cm), {len(shelters)} điểm sơ tán an toàn mở cửa."
        )

        messages = [{"role": "system", "content": sys_prompt}]
        if conversation_history:
            for item in conversation_history[-4:]:
                messages.append(item)

        user_content = f"Vị trí người dùng: Lat {lat}, Lng {lng}\nCâu hỏi: {query}"
        messages.append({"role": "user", "content": user_content})

        raw_resp = await self._call_groq_api(messages, json_mode=False, temperature=0.3)
        if raw_resp:
            # Gợi ý hành động nhanh phù hợp
            actions = []
            q_lower = query.lower()
            if any(k in q_lower for k in ["đường", "xe máy", "ô tô", "ngập"]):
                actions.append(SuggestedAction(label="🧭 Mở Tìm đường Né ngập", action="switch_tab", tab="route"))
            if any(k in q_lower for k in ["sơ tán", "tránh trú", "ở đâu"]):
                actions.append(SuggestedAction(label="🛡️ Xem trạm sơ tán gần nhất", action="switch_tab", tab="evac"))
            if any(k in q_lower for k in ["cứu", "sos", "mắc kẹt", "điện giật"]):
                actions.append(SuggestedAction(label="🆘 Phát tín hiệu SOS", action="open_sos"))

            return AIChatResult(
                reply=raw_resp,
                suggested_actions=actions,
                sources_consulted=["Groq LLaMA 3.3", "NorthStar Sensor Network", "PCTT Database"],
                provider_used=f"groq ({self.model})",
                is_fallback=False
            )

        # Fallback nếu gọi Groq không thành công
        return await self.fallback_engine.chat(query, conversation_history, context, lat, lng)

    async def get_status(self) -> ProviderStatusResult:
        """Kiểm tra tình trạng hoạt động của Groq Provider."""
        if not self._has_valid_key():
            return ProviderStatusResult(
                enabled=True,
                configured_provider="groq",
                active_provider="mock_offline",
                model=self.model,
                status="offline_fallback",
                is_fallback_active=True,
                capabilities=[
                    "Disaster Report Analysis (Offline Fallback)",
                    "Disaster Information Summarization (Offline Fallback)",
                    "Rescue Information Classification (Offline Fallback)",
                    "Emergency Assistant Chat (Rule Engine)"
                ],
                message="GROQ_API_KEY chưa được cấu hình. Hệ thống tự động chuyển sang chế độ Ngoại tuyến (Rule-based Mock)."
            )

        # Kiểm tra thử kết nối nhanh
        test_msg = [{"role": "user", "content": "ping"}]
        test_res = await self._call_groq_api(test_msg, temperature=0.0)
        if test_res:
            return ProviderStatusResult(
                enabled=True,
                configured_provider="groq",
                active_provider=f"groq ({self.model})",
                model=self.model,
                status="online",
                is_fallback_active=False,
                capabilities=[
                    "Disaster Report Analysis (LPU Accelerated)",
                    "Disaster Information Summarization (LLaMA 3.3 70B)",
                    "Rescue Information Classification (Zero-shot NLP)",
                    "Emergency Assistant Chat (Real-time Grounded)"
                ],
                message=f"Groq API kết nối thành công với mô hình {self.model}."
            )
        else:
            return ProviderStatusResult(
                enabled=True,
                configured_provider="groq",
                active_provider="mock_offline",
                model=self.model,
                status="offline_fallback",
                is_fallback_active=True,
                capabilities=[
                    "Disaster Report Analysis (Offline Fallback)",
                    "Disaster Information Summarization (Offline Fallback)",
                    "Rescue Information Classification (Offline Fallback)",
                    "Emergency Assistant Chat (Rule Engine)"
                ],
                message="Không thể kết nối tới Groq Cloud API hoặc timeout. Chế độ dự phòng Ngoại tuyến đã được kích hoạt."
            )
