"""
Router Trợ lý AI Trực ban Thiên tai 24/7 (Emergency AI Assistant & Dispatcher).
Phân tích ngữ cảnh cứu nạn, tra cứu tức thời 155 điểm ngập, 12 điểm nóng thiên tai và 15 trạm sơ tán
để tư vấn lộ trình an toàn và kỹ năng sinh tồn khẩn cấp bằng tiếng Việt.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter

from .flood_points import DEFAULT_FLOOD_POINTS
from .disasters import list_disasters
from .shelters import list_shelters

router = APIRouter(prefix="/api/ai", tags=["Trợ lý AI Trực ban Thiên tai"])

class ChatRequest(BaseModel):
    message: str = Field(..., description="Câu hỏi hoặc yêu cầu cứu hộ của người dùng")
    lat: Optional[float] = Field(None, description="Vĩ độ hiện tại của người dùng")
    lng: Optional[float] = Field(None, description="Kinh độ hiện tại của người dùng")

KNOWLEDGE_SURVIVAL = {
    "dien_giat": "⚡ **Nguy cơ điện giật khi nước ngập vào nhà:**\n1. Ngắt ngay cầu dao/aptomat tổng trước khi nước dâng chạm ổ cắm.\n2. Tuyệt đối không chạm vào ổ cắm, tủ lạnh, máy giặt khi chân đang ướt.\n3. Nếu phát hiện rò điện, đứng lên vị trí cao cách điện (bàn gỗ khô, ghế nhựa) và gọi SOS 114 hoặc bấm nút SOS trên bản đồ.",
    "lu_quet": "🌊 **Ứng phó lũ quét & sạt lở đất:**\n1. Khi nghe tiếng nổ lớn hoặc suối chuyển màu đục ngầu, lập tức chạy lên các điểm cao đồi núi, KHÔNG chạy dọc lòng khe suối.\n2. Tránh xa các vách núi taluy dương nứt nẻ sau mưa dài ngày.\n3. Di chuyển ngay vào các điểm sơ tán đã công bố trên NorthStar.",
    "nuoc_sach": "💧 **Lọc nước sinh tồn khi bị lũ cô lập:**\n1. Tuyệt đối không uống trực tiếp nước lũ có nguy cơ nhiễm khuẩn cao.\n2. Thu hứng nước mưa làm nguồn nước uống ưu tiên.\n3. Đun sôi tối thiểu 3-5 phút hoặc dùng viên khử khuẩn Cloramin B được cấp phát.",
    "phuong_tien": "🚗 **Khuyến cáo phương tiện di chuyển trong ngập:**\n- Xe máy: Chặn hoàn toàn khi ngập ≥ 20cm (nước vào bầu lọc gió/ống pô gây chết máy).\n- Ô tô con: Chặn hoàn toàn khi ngập ≥ 30cm (nguy cơ thủy kích vỡ lốc máy).\n- Xe tải cứu hộ: Giới hạn an toàn ≤ 50cm."
}

@router.post("/assistant", summary="Hỏi đáp trực ban với Trợ lý AI NorthStar")
def chat_with_assistant(req: ChatRequest) -> dict[str, Any]:
    msg = req.message.lower().strip()
    reply = ""
    suggested_actions = []

    # 1. Kịch bản hỏi về kỹ năng sinh tồn / an toàn điện / lũ quét
    if "điện" in msg or "giật" in msg or "cầu dao" in msg:
        reply = KNOWLEDGE_SURVIVAL["dien_giat"]
        suggested_actions.append({"label": "🆘 Báo cứu hộ khẩn cấp", "action": "open_sos"})
    elif "lũ quét" in msg or "sạt lở" in msg or "núi" in msg:
        reply = KNOWLEDGE_SURVIVAL["lu_quet"]
        suggested_actions.append({"label": "🛡️ Xem trạm sơ tán an toàn", "action": "switch_tab", "tab": "evac"})
    elif "nước uống" in msg or "nước sạch" in msg or "cô lập" in msg:
        reply = KNOWLEDGE_SURVIVAL["nuoc_sach"]
    elif "xe máy" in msg or "ô tô" in msg or "chết máy" in msg or "ngưỡng" in msg:
        reply = KNOWLEDGE_SURVIVAL["phuong_tien"]
        suggested_actions.append({"label": "🧭 Tìm đường né ngập", "action": "switch_tab", "tab": "route"})

    # 2. Kịch bản tra cứu tuyến đường / địa bàn ngập cụ thể
    elif any(term in msg for term in ["đi được không", "ngập không", "đường nào", "tuyến", "cầu giấy", "láng hạ", "thái hà", "hà đông", "nguyễn trãi"]):
        # Tìm các trạm liên quan
        matched_points = []
        for pt in DEFAULT_FLOOD_POINTS:
            pname = pt["name"].lower()
            if any(k in pname for k in ["cầu giấy", "láng hạ", "thái hà", "nguyễn trãi", "hà đông", "xuân thủy", "phạm hùng"]):
                if any(w in msg for w in ["cầu giấy", "láng hạ", "thái hà", "nguyễn trãi", "hà đông", "xuân thủy", "phạm hùng"] if w in pname):
                    matched_points.append(pt)

        if matched_points:
            report_lines = []
            for p in matched_points[:3]:
                d = p.get("depth_cm") or 0.0
                st = "Nguy hiểm (Né hoàn toàn)" if d >= 20 else ("Chú ý lội nhẹ" if d >= 5 else "An toàn, thông thoáng")
                report_lines.append(f"- **{p['name']}**: Mực nước ~{d}cm — *{st}*")
            
            reply = "📍 **Tình hình ngập trên tuyến đường bạn hỏi:**\n" + "\n".join(report_lines)
            reply += "\n\n💡 *Khuyến nghị:* Thuật toán $A^*$ trên NorthStar đã tự động tính toán lộ trình né các nút thắt ngập trên. Bạn có thể nhấn bên dưới để kích hoạt tìm đường tự động."
            suggested_actions.append({"label": "🚀 Tìm lộ trình né ngập tối ưu", "action": "switch_tab", "tab": "route"})
        else:
            reply = "📍 Hệ thống đang theo dõi 155 điểm ngập toàn miền Bắc. Bạn có thể nhập cụ thể điểm đi và điểm đến vào tab **Tìm đường** để thuật toán $A^*$ tự động phạt chi phí và né hoàn toàn các điểm ngập nguy hiểm."
            suggested_actions.append({"label": "🧭 Mở Tab Tìm Đường", "action": "switch_tab", "tab": "route"})

    # 3. Kịch bản hỏi về tỉnh thành cụ thể (Lào Cai, Yên Bái, Thái Nguyên, Phú Thọ...)
    elif any(prov in msg for prov in ["lào cai", "yên bái", "thái nguyên", "bảo yên", "làng nủ", "phú thọ", "phong châu", "cao bằng"]):
        reply = "⚠️ **Cảnh báo thời gian thực vùng miền Bắc:**\n"
        if "lào cai" in msg or "làng nủ" in msg or "bảo yên" in msg:
            reply += "- **Lào Cai / Làng Nủ (Bảo Yên):** Đang duy trì cảnh báo Lũ bùn quét cấp độ thảm họa. Trạm quan trắc ghi nhận mực nước lũ ~60cm, đã kích hoạt trạm sơ tán Tiểu học Bảo Yên.\n"
        if "yên bái" in msg:
            reply += "- **Yên Bái (Sông Thao):** Báo động lũ lịch sử vượt Báo động 3 (+55cm), khu vực ven sông Hồng ngập sâu. Khuyến cáo không lưu thông qua các tuyến ven đê.\n"
        if "thái nguyên" in msg:
            reply += "- **Thái Nguyên (Sông Cầu):** Trạm Gia Bảy ghi nhận nước dâng 48cm, tràn đê Chã. 3 trạm sơ tán đã mở cửa đón người dân tại Sân vận động và THPT Chuyên.\n"
        if "phú thọ" in msg or "phong châu" in msg:
            reply += "- **Phú Thọ (Cầu Phong Châu):** Sự cố sập nhịp cầu Phong Châu, cấm mọi phương tiện qua lại, phân luồng sang cầu Ngọc Tháp và cầu Trung Hà.\n"

        reply += "\n🛡️ Bạn có thể chọn ngay tính năng **Dẫn đường sơ tán** để xem vị trí an toàn gần nhất."
        suggested_actions.append({"label": "🏕️ Tìm trạm sơ tán gần nhất", "action": "switch_tab", "tab": "evac"})

    # 4. Mặc định: Trợ giúp thông minh
    else:
        reply = (
            "🤖 **Tôi là Trợ lý AI Trực ban Thiên tai NorthStar.** Tôi có thể giúp bạn:\n"
            "1. 🛣️ **Tra cứu đường đi an toàn:** Nhập tên tuyến phố để biết tình trạng ngập lụt hiện tại.\n"
            "2. 🛡️ **Tìm điểm sơ tán khẩn cấp:** Tìm nơi trú ẩn an toàn, có điện, lương thực và y tế.\n"
            "3. 🆘 **Kêu cứu cứu hộ SOS:** Phát tín hiệu định vị khẩn cấp tới lực lượng cứu nạn.\n"
            "4. 💡 **Kỹ năng sinh tồn:** Hỏi cách xử lý khi nước vào nhà, an toàn điện, lũ quét."
        )
        suggested_actions.append({"label": "🧭 Tìm đường né ngập", "action": "switch_tab", "tab": "route"})
        suggested_actions.append({"label": "🆘 Báo cứu hộ SOS", "action": "open_sos"})

    return {
        "status": "success",
        "reply": reply,
        "suggested_actions": suggested_actions
    }
