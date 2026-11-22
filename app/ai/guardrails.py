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
Bộ Quy tắc Nghiệp vụ Phân loại & Chống hạ mức Ưu tiên Sai (Deterministic Guardrails Engine).
Đảm bảo:
1. AI chỉ mang tính chất đề xuất (Advisory Proposal), không tự quyết hoàn toàn.
2. Các dấu hiệu nguy hiểm đến tính mạng (đe dọa tức thời, cấp cứu y tế, nước dâng sâu,
   mắc kẹt nóc nhà, nhóm người yếu thế) TUYỆT ĐỐI KHÔNG BỊ HẠ MỨC ƯU TIÊN dù AI đề xuất P3/P4.
3. Khi dữ liệu thiếu hoặc có mâu thuẫn, gắn cờ cần xác minh và giữ nguyên trong hàng đợi khẩn cấp.
"""

from typing import List, Tuple
from .schemas import ReliefExtractedData, ReliefVerificationResult


# Thứ tự ưu tiên (Số càng nhỏ, mức độ khẩn cấp càng cao)
PRIORITY_RANKS = {
    "P1": 1,  # Nguy hiểm tức thời
    "P2": 2,  # Nguy cơ cao
    "P3": 3,  # Cần cứu trợ
    "P4": 4,  # Theo dõi
}


class ReliefGuardrailsEngine:
    """Động cơ quy tắc nghiệp vụ điều phối cứu nạn NorthStar."""

    @classmethod
    def evaluate_priority(
        cls,
        extracted: ReliefExtractedData,
        verification: ReliefVerificationResult
    ) -> Tuple[str, List[str], List[str], bool, bool]:
        """
        Đánh giá mức ưu tiên dựa trên bộ quy tắc bảo vệ và đối chiếu với AI.
        Trả về:
        (final_priority, final_reasons, guardrails_applied, was_downgrade_prevented, requires_human_review)
        """
        guardrails_applied: List[str] = []
        rule_reasons: List[str] = []
        rule_min_priority = "P4"

        def upgrade_rule_priority(target_priority: str, rule_name: str, reason: str):
            nonlocal rule_min_priority
            guardrails_applied.append(rule_name)
            rule_reasons.append(reason)
            # Càng nhỏ càng khẩn cấp
            if PRIORITY_RANKS[target_priority] < PRIORITY_RANKS[rule_min_priority]:
                rule_min_priority = target_priority

        # ----------------------------------------------------------------------
        # QUY TẮC P1: NGUY HIỂM TỨC THỜI (Đe dọa trực tiếp đến tính mạng)
        # ----------------------------------------------------------------------
        # 1. Cấp cứu y tế hoặc chấn thương nghiêm trọng
        if extracted.medical_emergency:
            upgrade_rule_priority(
                "P1",
                "RULE_P1_MEDICAL_EMERGENCY",
                "Phát hiện trường hợp cấp cứu y tế khẩn cấp hoặc chấn thương đe dọa tính mạng"
            )

        # 2. Nguy hiểm tính mạng tức thời (sập nhà, lũ cuốn, mắc kẹt cô lập hoàn toàn)
        if extracted.immediate_danger:
            upgrade_rule_priority(
                "P1",
                "RULE_P1_IMMEDIATE_DANGER",
                "Có dấu hiệu đe dọa trực tiếp đến tính mạng cần can thiệp giải cứu tức thì"
            )

        # 3. Nước dâng nhanh kết hợp mực nước sâu (>= 1.0m)
        if extracted.water_trend == "rising" and extracted.water_level_m is not None and extracted.water_level_m >= 1.0:
            upgrade_rule_priority(
                "P1",
                "RULE_P1_RISING_WATER_DEEP",
                f"Mực nước dâng nhanh và ngập sâu ({extracted.water_level_m:.1f}m), nguy cơ nhấn chìm công trình"
            )

        # 4. Ngập cực sâu (>= 1.8m) bất kể xu hướng
        if extracted.water_level_m is not None and extracted.water_level_m >= 1.8:
            upgrade_rule_priority(
                "P1",
                "RULE_P1_EXTREME_DEPTH",
                f"Mực nước ngập vượt quá chiều cao người lớn ({extracted.water_level_m:.1f}m)"
            )

        # 5. Mắc kẹt trên mái nhà hoặc tum/gác lửng không còn đường thoát
        if extracted.mobility_status in ("trapped_roof", "trapped_attic"):
            upgrade_rule_priority(
                "P1",
                "RULE_P1_TRAPPED_ROOF",
                "Người dân bị cô lập trên mái nhà/mái tôn, mất hoàn toàn lối thoát hiểm đường bộ"
            )

        # ----------------------------------------------------------------------
        # QUY TẮC P2: NGUY CƠ CAO (Có người dễ bị tổn thương, nguy cơ cô lập)
        # ----------------------------------------------------------------------
        # 6. Có nhóm người dễ bị tổn thương (trẻ em, người già, người khuyết tật, thai phụ)
        if len(extracted.vulnerable_people) > 0:
            v_str = ", ".join(extracted.vulnerable_people)
            upgrade_rule_priority(
                "P2",
                "RULE_P2_VULNERABLE_POPULATION",
                f"Có người cần hỗ trợ đặc biệt ({v_str}), sức chống chịu kém trong lũ lụt"
            )

        # 7. Nước đang dâng nhưng chưa đến ngưỡng P1 (nước dâng từ 0.3m đến < 1.0m)
        if extracted.water_trend == "rising" and (extracted.water_level_m is None or extracted.water_level_m < 1.0):
            upgrade_rule_priority(
                "P2",
                "RULE_P2_RISING_WATER_EARLY",
                "Nước lũ đang có xu hướng tiếp tục dâng, nguy cơ trở thành ngập sâu"
            )

        # 8. Mực nước ngập ngang thắt lưng (0.7m - 1.7m)
        if extracted.water_level_m is not None and 0.7 <= extracted.water_level_m < 1.8:
            upgrade_rule_priority(
                "P2",
                "RULE_P2_MODERATE_DEPTH",
                f"Mực nước ngập đáng kể ({extracted.water_level_m:.1f}m), hạn chế nghiêm trọng khả năng tự sơ tán"
            )

        # 9. Bị cô lập chia cắt không thể tự di chuyển
        if extracted.mobility_status in ("isolated", "cannot_move"):
            upgrade_rule_priority(
                "P2",
                "RULE_P2_ISOLATED_MOBILITY",
                "Khu vực bị cô lập chia cắt hoặc người gặp nạn mất khả năng tự sơ tán"
            )

        # ----------------------------------------------------------------------
        # QUY TẮC P3: CẦN CỨU TRỢ (Nhu cầu thiết yếu, chưa nguy hiểm tức thời)
        # ----------------------------------------------------------------------
        if len(extracted.relief_needs) > 0 and rule_min_priority == "P4":
            upgrade_rule_priority(
                "P3",
                "RULE_P3_ESSENTIAL_RELIEF",
                "Có nhu cầu tiếp tế thiết yếu (lương thực, nước uống, thuốc men cơ bản)"
            )

        # ----------------------------------------------------------------------
        # SO SÁNH VỚI ĐỀ XUẤT BAN ĐẦU CỦA AI (CHỐNG HẠ MỨC ƯU TIÊN SAI)
        # ----------------------------------------------------------------------
        ai_prop = extracted.raw_ai_priority if extracted.raw_ai_priority in PRIORITY_RANKS else "P3"
        ai_rank = PRIORITY_RANKS[ai_prop]
        rule_rank = PRIORITY_RANKS[rule_min_priority]

        was_downgrade_prevented = False
        final_priority = ai_prop
        all_reasons = list(extracted.ai_priority_reasons)

        if rule_rank < ai_rank:
            # Quy tắc phát hiện tình huống nguy hiểm hơn AI đánh giá
            # CẤM HẠ MỨC: Bắt buộc nâng lên mức khẩn cấp hơn của Quy tắc
            final_priority = rule_min_priority
            was_downgrade_prevented = True
            all_reasons.insert(0, f"🛡️ [GUARDRAIL CAN THIỆP]: Ngăn chặn AI hạ mức ưu tiên sai ({ai_prop} ➔ {final_priority}).")
            for r in rule_reasons:
                if r not in all_reasons:
                    all_reasons.append(r)
        elif rule_rank > ai_rank:
            # AI phát hiện ngữ cảnh phức tạp hơn và đề xuất mức cao hơn quy tắc tối thiểu
            # Tôn trọng đề xuất khẩn cấp của AI (không tự ý hạ xuống của AI)
            final_priority = ai_prop
            for r in rule_reasons:
                if r not in all_reasons:
                    all_reasons.append(r)
        else:
            final_priority = ai_prop
            for r in rule_reasons:
                if r not in all_reasons:
                    all_reasons.append(r)

        # ----------------------------------------------------------------------
        # ĐÁNH GIÁ YÊU CẦU XÁC MINH CỦA CON NGƯỜI (HUMAN REVIEW)
        # ----------------------------------------------------------------------
        requires_human_review = True  # Luôn cần người điều phối xác nhận trước khi điều động phương tiện
        if verification.conflicts_detected:
            all_reasons.append(f"⚠️ Phát hiện {len(verification.conflicts_detected)} mâu thuẫn dữ liệu cần xác minh.")
        if not verification.has_valid_coords and not extracted.location_text:
            all_reasons.append("⚠️ Chưa có thông tin vị trí địa lý cụ thể.")

        return final_priority, all_reasons, guardrails_applied, was_downgrade_prevented, requires_human_review
