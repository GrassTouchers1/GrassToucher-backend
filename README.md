# 🚀 NORTHSTAR Backend – Multi-Hazard Geo-API Gateway & Disaster Intelligence Hub

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![OSI Approved](https://img.shields.io/badge/OSI-Approved%20Open%20Source-brightgreen.svg)](https://opensource.org/licenses)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20PostGIS-336791.svg?logo=postgresql)](https://postgis.net/)
[![Alembic](https://img.shields.io/badge/Migrations-Alembic-red.svg)](https://alembic.sqlalchemy.org/)
[![WebSocket](https://img.shields.io/badge/WebSocket-W3C%20Standard-4A154B.svg)](https://websockets.readthedocs.io/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> **Cổng giao tiếp dịch vụ API RESTful, WebSocket dẫn đường thời gian thực và quản lý nghiệp vụ đa thiên tai.**  
> Dự án 100% Mã nguồn mở, kế thừa FloodNav, tích hợp PostGIS, Alembic Migrations, cơ chế Circuit Breaker Fallback và kết nối trực tiếp với package `grasstoucher_core`.

---

## 🏗️ 1. Kiến trúc Hệ thống

```mermaid
flowchart TD
    subgraph Client["Frontend / Web PWA / Clients"]
        WEB["NorthStar PWA Interface"]
    end

    subgraph Backend["NorthStar Backend (FastAPI)"]
        API["REST Endpoints (/api/...)"]
        WS["WebSocket Server (/ws/navigation)"]
        CB["Circuit Breaker Engine"]
    end

    subgraph Core["Core Engine (Zero-DB Package)"]
        CORE["grasstoucher_core (A*, Multi-target Dijkstra, Hydrology AI)"]
    end

    subgraph Storage["Data Tier"]
        DB[("PostgreSQL 16 + PostGIS")]
        FALLBACK[("SQLite / In-Memory Fallback")]
    end

    WEB <-->|"HTTP REST"| API
    WEB <-->|"Realtime GPS, Alerts & SOS"| WS
    API --> CB
    CB <-->|"Primary"| DB
    CB -.->|"Circuit Breaker Fallback"| FALLBACK
    API --> CORE
```

---

## 📡 2. Danh mục API chính (OpenAPI Specification)

### 2.1. Quản lý Đa thiên tai & Cứu hộ (NorthStar New Modules)
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET / POST** | `/api/disasters` | Lấy danh sách vùng thiên tai (lũ lụt, sạt lở, bão) / Khai báo vùng mới |
| **GET / POST** | `/api/shelters` | Danh sách điểm sơ tán, cứu hộ an toàn (sức chứa, tài nguyên) / Tạo mới |
| **GET** | `/api/shelters/nearest` | Tìm điểm sơ tán gần nhất theo tọa độ GPS và bán kính tìm kiếm |
| **GET / POST** | `/api/sos` | Danh sách yêu cầu cứu trợ khẩn cấp / Phát tín hiệu cầu cứu SOS từ người dân |
| **PATCH** | `/api/sos/{id}/status` | Đội cứu hộ cập nhật trạng thái SOS (`pending`, `verified`, `in_progress`, `rescued`) |
| **POST** | `/api/route/evacuate` | Định tuyến sơ tán khẩn cấp (Multi-target Dijkstra né vùng nguy hiểm đến nơi an toàn) |

### 2.2. Kế thừa FloodNav (Bảo toàn 100% Tương thích ngược)
| Phương thức | Đường dẫn | Chức năng nghiệp vụ |
|---|---|---|
| **GET** | `/api/health` | Kiểm tra trạng thái hệ thống, kết nối PostGIS và chế độ Fallback |
| **GET / POST** | `/api/flood-points` | Danh sách 130 điểm ngập (GeoJSON) / Tạo trạm quan trắc mới |
| **POST** | `/api/readings` | Cảm biến IoT gửi chuỗi thời gian mực nước |
| **POST** | `/api/reports` | Báo cáo ngập cộng đồng (Tự xác nhận khi $\ge 3$ báo cáo / 100m / 15p) |
| **POST** | `/api/route` | Tìm 2 lộ trình song song: **Nhanh nhất** và **Né ngập an toàn** |
| **GET** | `/api/weather/hanoi` | Lấy dữ liệu lượng mưa thực tế theo giờ từ Open-Meteo API |
| **GET** | `/api/predictions` | Dự báo mực nước dâng sau 30/60 phút bằng Scikit-Learn |
| **WS** | `/ws/navigation` & `/ws/navigation/{session_id}` | Kênh WebSocket hai chiều theo dõi GPS và tự động **Re-routing** |

Tài liệu Swagger UI tương tác trực tiếp có sẵn tại: `http://localhost:8000/docs`

---

## ⚡ 3. Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Tạo môi trường ảo & Cài đặt thư viện
```bash
git clone https://github.com/GrassTouchers1/GrassToucher-backend.git
cd GrassToucher-backend

python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Cài đặt Core package và dependencies
pip install -e ../GrassToucher-core
pip install -r requirements.txt
```

### Bước 2: Migration Database với Alembic (Tùy chọn PostgreSQL)
- Cấu hình file `.env` chứa `DATABASE_URL=postgresql://user:password@localhost:5432/floodnav`.
- Chạy migration tự động:
  ```bash
  alembic upgrade head
  ```
*(Lưu ý: Nếu không cấu hình PostgreSQL, hệ thống tự động kích hoạt chế độ SQLite / In-Memory Fallback tích hợp sẵn dữ liệu mẫu cho 5 vùng thiên tai, 6 điểm sơ tán và 130 điểm ngập).*

### Bước 3: Khởi chạy Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```


---

## 📄 4. Giấy phép Bản quyền (License)
Phát hành theo giấy phép **Apache License 2.0 (OSI-Approved)**. Xem chi tiết tại [LICENSE](LICENSE).  
Quy định tham gia đóng góp: [CONTRIBUTING.md](CONTRIBUTING.md).
