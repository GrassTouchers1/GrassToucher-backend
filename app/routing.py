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
