# KIẾN TRÚC GIS VÀ BẢN ĐỒ TÁC CHIẾN ĐA LỚP (GIS ARCHITECTURE)
## Thiết kế Đồ thị Mạng lưới Giao thông, Định tuyến Đa Hiểm họa & Phân tích Tiếp cận

---

## 1. NGUYÊN TẮC VẬN HÀNH GIS TRONG NORTHSTAR COMMAND

1. **Bản đồ là trung tâm điều hành:** Bản đồ GIS không chỉ là công cụ minh họa mà là giao diện điều khiển tác chiến chính (Common Operating Picture - COP).
2. **Phân tách tuyệt đối giữa Core và Backend:** Toàn bộ thuật toán đồ thị, tìm đường và phân tích không gian chuyên sâu được thực thi bên trong thư viện `GrassToucher-core` (sử dụng NetworkX, OSMnx và Shapely), giao tiếp với FastAPI Backend qua Python Interface thuần túy.
3. **Định tuyến theo rủi ro thực tế (Multi-Hazard Risk Cost Function):** Tuyến đường cứu hộ không đơn thuần là đường ngắn nhất về khoảng cách hình học, mà là tuyến đường có mức độ rủi ro thấp nhất và phương tiện có thể vượt qua an toàn.
4. **Không cam kết an toàn tuyệt đối:** Mọi đoạn đường chưa có xác minh thực địa từ chốt cứu nạn đều phải hiển thị mức độ tin cậy kèm cảnh báo rủi ro cho người lái phương tiện.

---

## 2. KIẾN TRÚC ĐA LỚP BẢN ĐỒ (SPATIAL MULTI-LAYER STACK)

Bản đồ COMMAND xếp chồng các lớp dữ liệu không gian theo thứ tự từ nền đến dữ liệu thời gian thực:

```
[Layer 7 - Tác chiến]  Vị trí Đội cứu hộ (Marker xuồng/cano), Tuyến đường điều động (Polyline)
[Layer 6 - Khẩn cấp]   Tín hiệu SOS (Marker P1 đỏ nhấp nháy, P2 cam, P3 vàng)
[Layer 5 - Cơ sở]      Điểm Sơ tán (Safe Zones), Bệnh viện dã chiến, Kho hàng cứu trợ
[Layer 4 - Nguy hiểm]  Vùng sạt lở taluy, Điểm ngập sâu, Cầu yếu cấm lưu thông (Polygons)
[Layer 3 - Khí tượng]  Mạng lưới Trạm thủy văn sông, Lớp phủ Radar lượng mưa 24h
[Layer 2 - Vệ tinh]    Vùng ngập nước mặt trích xuất viễn thám Sentinel-1 SAR
[Layer 1 - Giao thông] Mạng lưới đường bộ OpenStreetMap (Đồ thị NetworkX)
[Layer 0 - Bản đồ nền] OpenStreetMap chuẩn / Chế độ Ban đêm (Dark Mode)
```

---

## 3. THUẬT TOÁN ĐỊNH TUYẾN ĐA PHƯƠNG TIỆN & HÀM TRỌNG SỐ RỦI RO

Lõi `grasstoucher_core/routing.py` nâng cấp hàm trọng số A* kết hợp đặc tính phương tiện và chướng ngại vật:

### Hàm Trọng số Chi phí Rủi ro (Risk Cost Function):
Chi phí của cạnh đường $e = (u, v)$ trong đồ thị:
$$Cost(e) = Length(e) \times \left(1 + W_{flood}(e, VehicleType) + W_{slope}(e) + W_{closure}(e)\right)$$

Trong đó:
- $Length(e)$: Chiều dài thực tế của đoạn đường (mét).
- $W_{flood}$: Trọng số ngập nước phụ thuộc vào loại phương tiện:
  - **Xe cứu thương / Xe con:** Nếu $Depth \ge 20\text{ cm} \rightarrow W_{flood} = \infty$ (Cấm tuyệt đối).
  - **Xe tải gầm cao:** Chịu ngập đến $60\text{ cm}$. Nếu $Depth \ge 60\text{ cm} \rightarrow W_{flood} = \infty$.
  - **Xuồng cao su / Cano cứu nạn:** Nếu $Depth < 15\text{ cm} \rightarrow W_{flood} = \infty$ (Mắc cạn, không thể chạy động cơ).
- $W_{slope}$: Trọng số nguy cơ sạt lở dựa trên độ dốc taluy trích xuất từ dữ liệu cao độ số (DEM).
- $W_{closure}$: Đoạn đường đã có chốt chặn giao thông cảnh báo cấm qua $\rightarrow W_{closure} = \infty$.

---

## 4. PHÂN TÍCH VÙNG TIẾP CẬN & GỢI Ý ĐIỂM SƠ TÁN (ISOCHRONE & REACHABILITY)

Khi nhận được yêu cầu cứu hộ từ một cụm dân cư bị cô lập:
1. `grasstoucher_core` sử dụng thuật toán Dijkstra đa nguồn (Multi-source Dijkstra) quét ngược từ vị trí các điểm sơ tán (`safe_zones`) lân cận.
2. Hệ thống tạo ra các đường bình thời (Isochrone Contours): Vùng tiếp cận trong 15 phút, 30 phút, 45 phút.
3. Thuật toán tự động xếp hạng và gợi ý điểm sơ tán tối ưu cho Dispatcher dựa trên 3 tiêu chí:
   $$\text{Score} = 0.5 \times \frac{1}{\text{Thời gian di chuyển}} + 0.3 \times \frac{\text{Chỗ trống còn lại}}{\text{Sức chứa tối đa}} + 0.2 \times \text{Mức độ sẵn sàng y tế}$$
4. **Quy tắc đạo đức công nghệ:** Điểm sơ tán đề xuất chỉ mang tính chất khuyến nghị. Quyết định điều chuyển nạn nhân đến trường học hay nhà văn hóa cụ thể phải do Dispatcher hoặc Chỉ huy trưởng trực tiếp phê duyệt.
