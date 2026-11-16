"""
Router Định tuyến Sơ tán Khẩn cấp (Evacuation Routing).
Kết nối trực tiếp thuật toán Dijkstra Đa nguồn & Trở kháng Đa thiên tai từ grasstoucher_core.
"""
import logging
from fastapi import APIRouter, HTTPException

from grasstoucher_core.routing import find_evacuation_route
from ..graph import get_graph, fetch_flood_sources, GraphNotReady
from ..schemas import EvacuationRouteRequest
from .shelters import list_shelters
from .disasters import list_disasters

log = logging.getLogger("northstar.evacuation")
router = APIRouter(prefix="/api/route", tags=["Định tuyến Sơ tán"])


@router.post("/evacuate")
def calculate_evacuation_route(body: EvacuationRouteRequest):
    """
    Tìm lộ trình sơ tán tối ưu tới trạm cứu hộ an toàn gần nhất:
    - Tránh các cung đường ngập sâu, sạt lở hoặc cây đổ
    - Hỗ trợ các phương tiện: đi bộ (walk), xe máy (motorbike), ô tô (car)
    """
    try:
        graph = get_graph()
    except GraphNotReady as e:
        raise HTTPException(503, f"Đồ thị giao thông chưa sẵn sàng: {e}")

    # 1. Thu thập danh sách điểm sơ tán còn mở cửa
    shelters_fc = list_shelters(status="open")
    shelters = [
        {
            "id": f["properties"]["id"],
            "name": f["properties"]["name"],
            "address": f["properties"].get("address"),
            "lng": f["geometry"]["coordinates"][0],
            "lat": f["geometry"]["coordinates"][1],
            "capacity": f["properties"]["capacity"],
            "current_occupancy": f["properties"]["current_occupancy"],
            "contact_phone": f["properties"].get("contact_phone"),
            "status": f["properties"]["status"],
        }
        for f in shelters_fc.get("features", [])
    ]

    if not shelters:
        raise HTTPException(404, "Không có điểm sơ tán nào khả dụng trong hệ thống.")

    # 2. Thu thập các nguồn thiên tai (ngập lụt và các sự kiện nguy cơ khác)
    flood_sources = fetch_flood_sources(use_ai_prediction=True)
    hazard_map = graph.flood_edges(flood_sources)

    # Bổ sung các vùng thiên tai đa dạng từ router disasters
    try:
        disasters_fc = list_disasters(active_only=True)
        disaster_hazards = [
            {
                "lng": f["geometry"]["coordinates"][0],
                "lat": f["geometry"]["coordinates"][1],
                "hazard_type": f["properties"]["hazard_type"],
                "severity": f["properties"]["severity"],
                "radius_m": f["properties"].get("radius_m", 150.0),
                "name": f["properties"]["title"],
                "passable": False if f["properties"]["severity"] in ("high", "critical") else True
            }
            for f in disasters_fc.get("features", [])
        ]
        disaster_edges = graph.hazard_edges(disaster_hazards)
        hazard_map.update(disaster_edges)
    except Exception as e:
        log.warning("Không thể hợp nhất dữ liệu đa thiên tai vào hazard_map: %s", e)

    # 3. Chạy thuật toán tìm đường sơ tán từ Core
    res = find_evacuation_route(
        graph=graph,
        hazard_map=hazard_map,
        origin_lng=body.origin.lng,
        origin_lat=body.origin.lat,
        shelters=shelters,
        vehicle=body.vehicle
    )

    if not res.get("found"):
        raise HTTPException(422, res.get("reason", "Không thể tìm thấy lộ trình sơ tán an toàn."))

    return res
