"""
Router dữ liệu khí tượng thủy văn & quan trắc thiên tai chuẩn mở quốc tế.
Tích hợp:
1. Open-Meteo Weather API & Flood API (Tuân thủ Open-Meteo Terms, Giấy phép CC-BY 4.0)
2. Copernicus GloFAS (Global Flood Awareness System)
3. NASA GPM (Global Precipitation Measurement - NASA Open Data Policy)
4. Danh mục Giấy phép Chuẩn OSI (Open Source Initiative) - Tuyệt đối không cào dữ liệu (Zero Scraping)
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from grasstoucher_core.weather import (
    fetch_hanoi_weather,
    fetch_open_meteo_flood,
    get_glofas_basin_status,
    fetch_nasa_gpm_precipitation,
    get_osi_open_data_registry,
)

router = APIRouter(prefix="/api/weather", tags=["Khí tượng & Thủy văn Mở (Open-Meteo / GloFAS / NASA GPM)"])
log = logging.getLogger("floodnav.weather")


@router.get(
    "/hanoi",
    summary="Dự báo thời tiết & lượng mưa theo giờ Hà Nội (Open-Meteo Weather API)",
    description="Truy xuất lượng mưa thực tế theo từng giờ từ Open-Meteo. Tuân thủ Open-Meteo Terms (CC-BY 4.0)."
)
def get_hanoi_weather():
    return fetch_hanoi_weather()


@router.get(
    "/flood-forecast",
    summary="Dự báo lưu lượng dòng chảy sông ngòi (Open-Meteo Flood API / Copernicus GloFAS)",
    description="Truy xuất lưu lượng dòng chảy sông (River Discharge m³/s) và ngưỡng nguy cơ lũ từ Open-Meteo Flood API vận hành bởi mô hình Copernicus GloFAS."
)
def get_flood_forecast(
    lat: float = Query(21.0285, description="Vĩ độ"),
    lng: float = Query(105.8542, description="Kinh độ"),
    basin_name: str = Query("Lưu vực Sông Hồng", description="Tên lưu vực sông"),
    forecast_days: int = Query(7, ge=1, le=14, description="Số ngày dự báo")
):
    return fetch_open_meteo_flood(lat=lat, lng=lng, basin_name=basin_name, forecast_days=forecast_days)


@router.get(
    "/glofas-basins",
    summary="Giám sát các lưu vực sông trọng điểm Bắc Bộ (Copernicus GloFAS Model)",
    description="Theo dõi lưu lượng và ngưỡng báo động lũ trên các sông: Sông Hồng, Sông Cầu, Sông Thao, Sông Lô."
)
def get_glofas_basins():
    return get_glofas_basin_status()


@router.get(
    "/nasa-gpm",
    summary="Quan trắc mưa vệ tinh không gian NASA GPM (Global Precipitation Measurement)",
    description="Truy xuất lượng mưa tích lũy 24h và cường độ mưa đỉnh theo chuẩn dữ liệu mở vệ tinh NASA IMERG."
)
def get_nasa_gpm_data(
    lat: float = Query(21.0285, description="Vĩ độ"),
    lng: float = Query(105.8030, description="Kinh độ"),
    location: str = Query("Hà Nội", description="Tên khu vực")
):
    return fetch_nasa_gpm_precipitation(lat=lat, lng=lng, location_name=location)


@router.get(
    "/open-data-licenses",
    summary="Danh mục Giấy phép Chuẩn Mở OSI & Cam kết Dữ liệu Mở (Zero Web Scraping)",
    description="Bảng kê khai tính hợp pháp bản quyền của toàn bộ dữ liệu (Open-Meteo, GloFAS, NASA GPM, OpenStreetMap) và mã nguồn chuẩn OSI."
)
def get_open_data_licenses():
    return get_osi_open_data_registry()
