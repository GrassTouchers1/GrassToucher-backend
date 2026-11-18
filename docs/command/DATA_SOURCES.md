# DANH MỤC NGUỒN DỮ LIỆU MỞ & CHÍNH SÁCH BẢN QUYỀN (DATA SOURCES REGISTRY)
## Danh mục Nguồn Dữ liệu Khí tượng, Thủy văn, Không gian & Chính sách Zero Web Scraping

---

## 1. TUYÊN NGÔN ZERO WEB SCRAPING & TUÂN THỦ PHÁP LÝ

Hệ sinh thái NORTHSTAR COMMAND cam kết tuân thủ $100\%$ các quy chuẩn pháp lý và đạo đức công nghệ:
1. **Tuyệt đối không cào dữ liệu trái phép (Zero Web Scraping):** Không sử dụng bất kỳ công cụ bot, parser HTML hay kỹ thuật can thiệp tự động nào để trích xuất dữ liệu từ các cổng thông tin điện tử của cơ quan nhà nước khi chưa có API công khai hoặc văn bản thỏa thuận chính thức.
2. **Ưu tiên Open Data có giấy phép quốc tế chuẩn mực:** Toàn bộ dữ liệu khí tượng, thủy văn và bản đồ giao thông được tích hợp trực tiếp qua các REST API chính thức từ các tổ chức khoa học hàng đầu thế giới với điều khoản cấp phép rõ ràng (ODbL, CC-BY 4.0, NASA Open Access, Copernicus Open Access).
3. **Minh bạch ghi nhận bản quyền (Attribution Transparency):** Mọi lớp dữ liệu hiển thị trên giao diện COMMAND đều phải ghi rõ đơn vị cung cấp dữ liệu và thời điểm cập nhật mới nhất.

---

## 2. MA TRẬN ĐẶC TẢ CÁC NGUỒN DỮ LIỆU CHÍNH THỨC

| STT | Tên Nguồn Dữ Liệu | Đơn vị Cung Cấp | Giấy Phép Sử Dụng | Tần Suất Cập Nhật | Độ Phân Giải / Độ Trễ | Giao Thức Tích Hợp | Mục Đích Ứng Dụng |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **1** | **OpenStreetMap (OSM)** | OpenStreetMap Foundation | **ODbL 1.0** (Open Database License) | Tuần / Tháng | Từng nút giao thông / thời gian thực | OSMnx, Overpass API, PBF extracts | Trích xuất đồ thị hình học đường bộ, cầu cống, đê điều cho thuật toán tìm đường cứu hộ. |
| **2** | **Open-Meteo API** | Open-Meteo GmbH | **CC-BY 4.0** (Open Data) | Mỗi giờ (Hourly) | 1 km - 11 km / Trễ 15 phút | RESTful JSON API | Cung cấp nhiệt độ thực tế, lượng mưa tích lũy 1h/24h, tốc độ và hướng gió bề mặt. |
| **3** | **Copernicus GloFAS** | Trung tâm Khí tượng Châu Âu (ECMWF) | **Copernicus Open Access License** | 1 - 2 lần / ngày | Lưu vực sông toàn cầu / Trễ 3-6 giờ | WMS / REST API Copernicus Data Space | Dự báo lưu lượng dòng chảy lũ và cảnh báo ngập lụt sớm trên các lưu vực sông Hồng và sông Mê Kông. |
| **4** | **NASA GPM IMERG** | Cơ quan Hàng không Vũ trụ Mỹ (NASA) | **NASA Open Data Policy** | Mỗi 30 phút (Early Run) | $0.1^\circ \times 0.1^\circ$ (~10 km) / Trễ 4 giờ | OPeNDAP, GeoTIFF, REST | Giám sát cường độ mưa vệ tinh trên diện rộng phục vụ cảnh báo nguy cơ lũ quét và lũ thượng nguồn. |
| **5** | **Sentinel-1 SAR** | Cơ quan Vũ trụ Châu Âu (ESA) | **Copernicus Open Access** | Chu kỳ 6 - 12 ngày | 10 m / Trễ 6 - 24 giờ | STAC API / Copernicus Sentinel Hub | Ảnh radar khẩu độ tổng hợp xuyên mây, phát hiện các vùng trũng bị ngập nước mặt sau các cơn bão lớn. |
| **6** | **HydroSHEDS** | WWF / USGS / Viện Địa lý ĐH McGill | **Open for Non-Commercial & Humanitarian** | Tĩnh (Static Baseline) | 3 - 15 arc-seconds | Shapefile, GeoJSON | Dữ liệu ranh giới lưu vực sông, hướng dòng chảy và mạng lưới sông ngòi tự nhiên tại Việt Nam. |

---

## 3. QUY ĐỊNH GHI NGUỒN VÀ HIỂN THỊ (ATTRIBUTION RULES)

- **Trên bản đồ Leaflet:** Dòng chú thích bắt buộc tại chân trang:  
  `© OpenStreetMap contributors (ODbL) | Weather data by Open-Meteo (CC-BY 4.0) | Hydrological forecasts by Copernicus GloFAS | Rainfall by NASA GPM`.
- **Trên báo cáo SitRep:** Mọi con số lượng mưa hoặc mực nước trích dẫn trong văn bản đều phải ghi chú rõ: `Nguồn: Open-Meteo (Đối soát trạm lúc HH:mm)` hoặc `Dự báo: Copernicus GloFAS Model Run`.
- **Cơ chế khi mất kết nối nguồn:** Nếu API bên ngoài không phản hồi (HTTP 5xx hoặc Timeout), hệ thống hiển thị biểu tượng cảnh báo màu vàng: *"Dữ liệu lúc [Thời gian gần nhất] - Không tự động cập nhật"* và ghi nhận lỗi vào bảng `data_ingestion_logs`.
