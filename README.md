# 🚀 NORTHSTAR Backend – Multi-Hazard Geo-API Gateway & Disaster Intelligence Hub

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![OSI Approved](https://img.shields.io/badge/OSI-Approved%20Open%20Source-brightgreen.svg)](https://opensource.org/licenses)
[![Changelog](https://img.shields.io/badge/Changelog-Keep%20a%20Changelog-orange.svg)](CHANGELOG.md)
[![Building from Source](https://img.shields.io/badge/Build-From%20Source-blue.svg)](INSTALL.md)
[![Release](https://img.shields.io/badge/Release-v1.0.0-green.svg)](https://github.com/GrassTouchers1/GrassToucher-backend/releases)
[![Bug Tracker](https://img.shields.io/badge/Bug%20Tracker-GitHub%20Issues-red.svg)](https://github.com/GrassTouchers1/GrassToucher-backend/issues)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20PostGIS-336791.svg?logo=postgresql)](https://postgis.net/)
[![Alembic](https://img.shields.io/badge/Migrations-Alembic-red.svg)](https://alembic.sqlalchemy.org/)
[![WebSocket](https://img.shields.io/badge/WebSocket-W3C%20Standard-4A154B.svg)](https://websockets.readthedocs.io/)
[![Whisper AI](https://img.shields.io/badge/AI-Whisper%20Voice%20SOS-orange.svg)](https://openai.com/research/whisper)
[![Tests Passing](https://img.shields.io/badge/Tests-28%2F28%20Passing-brightgreen.svg)](https://docs.python.org/3/library/unittest.html)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> **Cổng giao tiếp dịch vụ API RESTful, WebSocket định vị thời gian thực, xử lý âm thanh Voice SOS bằng AI và Trung tâm Tình báo Thiên tai.**  
> Dự án 100% Mã nguồn mở, kế thừa FloodNav, tích hợp PostGIS, Alembic Migrations, cơ chế Circuit Breaker Fallback (Zero-Downtime) và kết nối trực tiếp với thư viện thuật toán lõi `grasstoucher_core`.

---

## 🎯 1. Vai trò trong Hệ sinh thái NORTHSTAR

Backend đóng vai trò trục xương sống xử lý dữ liệu phục vụ đồng thời 2 phân hệ người dùng:
1. **NORTHSTAR COMMAND (Trung tâm Tiếp nhận & Điều phối Tác chiến):**
   - Tiếp nhận dòng tin tức thời từ nhiều nguồn: Người dân báo nạn (SOS), tin cộng đồng, tổng đài PCCC 114, cảm biến thủy văn IoT và ảnh viễn thám radar Sentinel-1 SAR.
   - Thẩm định, lọc trùng không gian 50m (Spatial Deduplication) và đóng gói dữ liệu tác chiến chuyển giao cho các đội cứu hộ thực địa (PCCC 114, Cấp cứu 115, Chữ Thập Đỏ, Đoàn xe 4x4, Đội thợ lặn).
   - Tự động biên soạn Báo cáo Tác chiến quân sự SitRep và hỗ trợ mô phỏng bão lũ 0–100mm.
2. **NORTHSTAR CITIZEN (Ứng dụng Dân sự PWA):**
   - Cung cấp định tuyến né ngập A* theo thời gian thực cho xe máy và ô tô.
   - Cứu hộ khẩn cấp bằng giọng nói (Voice SOS) với nhận diện tiếng Việt và bóc tách tọa độ tự động.
   - Tìm kiếm điểm sơ tán an toàn gần nhất bằng thuật toán Multi-target Dijkstra.

---

## 🏗️ 2. Kiến trúc Hệ thống

```mermaid
flowchart TD
    subgraph Clients["Tầng Giao Diện & Người Dùng"]
        CMD["NORTHSTAR COMMAND<br/>(Trung Tâm Điều Phối & Đóng Gói Tin)"]
        CTZ["NORTHSTAR CITIZEN<br/>(Ứng dụng Dân sự PWA)"]
        RESCUE["Lực Lượng Cứu Hộ Thực Địa<br/>(PCCC 114, 115, Xe 4x4, Thợ lặn)"]
    end

    subgraph Backend["NorthStar Backend (FastAPI Gateway)"]
        ROUTER["20 RESTful Routers (/api/...)"]
        WS["WebSocket Server (/ws/navigation)"]
        VOICE["AI Speech-to-Text Pipeline (Whisper + NER Geocoding)"]
        CB["Circuit Breaker Engine (Zero Downtime)"]
    end

    subgraph Core["Core Engine (Zero-DB Algorithmic Package)"]
        CORE["grasstoucher_core<br/>(A* Né Ngập, Multi-target Dijkstra, TSP, ML Thủy Văn)"]
    end

    subgraph Storage["Tầng Lưu Trữ Dữ Liệu"]
        DB[("PostgreSQL 16 + PostGIS<br/>(Primary Spatial DB)")]
        FALLBACK[("SQLite / In-Memory Fallback<br/>(Tự động kích hoạt khi DB chính ngắt)")]
    end

    CMD <-->|"HTTP REST / OpenAPI"| ROUTER
    CTZ <-->|"HTTP REST / Voice SOS"| ROUTER
    CTZ <-->|"Realtime GPS Re-routing"| WS
    ROUTER --> VOICE
    ROUTER --> CB
    CB <-->|"Primary Online"| DB
    CB -.->|"Circuit Breaker Active"| FALLBACK
    ROUTER --> CORE
    CMD -.->|"Gói Tin Tác Chiến (Zalo / SMS / QR)"| RESCUE
```

---

## 📡 3. Danh mục API Tác chiến (OpenAPI Specification)

Toàn bộ hệ thống bao gồm 20 Router chuyên dụng được phân nhóm rõ ràng:

### 3.1. Tiếp nhận & Đóng gói Chuyển giao Cứu hộ (Intake & Tactical Hand-off)
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET / POST** | `/api/sos` | Danh sách yêu cầu SOS khẩn cấp / Phát tín hiệu cầu cứu từ người dân |
| **POST** | `/api/sos/voice` | Tiếp nhận file ghi âm giọng nói, chuyển văn bản qua Whisper AI và tự động bóc tách tọa độ/địa chỉ |
| **PATCH** | `/api/sos/{id}/status` | Cập nhật tiến độ xử lý (`pending`, `verified`, `in_progress`, `rescued`) |
| **GET / POST** | `/api/rescue-dispatch/packages` | Đóng gói thông tin cứu nạn chuyển giao (Tọa độ, link Google Maps, nhân khẩu, độ sâu ngập, lộ trình A*, điểm sơ tán) |
| **POST** | `/api/rescue-dispatch/export-zalo` | Sinh gói tin chuẩn hóa 1-chạm gửi trực tiếp qua Zalo/SMS cho Chỉ huy đội cứu hộ |
| **GET / POST** | `/api/reports` | Tiếp nhận tin báo dân sự kèm ảnh hiện trường; tự động khử trùng lặp 50m |
| **POST** | `/api/reports/{id}/verify` | Thẩm định viên xác nhận hoặc bác bỏ tin báo thiên tai |

### 3.2. Giám sát Tình báo Thiên tai & Viễn thám (Disaster Intelligence)
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET / POST** | `/api/flood-points` | Danh sách trạm quan trắc ngập toàn Miền Bắc (GeoJSON) |
| **POST** | `/api/readings` | Cảm biến IoT gửi chuỗi thời gian mực nước tự động |
| **GET** | `/api/weather/realtime` | Lấy dữ liệu nhiệt độ, độ ẩm, lượng mưa thời gian thực từ Open-Meteo API |
| **GET** | `/api/predictions` | Dự báo mực nước dâng sau 30/60 phút bằng Scikit-Learn Gradient Boosting |
| **GET** | `/api/satellite/sar` | Dữ liệu viễn thám radar vệ tinh Sentinel-1 SAR bóc tách vết ngập xuyên mây |
| **POST** | `/api/simulation/storm-surge` | Giả lập lượng mưa bão 0–100mm và dự báo phạm vi mở rộng vùng cô lập |

### 3.3. Không gian Địa lý & Sơ tán An toàn (GIS & Evacuation)
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET / POST** | `/api/shelters` | Mạng lưới điểm sơ tán kiên cố (sức chứa, tồn kho lương thực, nước sạch, áo phao) |
| **GET** | `/api/shelters/nearest` | Tìm điểm sơ tán tối ưu gần nhất theo tọa độ GPS |
| **GET / POST** | `/api/disasters` | Bản đồ phân vùng thiên tai trọng điểm (Lũ lụt, sạt lở, cô lập giao thông) |
| **POST** | `/api/route` | Tìm 2 lộ trình song song: **Nhanh nhất** và **Né ngập an toàn A\*** |
| **POST** | `/api/route/evacuate` | Định tuyến sơ tán khẩn cấp (Multi-target Dijkstra né vùng nguy hiểm đến nơi an toàn) |
| **WS** | `/ws/navigation` | Kênh WebSocket hai chiều theo dõi vị trí GPS và tự động **Re-routing** khi gặp ngập mới |

### 3.4. Báo cáo Tác chiến SitRep & Pháp lý Dữ liệu Mở
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET** | `/api/sitrep/latest` | Sinh tự động Báo cáo Tác chiến chuẩn quân sự (SitRep) định dạng Markdown/PDF |
| **GET** | `/api/data-sources` | Minh bạch danh mục 100% nguồn dữ liệu mở, cơ quan phát hành và giấy phép bản quyền |
| **GET** | `/api/health` | Kiểm tra tình trạng kết nối PostGIS, trạng thái Circuit Breaker và tài nguyên hệ thống |

> 📚 Swagger UI tài liệu API tương tác trực tiếp có sẵn tại: `http://localhost:8000/docs`

---

## ⚡ 4. Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Chuẩn bị Môi trường ảo & Thư viện
```bash
git clone -b dev https://github.com/GrassTouchers1/GrassToucher-backend.git
cd GrassToucher-backend

# Khởi tạo môi trường ảo Python
python -m venv venv

# Kích hoạt trên Windows:
.\venv\Scripts\activate
# Hoặc trên Linux/macOS:
source venv/bin/activate

# Cài đặt Core Engine và toàn bộ dependencies
pip install -e ../GrassToucher-core
pip install -r requirements.txt
```

### Bước 2: Cấu hình Cơ sở Dữ liệu
Sao chép file `.env.example` thành `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/floodnav
FALLBACK_MODE=auto
OPEN_METEO_URL=https://api.open-meteo.com/v1/forecast
PORT=8000
```
> 💡 **Cơ chế Fallback Tự Động:** Nếu máy chủ không cài đặt PostgreSQL hoặc dịch vụ đang tạm ngắt, backend sẽ **ngay lập tức kích hoạt Circuit Breaker Fallback** (sử dụng SQLite và In-Memory Seed Storage). Toàn bộ 20 router và giao diện người dùng vẫn hoạt động 100% bình thường với đầy đủ dữ liệu mẫu của 155 trạm, 12 vùng nguy hiểm, 15 điểm sơ tán và 14 tin SOS.

Nếu có PostgreSQL, chạy migration cấu trúc dữ liệu với Alembic:
```bash
alembic upgrade head
```

### Bước 3: Khởi chạy Máy chủ API
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 🧪 5. Kiểm thử Tự động (Automated Test Suite)

Toàn bộ backend được bảo vệ bởi bộ test case tự động bao phủ A* Routing, Multi-target Dijkstra, Voice SOS Geocoding, Fallback Storage và các API Endpoints:

```bash
# Chạy bộ 28 bài kiểm thử tự động
$env:PYTHONPATH = ".;..\GrassToucher-core"
python -m unittest discover -s tests
```

**Kết quả kiểm thử thực tế:**
```text
Ran 28 tests in 22.862s
OK
[Benchmark] Thời gian tìm đường A* né ngập (2235 nút): 145.05 ms
```

---

## 🌍 6. Nguồn Dữ liệu Mở & Tính Pháp lý Bản quyền (Open Data Compliance)

Hệ thống tuân thủ nghiêm ngặt nguyên tắc **100% Open Data & Open Source** (Tuyệt đối không cào web lậu, không sử dụng API đóng, không phụ thuộc cổng KTTV Quốc gia NCHMF), tra cứu minh bạch qua `GET /api/data-sources`:
- **[OpenStreetMap (OSM)](https://www.openstreetmap.org)**: Giấy phép ODbL 1.0 (Open Data) - Mạng lưới giao thông và không gian đô thị.
- **[Copernicus Sentinel-1 SAR](https://dataspace.copernicus.eu)**: EU Copernicus Open Access Policy - Viễn thám radar vệ tinh xuyên mây bão bóc tách vết ngập bề mặt 24/7.
- **[Copernicus GloFAS (Global Flood Awareness System)](https://www.globalfloods.eu)**: EU Copernicus Policy - Cảnh báo lũ sớm, lưu lượng xả đáy và dòng chảy sông ngòi quốc tế.
- **[Open Development Mekong (ODM)](https://data.vietnam.opendevelopmentmekong.net)**: Giấy phép CC-BY 4.0 - Thủy văn sông ngòi, lưu vực sông Hồng - Thái Bình và hồ chứa thủy điện.
- **[Open-Meteo Weather API](https://open-meteo.com)**: Giấy phép CC-BY 4.0 - Dự báo nhiệt độ, sức gió và lượng mưa thời gian thực.
- **[OpenAQ Air Quality Network](https://openaq.org)**: Giấy phép CC-BY 4.0 - Mạng lưới 18 trạm quan trắc chất lượng không khí, chỉ số US AQI, bụi mịn PM2.5, PM10, CO, NO₂.
- **[NASA GPM IMERG](https://gpm.nasa.gov)**: NASA Open Data Policy - Đo lượng mưa vệ tinh viễn thám mở toàn cầu.

---

## 📄 7. Tuyên Bố Giấy Phép & Tuân Thủ Chuẩn Mã Nguồn Mở (OSI & PoF Compliance)

Toàn bộ phân hệ Backend được phát hành và kiểm định nghiêm ngặt theo các tiêu chuẩn mã nguồn mở quốc tế:
- ⚖️ **Giấy phép phần mềm:** [Apache License 2.0](LICENSE) (OSI-Approved, `SPDX-License-Identifier: Apache-2.0` gắn trên từng tệp mã nguồn).
- 📋 **Báo cáo kiểm định bản quyền:** [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).
- 📦 **Hướng dẫn dịch & cài đặt từ mã nguồn sạch:** [INSTALL.md](INSTALL.md).
- 📝 **Lịch sử phiên bản phát hành:** [CHANGELOG.md](CHANGELOG.md) (Chuẩn Keep a Changelog v1.1.0 & Semantic Versioning v2.0.0).
- 🤝 **Quy chuẩn đóng góp:** [CONTRIBUTING.md](CONTRIBUTING.md).
- 🐛 **Hệ thống Quản lý Lỗi (Bug Tracker):** Tiếp nhận tại [GitHub Issues](https://github.com/GrassTouchers1/GrassToucher-backend/issues) với Issue Templates chuẩn trong `.github/ISSUE_TEMPLATE/`.
- 🏷️ **Bản phát hành chính thức dự thi:** [Release v1.0.0](https://github.com/GrassTouchers1/GrassToucher-backend/releases/tag/v1.0.0).
