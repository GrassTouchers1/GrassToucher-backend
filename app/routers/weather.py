"""
Router lấy dữ liệu thời tiết & dự báo lượng mưa Hà Nội từ Open-Meteo API.
Kế thừa bộ nhớ đệm (Cache 5 phút) từ grasstoucher_core.weather.
"""
import logging
from fastapi import APIRouter
from grasstoucher_core.weather import fetch_hanoi_weather

router = APIRouter(prefix="/api/weather", tags=["Thời tiết & Lượng mưa"])
log = logging.getLogger("floodnav.weather")


@router.get("/hanoi")
def get_hanoi_weather():
    """
    Lấy dự báo lượng mưa theo từng giờ trong ngày của Hà Nội từ Open-Meteo API.
    Có cơ chế bộ nhớ đệm 5 phút từ Core để tối ưu hiệu năng.
    """
    return fetch_hanoi_weather()
