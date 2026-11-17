# BẢN VẼ THIẾT KẾ KIẾN TRÚC HỆ THỐNG TỔNG THỂ
## SYSTEM ARCHITECTURE SPECIFICATION – NORTHSTAR RESCUE OS

> **Dự án:** NORTHSTAR – Open-source Emergency Response OS  
> **Mô hình kiến trúc:** Hybrid Centralized & Distributed Architecture (Kiến trúc Lai: Chỉ huy Tập trung & Tác chiến Phân tán)  
> **Nguyên tắc thiết kế:** Offline-First, Resilient by Design, Modular Monolith with Clean Architecture, OSI-Compliant.  

---

## 1. KIẾN TRÚC PHÂN TẦNG TỔNG THỂ (LAYERED ARCHITECTURE)

Hệ thống NORTHSTAR được tổ chức theo kiến trúc phân tầng rõ ràng (Clean / Onion Architecture), loại bỏ hoàn toàn sự phụ thuộc vòng giữa các thành phần:

```mermaid
graph TB
    subgraph "1. PRESENTATION LAYER (GIAO DIỆN ĐA PHÂN HỆ)"
        P1[Citizen Portal: SOS, Voice SOS, Tracking, Báo cáo]
        P2[Rescue Operations: Nhận nhiệm vụ, Bản đồ tác chiến, Báo cáo hiện trường]
        P3[Command Center: COP Dashboard, AI Triage, Phân bổ nguồn lực, SitRep]
    end

    subgraph "2. API GATEWAY & APPLICATION SERVICES (BACKEND FASTAPI)"
        GW[FastAPI Router & Security Middleware]
        AUTH[RBAC Auth Service: JWT & Role Guards]
        DISP[Rescue Dispatch Service: Task Lifecycle Engine]
        SYNC[Offline Sync Reconciliation Engine]
        WS[WebSocket Event Bus: Realtime Telemetry & Alerts]
    end

    subgraph "3. CORE DOMAIN & GIS ENGINE (GRASSTOUCHER-CORE)"
        CORE_GIS[GIS Road Network: NetworkX & OSMnx]
        CORE_ROUTING[Multi-Hazard A* Routing & Dijkstra Evacuation]
        CORE_PREDICT[Hydrological & Water Depth Prediction Engine]
        CORE_DATA[Open Data Adapters: GloFAS, NASA GPM, Open-Meteo]
    end

    subgraph "4. AI & INTELLIGENCE LAYER"
        AI_FAC[AI Provider Factory]
        AI_GROQ[Groq LPU Provider: Whisper & LLM Triage]
        AI_OFFLINE[Offline Local Fallback NLP Engine]
    end

    subgraph "5. PERSISTENCE & DATA STORAGE LAYER"
        DB_POSTGIS[(PostgreSQL 16 + PostGIS: Không gian Địa lý)]
        DB_CIRCUIT[(SQLite In-Memory Circuit Breaker: Dự phòng 100%)]
        LOCAL_STORAGE[(Client-side IndexedDB & PWA Cache: Ngoại tuyến)]
    end

    P1 & P2 & P3 -->|HTTP/REST & WSS| GW
    P1 & P2 & P3 -.->|Chế độ Mất Mạng Hoàn Toàn| LOCAL_STORAGE
    GW --> AUTH & DISP & SYNC & WS
    DISP & SYNC --> CORE_ROUTING & CORE_GIS
    DISP --> AI_FAC
    AI_FAC --> AI_GROQ & AI_OFFLINE
    DISP & SYNC & AUTH --> DB_POSTGIS
    DB_POSTGIS -.->|Nếu Rớt CSDL Hoặc Mất Điện| DB_CIRCUIT
```

---

## 2. QUY TRÌNH LUỒNG DỮ LIỆU TÁC CHIẾN CỨU NẠN (END-TO-END DATA FLOW)

Sơ đồ tuần tự thể hiện toàn bộ vòng đời của một yêu cầu cứu hộ từ khi nạn nhân phát tín hiệu cho đến khi được giải cứu an toàn:

```mermaid
sequenceDiagram
    autonumber
    actor Citizen as Người Dân (Nạn Nhân)
    participant CP as Citizen Portal (PWA)
    participant API as Backend API & WebSocket
    participant AI as AI Engine (Groq / Local)
    participant CMD as NorthStar Command Center
    actor Commander as Chỉ Huy Tác Chiến
    participant RO as Rescue Operations Portal
    actor Rescuer as Đội Cứu Hộ (Xuồng 114)

    Citizen->>CP: Nói kêu cứu qua Voice SOS / Bấm nút SOS
    CP->>CP: Tự động nắn tọa độ (Speech Geocoding / Chấm bản đồ)
    CP->>API: POST /api/citizen/sos (Tọa độ, Lời nói, Số người)
    
    alt Có kết nối Internet
        API->>AI: classify_emergency(transcript)
        AI-->>API: {urgency: 'critical', needs: ['xuồng', 'y tế'], people: 4}
        API->>API: Lưu CSDL PostGIS + Tạo mã theo dõi SOS-7821
        API-->>CP: Xác nhận {tracking_code: 'SOS-7821', status: 'acknowledged'}
        API->>CMD: WebSocket broadcast('new_sos_alert')
    else Mất kết nối Internet
        CP->>CP: Lưu vào hàng đợi cục bộ IndexedDB (SyncQueue)
        CP-->>Citizen: Hiển thị: "Đã lưu SOS trên máy. Sẽ tự động truyền tin khi có sóng!"
    end

    CMD->>Commander: Cảnh báo âm thanh & ghim mốc đỏ nhấp nháy trên COP Map
    Commander->>CMD: Chọn Đội cứu hộ phù hợp (Đội xuồng máy số 3 - 114)
    CMD->>API: POST /api/command/dispatch (Assign Task to Team #3)
    API->>RO: WebSocket push_task(Team #3)
    
    RO->>Rescuer: Chuông báo nhiệm vụ khẩn cấp trên điện thoại hiện trường
    Rescuer->>RO: Bấm "Tiếp Nhận Nhiệm Vụ (Acknowledge)"
    RO->>API: PATCH /api/rescue/tasks/{id} (status: 'dispatched')
    RO->>RO: Tính toán tuyến đường né ngập A* tiếp cận nạn nhân
    API-->>CP: Cập nhật trạng thái: "Đội cứu hộ đang trên đường tới!"

    Rescuer->>Rescuer: Xuồng máy tiếp cận mái nhà, đón 4 nạn nhân lên xuồng
    Rescuer->>RO: Bấm "Đã Tiếp Cận & Đang Sơ Tán" (status: 'in_progress')
    Rescuer->>RO: Chọn trạm sơ tán gần nhất (Dijkstra Evacuation Route)
    Rescuer->>RO: Bàn giao an toàn tại Trạm sơ tán -> Bấm "Hoàn Thành (Resolved)"
    RO->>API: PATCH /api/rescue/tasks/{id} (status: 'resolved', safe_zone_id: 12)
    API->>CMD: Cập nhật chỉ số COP: Giảm số ca chờ, tăng số nạn nhân được cứu
    API-->>CP: Thông báo nạn nhân: "Bạn đã được giải cứu an toàn!"
```

---

## 3. KIẾN TRÚC CHI TIẾT CÁC PHÂN HỆ

### 3.1. Phân hệ Citizen Portal (Giao diện Người Dân)
- **Công nghệ:** HTML5, Tailwind CSS, Leaflet GIS, Vanilla JS (Không nặng framework, tải trang dưới 1.2s trên 3G).
- **Trải nghiệm Người Dùng (UX):**
  - **Chế độ Ban Ngày / Ban Đêm Tương phản Cao:** Hỗ trợ nhìn rõ dưới trời mưa gió hoặc khi mất điện ban đêm.
  - **Khả năng tiếp cận (Accessibility):** Phông chữ `Be Vietnam Pro` sắc nét, nút bấm to bản ($>48\text{px}$) dễ thao tác khi ngón tay bị ướt nước.
  - **Phản hồi âm thanh hai chiều:** Web Speech Synthesis tiếng Việt phát thông báo hướng dẫn để nạn nhân đang hoảng loạn có thể nghe thấy ngay cả khi không nhìn vào màn hình.

### 3.2. Phân hệ Rescue Operations (Giao diện Đội Cứu Hộ)
- **Công nghệ:** Mobile-First Web PWA, tối ưu hóa cho màn hình điện thoại và máy tính bảng chuyên dụng trên ca-nô.
- **Năng lực đặc thù:**
  - **Giao diện Tác chiến Hiện trường (Field Tactical View):** Bản đồ chỉ hiển thị các lớp thông tin trọng yếu: Mốc SOS của đội được giao, độ sâu luồng nước, điểm chướng ngại vật (dây điện, ngầm tràn), trạm sơ tán an toàn.
  - **Nút hành động lớn (Large Action Buttons):** "NHẬN LỆNH" $\rightarrow$ "XUẤT PHÁT" $\rightarrow$ "ĐÃ TIẾP CẬN" $\rightarrow$ "HOÀN THÀNH".
  - **Chế độ Tiết kiệm Pin (Extreme Power Saving):** Tùy chọn giao diện tối (True Black OLED) và giảm tần suất GPS khi tàu dừng lại để bảo tồn pin thiết bị cứu hộ.

### 3.3. Phân hệ NorthStar Command (Trung tâm Chỉ huy Điều hành)
- **Công nghệ:** Desktop / Multi-monitor Responsive Web Dashboard.
- **Năng lực đặc thù:**
  - **Bản đồ Tình huống Toàn cảnh (Common Operating Picture - COP):** Cụm điểm (Clustering) các ca SOS, bản đồ nhiệt (Heatmap) nguy cơ sạt lở, biểu đồ xu hướng mực nước sông ngòi thời gian thực.
  - **Bảng Điều phối Lực lượng (Resource Matrix):** Thống kê tức thời: Tổng số đội trực chiến, số xuồng đang cơ động, số ca SOS nguy cấp chưa có đội tiếp cận.
  - **Hệ thống Phát hiện Trùng lặp (Deduplication):** Thuật toán Spatial-Temporal Clustering gom các tin báo cách nhau dưới 100 mét trong vòng 2 giờ thành một sự cố duy nhất, tránh việc phân công trùng lặp.
