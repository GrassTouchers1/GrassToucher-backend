# CHÍNH SÁCH BẢO MẬT VÀ BẢO VỆ QUYỀN RIÊNG TƯ (SECURITY & PRIVACY POLICY)
## Chuẩn mực Bảo vệ Dữ liệu Cá nhân PII, Kiểm soát Phiên & Nhật ký An ninh Bất biến

---

## 1. NGUYÊN TẮC BẢO VỆ DỮ LIỆU CÁ NHÂN (PII PROTECTION)

Trong các tình huống thiên tai khẩn cấp, người dân cung cấp số điện thoại, danh tính và vị trí chính xác của gia đình họ cho hệ thống cứu hộ. NORTHSTAR COMMAND đặt sự an toàn thông tin của người dân lên hàng đầu theo các quy định nghiêm ngặt:

1. **Mã hóa khi lưu trữ (Encryption at Rest):**
   - Trường số điện thoại nạn nhân (`phone_encrypted`) trong bảng `sos_requests` được mã hóa đối xứng **AES-256-GCM** trước khi ghi vào cơ sở dữ liệu.
   - Khóa giải mã được quản lý qua biến môi trường độc lập (`ENCRYPTION_SECRET_KEY`), không lưu trong mã nguồn hoặc kho git.
2. **Che mờ dữ liệu trên giao diện (UI Masking by Default):**
   - Mọi màn hình danh sách cuộc gọi SOS mặc định chỉ hiển thị dạng che mờ: `0987***321` và họ tên rút gọn: `Trần Thị B`.
   - Chỉ khi Thẩm định viên (Verifier) hoặc Điều phối viên (Dispatcher) có thẩm quyền bấm nút *"Mở số điện thoại để liên hệ"* thì hệ thống mới gửi yêu cầu giải mã riêng lẻ, đồng thời kích hoạt ghi nhận sự kiện `VIEW_PII_DATA` vào bảng `audit_logs`.
3. **Không công khai vị trí chính xác của nạn nhân:**
   - Trên bản đồ dành cho công chúng, vị trí cứu hộ được làm nhòe (Fuzzy Obfuscation) trong bán kính ngẫu nhiên 200m - 500m để bảo vệ tư gia khỏi kẻ xấu lợi dụng tình trạng di tản.
   - Chỉ có Điều phối viên COMMAND và Đội cứu hộ được giao nhiệm vụ cụ thể mới nhìn thấy tọa độ GPS chính xác để điều động phương tiện tiếp cận.

---

## 2. QUẢN LÝ PHIÊN ĐĂNG NHẬP & PHÂN QUYỀN (SESSION & TOKEN SECURITY)

- **Cơ chế Token Kép (Dual-Token Scheme):**
  - **Access Token:** Định dạng JWT (JSON Web Token) có thời hạn sống ngắn (**15 phút**), mang thông tin `sub` (User ID), `role`, `geo_scope` và danh sách quyền `permissions`.
  - **Refresh Token:** Lưu trữ trong cookie an toàn (`HttpOnly`, `Secure`, `SameSite=Strict`), thời hạn sống **7 ngày**, hỗ trợ cơ chế tự động xoay vòng khóa (Token Rotation) để chống đánh cắp phiên.
- **Ràng buộc Địa chỉ IP & Thiết bị:** Khi một tài khoản nhân sự COMMAND đăng nhập từ một địa chỉ IP hoặc trình duyệt lạ, hệ thống yêu cầu xác thực OTP qua email/SMS và gửi cảnh báo tới Quản trị viên hệ thống.
- **Hết hạn phiên tự động:** Sau 30 phút không có thao tác chuột hoặc bàn phím tại bảng điều khiển tác chiến, hệ thống tự động khóa màn hình làm việc (Screen Lock) để tránh người ngoài tiếp cận khi nhân viên rời vị trí trực.

---

## 3. KIỂM SOÁT XUẤT DỮ LIỆU & BẢN QUYỀN SỐ (EXPORT WATERMARKING)

- Chỉ có vai trò **`COMMAND_DIRECTOR`** và **`DISPATCHER`** mới được cấp quyền xuất danh sách nạn nhân hoặc báo cáo tình hình tác chiến (SitRep) ra định dạng CSV/PDF.
- Mọi tài liệu PDF hoặc file Excel được trích xuất từ hệ thống đều tự động được nhúng chìm (Dynamic Watermarking) gồm:
  - Tên đầy đủ và mã nhân sự của người xuất dữ liệu.
  - Thời gian xuất chính xác từng giây.
  - Địa chỉ IP của máy trạm thực hiện.
  - Dòng cảnh báo: *"Tài liệu nghiệp vụ cứu nạn nội bộ - Nghiêm cấm phát tán ra công chúng"*.

---

## 4. NHẬT KÝ AN NINH BẤT BIẾN (IMMUTABLE AUDIT TRAIL)

Bảng `audit_logs` được cấu hình phân quyền đặc biệt tại mức cơ sở dữ liệu PostgreSQL (PostgreSQL Table Grants):
- **Quyền cho phép:** `INSERT`, `SELECT`.
- **Quyền cấm tuyệt đối:** `UPDATE`, `DELETE`, `TRUNCATE`.
- Ngay cả tài khoản Super Admin cũng không thể sửa đổi hoặc xóa các dòng nhật ký đã ghi.
- Định kỳ hằng ngày, các bản ghi Audit Log được băm kiểm tra tính toàn vẹn (SHA-256 Merkle Tree Hash) và đẩy sang kho lưu trữ dã chiến WORM (Write Once, Read Many).
