# MA TRẬN PHÂN QUYỀN VÀ KIỂM SOÁT PHẠM VI TRUY CẬP (ROLE-PERMISSION MATRIX)
## Đặc tả Cơ chế RBAC & Phân định Phạm vi Dữ liệu Nghiêm ngặt trong NORTHSTAR COMMAND

---

## 1. NGUYÊN TẮC THIẾT KẾ BẢO MẬT & PHÂN QUYỀN

1. **Thực thi tại Backend (Server-side Enforcement):** Quyền hạn không bao giờ chỉ là việc ẩn/hiện nút bấm trên giao diện người dùng. Mọi yêu cầu HTTP/WebSocket gửi đến API đều phải được kiểm tra qua `require_role_and_scope` dependency tại FastAPI.
2. **Nguyên tắc Đặc quyền Tối thiểu (Principle of Least Privilege):** Mỗi người dùng chỉ được cấp đúng những quyền cần thiết để hoàn thành nhiệm vụ được giao.
3. **Phân định Phạm vi 4 Chiều (4-Dimensional Scope):**
   - **Role Scope:** Nhóm vai trò nghiệp vụ (7 vai trò nội bộ + 3 vai trò bên ngoài).
   - **Geographic Scope:** Phạm vi địa lý theo phân cấp hành chính (`ALL_VIETNAM`, `PROVINCE_CODE`, `DISTRICT_CODE`).
   - **Organization Scope:** Tổ chức trực thuộc (Ban Chỉ huy Quân sự, Công an PCCC, Hội đồng Đội thiện nguyện).
   - **PII Visibility Scope:** Giới hạn quyền xem số điện thoại, danh tính nạn nhân (`FULL`, `MASKED`, `NONE`).

---

## 2. ĐỊNH NGHĨA 10 NHÓM VAI TRÒ TRONG HỆ THỐNG

| Mã Vai trò | Tên Vai trò Nghiệp vụ | Mô tả Trách nhiệm Cốt lõi | Quyền Xem Dữ liệu Cá nhân (PII) |
| :--- | :--- | :--- | :---: |
| **`SUPER_ADMIN`** | Quản trị viên Kỹ thuật | Quản lý hạ tầng máy chủ, tài khoản, cấu hình API, xem log hệ thống. | **MASKED** *(Không tự ý xem PII nghiệp vụ trừ khi bật chế độ khẩn cấp)* |
| **`COMMAND_DIRECTOR`** | Chỉ huy trưởng Trung tâm | Giám sát toàn cảnh COP, phê duyệt phương án cứu nạn lớn, ký duyệt SitRep. | **FULL** *(Trong phạm vi địa lý phụ trách)* |
| **`DISPATCHER`** | Điều phối viên Tác chiến | Tiếp nhận, phân loại ưu tiên (P1-P4), điều động đội cứu hộ, giám sát ca cứu nạn. | **FULL** *(Chỉ trên ca nhiệm vụ được phân công)* |
| **`DATA_ANALYST`** | Chuyên viên Phân tích Dữ liệu | Giám sát trạm đo mưa, trạm thủy văn, phân tích mô hình ngập lụt & radar bão. | **NONE** *(Chỉ làm việc với dữ liệu GIS ẩn danh)* |
| **`INFORMATION_VERIFIER`**| Nhân viên Xác minh Thông tin | Thẩm định các cuộc gọi SOS, báo cáo hiện trường, lọc báo cáo ảo và phát hiện trùng lặp. | **FULL** *(Để phục vụ gọi điện đối soát thực tế)* |
| **`RESCUE_COORDINATOR`** | Điều phối viên Đội Cứu Hộ | Quản lý quân số, cano, trang thiết bị chuyên dụng, phân bổ đội hình ứng trực. | **MASKED** *(Chỉ thấy thông tin cần thiết của ca cứu nạn)* |
| **`RELIEF_COORDINATOR`** | Điều phối viên Cứu trợ | Quản lý các tổ chức thiện nguyện, kết nối nhu cầu lương thực/thuốc men đã xác minh. | **NONE** *(Chỉ thấy số người & địa điểm tập kết an toàn)* |
| **`CITIZEN`** *(Ngoài)* | Người dân | Gửi SOS 1-chạm hoặc giọng nói, gửi báo cáo thiên tai, tra cứu đơn theo mã. | **OWN_ONLY** *(Chỉ xem đúng mã đơn của chính mình)* |
| **`RESCUER`** *(Ngoài)* | Đội Cứu Hộ Hiện Trường | Nhận lệnh tác chiến, xem vị trí tọa độ nạn nhân, cập nhật trạng thái nhiệm vụ. | **TASK_ONLY** *(Chỉ xem PII nạn nhân thuộc ca mình nhận)* |
| **`VOLUNTEER`** *(Ngoài)* | Đội Thiện Nguyện | Đăng ký hàng cứu trợ, nhận danh sách điểm cứu trợ đã được chỉ huy duyệt. | **NONE** *(Không xem thông tin cá nhân hộ dân)* |

---

## 3. BẢNG MA TRẬN QUYỀN HẠN CHI TIẾT (CRUD + ACTIONS MATRIX)

**Ký hiệu:**  
- **V:** View (Xem) | **C:** Create (Tạo mới) | **U:** Update (Cập nhật) | **D:** Delete (Xóa)  
- **Ver:** Verify (Xác minh) | **Ass:** Assign (Phân công) | **App:** Approve (Phê duyệt) | **Exp:** Export (Xuất dữ liệu)  
- **[-]**: Không có quyền

| Thực thể Dữ liệu / Nghiệp vụ | SUPER ADMIN | COMMAND DIRECTOR | DISPATCHER | DATA ANALYST | INFO VERIFIER | RESCUE COORD | RELIEF COORD | RESCUER (Hiện trường) | VOLUNTEER (Thiện nguyện) | CITIZEN (Dân sự) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Yêu cầu SOS (SOS Requests)** | V (Masked) | V, App, Exp | V, U, Ass, Exp | V (Geo only) | V, Ver, U | V (Masked) | V (Count only)| V (Assigned), U | - | C, V (Own Code) |
| **Báo cáo sự cố (Citizen Reports)**| V | V, Exp | V, U, Exp | V, Exp | V, Ver, U | V | V | V | - | C, V (Own Code) |
| **Dữ liệu Khí tượng & Mưa** | V, U | V, Exp | V | V, C, U, Exp | V | V | V | V | V | V (Public) |
| **Mực nước & Trạm Thủy văn** | V, U | V, Exp | V | V, C, U, Exp | V | V | V | V | V | V (Public) |
| **Đội Cứu Hộ & Phương tiện** | V, C, U, D | V, App | V, Ass | V (Stats only)| V | V, C, U, Ass | - | V (Own), U (Status)| - | - |
| **Đoàn Thiện Nguyện & Kho hàng**| V, C, U, D | V, App | V | V (Stats only)| - | - | V, C, U, Ass | - | V (Own), C, U (Stock)| - |
| **Điểm Sơ Tán (Safe Zones)** | V, C, U, D | V, App, Exp | V, U | V | V | V, U | V, U | V | V | V (Active only) |
| **Nhiệm vụ Cứu Nạn (Rescue Tasks)**| V | V, App, Exp | V, C, U, Ass | V (Analytics) | V | V, Ass | - | V (Assigned), U | - | - |
| **Nhiệm vụ Cứu Trợ (Relief Tasks)**| V | V, App, Exp | V, C, U, Ass | V (Analytics) | - | - | V, C, U, Ass | - | V (Assigned), U | - |
| **Báo cáo SitRep (QĐ 18/2021)** | V, Exp | V, App, Exp | V, C, Exp | V, C, Exp | - | V (Stats) | V (Stats) | - | - | - |
| **Lịch sử Kiểm toán (Audit Logs)** | V, Exp | V, Exp | - | - | - | - | - | - | - | - |
| **Cấu hình Hạ tầng & API Keys** | V, C, U, D | V | - | - | - | - | - | - | - | - |

---

## 4. CƠ CHẾ RÀO CHẮN PHẠM VI (SCOPE GUARDS CODE SPECIFICATION)

Ví dụ về cơ chế Decorator kiểm tra quyền kết hợp phạm vi địa lý tại Backend:

```python
# Minh họa logic kiểm soát quyền trong app/core/security.py
@router.post("/api/v1/rescue-tasks/dispatch")
async def dispatch_rescue_task(
    payload: DispatchTaskSchema,
    current_user: User = Depends(require_permission("TASK_ASSIGN")),
    geo_scope: GeoScope = Depends(get_user_geographic_scope)
):
    # 1. Kiểm tra quyền thao tác nghiệp vụ
    if current_user.role not in [UserRole.DISPATCHER, UserRole.COMMAND_DIRECTOR]:
        raise HTTPException(status_code=403, detail="Không có thẩm quyền điều động lực lượng")
        
    # 2. Kiểm tra rào chắn địa lý (Geographic Boundary Check)
    if not geo_scope.contains_point(payload.target_lat, payload.target_lng):
        raise HTTPException(
            status_code=403, 
            detail=f"Mục tiêu nằm ngoài phạm vi địa bàn phụ trách ({geo_scope.province_name})"
        )
        
    # 3. Ghi vết Audit Log trước khi thực hiện
    await log_security_action(
        user_id=current_user.id,
        action="DISPATCH_RESCUE_TASK",
        target_id=payload.task_id,
        details={"team_id": payload.team_id, "priority": payload.priority}
    )
    return await execute_dispatch(payload)
```
