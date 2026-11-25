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
Router Điều phối Cứu hộ Đa điểm Thông minh (Multi-Stop Rescue Dispatch Optimization).
Tối ưu hóa thứ tự tiếp cận nhiều điểm SOS dựa trên:
1. Mức độ nguy cấp (HIGH/CRITICAL ưu tiên trước)
2. Nhóm đối tượng yếu thế (Trẻ nhỏ, người già có trọng số ưu tiên cao hơn)
3. Mực nước ngập và khả năng vượt chướng ngại của phương tiện (xuồng máy, xe tải, xe con)
4. Khoảng cách địa lý ngắn nhất (Greedy TSP với trọng số rủi ro)
"""

import math
from typing import Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from ..auth import AuthUser, record_audit_event, require_roles
from .sos import _fetch_sos_collection
from .shelters import list_shelters

router = APIRouter(prefix="/api/rescue", tags=["Điều phối Cứu hộ Đa điểm"])

class DispatchRequest(BaseModel):
    start_lat: float = Field(21.0285, description="Vĩ độ điểm xuất phát đội cứu hộ")
    start_lng: float = Field(105.8542, description="Kinh độ điểm xuất phát đội cứu hộ")
    sos_ids: Optional[list[int]] = Field(None, description="Danh sách ID các điểm SOS cần cứu nạn (để trống sẽ tự động lấy tất cả các điểm chờ cứu hộ)")
    vehicle_type: str = Field("truck", description="Loại phương tiện: boat (xuồng), truck (xe tải cứu hộ), car (ô tô gầm cao), motor (xe máy)")
    team_name: Optional[str] = Field("Đội Cứu nạn Phản ứng Nhanh", description="Tên đội cứu hộ")

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách đường chim bay giữa 2 điểm toạ độ (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.post("/dispatch", summary="Lập kế hoạch tối ưu cứu hộ đa điểm tuần tự")
def optimize_rescue_dispatch(
    req: DispatchRequest,
    user: AuthUser = Depends(require_roles("rescue", "coordinator", "admin")),
) -> dict[str, Any]:
    # Lấy toàn bộ SOS beacons hiện có
    sos_geojson = _fetch_sos_collection()
    record_audit_event("rescue_dispatch_plan", "dispatch", req.team_name, "success", f"vehicle={req.vehicle_type}", actor=user)
    all_beacons = {f["properties"]["id"]: f for f in sos_geojson.get("features", [])}

    target_beacons = []
    if req.sos_ids and len(req.sos_ids) > 0:
        for sid in req.sos_ids:
            if sid in all_beacons:
                target_beacons.append(all_beacons[sid])
    else:
        # Tự động chọn các điểm SOS chưa giải cứu
        target_beacons = [f for f in all_beacons.values() if f["properties"].get("status") != "rescued"]

    if not target_beacons:
        # Nếu tất cả đã giải cứu, lấy top 5 điểm gần nhất
        target_beacons = list(all_beacons.values())[:5]

    if not target_beacons:
        raise HTTPException(status_code=400, detail="Hiện không có điểm SOS nào cần điều phối cứu hộ.")

    # Xác định giới hạn ngập theo loại phương tiện
    vehicle_limits = {
        "boat": 999.0,     # Xuồng máy hoạt động được ở mọi mức nước sâu
        "truck": 55.0,     # Xe tải lội nước cứu hộ
        "car": 30.0,       # Ô tô gầm cao
        "motor": 20.0      # Xe máy
    }
    max_passable_depth = vehicle_limits.get(req.vehicle_type, 45.0)

    # Đánh giá trọng số ưu tiên cho từng điểm SOS
    scored_targets = []
    for f in target_beacons:
        p = f["properties"]
        coords = f["geometry"]["coordinates"]
        
        # Điểm cơ bản theo mức độ ưu tiên
        priority_scores = {"critical": 120, "high": 90, "medium": 60, "low": 30}
        score = priority_scores.get(str(p.get("priority", "medium")).lower(), 50)
        
        # Cộng điểm nếu có người già hoặc trẻ nhỏ (+40 điểm)
        if p.get("has_elderly_or_children"):
            score += 40
            
        # Cộng điểm theo số người mắc kẹt
        people = int(p.get("people_count") or 1)
        score += min(people * 8, 40)
        
        scored_targets.append({
            "id": p["id"],
            "contact_name": p["contact_name"],
            "phone": p["phone"],
            "people_count": people,
            "has_elderly_or_children": p.get("has_elderly_or_children", False),
            "water_level_cm": p.get("water_level_cm", 0.0),
            "priority": p.get("priority", "medium"),
            "score": score,
            "lat": coords[1],
            "lng": coords[0],
            "is_passable": (p.get("water_level_cm", 0.0) <= max_passable_depth)
        })

    # Thuật toán Greedy TSP với trọng số cứu hộ:
    # Tại mỗi bước, chọn điểm kế tiếp tối đa hóa: (score / (distance_km + 0.5))
    current_lat = req.start_lat
    current_lng = req.start_lng
    unvisited = list(scored_targets)
    ordered_stops = []
    total_distance_km = 0.0
    step_num = 1

    # Thêm điểm bắt đầu
    ordered_stops.append({
        "step": step_num,
        "type": "start",
        "title": f"Xuất phát: {req.team_name}",
        "lat": current_lat,
        "lng": current_lng,
        "action": "Tập kết đội hình & trang bị cứu nạn",
        "distance_from_prev_km": 0.0
    })

    while unvisited:
        best_candidate = None
        best_metric = -1.0
        best_dist = 0.0

        for candidate in unvisited:
            dist = haversine_km(current_lat, current_lng, candidate["lat"], candidate["lng"])
            # Metric ưu tiên: điểm cao và khoảng cách gần
            metric = candidate["score"] / (dist + 0.3)
            
            # Cảnh báo nếu phương tiện không vào được do nước quá sâu
            if not candidate["is_passable"]:
                metric *= 0.5 # Giảm độ ưu tiên đường bộ, cảnh báo cần chuyển tải xuồng

            if metric > best_metric:
                best_metric = metric
                best_candidate = candidate
                best_dist = dist

        step_num += 1
        total_distance_km += best_dist
        current_lat = best_candidate["lat"]
        current_lng = best_candidate["lng"]

        ordered_stops.append({
            "step": step_num,
            "type": "rescue",
            "sos_id": best_candidate["id"],
            "title": f"Cứu nạn #{best_candidate['id']}: {best_candidate['contact_name']}",
            "contact_name": best_candidate["contact_name"],
            "phone": best_candidate["phone"],
            "people_count": best_candidate["people_count"],
            "has_elderly_or_children": best_candidate["has_elderly_or_children"],
            "water_level_cm": best_candidate["water_level_cm"],
            "priority": best_candidate["priority"],
            "is_passable": best_candidate["is_passable"],
            "lat": current_lat,
            "lng": current_lng,
            "distance_from_prev_km": round(best_dist, 2),
            "action": f"Tiếp cận đưa {best_candidate['people_count']} nạn nhân lên phương tiện"
        })

        unvisited.remove(best_candidate)

    # Tìm trạm sơ tán an toàn gần nhất từ điểm cứu hộ cuối cùng
    shelters_geojson = list_shelters()
    shelter_features = shelters_geojson.get("features", [])
    nearest_shelter = None
    min_shelter_dist = 999999.0

    for s in shelter_features:
        s_coords = s["geometry"]["coordinates"]
        s_dist = haversine_km(current_lat, current_lng, s_coords[1], s_coords[0])
        if s_dist < min_shelter_dist:
            min_shelter_dist = s_dist
            nearest_shelter = s

    if nearest_shelter:
        s_props = nearest_shelter["properties"]
        s_coords = nearest_shelter["geometry"]["coordinates"]
        step_num += 1
        total_distance_km += min_shelter_dist
        ordered_stops.append({
            "step": step_num,
            "type": "shelter",
            "title": f"Trạm an toàn: {s_props['name']}",
            "shelter_id": s_props["id"],
            "address": s_props.get("address", ""),
            "contact_phone": s_props.get("contact_phone", ""),
            "lat": s_coords[1],
            "lng": s_coords[0],
            "distance_from_prev_km": round(min_shelter_dist, 2),
            "action": "Bàn giao nạn nhân vào khu sơ tán an toàn & y tế"
        })

    # Ước tính thời gian di chuyển (tốc độ xe ngập lũ ~ 20-30 km/h)
    avg_speed = 25.0
    estimated_duration_min = round((total_distance_km / avg_speed) * 60 + (len(target_beacons) * 15)) # 15 phút xử lý mỗi điểm

    # Tạo polyline toạ độ nối liền các chặng
    route_polyline = [[s["lat"], s["lng"]] for s in ordered_stops]

    return {
        "status": "success",
        "dispatch_id": f"DISPATCH-{int(req.start_lat*1000)}-{len(target_beacons)}",
        "team_name": req.team_name,
        "vehicle_type": req.vehicle_type,
        "max_passable_depth_cm": max_passable_depth,
        "total_stops": len(ordered_stops),
        "total_sos_targets": len(target_beacons),
        "total_people_rescued": sum(c["people_count"] for c in scored_targets),
        "total_distance_km": round(total_distance_km, 2),
        "estimated_duration_min": estimated_duration_min,
        "ordered_stops": ordered_stops,
        "route_polyline": route_polyline
    }
