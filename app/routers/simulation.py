"""
Router mô phỏng kịch bản ngập lụt theo dòng thời gian (Time-lapse Flood Timeline Simulator).
Cung cấp diễn biến mực nước 155 trạm đo qua các mốc thời gian T+0h, T+3h, T+6h, T+12h, T+24h
dựa trên lượng mưa mô phỏng hoàn lưu bão Yagi 2024.
"""

from typing import Any
from fastapi import APIRouter, Query

from .flood_points import DEFAULT_FLOOD_POINTS

router = APIRouter(prefix="/api/simulation", tags=["Mô phỏng Dòng thời gian Lũ lụt"])

TIMELINE_STEPS = [
    {
        "hour": 0,
        "label": "T+0h: Trước bão (Bình thường)",
        "rainfall_mm": 2.0,
        "weather_state": "Mây rải rác, gió nhẹ",
        "description": "Các trạm thủy văn và điểm đo nội đô đều trong ngưỡng an toàn, dòng chảy bình thường."
    },
    {
        "hour": 3,
        "label": "T+3h: Bão áp sát ven biển",
        "rainfall_mm": 35.0,
        "weather_state": "Mưa rào lớn, gió cấp 8",
        "description": "Quảng Ninh, Hải Phòng và Hà Nội bắt đầu ngập các điểm trũng thấp (10 - 20cm)."
    },
    {
        "hour": 6,
        "label": "T+6h: Đỉnh điểm bão đổ bộ",
        "rainfall_mm": 90.0,
        "weather_state": "Mưa xối xả, gió giật cấp 12",
        "description": "Nội đô ngập sâu (30 - 55cm). Báo động cấp 2 trên sông Cầu và sông Thương."
    },
    {
        "hour": 12,
        "label": "T+12h: Hoàn lưu mưa lũ thượng nguồn",
        "rainfall_mm": 170.0,
        "weather_state": "Mưa xối xả vùng núi, lũ quét",
        "description": "Lũ quét lịch sử Làng Nủ (Bảo Yên), Yên Bái ngập chìm, đê sông Bùi và đê Chã báo động đỏ cấp 3."
    },
    {
        "hour": 24,
        "label": "T+24h: Nước rút dần ở hạ lưu",
        "rainfall_mm": 20.0,
        "weather_state": "Mưa rải rác, lũ thượng nguồn rút chậm",
        "description": "Nội đô Hà Nội tiêu thoát cơ bản an toàn (<15cm), các vùng trũng Chương Mỹ, Yên Bái ngập dai dẳng."
    }
]

def calculate_step_depths(hour: int, rainfall_mm: float) -> list[dict[str, Any]]:
    """Tính toán mực nước dự báo cho 155 điểm theo từng mốc thời gian."""
    points_state = []
    
    # Hệ số tác động theo mốc giờ
    factor_map = {
        0: 0.05,
        3: 0.35,
        6: 0.90,
        12: 1.45,
        24: 0.40
    }
    factor = factor_map.get(hour, 0.5)

    for pt in DEFAULT_FLOOD_POINTS:
        base_depth = pt.get("depth_cm") or 0.0
        threshold = pt.get("threshold_cm") or 20.0
        pid = pt["id"]

        # Các trạm đặc thù miền núi / rốn ngập (Làng Nủ, Yên Bái, Chương Mỹ, v.v.)
        is_flash_flood_prone = pid in [131, 132, 133, 134, 135, 136, 137, 138, 142, 155]
        
        if hour == 0:
            sim_depth = 0.0 if not is_flash_flood_prone else min(base_depth * 0.15, 4.0)
        elif hour == 3:
            sim_depth = round(12.0 + (pid % 7) * 2.5, 1)
        elif hour == 6:
            sim_depth = round(32.0 + (pid % 9) * 3.5, 1)
        elif hour == 12:
            if is_flash_flood_prone:
                sim_depth = round(base_depth * 1.35 if base_depth > 0 else 55.0, 1)
            else:
                sim_depth = round(38.0 + (pid % 8) * 3.0, 1)
        elif hour == 24:
            if is_flash_flood_prone:
                sim_depth = round(base_depth * 0.65 if base_depth > 0 else 25.0, 1)
            else:
                sim_depth = round(max(3.0, (pid % 5) * 2.0), 1)
        else:
            sim_depth = round(rainfall_mm * 0.35, 1)

        # Xác định trạng thái cảnh báo
        if sim_depth < 5.0:
            status = "safe"
        elif sim_depth < threshold:
            status = "warning"
        else:
            status = "danger"

        points_state.append({
            "id": pid,
            "name": pt["name"],
            "lat": pt["lat"],
            "lng": pt["lng"],
            "simulated_depth_cm": sim_depth,
            "threshold_cm": threshold,
            "status": status
        })

    return points_state


@router.get("/timeline", summary="Lấy dữ liệu mô phỏng ngập lụt theo dòng thời gian")
def get_simulation_timeline(
    scenario: str = Query("yagi_typhoon", description="Tên kịch bản (VD: yagi_typhoon)"),
    hour: int = Query(None, description="Mốc thời gian cụ thể (0, 3, 6, 12, 24)")
) -> dict[str, Any]:
    """
    Trả về toàn bộ các mốc thời gian mô phỏng hoặc chi tiết 1 mốc thời gian cụ thể.
    """
    if hour is not None:
        matched_step = next((s for s in TIMELINE_STEPS if s["hour"] == hour), TIMELINE_STEPS[0])
        points = calculate_step_depths(matched_step["hour"], matched_step["rainfall_mm"])
        return {
            "scenario": scenario,
            "current_step": matched_step,
            "total_points": len(points),
            "safe_count": sum(1 for p in points if p["status"] == "safe"),
            "warning_count": sum(1 for p in points if p["status"] == "warning"),
            "danger_count": sum(1 for p in points if p["status"] == "danger"),
            "points": points
        }

    # Trả về tổng quan toàn bộ timeline
    return {
        "scenario": scenario,
        "title": "Mô phỏng Hoàn lưu Bão số 3 (Yagi) & Lũ lụt Lịch sử Miền Bắc",
        "description": "Kịch bản tổng hợp mô phỏng diễn biến lượng mưa từ 2mm đến 170mm và phản ứng thủy văn trên 155 trạm đo.",
        "steps": TIMELINE_STEPS
    }
