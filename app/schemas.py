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

"""Các mô hình dữ liệu (validate đầu vào cho API)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class FloodPointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lng: float = Field(ge=-180, le=180, description="Kinh độ")
    lat: float = Field(ge=-90, le=90, description="Vĩ độ")
    sensor_id: Optional[str] = Field(default=None, max_length=60)
    threshold_cm: int = Field(default=20, ge=1, le=200)


class FloodPointUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    sensor_id: Optional[str] = Field(default=None, max_length=60)
    threshold_cm: Optional[int] = Field(default=None, ge=1, le=200)

    @model_validator(mode="after")
    def lng_lat_together(self):
        if (self.lng is None) != (self.lat is None):
            raise ValueError("Phải gửi cả lng và lat cùng nhau (hoặc không gửi cả hai)")
        return self


class ReadingCreate(BaseModel):
    """Số đo mực nước. Gửi kèm point_id HOẶC sensor_id."""
    depth_cm: float = Field(ge=0, le=500)
    point_id: Optional[int] = None
    sensor_id: Optional[str] = None
    source: Literal["sensor", "crowd", "ai"] = "sensor"

    @model_validator(mode="after")
    def need_point_or_sensor(self):
        if self.point_id is None and not self.sensor_id:
            raise ValueError("Cần gửi point_id hoặc sensor_id")
        return self


class ReportCreate(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    level: Literal["light", "medium", "heavy"]
    user_id: Optional[int] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)


class ReportClear(BaseModel):
    """Người dùng báo 'đã hết ngập' tại vị trí của họ."""
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class LngLat(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class RouteRequest(BaseModel):
    origin: LngLat
    destination: LngLat
    vehicle: Literal["motorbike", "car"] = "motorbike"
    use_ai_prediction: bool = False


# ==========================================
# NORTHSTAR MULTI-HAZARD & DISASTER SCHEMAS
# ==========================================

class DisasterCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    hazard_type: Literal["flood", "landslide", "storm", "heavy_rain", "flash_flood", "other"] = "flood"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["warning", "active", "receding", "resolved"] = "active"
    description: Optional[str] = Field(default=None, max_length=500)
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    radius_m: float = Field(default=150.0, ge=10.0, le=50000.0)


class ShelterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: Optional[str] = Field(default=None, max_length=250)
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    capacity: int = Field(default=200, ge=1, le=50000)
    current_occupancy: int = Field(default=0, ge=0)
    contact_phone: Optional[str] = Field(default=None, max_length=30)
    supplies_status: Optional[str] = Field(default="Sẵn sàng (Lương thực & Y tế)", max_length=120)
    status: Literal["open", "full", "closed"] = "open"


class SOSCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=8, max_length=20)
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    people_count: int = Field(default=1, ge=1, le=100)
    has_elderly_or_children: bool = False
    water_level_cm: float = Field(default=0.0, ge=0.0, le=500.0)
    priority: Literal["low", "medium", "high", "critical"] = "high"
    notes: Optional[str] = Field(default=None, max_length=500)


class SOSStatusUpdate(BaseModel):
    status: Literal["pending", "acknowledged", "dispatched", "rescued", "cancelled"]


class EvacuationRouteRequest(BaseModel):
    origin: LngLat
    vehicle: Literal["walk", "motorbike", "car"] = "walk"

