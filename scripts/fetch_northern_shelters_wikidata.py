# Copyright 2026 GrassTouchers
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

"""
Truy vấn danh sách cơ sở hạ tầng kiên cố thực tế khu vực Phía Bắc Việt Nam
từ Wikidata SPARQL (giấy phép dữ liệu mở CC0 1.0 Public Domain) làm điểm sơ tán.
Duyệt phân cấp lớp con (wdt:P31/wdt:P279*) để bao phủ cả các tỉnh ngoài Hà Nội.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Khung địa lý Phía Bắc Việt Nam (từ Ninh Bình/Thanh Hóa Bắc trở ra)
NORTH_LAT_MIN = 20.0
NORTH_LAT_MAX = 23.4
NORTH_LNG_MIN = 102.1
NORTH_LNG_MAX = 108.1

TYPE_CONFIG = {
    "wd:Q16917": ("Bệnh viện / Cơ sở y tế", 800, "Sẵn sàng tiếp nhận cấp cứu, y tế và trú ẩn an toàn"),
    "wd:Q3918": ("Khuôn viên Đại học", 1500, "Giảng đường/KTX kiên cố nhiều tầng, điện nước dự phòng"),
    "wd:Q189004": ("Trường Cao đẳng / Học viện", 1000, "Khu nhà kiên cố, sân rộng tập kết cứu hộ"),
    "wd:Q9826": ("Trường THPT", 700, "Khối phòng học nhiều tầng kiên cố, điểm tránh trú cộng đồng"),
    "wd:Q3914": ("Trường học kiên cố", 600, "Phòng học kiên cố phục vụ sơ tán khẩn cấp"),
    "wd:Q483110": ("Sân vận động / Nhà thi đấu", 2000, "Không gian rộng lớn tiếp nhận sơ tán tập trung"),
    "wd:Q1076486": ("Nhà thi đấu / Khu liên hợp thể thao", 1800, "Mái che kiên cố, sức chứa lớn"),
    "wd:Q1329623": ("Trung tâm Văn hóa", 900, "Hội trường cộng đồng kiên cố phục vụ tránh trú"),
}

POINT_RE = re.compile(r"Point\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)")
QID_RE = re.compile(r"^Q\d+$")


def _run_sparql(query: str) -> list:
    url = f"{SPARQL_ENDPOINT}?format=json&query={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NORTHSTAR-Rescue-OpenData/1.0 (Apache-2.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return raw.get("results", {}).get("bindings", [])


def fetch_northern_shelters(output_path: Path) -> dict:
    seen_qids = set()
    seen_names = set()
    items = []

    if output_path.exists():
        try:
            old = json.loads(output_path.read_text(encoding="utf-8"))
            for old_item in old.get("shelters", []):
                qid = old_item.get("wikidata_id")
                name = (old_item.get("name") or "").strip()
                if qid:
                    seen_qids.add(qid)
                if name:
                    seen_names.add(name.lower())
                items.append(old_item)
        except Exception:
            pass

    for type_qid, (role_label, capacity, supplies) in TYPE_CONFIG.items():
        query = f"""
        SELECT DISTINCT ?item ?itemLabel ?coord WHERE {{
          ?item wdt:P17 wd:Q881 ;
                wdt:P625 ?coord ;
                wdt:P31/wdt:P279* {type_qid} .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "vi,en". }}
        }}
        LIMIT 1000
        """
        try:
            bindings = _run_sparql(query)
        except Exception as exc:
            print(f"[WARN] Query failed for {type_qid}: {exc}")
            time.sleep(2.0)
            continue

        for row in bindings:
            item_uri = row.get("item", {}).get("value", "")
            qid = item_uri.rsplit("/", 1)[-1] if item_uri else ""
            if not qid or qid in seen_qids:
                continue

            name = (row.get("itemLabel", {}).get("value") or "").strip()
            if not name or QID_RE.match(name):
                continue

            coord_str = row.get("coord", {}).get("value", "")
            m = POINT_RE.match(coord_str)
            if not m:
                continue
            lng = round(float(m.group(1)), 6)
            lat = round(float(m.group(2)), 6)
            if not (NORTH_LAT_MIN <= lat <= NORTH_LAT_MAX and NORTH_LNG_MIN <= lng <= NORTH_LNG_MAX):
                continue

            norm_name = name.lower()
            if norm_name in seen_names:
                continue

            admin = (row.get("adminLabel", {}).get("value") or "").strip()
            if admin and not QID_RE.match(admin):
                address = f"{admin}, Phía Bắc Việt Nam"
            else:
                address = "Khu vực Phía Bắc Việt Nam"

            seen_qids.add(qid)
            seen_names.add(norm_name)
            items.append({
                "wikidata_id": qid,
                "name": name,
                "address": address,
                "category": role_label,
                "lng": lng,
                "lat": lat,
                "capacity": capacity,
                "current_occupancy": 0,
                "contact_phone": None,
                "supplies_status": f"{supplies} (Nguồn: Wikidata {qid} - CC0 1.0)",
                "status": "open",
            })

        time.sleep(1.5)

    items.sort(key=lambda x: x["name"])
    payload = {
        "source": "Wikidata SPARQL (https://query.wikidata.org/sparql)",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "region": "Northern Vietnam (20.0N-23.4N, 102.1E-108.1E)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "shelters": items,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "northern_shelters.json"
    result = fetch_northern_shelters(out)
    print(f"Saved {result['count']} Northern Vietnam shelters (CC0-1.0) to {out}")
