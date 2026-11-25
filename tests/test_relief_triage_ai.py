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
Bộ Kiểm thử Toàn diện Hệ thống AI Phân loại & Điều phối Yêu cầu Cứu trợ NorthStar.
Kiểm thử 10 kịch bản giả lập theo yêu cầu nhiệm vụ:
1. Người dân bị mắc kẹt trên nóc/tum trong vùng ngập sâu
2. Có người bị thương nặng hoặc cần hỗ trợ y tế khẩn cấp
3. Có trẻ em sơ sinh, người cao tuổi hoặc người khuyết tật
4. Nước lũ đang dâng nhanh đe dọa công trình
5. Yêu cầu thiếu thông tin vị trí
6. Yêu cầu có thông tin mâu thuẫn
7. Nhiều yêu cầu gần nhau cùng một vị trí (<50m)
8. Yêu cầu trùng lặp số điện thoại
9. AI server không phản hồi (Timeout / Network failure) -> Fallback an toàn
10. AI trả về JSON sai định dạng (Malformed JSON) -> Khôi phục / Phục hồi

Đồng thời kiểm thử:
- Khả năng trích xuất dữ liệu có cấu trúc
- Độ chính xác phân loại P1 - P4
- Cơ chế Guardrails chống hạ mức ưu tiên sai
- Hàng chờ điều phối (Priority-based + FIFO)
- Chức năng Điều phối viên xác nhận / ghi đè kèm Nhật ký Audit
"""

import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.ai.schemas import (
    ReliefRequestCreate,
    ReliefTriageResult,
    ReliefExtractedData,
    ReliefVerificationResult,
)
from app.ai.qwen_provider import QwenProvider
from app.ai.guardrails import ReliefGuardrailsEngine
from app.ai.verification import ReliefVerificationEngine
from app.fallback_storage import (
    save_fallback_relief_request,
    get_fallback_relief_queue,
    get_fallback_relief_request_by_id,
    override_fallback_relief_priority,
)


class TestReliefTriageAISystem(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.provider = QwenProvider(
            api_base="http://127.0.0.1:9999/v1",  # mock base to test fallback
            timeout_sec=0.5
        )

    # --------------------------------------------------------------------------
    # Kịch bản 1: Mắc kẹt trên mái nhà vùng ngập sâu (Trapped on roof)
    # --------------------------------------------------------------------------
    def test_scenario_01_trapped_on_roof(self):
        async def run():
            req = ReliefRequestCreate(
                message="Nước ngập đến nóc nhà rồi, 4 người chúng tôi đang trèo lên mái tôn chờ cứu hộ, nước chảy rất xiết!",
                contact_name="Lê Văn Hùng",
                phone="0988776655",
                location_text="Xóm Bến, Quang Vinh, Thái Nguyên",
                lat=21.5975,
                lng=105.8385
            )
            result = await self.provider.triage_relief_request(req)
            self.assertEqual(result.final_priority, "P1")
            self.assertIn("trapped_roof", result.extracted.mobility_status)
            self.assertTrue(result.extracted.immediate_danger)
            self.assertIn("RULE_P1_TRAPPED_ROOF", result.guardrails_applied)
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 2: Cấp cứu y tế / Người bị thương (Medical emergency)
    # --------------------------------------------------------------------------
    def test_scenario_02_medical_emergency(self):
        async def run():
            req = ReliefRequestCreate(
                message="Bà cụ 85 tuổi bị tai biến lên cơn co giật khó thở, nước ngập 1m cô lập không đưa đi viện được, cần cấp cứu gấp!",
                contact_name="Trần Văn Minh",
                phone="0912345678",
                location_text="Phường Hồng Hà, Yên Bái"
            )
            result = await self.provider.triage_relief_request(req)
            self.assertEqual(result.final_priority, "P1")
            self.assertTrue(result.extracted.medical_emergency)
            self.assertIn("RULE_P1_MEDICAL_EMERGENCY", result.guardrails_applied)
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 3: Nhóm người yếu thế (Trẻ em, Người già, Người khuyết tật)
    # --------------------------------------------------------------------------
    def test_scenario_03_vulnerable_people(self):
        async def run():
            req = ReliefRequestCreate(
                message="Gia đình có 2 cháu nhỏ 1 tuổi và 3 tuổi cùng 1 cụ già liệt giường, nước ngập 50cm, xin tiếp tế sữa và tã lót",
                contact_name="Nguyễn Thị Mai",
                phone="0901234567",
                location_text="Huyện Bảo Yên, Lào Cai"
            )
            result = await self.provider.triage_relief_request(req)
            self.assertIn(result.final_priority, ["P1", "P2"])  # Nhóm yếu thế ít nhất P2
            self.assertTrue(len(result.extracted.vulnerable_people) >= 2)
            self.assertIn("children", result.extracted.vulnerable_people)
            self.assertIn("elderly", result.extracted.vulnerable_people)
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 4: Nước đang dâng nhanh (Rising water trend)
    # --------------------------------------------------------------------------
    def test_scenario_04_rising_water_escalation(self):
        async def run():
            req = ReliefRequestCreate(
                message="Nước lũ cuồn cuộn đang dâng rất nhanh, 1 tiếng trước mới đến mắt cá chân giờ đã lên 1.2 mét tràn vào nhà!",
                contact_name="Hoàng Văn Thắng",
                location_text="Xã Nam Phương Tiến, Chương Mỹ, Hà Nội",
                lat=20.8930,
                lng=105.6590
            )
            result = await self.provider.triage_relief_request(req)
            self.assertEqual(result.extracted.water_trend, "rising")
            self.assertEqual(result.final_priority, "P1")  # Nước dâng nhanh >= 1m -> P1
            self.assertIn("RULE_P1_RISING_WATER_DEEP", result.guardrails_applied)
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 5: Yêu cầu thiếu vị trí (Missing location)
    # --------------------------------------------------------------------------
    def test_scenario_05_missing_location_handling(self):
        async def run():
            req = ReliefRequestCreate(
                message="Cứu chúng tôi với, nước vào ngập hết đồ đạc rồi!",
                phone="0988001122"
            )
            result = await self.provider.triage_relief_request(req)
            self.assertFalse(result.verification.has_valid_coords)
            self.assertEqual(result.verification.verification_status, "needs_verification")
            self.assertTrue(result.requires_human_review)
            self.assertIn("vị trí / tọa độ", result.extracted.missing_information)
            # Dữ liệu KHÔNG bị hủy bỏ mà được giữ lại để điều phối viên kiểm tra
            self.assertIsNotNone(result.request_id)
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 6: Dữ liệu mâu thuẫn (Conflicting information)
    # --------------------------------------------------------------------------
    def test_scenario_06_conflicting_information_detection(self):
        async def run():
            # Mâu thuẫn: nước đang rút nhưng lại báo trèo nóc nhà chìm ngập khẩn cấp
            req = ReliefRequestCreate(
                message="Nước đang rút bớt nhưng nhà tôi sắp chìm, đang trên nóc nhà nguy kịch cứu gấp!",
                location_text="Tam Nông, Phú Thọ"
            )
            result = await self.provider.triage_relief_request(req)
            self.assertTrue(len(result.verification.conflicts_detected) > 0)
            self.assertEqual(result.verification.verification_status, "needs_verification")
            # Dù có mâu thuẫn, do có nguy hiểm tính mạng vẫn không được hạ mức
            self.assertEqual(result.final_priority, "P1")
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 7: Nhiều yêu cầu cùng một vị trí (< 50m)
    # --------------------------------------------------------------------------
    def test_scenario_07_nearby_duplicate_detection(self):
        async def run():
            existing = [
                {
                    "request_id": "NS-PREV-01",
                    "lat": 21.0285,
                    "lng": 105.8542,
                    "phone": "0911111111"
                }
            ]
            # Yêu cầu mới cách điểm cũ ~10 mét
            req = ReliefRequestCreate(
                message="Nhà bên cạnh đã báo rồi, tôi báo thêm vì nhà tôi có trẻ con",
                lat=21.0286,
                lng=105.8543,
                phone="0922222222"
            )
            result = await self.provider.triage_relief_request(req, existing_requests=existing)
            self.assertTrue(result.verification.is_duplicate)
            self.assertEqual(result.verification.duplicate_of_id, "NS-PREV-01")
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 8: Yêu cầu trùng lặp số điện thoại (Duplicate phone)
    # --------------------------------------------------------------------------
    def test_scenario_08_exact_phone_duplicate(self):
        async def run():
            existing = [
                {
                    "request_id": "NS-FIRST-01",
                    "lat": 21.5,
                    "lng": 105.8,
                    "phone": "0987654321"
                }
            ]
            req = ReliefRequestCreate(
                message="Gọi lại lần 2 giục cứu hộ mau lên nước dâng thêm rồi",
                phone="0987654321"
            )
            result = await self.provider.triage_relief_request(req, existing_requests=existing)
            self.assertTrue(result.verification.is_duplicate)
            self.assertEqual(result.verification.duplicate_of_id, "NS-FIRST-01")
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 9: AI Timeout / Offline Fallback (Không mất dữ liệu)
    # --------------------------------------------------------------------------
    def test_scenario_09_ai_offline_fallback_zero_data_loss(self):
        async def run():
            # Giả lập Qwen Provider kết nối tới cổng không tồn tại -> bắt buộc kích hoạt fallback
            provider = QwenProvider(api_base="http://127.0.0.1:65530/v1", timeout_sec=0.1)
            req = ReliefRequestCreate(
                message="Gia đình 5 người ngập 1.5m nước chảy xiết tại Hạ Long, cần xuồng sơ tán khẩn",
                phone="0912456789",
                lat=20.9750,
                lng=107.0920
            )
            result = await provider.triage_relief_request(req)
            self.assertTrue(result.is_fallback)
            self.assertEqual(result.provider_used, "mock_offline_fallback")
            # Dữ liệu được trích xuất an toàn bằng Rule Engine
            self.assertEqual(result.extracted.people_count, 5)
            self.assertEqual(result.extracted.water_level_m, 1.5)
            self.assertIn("boat_evacuation", result.extracted.relief_needs)
            self.assertEqual(result.final_priority, "P1")
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kịch bản 10: AI trả về JSON sai định dạng (JSON Repair / Fallback)
    # --------------------------------------------------------------------------
    def test_scenario_10_malformed_json_handling(self):
        async def run():
            provider = QwenProvider()
            # Test sanitization với chuỗi có markdown và dấu phẩy thừa
            bad_json = """
            Chào bạn, dưới đây là kết quả phân tích:
            ```json
            {
              "request_id": "NS-TEST",
              "people_count": 3,
              "water_level_m": 0.8,
              "water_trend": "rising",
              "vulnerable_people": ["elderly",],
              "medical_emergency": false,
              "immediate_danger": false,
              "raw_ai_priority": "P2",
              "ai_priority_reasons": ["Nước đang dâng",],
            }
            ```
            Hy vọng thông tin này giúp ích cho đội cứu hộ.
            """
            cleaned = provider._sanitize_json(bad_json)
            parsed = json.loads(cleaned)
            self.assertEqual(parsed["request_id"], "NS-TEST")
            self.assertEqual(parsed["people_count"], 3)
            self.assertEqual(parsed["water_trend"], "rising")
            self.assertEqual(parsed["raw_ai_priority"], "P2")
        asyncio.run(run())

    # --------------------------------------------------------------------------
    # Kiểm thử Cơ chế Guardrails Chống hạ mức Ưu tiên (Anti-downgrade)
    # --------------------------------------------------------------------------
    def test_guardrails_prevent_downgrade(self):
        # AI đề xuất P3, nhưng có cấp cứu y tế và nước dâng 1.5m -> Phải cưỡng chế lên P1
        extracted = ReliefExtractedData(
            request_id="NS-GUARD-01",
            water_level_m=1.5,
            water_trend="rising",
            medical_emergency=True,
            immediate_danger=True,
            raw_ai_priority="P3",  # AI đánh giá thấp sai sót
            ai_priority_reasons=["AI ban đầu đánh giá P3"]
        )
        verification = ReliefVerificationResult(
            is_structurally_valid=True,
            has_valid_coords=True,
            has_valid_people_count=True,
            has_valid_water_level=True,
            verification_status="structurally_valid"
        )
        final_p, reasons, applied, was_prevented, review = ReliefGuardrailsEngine.evaluate_priority(extracted, verification)
        self.assertEqual(final_p, "P1")
        self.assertTrue(was_prevented)
        self.assertTrue(any("Ngăn chặn AI hạ mức ưu tiên sai" in r for r in reasons))

    # --------------------------------------------------------------------------
    # Kiểm thử REST API Hàng chờ Điều phối (Priority Queue Sorting & Filter)
    # --------------------------------------------------------------------------
    def test_api_relief_queue_and_override(self):
        # 1. Tạo 1 yêu cầu P1
        r1 = self.client.post("/api/relief/requests", json={
            "message": "Nước ngập nóc nhà Quang Vinh Thái Nguyên 2m nguy kịch!",
            "phone": "0988111222",
            "lat": 21.5975,
            "lng": 105.8385
        })
        self.assertEqual(r1.status_code, 201)
        data1 = r1.json()
        req1_id = data1["request_id"]
        self.assertEqual(data1["final_priority"], "P1")

        # 2. Tạo 1 yêu cầu P3 (chỉ cần lương thực)
        r2 = self.client.post("/api/relief/requests", json={
            "message": "Nước không vào nhà, xin hỗ trợ mì tôm và nước sạch dự phòng",
            "phone": "0988333444",
            "lat": 21.0300,
            "lng": 105.8500
        })
        self.assertEqual(r2.status_code, 201)
        data2 = r2.json()
        req2_id = data2["request_id"]
        self.assertEqual(data2["final_priority"], "P3")

        # 3. Lấy hàng chờ (xác thực Điều phối viên RBAC): P1 phải đứng trước P3
        login_res = self.client.post("/api/auth/login", json={
            "username": "coordinator_demo",
            "password": os.getenv("NORTHSTAR_DEMO_PASSWORD", "NorthStarDemo@2026"),
        })
        self.assertEqual(login_res.status_code, 200)
        coord_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        resp_q = self.client.get("/api/relief/queue", headers=coord_headers)
        self.assertEqual(resp_q.status_code, 200)
        items = resp_q.json()["items"]
        self.assertTrue(len(items) >= 2)

        # Kiểm tra thứ tự sắp xếp: Tất cả P1 phải xuất hiện trước P3
        priorities = [it["final_priority"] for it in items]
        if "P1" in priorities and "P3" in priorities:
            first_p1_idx = priorities.index("P1")
            first_p3_idx = priorities.index("P3")
            self.assertLess(first_p1_idx, first_p3_idx, "P1 phải đứng trước P3 trong hàng chờ điều phối")

        # 4. Người điều phối ghi đè mức ưu tiên của req2 từ P3 lên P2 kèm lý do
        override_resp = self.client.patch(f"/api/relief/queue/{req2_id}/override", json={
            "new_priority": "P2",
            "dispatcher_name": "Thiếu tá Nguyễn Văn Bình",
            "reason": "Thực địa ghi nhận khu vực chuẩn bị xả lũ, cần ưu tiên tiếp tế sớm."
        }, headers=coord_headers)
        self.assertEqual(override_resp.status_code, 200)
        updated_data = override_resp.json()["data"]
        self.assertEqual(updated_data["final_priority"], "P2")

        # 5. Kiểm tra audit trail
        detail_resp = self.client.get(f"/api/relief/queue/{req2_id}", headers=coord_headers)
        self.assertEqual(detail_resp.status_code, 200)
        history = detail_resp.json().get("override_history", [])
        self.assertTrue(any(h.get("actor") == "Thiếu tá Nguyễn Văn Bình" for h in history))

        # 6. Kiểm tra API stats
        stats_resp = self.client.get("/api/relief/stats", headers=coord_headers)
        self.assertEqual(stats_resp.status_code, 200)
        st = stats_resp.json()
        self.assertIn("by_priority", st)
        self.assertIn("total_requests", st)


if __name__ == "__main__":
    unittest.main()
