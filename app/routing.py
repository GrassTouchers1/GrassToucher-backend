"""
GrassToucher Backend - Routing Bridge.
Kế thừa trực tiếp giải thuật A* và tính toán chi phí cạnh từ grasstoucher_core.routing.
Bảo toàn 100% tương thích ngược cho mọi module gọi app.routing.
"""
from grasstoucher_core.routing import (
    vehicle_limit,
    flood_penalty,
    edge_cost,
    best_edge,
    find_path,
    edge_coords,
    describe_route,
    calculate_routes,
    slice_coords_to_proj,
)

__all__ = [
    "vehicle_limit",
    "flood_penalty",
    "edge_cost",
    "best_edge",
    "find_path",
    "edge_coords",
    "describe_route",
    "calculate_routes",
    "slice_coords_to_proj",
]
