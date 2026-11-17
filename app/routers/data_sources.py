"""Router cung cấp thông tin pháp lý, danh mục và giấy phép các nguồn Dữ liệu Mở (Open Data Sources) của hệ thống NorthStar."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/data-sources", tags=["Nguồn dữ liệu mở (Open Data)"])

OPEN_DATA_CATALOG = {
    "system": "NorthStar - Vietnam Disaster Intelligence & Multi-Hazard Response Ecosystem",
    "software_license": "Apache-2.0 License (100% Open Source Software)",
    "open_data_compliance": True,
    "total_sources": 5,
    "sources": [
        {
            "id": "osm",
            "name": "OpenStreetMap (OSM)",
            "organization": "OpenStreetMap Foundation (OSMF)",
            "url": "https://www.openstreetmap.org",
            "category": "Mạng lưới đường giao thông & Dữ liệu không gian",
            "license": "Open Database License (ODbL) 1.0",
            "license_type": "Open Data (Tự do khai thác & chia sẻ có ghi công)",
            "is_open_data": True,
            "usage_in_northstar": "Xây dựng đồ thị mạng lưới đường bộ (Road Network Graph) qua OSMnx và NetworkX; làm nền tảng tính toán thuật toán A* né ngập và Dijkstra sơ tán cứu hộ."
        },
        {
            "id": "copernicus_sentinel1",
            "name": "Copernicus Data Space Ecosystem (Sentinel-1 SAR)",
            "organization": "European Space Agency (ESA) & European Commission (EC)",
            "url": "https://dataspace.copernicus.eu",
            "category": "Ảnh viễn thám vệ tinh Radar khẩu độ tổng hợp (SAR)",
            "license": "Copernicus Full, Free and Open Access Policy (Regulation EU No 377/2014)",
            "license_type": "Open Satellite Data (Toàn diện, miễn phí và mở)",
            "is_open_data": True,
            "usage_in_northstar": "Vệ tinh radar băng C (SAR) xuyên mây bão 24/7, bóc tách vết ngập bề mặt (Water Inundation Mask) phục vụ xác định bán kính vùng ngập và sạt trượt nguy hiểm."
        },
        {
            "id": "opendevelopment_mekong",
            "name": "Open Development Mekong (ODM)",
            "organization": "Open Development Initiative (ODI)",
            "url": "https://data.vietnam.opendevelopmentmekong.net",
            "category": "Dữ liệu sông ngòi, lưu vực nước và môi trường",
            "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
            "license_type": "Open Data (Được phép sao chép, phân phối và biến đổi)",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp bản đồ số ranh giới thủy văn, mạng lưới lưu vực sông Hồng - Thái Bình, vị trí các hồ chứa thủy điện (Hòa Bình, Tuyên Quang, Thác Bà) và vùng trũng thấp."
        },
        {
            "id": "nchmf",
            "name": "Trung tâm Dự báo Khí tượng Thủy văn Quốc gia (NCHMF)",
            "organization": "Tổng cục Khí tượng Thủy văn - Bộ Tài nguyên và Môi trường Việt Nam",
            "url": "https://nchmf.gov.vn",
            "category": "Thông tin khí tượng, cấp độ rủi ro & báo động lũ",
            "license": "Dữ liệu công ích (Nghị định 47/2020/NĐ-CP & Luật Tiếp cận thông tin 2016)",
            "license_type": "Public Sector Information / Open Government Data",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp các mốc báo động lũ (Báo động 1, 2, 3) trên các trạm thủy văn Sông Hồng, Sông Thao, Sông Cầu, Sông Thương, Sông Lô, Sông Đáy và các bản tin cảnh báo lũ quét khẩn cấp."
        },
        {
            "id": "open_meteo",
            "name": "Open-Meteo Weather API",
            "organization": "Open-Meteo Inc.",
            "url": "https://open-meteo.com",
            "category": "Dữ liệu thời tiết & dự báo lượng mưa thời gian thực",
            "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
            "license_type": "Open API (Miễn phí phi thương mại có ghi công)",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp lượng mưa thực tế (mm/h) theo giờ tại các trạm quan trắc phục vụ mô hình AI Machine Learning (Gradient Boosting) dự báo mực nước dâng sau 30/60 phút."
        }
    ]
}

@router.get("", summary="Lấy danh mục các nguồn dữ liệu mở & giấy phép bản quyền")
def get_open_data_sources():
    """Trả về danh mục chi tiết các nguồn dữ liệu mở, cơ sở pháp lý và vai trò trong hệ thống NorthStar."""
    return OPEN_DATA_CATALOG
