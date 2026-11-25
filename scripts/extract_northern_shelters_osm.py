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
Trích xuất danh sách điểm sơ tán công cộng kiên cố khu vực Phía Bắc Việt Nam
từ file OpenStreetMap Geofabrik (.osm.pbf, giấy phép ODbL 1.0) và hợp nhất với Wikidata (CC0 1.0).
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import osmium

NORTH_LAT_MIN = 20.0
NORTH_LAT_MAX = 23.4
NORTH_LNG_MIN = 102.1
NORTH_LNG_MAX = 108.1

PRIORITY_AMENITIES = {
    "hospital": ("Bệnh viện / Cơ sở y tế", 800, "Tiếp nhận cấp cứu, y tế và trú ẩn an toàn"),
    "community_centre": ("Nhà văn hóa / Trung tâm cộng đồng", 500, "Điểm tập kết & tránh trú cộng đồng"),
    "townhall": ("Trụ sở UBND / Cơ quan hành chính", 400, "Trụ sở kiên cố, đầu mối điều phối cứu trợ"),
    "shelter": ("Điểm trú ẩn / Sơ tán", 600, "Điểm trú ẩn khẩn cấp"),
    "university": ("Trường Đại học", 1500, "Giảng đường/KTX kiên cố nhiều tầng"),
    "college": ("Trường Cao đẳng", 1000, "Khu nhà kiên cố, sân rộng tập kết"),
    "school": ("Trường học kiên cố", 600, "Phòng học nhiều tầng kiên cố"),
}

PRIORITY_LEISURE = {
    "sports_centre": ("Nhà thi đấu / Trung tâm TDTT", 1500, "Không gian mái che rộng tiếp nhận sơ tán"),
    "stadium": ("Sân vận động", 2000, "Bãi tập kết rộng, tiếp nhận trực thăng/cứu trợ"),
}


def format_osm_address(tags) -> str:
    parts = [
        tags.get("addr:full"),
        tags.get("addr:street"),
        tags.get("addr:subdistrict") or tags.get("addr:ward"),
        tags.get("addr:district") or tags.get("addr:county"),
        tags.get("addr:city") or tags.get("addr:province") or tags.get("addr:state"),
    ]
    cleaned = [p.strip() for p in parts if p and p.strip()]
    if cleaned:
        return ", ".join(dict.fromkeys(cleaned))
    return "Khu vực Phía Bắc Việt Nam (OpenStreetMap)"


class NorthernShelterHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.records = []
        self.school_grid_counts = defaultdict(int)
        self.seen_names = set()

    def _consider(self, osm_type: str, osm_id: int, lat: float, lng: float, tags):
        if not (NORTH_LAT_MIN <= lat <= NORTH_LAT_MAX and NORTH_LNG_MIN <= lng <= NORTH_LNG_MAX):
            return
        name = (tags.get("name:vi") or tags.get("name") or "").strip()
        if not name or len(name) < 3:
            return

        amenity = (tags.get("amenity") or "").strip()
        leisure = (tags.get("leisure") or "").strip()

        if amenity in PRIORITY_AMENITIES:
            cat_label, capacity, supplies = PRIORITY_AMENITIES[amenity]
            is_school = amenity == "school"
        elif leisure in PRIORITY_LEISURE:
            cat_label, capacity, supplies = PRIORITY_LEISURE[leisure]
            is_school = False
        else:
            return

        norm_key = f"{name.lower()}|{round(lat, 2)}|{round(lng, 2)}"
        if norm_key in self.seen_names:
            return

        # Giữ tối đa 2 trường học đại diện mỗi ô lưới ~8km x 8km để phủ đều các tỉnh mà không làm quá tải bản đồ
        if is_school:
            grid_key = (int(lat / 0.08), int(lng / 0.08))
            if self.school_grid_counts[grid_key] >= 2:
                return
            self.school_grid_counts[grid_key] += 1

        self.seen_names.add(norm_key)
        self.records.append({
            "osm_id": f"{osm_type}/{osm_id}",
            "name": name,
            "address": format_osm_address(tags),
            "category": cat_label,
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "capacity": capacity,
            "current_occupancy": 0,
            "contact_phone": tags.get("phone") or tags.get("contact:phone") or None,
            "supplies_status": f"{supplies} (Nguồn: OpenStreetMap {osm_type}/{osm_id} - ODbL 1.0)",
            "status": "open",
        })

    def node(self, n):
        if not n.location.valid():
            return
        self._consider("node", n.id, n.location.lat, n.location.lon, n.tags)

    def way(self, w):
        amenity = w.tags.get("amenity")
        leisure = w.tags.get("leisure")
        if amenity not in PRIORITY_AMENITIES and leisure not in PRIORITY_LEISURE:
            return
        lats, lngs = [], []
        for nd in w.nodes:
            if nd.location.valid():
                lats.append(nd.location.lat)
                lngs.append(nd.location.lon)
        if not lats:
            return
        self._consider("way", w.id, sum(lats) / len(lats), sum(lngs) / len(lngs), w.tags)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", required=True, help="Đường dẫn file vietnam-latest.osm.pbf")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "northern_shelters.json"),
        help="Đường dẫn file JSON đầu ra",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    existing_items = []
    if out_path.exists():
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            existing_items = old.get("shelters", [])
        except Exception:
            existing_items = []

    handler = NorthernShelterHandler()
    handler.apply_file(args.pbf, locations=True, idx="flex_mem")

    merged = []
    seen = set()
    for item in existing_items + handler.records:
        key = f"{(item.get('name') or '').strip().lower()}|{round(float(item['lat']), 2)}|{round(float(item['lng']), 2)}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    merged.sort(key=lambda x: x["name"])
    payload = {
        "sources": [
            "OpenStreetMap contributors via Geofabrik (https://download.geofabrik.de/asia/vietnam-latest.osm.pbf)",
            "Wikidata SPARQL (https://query.wikidata.org/sparql)",
        ],
        "licenses": ["ODbL-1.0 (OpenStreetMap)", "CC0-1.0 (Wikidata)"],
        "attribution": "© OpenStreetMap contributors (ODbL 1.0) & Wikidata (CC0 1.0)",
        "region": "Northern Vietnam (20.0N-23.4N, 102.1E-108.1E)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(merged),
        "shelters": merged,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(handler.records)} OSM records; merged total={len(merged)} saved to {out_path}")


if __name__ == "__main__":
    main()
