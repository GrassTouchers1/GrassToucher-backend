# DANH MỤC NGUỒN DỮ LIỆU MỞ & BẢN QUYỀN SỞ HỮU TRÍ TUỆ
## OPEN DATA REGISTRY & ATTRIBUTION MANIFEST – NORTHSTAR OS

> **Dự án:** NORTHSTAR – Open-source Emergency Response OS  
> **Cam kết Pháp lý:** 100% dữ liệu sử dụng trong hệ thống có nguồn gốc hợp pháp, minh bạch, tuân thủ giấy phép dữ liệu mở quốc tế.  
> **Tuyên ngôn:** **TUYỆT ĐỐI KHÔNG CÀO DỮ LIỆU TRÁI PHÉP (ZERO WEB SCRAPING)** từ các cổng thông tin đóng hoặc trang web cơ quan nhà nước không cấp phép.  

---

## 1. BẢNG TỔNG HỢP CÁC NGUỒN DỮ LIỆU MỞ CHÍNH THỨC

| Tên Nguồn Dữ Liệu | Đơn Vị Cung Cấp | Đường Dẫn Chính Thức | Giấy Phép / Điều Khoản | Cơ Chế Truy Xuất | Vai Trò Kỹ Thuật Trong NorthStar |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenStreetMap (OSM)** | OpenStreetMap Foundation | [openstreetmap.org](https://www.openstreetmap.org) | **ODbL 1.0** (Open Database License) | Overpass API / OSMnx / GraphML | Cung cấp mạng lưới hình học đường bộ, các nút giao thông, cầu cống để xây dựng đồ thị toán học cho thuật toán tìm đường né ngập $A^*$ và sơ tán Dijkstra. |
| **Copernicus GloFAS** | Ủy ban Châu Âu & ECMWF | [global-flood.emergency.copernicus.eu](https://global-flood.emergency.copernicus.eu/) | **Copernicus Open Access Policy** / CC-BY 4.0 | Open-Meteo Flood REST API | Cung cấp mô hình thủy văn toàn cầu dự báo lưu lượng dòng chảy sông ngòi ($m^3/s$) và ngưỡng vượt chu kỳ lặp lũ (2 năm, 5 năm, 20 năm) trên các lưu vực sông ngòi Việt Nam. |
| **Open-Meteo Weather API** | Open-Meteo GmbH | [open-meteo.com/en/terms](https://open-meteo.com/en/terms) | **Creative Commons CC-BY 4.0** | REST JSON API (Fair Use) | Cung cấp chuỗi số liệu lượng mưa thực tế theo giờ (mm/h), độ ẩm đất và dự báo thời tiết ngắn hạn nạp vào mô hình AI Gradient Boosting. |
| **NASA GPM IMERG** | NASA Earth Science Data Systems | [gpm.nasa.gov/data](https://gpm.nasa.gov/data) | **NASA Open Data Policy** (Public Domain) | Earthdata / Open Data Products | Dữ liệu viễn thám không gian đo mưa đa vệ tinh phục vụ theo dõi mưa bão cực đoan trên diện rộng, đánh giá nguy cơ lũ quét và sạt lở đất vùng cao. |
| **Copernicus Sentinel-1 SAR** | Cơ quan Vũ trụ Châu Âu (ESA) | [dataspace.copernicus.eu](https://dataspace.copernicus.eu) | **EU Open Access Policy** | Copernicus Data Space OData API | Radar khẩu độ tổng hợp C-band SAR có khả năng xuyên qua mây mù, mưa bão 24/7 để phân tích vết ngập nước (Water Inundation Mask) và khoanh vùng bán kính nguy hiểm. |
| **OpenAQ Air Quality Network** | OpenAQ Community & Open-Meteo | [openaq.org](https://openaq.org) | **Creative Commons CC-BY 4.0** | REST JSON API | Mạng lưới trạm quan trắc chỉ số US AQI, bụi mịn PM2.5, PM10 thời gian thực cho 26 tỉnh thành miền Bắc. |

---

## 2. QUY CHUẨN GHI CÔNG & ĐIỀU KHOẢN SỬ DỤNG (ATTRIBUTION SPECIFICATIONS)

### 2.1. OpenStreetMap
- **Yêu cầu ghi công:** `"© OpenStreetMap contributors, ODbL 1.0"`.
- **Triển khai trong NorthStar:** Đã tích hợp nhãn bản quyền ở góc dưới bên phải bản đồ Leaflet trên toàn bộ các phân hệ (`map_core.js`).

### 2.2. Open-Meteo & Copernicus GloFAS
- **Yêu cầu ghi công:** `"Weather and flood data by Open-Meteo.com under CC-BY 4.0 (GloFAS model)"`.
- **Điều khoản Fair Use:**
  - Hệ thống tích hợp bộ nhớ đệm **In-Memory Cache (TTL 5 phút / 300 giây)** trong `grasstoucher_core/weather.py`.
  - Không gửi yêu cầu liên tục, khai báo rõ `User-Agent: GrassToucher-OpenSource-Research/1.0`.

### 2.3. NASA GPM (Global Precipitation Measurement)
- **Yêu cầu ghi công:** `"Data provided by NASA Global Precipitation Measurement (GPM) program and the NASA Earth Science Data Systems"`.
- **Mục đích:** Sử dụng dữ liệu khoa học mở phi thương mại, tôn trọng tính chính xác và không bóp méo số liệu đo đạc vệ tinh.

---

## 3. CHÍNH SÁCH THAY THẾ DỮ LIỆU ĐÓNG (ZERO WEB SCRAPING COMMITMENT)

### 3.1. Lý do loại bỏ triệt để việc cào dữ liệu NCHMF
- Trang web Trung tâm Dự báo Khí tượng Thủy văn Quốc gia (`nchmf.gov.vn`) là cổng thông tin công cộng của cơ quan chính phủ, **không cung cấp API dữ liệu mở có bản quyền tương thích với chuẩn FOSS / OSI**.
- Việc cào mã nguồn HTML (Web Scraping) gây các hệ lụy nghiêm trọng:
  1. Vi phạm điều khoản sử dụng và tiềm ẩn rủi ro pháp lý cho một dự án mã nguồn mở tham gia OLP 2026.
  2. Dễ bị gãy vỡ (fragile) khi cấu trúc HTML của trang web chính phủ thay đổi.
  3. Gây tải bất hợp pháp lên hạ tầng máy chủ của cơ quan phòng chống thiên tai nhà nước trong những thời điểm bão lũ nguy cấp.

### 3.2. Giải pháp kỹ thuật thay thế
- Toàn bộ thông số dự báo mưa, lưu lượng dòng chảy và cảnh báo ngập lụt được chuyển dịch 100% sang:
  - **Open-Meteo Weather API** thay thế dữ liệu lượng mưa.
  - **Copernicus GloFAS River Discharge API** thay thế dữ liệu lưu lượng và ngưỡng báo động lũ trên các sông Hồng, sông Cầu, sông Thao, sông Lô.
  - **Bản tin cảnh báo thiên tai chính thức** được nhập liệu hoặc điều phối thông qua phân hệ chỉ huy tác chiến của Ban Chỉ huy PCTT & TKCN, bảo đảm tính xác thực và trách nhiệm giải trình.
