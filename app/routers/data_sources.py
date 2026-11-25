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

"""Router cung cấp thông tin pháp lý, danh mục và giấy phép các nguồn Dữ liệu Mở (Open Data Sources) của hệ thống NorthStar."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/data-sources", tags=["Nguồn dữ liệu mở (Open Data)"])

OPEN_DATA_CATALOG = {
    "system": "NorthStar - Vietnam Disaster Intelligence & Multi-Hazard Response Ecosystem",
    "software_license": "Apache-2.0 License (100% Open Source Software)",
    "open_data_compliance": True,
    "total_sources": 6,
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
            "id": "openaq",
            "name": "OpenAQ & Open-Meteo Air Quality Open Data Network",
            "organization": "OpenAQ Community & Open-Meteo",
            "url": "https://openaq.org",
            "category": "Mạng lưới quan trắc chất lượng không khí & bụi mịn mở",
            "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
            "license_type": "Open Data (Tự do khai thác, chia sẻ và tích hợp)",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp chỉ số US AQI, nồng độ bụi mịn PM2.5, PM10, khí CO, NO2 thời gian thực của 18 trạm quan trắc trên toàn Miền Bắc, đưa ra cảnh báo hô hấp và khuyến cáo y tế tức thì."
        },
        {
            "id": "copernicus_glofas",
            "name": "Copernicus GloFAS (Global Flood Awareness System)",
            "organization": "European Centre for Medium-Range Weather Forecasts (ECMWF)",
            "url": "https://www.globalfloods.eu",
            "category": "Hệ thống cảnh báo sớm và dự báo lưu lượng lũ sông toàn cầu",
            "license": "Copernicus Open Access Policy (Regulation EU No 377/2014)",
            "license_type": "Open Satellite & Hydrological Data",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp mốc cảnh báo lũ, lưu lượng xả đáy và lưu lượng dòng chảy các lưu vực sông lớn (Sông Hồng, Sông Thao, Sông Lô) hoàn toàn trên chuẩn mở FOSS/OSI."
        },
        {
            "id": "nasa_gpm",
            "name": "NASA GPM (Global Precipitation Measurement)",
            "organization": "NASA Earth Science Data Systems",
            "url": "https://gpm.nasa.gov",
            "category": "Dữ liệu vệ tinh đo lượng mưa toàn cầu mở",
            "license": "NASA Open Data Policy (Free & Open Access)",
            "license_type": "Public Open Data",
            "is_open_data": True,
            "usage_in_northstar": "Cung cấp dữ liệu tích lũy mưa vệ tinh IMERG viễn thám, hỗ trợ kiểm chứng độc lập trường mưa và bổ trợ mô hình dự báo ngập lụt đa nguồn."
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


MODELS_ECOSYSTEM = {
    "system": "NorthStar - Multi-Hazard Advanced Modeling & Computational Ecosystem",
    "license": "Apache-2.0 (100% Free & Open Source Software)",
    "independent_of_proprietary_clouds": True,
    "pillars": [
        {
            "pillar_id": 1,
            "category": "Mô hình Vật lý Khí tượng & Thủy văn (Physics-based Simulation)",
            "technologies": [
                {
                    "name": "WRF (Weather Research and Forecasting)",
                    "license": "Public Domain",
                    "role": "Mô phỏng khí tượng số quy mô khu vực (NWP), dự báo bão, mưa lớn và áp thấp nhiệt đới.",
                    "integration_mode": "Scenario Ingestion (Nạp các trường mưa kịch bản bão lịch sử như bão Yagi)"
                },
                {
                    "name": "ANUGA Hydrodynamic Engine",
                    "license": "Open Source (Python / 2D SWE)",
                    "role": "Mô phỏng dòng chảy, độ sâu và vận tốc nước bằng phương trình nước nông 2D (Shallow Water Equations).",
                    "integration_mode": "Offline Scenario Matrix (Mô phỏng tiền tính toán kịch bản ngập lụt, vỡ đê và lũ quét)"
                },
                {
                    "name": "Deltares SFINCS",
                    "license": "GPL-3.0",
                    "role": "Mô phỏng ngập kết hợp đa yếu tố (Compound Flooding: Mưa lớn + Lũ sông + Triều cường ven biển).",
                    "integration_mode": "Coastal & Riverine Inundation Boundary Export"
                }
            ]
        },
        {
            "pillar_id": 2,
            "category": "Trí tuệ Nhân tạo & Học máy (AI & Machine Learning)",
            "technologies": [
                {
                    "name": "Scikit-Learn (Active in NorthStar Core)",
                    "license": "BSD-3-Clause",
                    "role": "Gradient Boosting Regressor dự báo mực nước dâng sau 30/60 phút theo thời gian thực (<5ms).",
                    "status": "production_active"
                },
                {
                    "name": "LightGBM",
                    "license": "MIT",
                    "role": "Gradient Boosting tối ưu tốc độ và dung lượng bộ nhớ cho tập dữ liệu chuỗi thời gian lớn.",
                    "status": "scalable_alternative"
                },
                {
                    "name": "PyTorch / MMDetection",
                    "license": "BSD / Apache-2.0",
                    "role": "Mạng nơ-ron tích chập (U-Net) phân đoạn vết ngập và nhận diện phương tiện, nhà cửa từ ảnh viễn thám.",
                    "status": "research_offline"
                }
            ]
        },
        {
            "pillar_id": 3,
            "category": "Bản đồ số & Quản lý Địa không gian (GIS Tier)",
            "technologies": [
                {
                    "name": "PostGIS 16 (Active in NorthStar Backend)",
                    "license": "GPL-2.0+",
                    "role": "Cơ sở dữ liệu không gian, lập chỉ mục R-Tree (GIST) và xử lý không gian (ST_DWithin, ST_Intersects, ST_Buffer).",
                    "status": "production_active"
                },
                {
                    "name": "QGIS Desktop",
                    "license": "GPL-2.0+",
                    "role": "Biên tập, chuẩn hóa ranh giới hành chính 63 tỉnh thành, mạng lưới lưu vực sông và xuất bản shapefiles.",
                    "status": "desktop_gis_authoring"
                },
                {
                    "name": "GeoServer",
                    "license": "GPL-2.0",
                    "role": "Phân phối các lớp dữ liệu bản đồ ngập lụt diện rộng qua các chuẩn WMS / WFS / WCS.",
                    "status": "wms_distribution_ready"
                }
            ]
        },
        {
            "pillar_id": 4,
            "category": "Định tuyến Thông minh & Dẫn đường Cứu hộ (Routing Engine)",
            "technologies": [
                {
                    "name": "NorthStar Adaptive A* & Multi-target Dijkstra (Active in Core)",
                    "license": "Apache-2.0",
                    "role": "Định tuyến né ngập thích ứng theo loại phương tiện (xe máy 20cm, ô tô 30cm) và sơ tán khẩn cấp đến nơi trú ẩn.",
                    "status": "production_active"
                },
                {
                    "name": "Valhalla Routing Engine",
                    "license": "MIT",
                    "role": "Bộ máy tìm đường C++ hiệu năng cao trên nền OpenStreetMap quy mô toàn quốc.",
                    "status": "national_scale_roadmap"
                }
            ]
        },
        {
            "pillar_id": 5,
            "category": "Dữ liệu Vệ tinh Viễn thám & Tái phân tích Khí tượng (Observation & Reanalysis)",
            "technologies": [
                {
                    "name": "Copernicus Sentinel-1 SAR",
                    "license": "EU Copernicus Open Access Policy",
                    "role": "Ảnh radar vệ tinh băng C xuyên mây bão 24/7 bóc tách vết ngập bề mặt (Water Inundation Mask).",
                    "status": "active_schema_supported"
                },
                {
                    "name": "NASA GPM IMERG",
                    "license": "NASA Open Data",
                    "role": "Lượng mưa viễn thám vệ tinh toàn cầu cập nhật mỗi 30 phút phục vụ quan trắc độc lập.",
                    "status": "active_schema_supported"
                },
                {
                    "name": "ECMWF ERA5",
                    "license": "Copernicus Climate Data Store",
                    "role": "Dữ liệu tái phân tích khí quyển lịch sử phục vụ huấn luyện và đánh giá mô hình.",
                    "status": "training_dataset_source"
                }
            ]
        }
    ]
}

@router.get("/models-ecosystem", summary="Khung kiến trúc mô hình vật lý, AI và GIS mở của NorthStar")
def get_models_ecosystem():
    """Trả về chi tiết 5 trụ cột công nghệ mô hình hóa mở: Khí tượng vật lý (WRF), Thủy văn 2D (ANUGA/SFINCS), AI/ML, GIS và Định tuyến."""
    return MODELS_ECOSYSTEM
