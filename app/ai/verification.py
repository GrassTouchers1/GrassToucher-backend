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
Module Xác minh Dữ liệu Yêu cầu Cứu trợ (Relief Data Verification Engine).
Phân biệt rõ:
- Hợp lệ về cấu trúc (Structurally Valid)
- Đã xác minh nguồn (Source Verified)
- Đã xác minh nội dung (Content Verified)
- Chưa đủ thông tin hoặc có mâu thuẫn (Needs Verification)

Quy tắc:
1. Thông tin do AI trích xuất KHÔNG được coi là thông tin đã xác minh.
2. Yêu cầu chưa xác minh nhưng có dấu hiệu nguy hiểm vẫn PHẢI GIỮ trong hàng đợi khẩn cấp.
3. Không tự động từ chối hoặc xóa yêu cầu khi thông tin bị thiếu hoặc mâu thuẫn.
"""

import math
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from .schemas import ReliefExtractedData, ReliefVerificationResult


# Tọa độ bao bọc lãnh thổ Việt Nam mở rộng (Bounding Box)
VN_BOUNDS = {
    "min_lat": 8.0,
    "max_lat": 24.5,
    "min_lng": 101.5,
    "max_lng": 110.5,
}

# Các nguồn tin cậy đã xác minh nguồn gốc
VERIFIED_SOURCES = {"hotline_114", "command_center", "rescue_team", "police", "local_authority", "field_recon"}


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Tính khoảng cách Haversine giữa 2 tọa độ theo mét."""
    R = 6371000.0  # bán kính Trái Đất (mét)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class ReliefVerificationEngine:
    """Động cơ kiểm tra tính hợp lệ, phát hiện trùng lặp và mâu thuẫn dữ liệu."""

    @classmethod
    def verify_request(
        cls,
        extracted: ReliefExtractedData,
        source: Optional[str] = "community",
        existing_requests: Optional[List[dict]] = None
    ) -> ReliefVerificationResult:
        notes: List[str] = []
        conflicts: List[str] = []

        # 1. Kiểm tra cấu trúc cơ bản
        is_structurally_valid = True
        if not extracted.request_id:
            is_structurally_valid = False
            notes.append("Thiếu mã yêu cầu (request_id)")

        # 2. Kiểm tra tính hợp lệ của tọa độ
        has_valid_coords = False
        if extracted.lat is not None and extracted.lng is not None:
            lat, lng = float(extracted.lat), float(extracted.lng)
            if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
                if (VN_BOUNDS["min_lat"] <= lat <= VN_BOUNDS["max_lat"] and
                    VN_BOUNDS["min_lng"] <= lng <= VN_BOUNDS["max_lng"]):
                    has_valid_coords = True
                    notes.append(f"Tọa độ GPS chuẩn xác trong lãnh thổ Việt Nam [{lat:.4f}, {lng:.4f}]")
                else:
                    has_valid_coords = False
                    conflicts.append(f"Tọa độ [{lat}, {lng}] nằm ngoài phạm vi hoạt động cứu nạn Việt Nam")
            else:
                conflicts.append("Tọa độ GPS vượt ngoài giới hạn địa lý [-90..90, -180..180]")
        else:
            notes.append("Chưa có tọa độ GPS số, cần hỗ trợ định vị thủ công từ địa chỉ")

        # 3. Kiểm tra số lượng người
        has_valid_people_count = False
        if extracted.people_count is not None:
            try:
                cnt = int(extracted.people_count)
                if 1 <= cnt <= 1000:
                    has_valid_people_count = True
                elif cnt <= 0:
                    conflicts.append(f"Số người khai báo không hợp lệ ({cnt} người)")
                else:
                    conflicts.append(f"Số người bất thường cần kiểm tra thực địa ({cnt} người)")
            except (ValueError, TypeError):
                conflicts.append("Số người không đúng định dạng số nguyên")
        else:
            notes.append("Chưa rõ số lượng người cụ thể (mặc định giả định ít nhất 1 người)")

        # 4. Kiểm tra mực nước
        has_valid_water_level = False
        if extracted.water_level_m is not None:
            try:
                wl = float(extracted.water_level_m)
                if 0.0 <= wl <= 25.0:
                    has_valid_water_level = True
                else:
                    conflicts.append(f"Mực nước khai báo ({wl}m) vượt ngưỡng vật lý thông thường")
            except (ValueError, TypeError):
                conflicts.append("Mực nước không đúng định dạng số thực theo mét")

        # 5. Kiểm tra thời gian
        has_valid_timestamp = True
        if extracted.timestamp:
            try:
                # Kiểm tra parse thời gian
                parsed = datetime.fromisoformat(extracted.timestamp.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if parsed > now:
                    # Chênh lệch quá 2 giờ tương lai
                    if (parsed - now).total_seconds() > 7200:
                        conflicts.append("Thời gian yêu cầu ở tương lai so với hiện tại")
                        has_valid_timestamp = False
            except Exception:
                # Nếu chuỗi tự do dạng "10 phút trước", vẫn chấp nhận
                has_valid_timestamp = True

        # 6. Phát hiện mâu thuẫn nội tại (Semantic Conflicts)
        # 6.1 Mâu thuẫn nước rút nhưng ngập nóc / nguy kịch
        if extracted.water_trend == "receding" and extracted.immediate_danger:
            conflicts.append("Mâu thuẫn: Ghi nhận nước đang rút nhưng trạng thái báo nguy hiểm tức thời/ngập nóc")

        # 6.2 Khả năng tự di chuyển mâu thuẫn với chấn thương/liệt
        if "medical_patient" in extracted.vulnerable_people or "bedridden" in extracted.vulnerable_people:
            if extracted.mobility_status == "can_walk":
                conflicts.append("Mâu thuẫn: Có bệnh nhân nằm liệt/cần cấp cứu nhưng trạng thái báo có thể tự đi lại")

        # 6.3 Người báo 0 người nhưng có danh sách người dễ tổn thương
        if extracted.people_count is not None and extracted.people_count == 0 and len(extracted.vulnerable_people) > 0:
            conflicts.append("Mâu thuẫn: Khai báo 0 người nhưng có danh sách nhóm đối tượng yếu thế")

        # 7. Phát hiện trùng lặp (Duplicate Detection)
        is_duplicate = False
        duplicate_of_id = None

        if existing_requests and len(existing_requests) > 0:
            req_phone = (extracted.contact_phone or "").strip()
            # Bỏ ký tự đặc biệt trong số điện thoại để so khớp
            clean_req_phone = re.sub(r"[^\d]", "", req_phone) if req_phone else ""

            for existing in existing_requests:
                ex_id = str(existing.get("request_id") or existing.get("id"))
                if ex_id == str(extracted.request_id):
                    continue

                # So khớp số điện thoại giống nhau
                ex_phone = str(existing.get("phone") or existing.get("contact_phone") or "")
                clean_ex_phone = re.sub(r"[^\d]", "", ex_phone) if ex_phone else ""
                if clean_req_phone and len(clean_req_phone) >= 9 and clean_req_phone == clean_ex_phone:
                    is_duplicate = True
                    duplicate_of_id = ex_id
                    notes.append(f"Trùng số điện thoại liên hệ với yêu cầu [{ex_id}]")
                    break

                # So khớp khoảng cách địa lý rất gần (< 50m)
                ex_lat = existing.get("lat")
                ex_lng = existing.get("lng")
                if has_valid_coords and ex_lat is not None and ex_lng is not None:
                    try:
                        dist = haversine_distance_m(float(extracted.lat), float(extracted.lng), float(ex_lat), float(ex_lng))
                        if dist <= 50.0:
                            is_duplicate = True
                            duplicate_of_id = ex_id
                            notes.append(f"Vị trí cách yêu cầu [{ex_id}] chỉ {dist:.1f}m (khả năng cùng một hộ dân/khu nhà)")
                            break
                    except Exception:
                        pass

        # 8. Xác định cấp độ xác minh (Verification Status)
        # Nguồn tin chính thống -> source_verified
        # Đã kiểm tra không mâu thuẫn -> structurally_valid
        # Thiếu thông tin cốt lõi (vị trí) hoặc có mâu thuẫn -> needs_verification
        src = (source or "community").lower().strip()
        if conflicts:
            verification_status = "needs_verification"
            notes.append("Yêu cầu cần xác minh do phát hiện mâu thuẫn dữ liệu")
        elif not has_valid_coords and not extracted.location_text:
            verification_status = "needs_verification"
            notes.append("Yêu cầu cần xác minh vì thiếu hoàn toàn thông tin vị trí")
        elif src in VERIFIED_SOURCES:
            verification_status = "source_verified"
            notes.append(f"Nguồn tin chính thống ({src}) đã được xác thực nguồn")
        elif is_structurally_valid:
            verification_status = "structurally_valid"
            notes.append("Dữ liệu hợp lệ về mặt cấu trúc cú pháp")
        else:
            verification_status = "unverified"

        return ReliefVerificationResult(
            is_structurally_valid=is_structurally_valid,
            has_valid_coords=has_valid_coords,
            has_valid_people_count=has_valid_people_count,
            has_valid_water_level=has_valid_water_level,
            has_valid_timestamp=has_valid_timestamp,
            is_duplicate=is_duplicate,
            duplicate_of_id=duplicate_of_id,
            conflicts_detected=conflicts,
            verification_status=verification_status,
            verification_notes=notes
        )
