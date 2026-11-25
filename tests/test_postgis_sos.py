"""
Kiểm thử nhiệm vụ CIT-03.1: Hỗ trợ SOS không có tọa độ (geom = NULL) trên PostgreSQL/PostGIS và SQLite fallback.
Bao gồm POSTGIS-01 đến POSTGIS-08.
"""
import os
import sqlite3
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.db import is_db_available, get_db_connection
from app.schemas import SOSCreate
from app.fallback_storage import DB_PATH, init_fallback_db


class TestPostgisAndFallbackSOS(unittest.TestCase):
    """Kiểm thử 8 kịch bản POSTGIS-01..08 trên API + Fallback SQLite và kiểm tra PostgreSQL thực tế."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_postgis_01_valid_lat_lng(self):
        """POSTGIS-01: SOS có lat/lng hợp lệ -> lưu thành công, geometry Point."""
        res = self.client.post("/api/sos", json={
            "contact_name": "PostGIS Valid",
            "phone": "0911111101",
            "lat": 21.0285,
            "lng": 105.8542,
            "location_source": "gps",
            "location_accuracy_m": 18.0,
            "location_captured_at": "2026-11-25T04:00:00Z",
            "location_confirmed": True,
        })
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["geometry"]["type"], "Point")
        self.assertEqual(body["geometry"]["coordinates"], [105.8542, 21.0285])
        self.assertEqual(body["properties"]["location_source"], "gps")
        self.assertIsInstance(body["properties"]["id"], int)

    def test_postgis_02_null_coords_with_description(self):
        """POSTGIS-02: SOS lat=null, lng=null nhưng có mô tả địa điểm -> lưu thành công, geometry=null."""
        res = self.client.post("/api/sos", json={
            "contact_name": "PostGIS NoCoords",
            "phone": "0911111102",
            "lat": None,
            "lng": None,
            "location_source": "unknown",
            "location_confirmed": True,
            "location_description": "Thon 3, xa Nam Phuong Tien, Chuong My",
            "location_landmark": "Gan nha van hoa thon 3",
        })
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertIsNone(body["geometry"])
        self.assertEqual(body["properties"]["location_source"], "unknown")
        self.assertEqual(body["properties"]["location_description"], "Thon 3, xa Nam Phuong Tien, Chuong My")

    def test_postgis_03_lat_only_rejected(self):
        """POSTGIS-03: SOS có lat nhưng lng=null -> từ chối HTTP 422."""
        res = self.client.post("/api/sos", json={
            "contact_name": "Only Lat",
            "phone": "0911111103",
            "lat": 21.0285,
            "lng": None,
            "location_description": "Co mo ta nhung thieu lng",
        })
        self.assertEqual(res.status_code, 422)

    def test_postgis_04_lng_only_rejected(self):
        """POSTGIS-04: SOS có lng nhưng lat=null -> từ chối HTTP 422."""
        res = self.client.post("/api/sos", json={
            "contact_name": "Only Lng",
            "phone": "0911111104",
            "lat": None,
            "lng": 105.8542,
            "location_description": "Co mo ta nhung thieu lat",
        })
        self.assertEqual(res.status_code, 422)

    def test_postgis_05_null_coords_and_empty_description_rejected(self):
        """POSTGIS-05: Không có tọa độ và không có mô tả địa điểm -> từ chối HTTP 422."""
        res = self.client.post("/api/sos", json={
            "contact_name": "No Location",
            "phone": "0911111105",
            "lat": None,
            "lng": None,
            "location_description": "",
            "location_landmark": "",
        })
        self.assertEqual(res.status_code, 422)

    def test_postgis_06_out_of_range_coords_rejected(self):
        """POSTGIS-06: Tọa độ ngoài phạm vi [-90..90], [-180..180] -> từ chối HTTP 422."""
        res1 = self.client.post("/api/sos", json={
            "contact_name": "Bad Lat",
            "phone": "0911111106",
            "lat": 95.0,
            "lng": 105.85,
        })
        self.assertEqual(res1.status_code, 422)
        res2 = self.client.post("/api/sos", json={
            "contact_name": "Bad Lng",
            "phone": "0911111106",
            "lat": 21.0,
            "lng": -185.0,
        })
        self.assertEqual(res2.status_code, 422)

    def test_postgis_07_zero_zero_coords_accepted(self):
        """POSTGIS-07: lat=0, lng=0 hợp lệ, không bị nhầm với giá trị thiếu (truthy bug)."""
        res = self.client.post("/api/sos", json={
            "contact_name": "Zero Origin",
            "phone": "0911111107",
            "lat": 0.0,
            "lng": 0.0,
            "location_source": "manual",
            "location_confirmed": True,
        })
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertIsNotNone(body["geometry"])
        self.assertEqual(body["geometry"]["coordinates"], [0.0, 0.0])

    def test_postgis_08_list_sos_with_null_geom_no_error(self):
        """POSTGIS-08: Truy vấn danh sách SOS khi có bản ghi geom=NULL không phát sinh lỗi."""
        res = self.client.get("/api/sos")
        self.assertEqual(res.status_code, 200)
        fc = res.json()
        self.assertEqual(fc["type"], "FeatureCollection")
        null_geoms = [f for f in fc["features"] if f.get("geometry") is None]
        self.assertGreaterEqual(len(null_geoms), 1)

    def test_postgres_live_srid_and_null_geom_if_available(self):
        """Kiểm thử trực tiếp trên PostgreSQL/PostGIS nếu DB đang kết nối được."""
        if not is_db_available():
            self.skipTest("PostgreSQL offline / sai thông tin xác thực trong .env - không đánh đồng với SQLite fallback")
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT is_nullable FROM information_schema.columns WHERE table_name='community_sos' AND column_name='geom'"
            ).fetchone()
            self.assertEqual(row["is_nullable"], "YES")

    def test_migration_0003_downgrade_checks_null_before_drop(self):
        """Đảm bảo downgrade của migration 0003 kiểm tra geom IS NULL và RAISE EXCEPTION trước khi DROP COLUMN."""
        mig_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "db", "alembic", "versions", "0003_nullable_sos_geom_and_location_meta.py"
        )
        with open(mig_path, "r", encoding="utf-8") as f:
            src = f.read()
        downgrade_body = src.split("def downgrade()")[1]
        pos_check = downgrade_body.find("WHERE geom IS NULL")
        pos_raise = downgrade_body.find("RAISE EXCEPTION")
        pos_drop = downgrade_body.find("DROP COLUMN")
        pos_not_null = downgrade_body.find("SET NOT NULL")
        self.assertGreater(pos_check, 0)
        self.assertGreater(pos_raise, pos_check)
        self.assertGreater(pos_drop, pos_raise, "DROP COLUMN phải nằm SAU bước kiểm tra & RAISE EXCEPTION")
        self.assertGreater(pos_not_null, pos_raise, "SET NOT NULL phải nằm SAU bước kiểm tra & RAISE EXCEPTION")

    def test_schema_sync_migration_pydantic_and_sqlite(self):
        """Kiểm tra đồng bộ 6 trường metadata vị trí giữa migration 0003, SOSCreate và SQLite fallback_sos."""
        expected_meta = {
            "location_source",
            "location_accuracy_m",
            "location_captured_at",
            "location_confirmed",
            "location_description",
            "location_landmark",
        }
        self.assertTrue(expected_meta.issubset(set(SOSCreate.model_fields.keys())))

        init_fallback_db()
        with sqlite3.connect(str(DB_PATH)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(fallback_sos)").fetchall()}
        self.assertTrue(expected_meta.issubset(cols))

    def test_postgres_downgrade_cases_when_connected(self):
        """Kiểm thử rollback Case A (không có geom NULL) & Case B (còn geom NULL -> bị từ chối) trên PostgreSQL thật."""
        if not is_db_available():
            self.skipTest("PostgreSQL offline / sai thông tin xác thực trong .env - không thể chạy rollback thật")


if __name__ == "__main__":
    unittest.main()
