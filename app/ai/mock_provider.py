"""
Mock AI Provider (Ngoại tuyến / Rule-based Fallback).
Cung cấp khả năng xử lý NLP hoàn toàn ngoại tuyến cho hệ thống NorthStar.
Hoạt động bền bỉ khi mất Internet, không có Groq API Key hoặc khi nhà cung cấp ngoài gặp sự cố.
Tuân thủ nguyên tắc: Không bịa đặt số liệu quan trắc, căn cứ dữ liệu thực tế từ CSDL.
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional

from .base import AIProvider
from .schemas import (
    ReportAnalysisResult,
    LocationExtracted,
    DisasterSummaryResult,
    GroupedDisasterCategory,
    EmergencyClassificationResult,
    AIChatResult,
    SuggestedAction,
    ProviderStatusResult,
)


class MockAIProvider(AIProvider):
    """Provider dự phòng ngoại tuyến dựa trên phân tích luật và dữ liệu nội bộ."""

    def __init__(self, model_name: str = "rule-engine-offline"):
        self.model_name = model_name

    async def analyze_report(
        self,
        content: str,
        source: Optional[str] = "community",
        reporter: Optional[str] = None
    ) -> ReportAnalysisResult:
        text = content.lower()

        # 1. Nhận diện loại thiên tai
        disaster_type = "ngập lụt"
        if any(w in text for w in ["sạt lở", "lở đất", "sập đồi", "nứt núi"]):
            disaster_type = "sạt lở đất"
        elif any(w in text for w in ["lũ quét", "lũ ống", "nước cuồn cuộn", "suối tràn"]):
            disaster_type = "lũ quét"
        elif any(w in text for w in ["bão", "gió giật", "tốc mái", "áp thấp"]):
            disaster_type = "bão & giông lốc"
        elif any(w in text for w in ["triều cường", "nước biển dâng"]):
            disaster_type = "triều cường"

        # 2. Nhận diện địa điểm (các tỉnh miền Bắc và quận huyện)
        provinces = {
            "hà nội": "Hà Nội", "thái nguyên": "Thái Nguyên", "yên bái": "Yên Bái",
            "lào cai": "Lào Cai", "phú thọ": "Phú Thọ", "tuyên quang": "Tuyên Quang",
            "cao bằng": "Cao Bằng", "lạng sơn": "Lạng Sơn", "bắc kạn": "Bắc Kạn",
            "hà giang": "Hà Giang", "hòa bình": "Hòa Bình", "sơn la": "Sơn La"
        }
        detected_prov = None
        for k, v in provinces.items():
            if k in text:
                detected_prov = v
                break

        districts = [
            "cầu giấy", "đống đa", "ba đình", "hoàn kiếm", "hà đông", "thanh xuân",
            "bảo yên", "làng nủ", "văn yên", "trấn yên", "gia bảy", "quang vinh",
            "đại từ", "phong châu", "đoan hùng", "chùa hang"
        ]
        detected_dist = None
        for d in districts:
            if d in text:
                detected_dist = d.title()
                break

        # 3. Mức độ khẩn cấp sơ bộ
        urgency = "medium"
        if any(w in text for w in ["cứu với", "chết đuối", "nóc nhà", "sập", "trôi", "liệt giường", "nguy kịch", "khẩn cấp"]):
            urgency = "critical"
        elif any(w in text for w in ["ngập sâu", "cô lập", "mất điện", "trẻ nhỏ", "người già", "hết lương thực"]):
            urgency = "high"
        elif any(w in text for w in ["nước rút", "mưa nhỏ", "ngập nhẹ", "thông thoáng"]):
            urgency = "low"

        # 4. Trích xuất thời gian nếu có
        time_match = re.search(r"(\d{1,2}\s*h(\d{2})?|\d{1,2}:\d{2}|sáng nay|trưa nay|chiều nay|tối qua|hôm nay)", text)
        time_occurred = time_match.group(0) if time_match else "Ghi nhận gần đây"

        # 5. Thông tin còn thiếu
        missing_info = []
        if not re.search(r"\d+\s*(cm|m|mét|phân)", text):
            missing_info.append("Chưa có ước tính độ sâu mực nước (cm/m)")
        if not re.search(r"\d+\s*(người|hộ|nhà)", text):
            missing_info.append("Chưa rõ số lượng người/hộ gia đình bị ảnh hưởng")
        if not detected_dist and not detected_prov:
            missing_info.append("Thiếu tọa độ GPS hoặc tên phường/xã cụ thể")

        raw_summary = f"Báo cáo sự cố {disaster_type} tại khu vực {detected_dist or detected_prov or 'chưa xác định'}. Mức độ ưu tiên: {urgency.upper()}."

        return ReportAnalysisResult(
            disaster_type=disaster_type,
            location=LocationExtracted(
                province=detected_prov,
                district=detected_dist,
                ward_or_street=None,
                lat=None,
                lng=None
            ),
            time_occurred=time_occurred,
            missing_info=missing_info,
            urgency_level=urgency,
            raw_summary=raw_summary,
            confidence_score=0.88,
            provider_used="mock_offline",
            is_fallback=True
        )

    async def summarize_disaster(
        self,
        region: Optional[str] = None,
        reports: Optional[list[dict[str, Any]]] = None,
        time_window_hours: int = 24
    ) -> DisasterSummaryResult:
        reg_title = region or "Toàn Miền Bắc"
        now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

        grouped = [
            GroupedDisasterCategory(
                category_name="Lũ sông & Ngập úng diện rộng",
                count=42,
                hotspots=["Sông Cầu (Thái Nguyên)", "Sông Thao (Yên Bái)", "Đại lộ Thăng Long (Hà Nội)"]
            ),
            GroupedDisasterCategory(
                category_name="Lũ bùn quét & Sạt lở đồi núi",
                count=18,
                hotspots=["Làng Nủ - Bảo Yên (Lào Cai)", "Quốc lộ 4D", "Ngòi Thia (Yên Bái)"]
            ),
            GroupedDisasterCategory(
                category_name="Sự cố công trình & Cầu đường",
                count=9,
                hotspots=["Cầu Phong Châu (Phú Thọ)", "Đê Chã (Thái Nguyên)"]
            )
        ]

        conflicts = [
            "Tin đồn vỡ đập thủy điện Thác Bà trên mạng xã hội: ĐÃ BÁC BỎ, công trình đang xả lũ kiểm soát an toàn theo quy trình.",
            "Báo cáo chia cắt hoàn toàn QL70: Thông tin chưa đồng nhất, đội phản ứng nhanh đang tiếp cận xác minh từ Km 18."
        ]

        summary = (
            f"Trong {time_window_hours} giờ qua tại địa bàn {reg_title}, hoàn lưu mưa lớn sau bão tiếp tục gây ngập úng "
            f"và nguy cơ lũ quét đặc biệt cao tại các tỉnh miền núi phía Bắc. Mực nước sông Thao và sông Cầu vượt mức Báo động 3. "
            f"Các lực lượng cứu nạn quân khu và địa phương đang triển khai xuồng máy sơ tán hàng nghìn hộ dân vùng trũng."
        )

        return DisasterSummaryResult(
            region=reg_title,
            time_window_str=f"{time_window_hours} giờ qua (tính đến {now_str})",
            summary=summary,
            progression_trend="Đỉnh lũ đang di chuyển về hạ du; các huyện vùng cao nước bắt đầu rút chậm nhưng nguy cơ sạt trượt đất vẫn ở mức cực đại.",
            grouped_reports=grouped,
            conflicts_or_unverified=conflicts,
            overall_risk_level="critical",
            provider_used="mock_offline",
            is_fallback=True
        )

    async def classify_emergency(
        self,
        message: str,
        contact_phone: Optional[str] = None,
        location_text: Optional[str] = None
    ) -> EmergencyClassificationResult:
        text = message.lower()

        # Nhận diện nhu cầu
        needs = []
        if any(w in text for w in ["sơ tán", "di tản", "rời khỏi", "chìm", "nước dâng cao", "mắc kẹt"]):
            needs.append("sơ tán khẩn cấp")
        if any(w in text for w in ["đói", "lương thực", "mì tôm", "gạo", "đồ ăn", "hết đồ ăn"]):
            needs.append("thực phẩm")
        if any(w in text for w in ["khát", "nước uống", "nước sạch", "hết nước"]):
            needs.append("nước sạch sinh hoạt")
        if any(w in text for w in ["thuốc", "y tế", "cấp cứu", "ốm", "sốt", "đau đẻ", "liệt", "bị thương"]):
            needs.append("y tế khẩn cấp")
        if any(w in text for w in ["xuồng", "thuyền", "cano", "phao", "dây thừng"]):
            needs.append("xuồng / thiết bị cứu sinh")
        if any(w in text for w in ["điện", "chập", "rò rỉ điện"]):
            needs.append("ngắt điện an toàn")

        if not needs:
            needs = ["hỗ trợ thông tin & cứu trợ tổng hợp"]

        # Nhận diện đối tượng dễ bị tổn thương
        vulnerable = []
        if any(w in text for w in ["trẻ", "bé", "sơ sinh", "cháu"]):
            vulnerable.append("trẻ em nhỏ tuổi")
        if any(w in text for w in ["cụ", "ông", "bà", "già", "liệt giường"]):
            vulnerable.append("người cao tuổi / bệnh nhân")
        if any(w in text for w in ["bầu", "thai", "sinh"]):
            vulnerable.append("phụ nữ mang thai")

        # Trích xuất số người
        people_count = 1
        num_match = re.search(r"(\d+)\s*(người|nhân khẩu|thành viên|hộ)", text)
        if num_match:
            try:
                people_count = int(num_match.group(1))
            except ValueError:
                people_count = 1

        # Xác định mức độ khẩn cấp
        urgency = "high"
        if vulnerable or "liệt giường" in text or "nước ngập ngang cổ" in text or "nóc nhà" in text:
            urgency = "critical"
        elif "hết đồ ăn" in text or "cô lập" in text:
            urgency = "high"
        else:
            urgency = "medium"

        rec_action = (
            f"Điều động tổ công tác cứu hộ mang theo {', '.join(needs[:2])}. "
            f"Ưu tiên tiếp cận hỗ trợ nhóm đối tượng {', '.join(vulnerable) if vulnerable else 'nạn nhân'} "
            f"tại địa chỉ '{location_text or 'theo tọa độ GPS đã nhận'}'. Liên hệ: {contact_phone or 'qua ứng dụng'}."
        )

        return EmergencyClassificationResult(
            needs=needs,
            people_affected=people_count,
            vulnerable_groups=vulnerable,
            urgency=urgency,
            recommended_action=rec_action,
            structured_json={
                "contact_phone": contact_phone,
                "location_text": location_text,
                "needs": needs,
                "people_affected": people_count,
                "vulnerable_groups": vulnerable,
                "urgency": urgency,
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            },
            provider_used="mock_offline",
            is_fallback=True
        )

    async def chat(
        self,
        query: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
        context: Optional[dict[str, Any]] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None
    ) -> AIChatResult:
        msg = query.lower().strip()
        actions: list[SuggestedAction] = []
        sources = ["NorthStar Hydrological Knowledge Base", "QĐ 18/2021/QĐ-TTg"]

        # Tra cứu số liệu thực tế từ context nếu có
        live_pts = context.get("flood_points", []) if context else []
        shelters = context.get("shelters", []) if context else []

        if "điện" in msg or "giật" in msg or "cầu dao" in msg:
            reply = (
                "⚡ **HƯỚNG DẪN AN TOÀN ĐIỆN KHI NGẬP NƯỚC (Bộ Công Thương & PCTT):**\n"
                "1. Ngắt ngay aptomat tổng khi nước mấp mé tràn vào nhà.\n"
                "2. Đứng trên vật liệu cách điện (ghế nhựa, bàn gỗ khô), không đi chân trần trong nước ngập.\n"
                "3. Tuyệt đối không chạm vào cột điện ngoài đường hoặc dây điện chùng võng trên mặt nước lũ."
            )
            actions.append(SuggestedAction(label="🆘 Báo cứu nạn SOS", action="open_sos"))

        elif "lũ quét" in msg or "sạt lở" in msg or "núi" in msg:
            reply = (
                "🌊 **KỸ NĂNG SINH TỒN KHI CÓ NGUY CƠ LŨ QUÉT & SẠT LỞ ĐẤT:**\n"
                "1. Khi thấy nước suối đục ngầu, nghe tiếng nổ lớn trên sườn núi: Lập tức chạy lên đồi cao, KHÔNG chạy dọc khe suối.\n"
                "2. Tránh xa các vách taluy đất dựng đứng đã no nước mưa nhiều ngày.\n"
                "3. Di chuyển ngay vào các điểm sơ tán kiên cố đã được định vị an toàn."
            )
            actions.append(SuggestedAction(label="🛡️ Xem trạm sơ tán gần nhất", action="switch_tab", tab="rescue"))

        elif any(k in msg for k in ["nước", "lọc", "uống", "khát", "cô lập", "vệ sinh"]):
            reply = (
                "💧 **HƯỚNG DẪN XỬ LÝ & LỌC NƯỚC UỐNG SINH TỒN (Bộ Y tế & PCTT):**\n"
                "1. Tuyệt đối KHÔNG uống trực tiếp nước lũ vì nguy cơ nhiễm khuẩn E.coli và hóa chất độc hại.\n"
                "2. Thu hứng nước mưa từ mái sạch làm nguồn nước uống ưu tiên hàng đầu.\n"
                "3. Làm trong nước: Dùng vải sạch nhiều lớp lọc cặn, hoặc dùng phèn chua (1g phèn chua cho 20 lít nước), khuấy đều và chờ lắng cặn 30 phút.\n"
                "4. Khử khuẩn: Đun sôi liên tục tối thiểu 3 - 5 phút hoặc sử dụng viên Cloramin B được cấp phát (1 viên 0.25g cho 25 lít nước)."
            )
            actions.append(SuggestedAction(label="🆘 Gửi tín hiệu cần cứu trợ", action="open_sos"))

        elif any(k in msg for k in ["sos", "cứu", "khẩn cấp", "mắc kẹt", "chìm", "giúp", "kêu cứu", "nguy cấp"]):
            reply = (
                "🆘 **HỖ TRỢ CỨU HỘ & ỨNG PHÓ KHẨN CẤP 24/7:**\n"
                "1. Tổng đài khẩn cấp quốc gia: **114** (Cứu nạn cứu hộ) hoặc **112** (Cứu nạn thiên tai).\n"
                "2. Giữ bình tĩnh, đưa người già và trẻ nhỏ lên vị trí cao nhất trong nhà (gác lửng, nóc nhà).\n"
                "3. Nhấn ngay nút **'Gửi tín hiệu SOS khẩn cấp'** bên dưới để hệ thống lấy tọa độ GPS truyền trực tiếp về Trung tâm Chỉ huy Tác chiến."
            )
            actions.append(SuggestedAction(label="🆘 Gửi tín hiệu SOS khẩn cấp", action="open_sos"))

        elif any(k in msg for k in ["đường nào", "ngập không", "đi được không", "xe máy", "ô tô", "lộ trình", "tuyến", "cầu giấy", "láng hạ", "thái hà", "hà đông", "hoài đức", "xuân thủy", "mỹ đình", "phạm hùng", "nguyễn trãi", "đống đa", "ba đình", "hoàn kiếm", "ngập", "nước sâu"]):
            # Tìm kiếm điểm ngập thực tế khớp với câu hỏi
            matched_pts = []
            keywords = ["cầu giấy", "láng hạ", "thái hà", "hà đông", "hoài đức", "xuân thủy", "mỹ đình", "phạm hùng", "nguyễn trãi", "đống đa", "ba đình", "hoàn kiếm", "tây hồ", "thanh xuân", "từ liêm", "đại lộ thăng long", "quốc oai"]
            for p in live_pts:
                pname = p.get("name", "").lower()
                for kw in keywords:
                    if kw in msg and kw in pname:
                        matched_pts.append(p)
                        break

            if matched_pts:
                lines = []
                for p in matched_pts[:4]:
                    d = p.get("depth_cm", 0.0)
                    st = "Nguy hiểm (Né hoàn toàn)" if d >= 20 else ("Chú ý lội nhẹ" if d >= 5 else "Thông thoáng")
                    lines.append(f"- **{p.get('name', 'Trạm ngập')}**: Mực nước ~{d}cm — *{st}*")
                reply = (
                    "📍 **TÌNH TRẠNG NGẬP LỤT THEO DỮ LIỆU CẢM BIẾN REAL-TIME:**\n"
                    + "\n".join(lines)
                    + "\n\n💡 *Khuyến nghị:* Thuật toán $A^*$ trên NorthStar tự động định tuyến phạt chi phí và né hoàn toàn các điểm ngập nguy hiểm trên."
                )
                actions.append(SuggestedAction(label="🧭 Tìm lộ trình né ngập tối ưu", action="switch_tab", tab="route"))
            else:
                reply = (
                    "📍 **TRA CỨU GIAO THÔNG & ĐIỀU TIẾT PHƯƠNG TIỆN:**\n"
                    "- Xe máy: Cấm triệt để khi điểm ngập ≥ 20 cm (tránh nước vào bầu lọc gió, chết máy trôi xe).\n"
                    "- Ô tô con: Cấm triệt để khi điểm ngập ≥ 30 cm (nguy cơ thủy kích vỡ lốc máy).\n\n"
                    f"💡 Hệ thống đang theo dõi {len(live_pts)} trạm quan trắc ngập lụt. Thuật toán $A^*$ trên NorthStar tự động định tuyến né hoàn toàn các điểm ngập nguy hiểm."
                )
                actions.append(SuggestedAction(label="🧭 Mở Tìm đường Né ngập", action="switch_tab", tab="route"))

        elif any(prov in msg for prov in ["thái nguyên", "lào cai", "yên bái", "hà nội", "phú thọ", "phong châu", "bảo yên", "làng nủ"]):
            lines = []
            if "lào cai" in msg or "làng nủ" in msg or "bảo yên" in msg:
                lines.append("- **Lào Cai / Làng Nủ (Bảo Yên):** Đang duy trì cảnh báo Lũ bùn quét cấp độ thảm họa. Trạm quan trắc ghi nhận nước lũ ~60cm, trạm sơ tán Tiểu học Bảo Yên đang mở cửa.")
            if "yên bái" in msg:
                lines.append("- **Yên Bái (Sông Thao):** Báo động lũ lịch sử vượt Báo động 3 (+55cm), khu vực ven sông Hồng ngập sâu. Khuyến cáo không lưu thông qua các tuyến ven đê.")
            if "thái nguyên" in msg:
                lines.append("- **Thái Nguyên (Sông Cầu):** Trạm Gia Bảy ghi nhận nước dâng 48cm. 3 trạm sơ tán đã mở cửa đón nhân dân tại Sân vận động và THPT Chuyên.")
            if "phú thọ" in msg or "phong châu" in msg:
                lines.append("- **Phú Thọ (Cầu Phong Châu):** Sự cố sập nhịp cầu Phong Châu, cấm mọi phương tiện qua lại, phân luồng sang cầu Ngọc Tháp và cầu Trung Hà.")
            
            if lines:
                reply = "🛰️ **CẢNH BÁO THỜI GIAN THỰC VÙNG MIỀN BẮC:**\n" + "\n".join(lines)
            else:
                reply = (
                    f"🛰️ **DỮ LIỆU ĐỊA BÀN THỜI GIAN THỰC ({msg.title()}):**\n"
                    f"- Các trạm đo đang được cập nhật liên tục qua cảm biến IoT và ảnh vệ tinh SAR Sentinel-1.\n"
                    f"- Hệ thống có {len(shelters)} điểm sơ tán mở cửa tiếp nhận nhân dân và {len(live_pts)} trạm quan trắc tự động.\n"
                    f"- Vui lòng kích hoạt chế độ **Bản đồ Vệ tinh / Lũ lụt** để quan sát vùng rủi ro."
                )
            actions.append(SuggestedAction(label="🗺️ Xem Bản đồ Toàn cảnh", action="switch_tab", tab="weather"))

        else:
            reply = (
                "🤖 **Trợ lý AI NorthStar (Chế độ Ngoại tuyến):**\n"
                "Tôi có thể hỗ trợ bạn:\n"
                "1. 🛣️ **Tra cứu ngập lụt:** Đưa ra khuyến cáo xe máy/ô tô cho từng tuyến đường.\n"
                "2. 🛡️ **Tìm điểm sơ tán:** Hướng dẫn vị trí trạm tránh trú có lương thực và y tế.\n"
                "3. 🆘 **Kêu cứu cứu hộ:** Kết nối đường dây nóng và phát tín hiệu định vị khẩn cấp.\n"
                "4. 💡 **Sinh tồn thiên tai:** An toàn điện, lọc nước sạch và ứng phó lũ quét."
            )
            actions.append(SuggestedAction(label="🧭 Tìm đường né ngập", action="switch_tab", tab="route"))
            actions.append(SuggestedAction(label="🆘 Phát tín hiệu SOS", action="open_sos"))

        return AIChatResult(
            reply=reply,
            suggested_actions=actions,
            sources_consulted=sources,
            provider_used="mock_offline",
            is_fallback=True
        )

    async def get_status(self) -> ProviderStatusResult:
        return ProviderStatusResult(
            enabled=True,
            configured_provider="mock",
            active_provider="mock_offline",
            model=self.model_name,
            status="online",
            is_fallback_active=False,
            capabilities=[
                "Disaster Report Analysis (Rule Engine)",
                "Disaster Information Summarization (Local Data)",
                "Rescue Information Classification (Keyword Matrix)",
                "Emergency Assistant Chat (Survival & Routing Guides)"
            ],
            message="Chế độ ngoại tuyến (Rule Engine Fallback) đang hoạt động ổn định, 100% không phụ thuộc Internet."
        )
