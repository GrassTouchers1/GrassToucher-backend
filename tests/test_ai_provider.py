"""
Bộ kiểm thử tự động (Unit Tests) cho AI Provider Layer & Groq Integration.
Sử dụng thư viện chuẩn unittest và AsyncMock.
Chạy trực tiếp với mọi môi trường Python: python -m unittest tests/test_ai_provider.py
Hoàn toàn không tốn token/quota API ngoài và không phụ thuộc mạng.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.ai.mock_provider import MockAIProvider
from app.ai.groq_provider import GroqProvider
from app.ai.factory import get_ai_provider, DisabledAIProvider
from app.ai.schemas import (
    ReportAnalysisResult,
    DisasterSummaryResult,
    EmergencyClassificationResult,
    AIChatResult,
    ProviderStatusResult,
)


class TestAIProviderSuite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    # --------------------------------------------------------------------------
    # 1. Kiểm thử MockAIProvider (Chế độ Ngoại tuyến / Rule-based)
    # --------------------------------------------------------------------------
    def test_mock_report_analysis(self):
        async def run_test():
            provider = MockAIProvider()
            content = "Nước ngập tràn vào nhà ở Cầu Giấy lúc 8h sáng, cụ già liệt giường không kịp sơ tán nguy kịch!"
            res = await provider.analyze_report(content=content, source="citizen_app")

            self.assertIsInstance(res, ReportAnalysisResult)
            self.assertIn(res.disaster_type, ["ngập lụt", "lũ quét"])
            self.assertEqual(res.location.district, "Cầu Giấy")
            self.assertIn(res.urgency_level, ["high", "critical"])
            self.assertTrue(res.is_fallback)
            self.assertIn("mock", res.provider_used)

        asyncio.run(run_test())

    def test_mock_disaster_summary(self):
        async def run_test():
            provider = MockAIProvider()
            res = await provider.summarize_disaster(region="Thái Nguyên", time_window_hours=12)

            self.assertIsInstance(res, DisasterSummaryResult)
            self.assertIn("Thái Nguyên", res.region)
            self.assertGreater(len(res.grouped_reports), 0)
            self.assertGreater(len(res.conflicts_or_unverified), 0)
            self.assertTrue(res.is_fallback)

        asyncio.run(run_test())

    def test_mock_classify_emergency(self):
        async def run_test():
            provider = MockAIProvider()
            msg = "Nhà tôi ở Bảo Yên có 7 người bị lũ cô lập, có 2 cháu bé và 1 người già, nước dâng tới nóc bếp hết đồ ăn!"
            res = await provider.classify_emergency(message=msg, contact_phone="0987654321", location_text="Bảo Yên")

            self.assertIsInstance(res, EmergencyClassificationResult)
            self.assertEqual(res.people_affected, 7)
            self.assertTrue(any("trẻ" in v for v in res.vulnerable_groups))
            self.assertTrue(any("thực phẩm" in n or "đồ ăn" in n or "sơ tán" in n for n in res.needs))
            self.assertIn(res.urgency, ["high", "critical"])
            self.assertTrue(res.is_fallback)

        asyncio.run(run_test())

    def test_mock_chat_assistant(self):
        async def run_test():
            provider = MockAIProvider()
            res = await provider.chat(query="Nước ngập vào nhà có nên bật cầu dao điện không?")

            self.assertIsInstance(res, AIChatResult)
            self.assertTrue("aptomat" in res.reply.lower() or "điện" in res.reply.lower())
            self.assertGreater(len(res.suggested_actions), 0)

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # 2. Kiểm thử GroqProvider với Mock HTTP (Thành công, Lỗi 401, Timeout)
    # --------------------------------------------------------------------------
    def test_groq_provider_success(self):
        async def run_test():
            mock_groq_json = {
                "disaster_type": "lũ quét",
                "province": "Lào Cai",
                "district": "Bảo Yên",
                "ward_or_street": "Làng Nủ",
                "time_occurred": "Sáng sớm nay",
                "missing_info": ["Mực nước chính xác"],
                "urgency_level": "critical",
                "raw_summary": "Lũ quét sạt lở tại Làng Nủ, Bảo Yên, mức độ đặc biệt nguy cấp.",
                "confidence_score": 0.98
            }

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_groq_json)}}]
            }

            provider = GroqProvider(api_key="gsk_mock_valid_key_1234567890", model="llama-3.3-70b-versatile")

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                res = await provider.analyze_report("Lũ bùn quét Làng Nủ sáng nay, cần cứu hộ gấp!")

                self.assertEqual(res.disaster_type, "lũ quét")
                self.assertEqual(res.location.district, "Bảo Yên")
                self.assertEqual(res.urgency_level, "critical")
                self.assertFalse(res.is_fallback)
                self.assertIn("groq", res.provider_used)

        asyncio.run(run_test())

    def test_groq_provider_fallback_on_401(self):
        async def run_test():
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API Key"

            provider = GroqProvider(api_key="gsk_invalid_mock_key_test", model="llama-3.3-70b-versatile")

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                res = await provider.analyze_report("Nước ngập đường Cầu Giấy")

                self.assertIsInstance(res, ReportAnalysisResult)
                self.assertTrue(res.is_fallback)
                self.assertIn("mock", res.provider_used)

        asyncio.run(run_test())

    def test_groq_provider_fallback_on_timeout(self):
        async def run_test():
            import httpx
            provider = GroqProvider(api_key="gsk_mock_valid_key_1234567890", model="llama-3.3-70b-versatile")

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.TimeoutException("Request timed out")
                res = await provider.classify_emergency("Cứu hộ 3 người mắc kẹt ở Yên Bái")

                self.assertIsInstance(res, EmergencyClassificationResult)
                self.assertTrue(res.is_fallback)
                self.assertIn("mock", res.provider_used)

        asyncio.run(run_test())

    def test_groq_provider_no_key(self):
        async def run_test():
            provider = GroqProvider(api_key="", model="llama-3.3-70b-versatile")
            res = await provider.analyze_report("Mưa ngập nặng tại Đống Đa")

            self.assertTrue(res.is_fallback)
            self.assertIn("mock", res.provider_used)

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # 3. Kiểm thử Tầng REST API Endpoints qua TestClient
    # --------------------------------------------------------------------------
    def test_api_status_endpoint(self):
        response = self.client.get("/api/ai/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("enabled", data)
        self.assertIn("active_provider", data)
        self.assertIn("status", data)

    def test_api_analyze_report_endpoint(self):
        payload = {
            "content": "Nước lũ tràn qua đê Chã gây ngập sâu các phường TP Thái Nguyên lúc 10h sáng",
            "source": "news",
            "reporter": "Báo Thái Nguyên"
        }
        response = self.client.post("/api/ai/analyze-report", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("disaster_type", data)
        self.assertIn("urgency_level", data)
        self.assertIn("location", data)

    def test_api_classify_emergency_endpoint(self):
        payload = {
            "message": "Cần cano cứu hộ đưa 5 người gồm 2 trẻ sơ sinh ra khỏi vùng ngập sâu Làng Nủ",
            "contact_phone": "0912345678",
            "location_text": "Làng Nủ, Bảo Yên, Lào Cai"
        }
        response = self.client.post("/api/ai/classify-emergency", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["people_affected"], 5)
        self.assertGreater(len(data["needs"]), 0)
        self.assertIn(data["urgency"], ["high", "critical"])

    def test_api_chat_endpoint(self):
        payload = {
            "query": "Lộ trình từ Cầu Giấy về Hà Đông xe máy có đi được không?",
            "include_live_context": True
        }
        response = self.client.post("/api/ai/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("suggested_actions", data)

    def test_api_summarize_disaster_endpoint(self):
        payload = {
            "region": "Thái Nguyên",
            "time_window_hours": 24
        }
        response = self.client.post("/api/ai/summarize-disaster", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("grouped_reports", data)

    def test_api_voice_sos_text_endpoint(self):
        payload = {
            "transcript": "Cứu tôi với, nước dâng tới nóc bếp ở Bảo Yên, có 4 người gồm 2 cháu nhỏ hết lương thực!",
            "lat": 22.2541,
            "lng": 104.3821,
            "contact_name": "Người gọi SOS",
            "contact_phone": "0987112233",
            "auto_create_beacon": True
        }
        response = self.client.post("/api/ai/voice-sos/text", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("transcript", data)
        self.assertIn("classification", data)
        self.assertIn("emergency_hotlines", data)
        self.assertIsNotNone(data["beacon"])

    def test_api_voice_sos_audio_endpoint_with_mock_whisper(self):
        with patch("app.routers.ai_endpoints.transcribe_audio_groq", new_callable=AsyncMock) as mock_stt:
            mock_stt.return_value = "Lũ bùn quét Làng Nủ, cần xuồng cứu hộ khẩn cấp đưa 3 người già đi cấp cứu!"
            dummy_audio = b"\x00" * 500
            response = self.client.post(
                "/api/ai/voice-sos?lat=22.254&lng=104.382&contact_name=VoiceTest",
                content=dummy_audio,
                headers={"Content-Type": "audio/webm"}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("Làng Nủ", data["transcript"])
            self.assertIn("classification", data)
            self.assertIsNotNone(data["beacon"])


if __name__ == "__main__":
    unittest.main()
