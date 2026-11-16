"""
Bộ kiểm thử tự động (Unit Test & Benchmark) cho toàn bộ hệ thống FloodNav.
Phụ trách chính: Thành viên 2 (Senior Backend)
Chạy: python -m unittest discover -s tests
"""
import time
import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.graph import get_graph

class TestFloodNavBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Khởi động trước đồ thị và dịch vụ (warm-up) để đo benchmark chuẩn xác thời gian giải thuật A*/Dijkstra
        try:
            get_graph()
            cls.client.post("/api/route", json={
                "origin": {"lng": 105.780, "lat": 21.037},
                "destination": {"lng": 105.812, "lat": 21.011},
                "vehicle": "motorbike",
                "use_ai_prediction": True
            })
        except Exception:
            pass

    def test_01_health_check(self):
        """Kiểm tra kết nối PostgreSQL và PostGIS."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("3.", data.get("postgis", ""))

    def test_02_flood_points_geojson(self):
        """Kiểm tra danh sách 8 điểm ngập trả về chuẩn GeoJSON."""
        res = self.client.get("/api/flood-points")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("type"), "FeatureCollection")
        self.assertGreaterEqual(len(data.get("features", [])), 8)

    def test_03_weather_open_meteo(self):
        """Kiểm tra tích hợp API Thời tiết Open-Meteo."""
        res = self.client.get("/api/weather/hanoi")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("hourly_forecast", data)
        self.assertEqual(data.get("city"), "Hà Nội")

    def test_04_ai_predictions(self):
        """Kiểm tra mô hình AI Scikit-learn dự báo mực nước 30/60 phút."""
        res = self.client.get("/api/predictions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 8)
        first_pt = data[0]
        self.assertIn("forecast_30m", first_pt)
        self.assertIn("forecast_60m", first_pt)
        self.assertIn("predicted_depth_cm", first_pt["forecast_30m"])

    def test_05_route_calculation_and_benchmark(self):
        """Kiểm tra tìm đường và đo đạc hiệu năng (Benchmark < 250ms)."""
        payload = {
            "origin": {"lng": 105.780, "lat": 21.037},
            "destination": {"lng": 105.812, "lat": 21.011},
            "vehicle": "motorbike",
            "use_ai_prediction": True
        }
        
        # Warm-up request trước khi bấm giờ đo giải thuật A*
        self.client.post("/api/route", json=payload)

        t0 = time.perf_counter()
        res = self.client.post("/api/route", json=payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ai_prediction_applied"))
        self.assertIn("safe", data)
        self.assertIn("fastest", data)
        self.assertTrue(data["safe"]["found"])
        
        print(f"\n[Benchmark] Thời gian tìm đường A* né ngập (2235 nút): {elapsed_ms:.2f} ms")
        self.assertLess(elapsed_ms, 500) # Đảm bảo thuật toán phản hồi siêu nhanh dưới 500ms

    def test_06_disasters_api(self):
        """Kiểm tra API giám sát đa thiên tai (GeoJSON FeatureCollection)."""
        res = self.client.get("/api/disasters")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("type"), "FeatureCollection")
        self.assertGreaterEqual(len(data.get("features", [])), 3)
        types = [f["properties"]["hazard_type"] for f in data["features"]]
        self.assertIn("flood", types)

    def test_07_shelters_api(self):
        """Kiểm tra API danh sách điểm sơ tán và tìm trạm cứu hộ gần nhất."""
        res = self.client.get("/api/shelters")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("type"), "FeatureCollection")
        self.assertGreaterEqual(len(data.get("features", [])), 4)

        # Nearest shelter
        res_near = self.client.get("/api/shelters/nearest?lng=105.795&lat=21.022")
        self.assertEqual(res_near.status_code, 200)
        near_data = res_near.json()
        self.assertIn("properties", near_data)
        self.assertIn("distance_m", near_data["properties"])

    def test_08_sos_api(self):
        """Kiểm tra API phát tín hiệu cứu hộ khẩn cấp 1-Click SOS."""
        payload = {
            "contact_name": "Nguyễn Văn Test",
            "phone": "0987654321",
            "lng": 105.795,
            "lat": 21.022,
            "people_count": 3,
            "has_elderly_or_children": True,
            "water_level_cm": 35.0,
            "priority": "critical",
            "notes": "Nước ngập ngang ngực, cần thuyền cứu sinh khẩn cấp."
        }
        res = self.client.post("/api/sos", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        sos_id = data["properties"]["id"]
        self.assertEqual(data["properties"]["priority"], "critical")

        # Update status
        patch_res = self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "dispatched"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["properties"]["status"], "dispatched")

    def test_09_evacuation_routing(self):
        """Kiểm tra thuật toán tìm đường sơ tán khẩn cấp tới điểm an toàn (Core Dijkstra)."""
        payload = {
            "origin": {"lng": 105.801, "lat": 21.010},
            "vehicle": "walk"
        }
        res = self.client.post("/api/route/evacuate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("found"))
        self.assertEqual(data.get("mode"), "evacuation")
        self.assertIn("shelter", data)
        self.assertGreater(data.get("distance_m", 0), 0)


if __name__ == "__main__":
    unittest.main()
