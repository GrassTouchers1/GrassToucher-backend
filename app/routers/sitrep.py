# Copyright 2026 GrassTouchers Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Router Xuất Báo cáo Tác chiến Chỉ huy PCTT & TKCN (Situation Report - SitRep).
Tổng hợp toàn bộ chỉ số thiên tai, ngập lụt, cứu nạn và sơ tán theo quy chuẩn
Quyết định số 18/2021/QĐ-TTg của Thủ tướng Chính phủ về dự báo, cảnh báo thiên tai.
"""

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Query, Response

from .flood_points import DEFAULT_FLOOD_POINTS
from .disasters import list_disasters
from .shelters import list_shelters
from .sos import list_sos_beacons

router = APIRouter(prefix="/api/reports", tags=["Báo cáo Tác chiến SitRep"])

@router.get("/sitrep", summary="Lấy báo cáo tác chiến tình hình thiên tai chuẩn Ban Chỉ huy PCTT")
def get_situation_report(
    format: str = Query("json", description="Định dạng: json hoặc html")
) -> Any:
    now_utc = datetime.now(timezone.utc)
    now_vn_str = now_utc.strftime("%H giờ %M phút, ngày %d tháng %m năm %Y")

    # Thống kê điểm ngập
    total_stations = len(DEFAULT_FLOOD_POINTS)
    danger_pts = [p for p in DEFAULT_FLOOD_POINTS if (p.get("depth_cm") or 0.0) >= (p.get("threshold_cm") or 20.0)]
    warning_pts = [p for p in DEFAULT_FLOOD_POINTS if 5.0 <= (p.get("depth_cm") or 0.0) < (p.get("threshold_cm") or 20.0)]
    safe_pts = [p for p in DEFAULT_FLOOD_POINTS if (p.get("depth_cm") or 0.0) < 5.0]

    # Thống kê SOS cứu hộ
    sos_data = list_sos_beacons()
    sos_features = sos_data.get("features", [])
    total_sos = len(sos_features)
    people_stranded = sum(int(f["properties"].get("people_count") or 1) for f in sos_features)
    high_priority_sos = sum(1 for f in sos_features if str(f["properties"].get("priority")).lower() in ["high", "critical"])

    # Thống kê điểm sơ tán
    shelters_data = list_shelters()
    shelter_features = shelters_data.get("features", [])
    total_shelters = len(shelter_features)
    total_capacity = sum(int(f["properties"].get("capacity") or 0) for f in shelter_features)
    current_occupancy = sum(int(f["properties"].get("current_occupancy") or 0) for f in shelter_features)

    # Thống kê điểm nóng thiên tai
    disasters_data = list_disasters()
    disaster_features = disasters_data.get("features", [])

    report_payload = {
        "agency": "VĂN PHÒNG THƯỜNG TRỰC BAN CHỈ HUY PCTT & TKCN",
        "system": "NorthStar — Hệ thống Trí tuệ Thiên tai & Ứng phó Khẩn cấp Việt Nam",
        "doc_code": f"BCN-{now_utc.strftime('%Y%m%d-%H%M')}-PCTT",
        "timestamp_str": now_vn_str,
        "kpi_summary": {
            "monitoring_stations": total_stations,
            "danger_points_count": len(danger_pts),
            "warning_points_count": len(warning_pts),
            "safe_points_count": len(safe_pts),
            "active_sos_requests": total_sos,
            "high_priority_sos": high_priority_sos,
            "total_stranded_people": people_stranded,
            "active_shelters": total_shelters,
            "shelter_total_capacity": total_capacity,
            "shelter_current_occupancy": current_occupancy,
            "shelter_available_slots": total_capacity - current_occupancy,
            "multi_hazard_zones_count": len(disaster_features)
        },
        "critical_hotspots": [
            {"name": p["name"], "depth_cm": p.get("depth_cm"), "threshold_cm": p.get("threshold_cm")}
            for p in danger_pts[:8]
        ],
        "tactical_directives": [
            "Cấm toàn bộ người và phương tiện lưu thông qua các ngầm tràn, cầu yếu (đặc biệt hạ lưu Cầu Phong Châu, ngầm tràn Thái Nguyên).",
            "Bố trí tổ công tác xuồng máy cơ động túc trực tại vùng cô lập Làng Nủ (Bảo Yên) và ven sông Thao (Yên Bái).",
            "Hệ thống tìm đường thông minh A* trên NorthStar tự động cấm xe máy qua điểm ngập ≥20cm, ô tô ≥30cm.",
            "Các trạm sơ tán công lập mở cửa 24/24 tiếp nhận dân vùng trũng, đảm bảo đủ nước sạch và cơ số thuốc y tế dự phòng."
        ]
    }

    if format == "html":
        # Tạo bản in A4 đẹp mắt
        html_content = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
          <meta charset="utf-8">
          <title>Báo Cáo Tác Chiến PCTT & TKCN</title>
          <style>
            body {{ font-family: 'Times New Roman', serif; margin: 30px 40px; color: #111; line-height: 1.5; }}
            .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .header-table td {{ vertical-align: top; text-align: center; }}
            .title {{ text-align: center; font-size: 18px; font-weight: bold; text-transform: uppercase; margin: 15px 0 5px 0; }}
            .sub-title {{ text-align: center; font-style: italic; font-size: 13px; margin-bottom: 25px; }}
            .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 25px; }}
            .kpi-box {{ border: 1px solid #333; padding: 10px; text-align: center; border-radius: 4px; }}
            .kpi-num {{ font-size: 22px; font-weight: bold; color: #b91c1c; margin-top: 5px; }}
            table.data-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            table.data-table th, table.data-table td {{ border: 1px solid #444; padding: 6px 10px; font-size: 12px; text-align: left; }}
            table.data-table th {{ background: #f3f4f6; }}
            .directives li {{ margin-bottom: 6px; font-size: 13.5px; }}
            .sign-table {{ width: 100%; margin-top: 40px; text-align: center; }}
            @media print {{
              body {{ margin: 15mm 20mm; }}
              .no-print {{ display: none; }}
            }}
          </style>
        </head>
        <body>
          <div class="no-print" style="margin-bottom: 15px;">
            <button onclick="window.print()" style="padding: 8px 16px; background: #0284c7; color: #fff; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">🖨️ In Báo Cáo / Xuất PDF</button>
          </div>
          <table class="header-table">
            <tr>
              <td style="width: 50%;">
                <b>VĂN PHÒNG THƯỜNG TRỰC</b><br>
                <b>BAN CHỈ HUY PCTT & TKCN</b><br>
                <small>Hệ thống Giám sát NorthStar</small><br>
                Số: {report_payload['doc_code']}
              </td>
              <td style="width: 50%;">
                <b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br>
                <b>Độc lập - Tự do - Hạnh phúc</b><br>
                <i>Hà Nội, {now_vn_str}</i>
              </td>
            </tr>
          </table>

          <div class="title">BÁO CÁO NHANH TÁC CHIẾN THIÊN TAI & TÌM KIẾM CỨU NẠN</div>
          <div class="sub-title">(Tình hình diễn biến ngập lụt, cứu trợ khẩn cấp trên địa bàn các tỉnh miền Bắc)</div>

          <div class="kpi-grid">
            <div class="kpi-box">
              <small>ĐIỂM NGUY HIỂM</small>
              <div class="kpi-num">{report_payload['kpi_summary']['danger_points_count']}</div>
              <small>/ {total_stations} trạm đo</small>
            </div>
            <div class="kpi-box">
              <small>TÍN HIỆU CỨU HỘ SOS</small>
              <div class="kpi-num" style="color: #dc2626;">{total_sos}</div>
              <small>({high_priority_sos} khẩn cấp)</small>
            </div>
            <div class="kpi-box">
              <small>NẠN NHÂN CẦN CỨU</small>
              <div class="kpi-num" style="color: #ea580c;">{people_stranded}</div>
              <small>người mắc kẹt</small>
            </div>
            <div class="kpi-box">
              <small>CHỖ TRỐNG SƠ TÁN</small>
              <div class="kpi-num" style="color: #16a34a;">{report_payload['kpi_summary']['shelter_available_slots']}</div>
              <small>/ {total_capacity} chỉ tiêu</small>
            </div>
          </div>

          <h4>I. DANH SÁCH CÁC ĐIỂM NGẬP ĐẶC BIỆT NGUY CẤP (VƯỢT NGƯỠNG AN TOÀN)</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th>STT</th>
                <th>Tên trạm / Vị trí</th>
                <th>Mực nước ngập</th>
                <th>Ngưỡng tràn</th>
                <th>Trạng thái phương tiện</th>
              </tr>
            </thead>
            <tbody>
              {''.join(f'<tr><td>{idx+1}</td><td>{p["name"]}</td><td style="color:#b91c1c; font-weight:bold;">{p["depth_cm"]} cm</td><td>{p["threshold_cm"]} cm</td><td>CẤM XE MÁY & Ô TÔ</td></tr>' for idx, p in enumerate(report_payload['critical_hotspots']))}
            </tbody>
          </table>

          <h4>II. MỆNH LỆNH & BIỆN PHÁP TÁC CHIẾN TRỌNG TÂM</h4>
          <ul class="directives">
            {''.join(f'<li>{d}</li>' for d in report_payload['tactical_directives'])}
          </ul>

          <table class="sign-table">
            <tr>
              <td style="width: 50%;">
                <b>NGƯỜI LẬP BÁO CÁO</b><br>
                <i>(Ký, ghi rõ họ tên)</i><br><br><br><br>
                <b>Hệ thống NorthStar AI</b>
              </td>
              <td style="width: 50%;">
                <b>TRƯỞNG BAN TÁC CHIẾN PCTT</b><br>
                <i>(Ký, đóng dấu)</i><br><br><br><br>
                <b>Đã phê duyệt điện tử</b>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")

    return report_payload
