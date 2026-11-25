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
Tích hợp Mô hình Qwen3-8B (HuggingFace: Qwen/Qwen3-8B) cho Phân loại & Điều phối Cứu trợ.
Tuân thủ chuẩn OpenAI API Chat Completions (hỗ trợ vLLM, Ollama, LM Studio, TGI).
Bao gồm:
- Tách biệt hoàn toàn tầng gọi AI khỏi logic nghiệp vụ
- Kỹ thuật Prompt Engineering định hướng cứu nạn thiên tai
- Cơ chế phân tách Sự thật người dân khai báo và Suy luận của AI
- Cơ chế phục hồi JSON (JSON Repair & Sanitize)
- Xử lý lỗi, Timeout và Fallback ngoại tuyến đảm bảo KHÔNG MẤT DỮ LIỆU
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from .base import AIProvider
from .guardrails import ReliefGuardrailsEngine
from .verification import ReliefVerificationEngine
from .mock_provider import MockAIProvider
from .schemas import (
    AIChatResult,
    DisasterSummaryResult,
    EmergencyClassificationResult,
    LocationExtracted,
    ProviderStatusResult,
    ReliefAuditEntry,
    ReliefExtractedData,
    ReliefRequestCreate,
    ReliefTriageResult,
    ReportAnalysisResult,
)

log = logging.getLogger("northstar.ai.qwen")

# System Prompt tối ưu cho mô hình Qwen3-8B
QWEN_SYSTEM_PROMPT = """Bạn là Chuyên gia AI Điều phối Cứu hộ Cứu nạn khẩn cấp cho Hệ thống NorthStar (Việt Nam).
Nhiệm vụ của bạn là tiếp nhận thông tin kêu cứu từ người dân (văn bản hoặc transcript âm thanh), trích xuất thông tin có cấu trúc, đánh giá mức độ khẩn cấp sơ bộ và đề xuất ưu tiên điều phối.

HƯỚNG DẪN BẮT BUỘC:
1. ĐÚNG SỰ THẬT: Phân biệt rõ thông tin người dân trực tiếp cung cấp (citizen_reported_facts) và thông tin bạn suy luận (ai_inferred_facts).
2. KHÔNG TỰ BỊA ĐẶT (ZERO HALLUCINATION): Nếu người dân không nhắc đến vị trí, số người, mực nước hay tình trạng bệnh lý, BẮT BUỘC trả về null hoặc "unknown". Tuyệt đối không tự ý bịa tọa độ GPS.
3. PHÂN LOẠI ƯU TIÊN SƠ BỘ (raw_ai_priority):
   - P1 (Nguy hiểm tức thời): Có dấu hiệu đe dọa trực tiếp tính mạng, chấn thương/cấp cứu y tế, nước ngập sâu dâng nhanh, mắc kẹt nóc nhà.
   - P2 (Nguy cơ cao): Nguy cơ bị cô lập, có người dễ bị tổn thương (trẻ em, người già, người tàn tật, thai phụ), nước đang dâng.
   - P3 (Cần cứu trợ): Cần hỗ trợ thiết yếu (thực phẩm, nước uống, thuốc men) nhưng chưa nguy hiểm tức thời.
   - P4 (Theo dõi): Chưa khẩn cấp, tiếp tục theo dõi diễn biến.
4. XU HƯỚNG MỰC NƯỚC (water_trend): "rising" (đang dâng), "stable" (ổn định), "receding" (đang rút), hoặc "unknown".
5. ĐỊNH DẠNG ĐẦU RA: Bắt buộc trả về DUY NHẤT một chuỗi JSON hợp lệ theo schema sau (không thêm văn bản chào hỏi, không dùng markdown giải thích):
{
  "request_id": "Mã yêu cầu (chuỗi)",
  "location_text": "Địa chỉ hoặc null",
  "lat": null,
  "lng": null,
  "province": "Tên tỉnh hoặc null",
  "district": "Tên quận/huyện hoặc null",
  "ward": "Tên phường/xã/thôn hoặc null",
  "timestamp": "Thời gian hoặc null",
  "people_count": null,
  "water_level_m": null,
  "water_trend": "unknown",
  "vulnerable_people": ["children", "elderly", "disabled", "pregnant", "medical_patient"],
  "medical_emergency": false,
  "immediate_danger": false,
  "mobility_status": "trapped_roof | trapped_attic | isolated | cannot_move | can_walk | unknown",
  "relief_needs": ["boat_evacuation", "food_water", "medical_kit", "lifejacket"],
  "contact_name": "Tên người liên hệ hoặc null",
  "contact_phone": "Số điện thoại hoặc null",
  "citizen_reported_facts": {},
  "ai_inferred_facts": {},
  "raw_ai_priority": "P1 | P2 | P3 | P4",
  "ai_priority_reasons": ["Lý do 1", "Lý do 2"],
  "missing_information": ["Các trường quan trọng còn thiếu"],
  "conflicting_information": ["Các điểm mâu thuẫn nếu có"]
}
"""


class QwenProvider(AIProvider):
    """
    Nhà cung cấp AI tích hợp mô hình Qwen3-8B.
    Kết nối qua chuẩn OpenAI API (vLLM / Ollama / TGI / LM Studio).
    """

    def __init__(
        self,
        api_base: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        model: str = "Qwen/Qwen3-8B",
        timeout_sec: float = 15.0
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.model = model
        self.timeout_sec = timeout_sec
        # Dự phòng offline bằng Mock Provider nếu Qwen không khả dụng
        self.fallback_provider = MockAIProvider(model_name="qwen3-8b-offline-fallback")

    def _sanitize_json(self, raw_text: str) -> str:
        """Làm sạch chuỗi trả về từ mô hình để trích xuất JSON hợp lệ."""
        text = raw_text.strip()
        # Loại bỏ markdown code blocks ```json ... ```
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
        # Tìm khối { ... } ngoài cùng
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace:last_brace + 1]
        # Xóa dấu phẩy thừa trước ngoặc đóng (trailing commas)
        text = re.sub(r",\s*([\]}])", r"\1", text)
        return text

    async def _call_qwen_chat(self, messages: List[Dict[str, str]], json_mode: bool = True) -> str:
        """Thực hiện HTTP POST tới endpoint /chat/completions chuẩn OpenAI."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Nhiệt độ thấp cho tác vụ phân loại và trích xuất
            "max_tokens": 1024,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.api_base}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"Qwen API error HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def triage_relief_request(
        self,
        request: ReliefRequestCreate,
        existing_requests: Optional[List[dict]] = None
    ) -> ReliefTriageResult:
        """
        Quy trình xử lý đầy đủ:
        1. Gọi Qwen3-8B trích xuất cấu trúc (hoặc fallback ngoại tuyến nếu lỗi/timeout)
        2. Chạy Động cơ Xác minh (ReliefVerificationEngine)
        3. Chạy Động cơ Quy tắc Nghiệp vụ Chống hạ mức (ReliefGuardrailsEngine)
        4. Tổng hợp bản ghi chuẩn hóa có nhật ký kiểm định (Audit Trail)
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = request.request_id or f"NS-{int(datetime.now().timestamp() * 1000) % 1000000:06d}"

        user_content = f"""Mã yêu cầu: {req_id}
Nguồn tin: {request.source or 'community'}
Tên người báo (nếu có): {request.contact_name or 'Chưa rõ'}
Số điện thoại (nếu có): {request.phone or 'Chưa rõ'}
Vị trí cung cấp (nếu có): {request.location_text or 'Chưa rõ'}
Tọa độ đã biết (nếu có): Lat={request.lat}, Lng={request.lng}
Nội dung thông tin kêu cứu:
"{request.message}"
"""
        messages = [
            {"role": "system", "content": QWEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        extracted_data: Optional[ReliefExtractedData] = None
        provider_used = "qwen3-8b"
        is_fallback = False

        try:
            raw_response = await self._call_qwen_chat(messages, json_mode=True)
            cleaned_json = self._sanitize_json(raw_response)
            parsed = json.loads(cleaned_json)

            # Đảm bảo giữ nguyên các trường người dùng đã gửi trực tiếp nếu AI không thấy
            if request.lat is not None and parsed.get("lat") is None:
                parsed["lat"] = request.lat
            if request.lng is not None and parsed.get("lng") is None:
                parsed["lng"] = request.lng
            if request.phone and not parsed.get("contact_phone"):
                parsed["contact_phone"] = request.phone
            if request.contact_name and not parsed.get("contact_name"):
                parsed["contact_name"] = request.contact_name
            if request.location_text and not parsed.get("location_text"):
                parsed["location_text"] = request.location_text

            parsed["request_id"] = req_id
            extracted_data = ReliefExtractedData(**parsed)

        except Exception as e:
            log.warning("Qwen3-8B không phản hồi hoặc JSON sai định dạng (%s). Tự động fallback sang động cơ quy tắc cứu nạn an toàn.", e)
            provider_used = "mock_offline_fallback"
            is_fallback = True
            extracted_data = self._rule_based_fallback_extract(req_id, request)

        # 2. Xác minh dữ liệu (Verification Engine)
        verification = ReliefVerificationEngine.verify_request(
            extracted=extracted_data,
            source=request.source,
            existing_requests=existing_requests
        )

        # 3. Áp dụng Bộ quy tắc Nghiệp vụ (Guardrails Engine)
        (
            final_priority,
            priority_reasons,
            guardrails_applied,
            was_downgrade_prevented,
            requires_human_review
        ) = ReliefGuardrailsEngine.evaluate_priority(
            extracted=extracted_data,
            verification=verification
        )

        # 4. Tạo bản ghi nhật ký kiểm định (Audit Trail)
        audit_history: List[ReliefAuditEntry] = [
            ReliefAuditEntry(
                timestamp=now_iso,
                actor=f"{provider_used}",
                action="created",
                new_priority=extracted_data.raw_ai_priority,
                reason="AI trích xuất ban đầu từ tin báo của người dân"
            )
        ]
        if was_downgrade_prevented:
            audit_history.append(
                ReliefAuditEntry(
                    timestamp=now_iso,
                    actor="business_guardrails",
                    action="rule_override",
                    old_priority=extracted_data.raw_ai_priority,
                    new_priority=final_priority,
                    reason=f"Kích hoạt bảo vệ: {', '.join(guardrails_applied)}"
                )
            )

        # Trạng thái điều phối
        status = "awaiting_dispatch"
        if verification.verification_status == "needs_verification" and final_priority in ("P3", "P4"):
            status = "needs_verification"

        return ReliefTriageResult(
            request_id=req_id,
            extracted=extracted_data,
            verification=verification,
            final_priority=final_priority,
            priority_reasons=priority_reasons,
            guardrails_applied=guardrails_applied,
            was_downgrade_prevented=was_downgrade_prevented,
            requires_human_review=requires_human_review,
            confidence_score=0.92 if not is_fallback else 0.75,
            status=status,
            created_at=now_iso,
            updated_at=now_iso,
            override_history=audit_history,
            provider_used=provider_used,
            is_fallback=is_fallback
        )

    def _rule_based_fallback_extract(self, req_id: str, request: ReliefRequestCreate) -> ReliefExtractedData:
        """Động cơ bóc tách dự phòng khi AI không khả dụng - đảm bảo KHÔNG MẤT DỮ LIỆU."""
        text = (request.message or "").lower()
        missing: List[str] = []
        conflicts: List[str] = []
        reasons: List[str] = []

        # 1. Trích xuất số người
        people_count = None
        p_match = re.search(r"(\d+)\s*(người|nhân khẩu|ng|bác|cháu|thành viên)", text)
        if p_match:
            people_count = int(p_match.group(1))
        elif "gia đình" in text:
            people_count = 4

        # 2. Trích xuất mực nước
        water_level_m = None
        w_match = re.search(r"(\d+(?:\.\d+)?)\s*(m|mét|met|cm)", text)
        if w_match:
            val = float(w_match.group(1))
            unit = w_match.group(2)
            water_level_m = val / 100.0 if unit == "cm" else val
        elif "nóc nhà" in text or "mái tôn" in text or "ngập tầng 2" in text:
            water_level_m = 2.0
            reasons.append("Người dân báo ngập đến nóc/tầng 2")
        elif "ngang ngực" in text or "ngang người" in text:
            water_level_m = 1.3
        elif "đầu gối" in text or "ngang bắp chân" in text:
            water_level_m = 0.4

        # 3. Xu hướng nước
        water_trend = "unknown"
        if any(k in text for k in ["nước đang lên", "nước dâng", "dâng nhanh", "cuồn cuộn", "chảy xiết", "tràn vào"]):
            water_trend = "rising"
            reasons.append("Nước đang dâng nhanh")
        elif any(k in text for k in ["rút dần", "đang rút", "rút bớt"]):
            water_trend = "receding"
        elif "ổn định" in text or "chững lại" in text:
            water_trend = "stable"

        # 4. Người dễ bị tổn thương
        vulnerable: List[str] = []
        if any(k in text for k in ["cụ già", "người già", "bà già", "ông lão", "bà lão", "tai biến", "liệt"]):
            vulnerable.append("elderly")
        if any(k in text for k in ["trẻ nhỏ", "trẻ em", "em bé", "cháu nhỏ", "cháu bé", "trẻ con", "sơ sinh", "con nhỏ", "cháu"]):
            vulnerable.append("children")
        if any(k in text for k in ["mang bầu", "mang thai", "bầu bí", "sắp sinh"]):
            vulnerable.append("pregnant")
        if any(k in text for k in ["khuyết tật", "liệt giường", "chân đau không đi được"]):
            vulnerable.append("disabled")

        # 5. Khả năng tự thoát hiểm & Nguy hiểm tức thời
        mobility_status = "unknown"
        if any(k in text for k in ["trên mái", "nóc nhà", "mái tôn", "leo lên tum"]):
            mobility_status = "trapped_roof"
            reasons.append("Đang mắc kẹt trên mái nhà")
        elif any(k in text for k in ["cô lập", "chia cắt", "không ra được", "mắc kẹt trong nhà"]):
            mobility_status = "isolated"

        # 6. Cấp cứu y tế & Nguy hiểm tức thời
        medical_emergency = False
        if any(k in text for k in ["cấp cứu", "mất máu", "chấn thương", "sốt cao", "co giật", "khó thở", "bệnh nhân", "thuốc trợ tim"]):
            medical_emergency = True
            reasons.append("Báo cáo có người cần trợ giúp y tế khẩn cấp")

        immediate_danger = False
        if mobility_status == "trapped_roof" or any(k in text for k in ["sắp sập", "sập nhà", "cuốn trôi", "chới với", "nguy kịch", "cứu gấp", "chết đuối", "chìm"]):
            immediate_danger = True
            reasons.append("Tình trạng đe dọa trực tiếp tính mạng")

        # 6. Khả năng tự thoát hiểm
        mobility_status = "unknown"
        if any(k in text for k in ["trên mái", "nóc nhà", "mái tôn", "leo lên tum"]):
            mobility_status = "trapped_roof"
            reasons.append("Đang mắc kẹt trên mái nhà")
        elif any(k in text for k in ["cô lập", "chia cắt", "không ra được", "mắc kẹt trong nhà"]):
            mobility_status = "isolated"

        # 7. Nhu cầu cứu trợ
        needs: List[str] = []
        if any(k in text for k in ["xuồng", "thuyền", "ca nô", "di tản", "sơ tán"]):
            needs.append("boat_evacuation")
        if any(k in text for k in ["lương thực", "nước uống", "đói", "sữa", "mì tôm", "cơm"]):
            needs.append("food_water")
        if any(k in text for k in ["phao", "áo phao"]):
            needs.append("lifejacket")
        if medical_emergency:
            needs.append("medical_kit")

        # 8. Mức ưu tiên sơ bộ
        raw_priority = "P3"
        if immediate_danger or medical_emergency or mobility_status == "trapped_roof" or (water_trend == "rising" and water_level_m and water_level_m >= 1.0):
            raw_priority = "P1"
        elif len(vulnerable) > 0 or water_trend == "rising" or (water_level_m and water_level_m >= 0.6) or mobility_status == "isolated":
            raw_priority = "P2"
        elif not needs:
            raw_priority = "P4"

        # Thiếu thông tin
        if not request.location_text and request.lat is None:
            missing.append("vị trí / tọa độ")
        if people_count is None:
            missing.append("số lượng người cụ thể")
        if water_level_m is None:
            missing.append("mực nước ngập đo lường")

        return ReliefExtractedData(
            request_id=req_id,
            location_text=request.location_text,
            lat=request.lat,
            lng=request.lng,
            people_count=people_count,
            water_level_m=water_level_m,
            water_trend=water_trend,
            vulnerable_people=vulnerable,
            medical_emergency=medical_emergency,
            immediate_danger=immediate_danger,
            mobility_status=mobility_status,
            relief_needs=needs,
            contact_name=request.contact_name,
            contact_phone=request.phone,
            citizen_reported_facts={"raw_message": request.message},
            ai_inferred_facts={"rule_derived": True},
            raw_ai_priority=raw_priority,
            ai_priority_reasons=reasons,
            missing_information=missing,
            conflicting_information=conflicts
        )

    # Các hàm triển khai abstract method từ AIProvider (để tương thích hoàn toàn)
    async def analyze_report(self, content: str, source: Optional[str] = "community", reporter: Optional[str] = None) -> ReportAnalysisResult:
        try:
            prompt = f"Phân tích báo cáo thiên tai sau thành JSON (disaster_type, location, urgency_level, raw_summary):\n{content}"
            messages = [{"role": "system", "content": "Bạn là chuyên gia phân tích thiên tai. Xuất JSON hợp lệ."}, {"role": "user", "content": prompt}]
            raw = await self._call_qwen_chat(messages, json_mode=True)
            data = json.loads(self._sanitize_json(raw))
            loc = data.get("location") or {}
            return ReportAnalysisResult(
                disaster_type=data.get("disaster_type", "ngập lụt"),
                location=LocationExtracted(
                    province=loc.get("province"), district=loc.get("district"),
                    ward_or_street=loc.get("ward_or_street"), lat=loc.get("lat"), lng=loc.get("lng")
                ),
                time_occurred=data.get("time_occurred"),
                missing_info=data.get("missing_info", []),
                urgency_level=data.get("urgency_level", "medium"),
                raw_summary=data.get("raw_summary", content[:120]),
                confidence_score=0.9,
                provider_used="qwen3-8b",
                is_fallback=False
            )
        except Exception as e:
            log.warning("Qwen analyze_report failed, fallback to mock: %s", e)
            res = await self.fallback_provider.analyze_report(content, source, reporter)
            res.provider_used = "mock_offline_fallback"
            res.is_fallback = True
            return res

    async def summarize_disaster(self, region: Optional[str] = None, reports: Optional[list] = None, time_window_hours: int = 24) -> DisasterSummaryResult:
        return await self.fallback_provider.summarize_disaster(region, reports, time_window_hours)

    async def classify_emergency(self, message: str, contact_phone: Optional[str] = None, location_text: Optional[str] = None) -> EmergencyClassificationResult:
        triage_res = await self.triage_relief_request(
            ReliefRequestCreate(message=message, phone=contact_phone, location_text=location_text)
        )
        urgency_map = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}
        return EmergencyClassificationResult(
            needs=triage_res.extracted.relief_needs,
            people_affected=triage_res.extracted.people_count or 1,
            vulnerable_groups=triage_res.extracted.vulnerable_people,
            urgency=urgency_map.get(triage_res.final_priority, "high"),
            recommended_action="; ".join(triage_res.priority_reasons) or "Đang chờ điều phối",
            structured_json=triage_res.model_dump(),
            provider_used=triage_res.provider_used,
            is_fallback=triage_res.is_fallback
        )

    async def chat(self, query: str, conversation_history: Optional[list] = None, context: Optional[dict] = None, lat: Optional[float] = None, lng: Optional[float] = None) -> AIChatResult:
        return await self.fallback_provider.chat(query, conversation_history, context, lat, lng)

    async def get_status(self) -> ProviderStatusResult:
        """Kiểm tra tình trạng máy chủ Qwen3-8B."""
        is_online = False
        msg = f"Đang kết nối tới mô hình {self.model} tại {self.api_base}"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{self.api_base}/models")
                if r.status_code == 200:
                    is_online = True
                    msg = f"Máy chủ {self.model} đang trực tuyến và sẵn sàng xử lý yêu cầu cứu nạn."
        except Exception:
            is_online = False
            msg = f"Không kết nối được Qwen3-8B ({self.api_base}). Chế độ dự phòng ngoại tuyến sẵn sàng."

        return ProviderStatusResult(
            enabled=True,
            configured_provider="qwen",
            active_provider="qwen3-8b" if is_online else "mock_offline_fallback",
            model=self.model,
            status="online" if is_online else "offline_fallback",
            is_fallback_active=not is_online,
            capabilities=["relief_triage", "guardrails_protection", "data_verification", "dispatch_queue"],
            message=msg
        )
