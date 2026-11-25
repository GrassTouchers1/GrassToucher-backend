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
Bo kiem thu Bao mat & Phan quyen RBAC phia May chu (Auth, RBAC, Anti-IDOR, Audit Log).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import auth, fallback_storage  # noqa: E402
from app.main import app  # noqa: E402


DEMO_PW = os.getenv("NORTHSTAR_DEMO_PASSWORD", "NorthStarDemo@2026")


class TestRBACSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = Path(self.tmp_dir.name) / "test_rbac.db"
        self.patchers = [
            patch.object(fallback_storage, "DB_PATH", self.test_db_path),
            patch("app.routers.sos.get_db_connection", side_effect=RuntimeError("Mocked PG offline")),
            patch("app.routers.disasters.get_db_connection", side_effect=RuntimeError("Mocked PG offline")),
            patch("app.routers.shelters.get_db_connection", side_effect=RuntimeError("Mocked PG offline")),
            patch("app.routers.flood_points.get_db_connection", side_effect=RuntimeError("Mocked PG offline")),
        ]
        for p in self.patchers:
            p.start()
        fallback_storage.init_fallback_db()
        auth.init_auth_tables()
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tmp_dir.cleanup()

    def _login(self, username: str, password: str = DEMO_PW) -> dict:
        r = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_guest_fail_closed_on_protected_endpoints(self):
        self.assertEqual(self.client.get("/api/sos").status_code, 401)
        self.assertEqual(self.client.get("/api/sos/mine").status_code, 401)
        self.assertEqual(self.client.get("/api/relief/queue").status_code, 401)
        self.assertEqual(self.client.post("/api/rescue/dispatch", json={}).status_code, 401)
        self.assertEqual(self.client.get("/api/reports/sitrep").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/users").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/audit-logs").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_token_tamper_and_logout_revocation(self):
        headers = self._login("coordinator_demo")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)

        # Tampered token must fail with 401
        bad_headers = {"Authorization": headers["Authorization"] + "tamper"}
        self.assertEqual(self.client.get("/api/auth/me", headers=bad_headers).status_code, 401)

        # Logout revokes jti cleanly
        out = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(out.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_privilege_escalation_blocked_on_register(self):
        esc = self.client.post("/api/auth/register", json={
            "username": "attacker01",
            "password": "Password123!",
            "full_name": "Attacker",
            "role": "admin",
        })
        self.assertEqual(esc.status_code, 403)

        ok = self.client.post("/api/auth/register", json={
            "username": "newcitizen01",
            "password": "Password123!",
            "full_name": "Nguyen Van Dan",
        })
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["user"]["role"], "citizen")

    def test_citizen_isolation_and_anti_idor_on_sos(self):
        c1_hdr = self._login("citizen_demo")
        c2_hdr = self._login("citizen_demo2")

        # Citizen cannot list all SOS or relief queue or dispatch
        self.assertEqual(self.client.get("/api/sos", headers=c1_hdr).status_code, 403)
        self.assertEqual(self.client.get("/api/relief/queue", headers=c1_hdr).status_code, 403)
        self.assertEqual(self.client.post("/api/rescue/dispatch", json={}, headers=c1_hdr).status_code, 403)
        self.assertEqual(self.client.get("/api/reports/sitrep", headers=c1_hdr).status_code, 403)

        # Citizen 1 creates SOS -> owns it
        sos_res = self.client.post("/api/sos", json={
            "contact_name": "An",
            "phone": "0911111111",
            "lng": 105.80,
            "lat": 21.02,
            "people_count": 2,
            "priority": "high",
        }, headers=c1_hdr)
        self.assertEqual(sos_res.status_code, 201)
        sos_id = sos_res.json()["properties"]["id"]

        # Citizen 1 sees it in /api/sos/mine, Citizen 2 does NOT
        mine1 = self.client.get("/api/sos/mine", headers=c1_hdr).json()["features"]
        mine2 = self.client.get("/api/sos/mine", headers=c2_hdr).json()["features"]
        self.assertTrue(any(f["properties"]["id"] == sos_id for f in mine1))
        self.assertFalse(any(f["properties"]["id"] == sos_id for f in mine2))

        # IDOR check: Citizen 2 cannot cancel Citizen 1's SOS
        idor = self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "cancelled"}, headers=c2_hdr)
        self.assertEqual(idor.status_code, 403)

        # Citizen 1 cannot escalate to dispatched/verified, only cancelled
        bad_status = self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "dispatched"}, headers=c1_hdr)
        self.assertEqual(bad_status.status_code, 403)

        ok_cancel = self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "cancelled"}, headers=c1_hdr)
        self.assertEqual(ok_cancel.status_code, 200)
        self.assertEqual(ok_cancel.json()["properties"]["status"], "cancelled")

    def test_rescue_coordinator_and_admin_boundaries(self):
        c_hdr = self._login("citizen_demo")
        r_hdr = self._login("rescue_demo")
        coord_hdr = self._login("coordinator_demo")
        adm_hdr = self._login("admin_demo")

        sos_res = self.client.post("/api/sos", json={
            "contact_name": "Bi co lap",
            "phone": "0922222222",
            "lng": 105.81,
            "lat": 21.03,
            "people_count": 3,
            "priority": "critical",
        }, headers=c_hdr)
        sos_id = sos_res.json()["properties"]["id"]

        # Rescue can list SOS, dispatch, view relief queue, set field status on_scene/rescued
        self.assertEqual(self.client.get("/api/sos", headers=r_hdr).status_code, 200)
        self.assertEqual(self.client.get("/api/relief/queue", headers=r_hdr).status_code, 200)
        self.assertEqual(self.client.post("/api/rescue/dispatch", json={"vehicle_type": "boat"}, headers=r_hdr).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "on_scene"}, headers=r_hdr).status_code, 200)
        # Rescue CANNOT verify/cancel or override priority or open admin endpoints
        self.assertEqual(self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "verified"}, headers=r_hdr).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/users", headers=r_hdr).status_code, 403)

        # Coordinator can set verified/dispatched, create disaster/shelter, but CANNOT access /api/admin/*
        self.assertEqual(self.client.patch(f"/api/sos/{sos_id}/status", json={"status": "dispatched"}, headers=coord_hdr).status_code, 200)
        self.assertEqual(self.client.post("/api/disasters", json={
            "title": "Sat lo test RBAC",
            "hazard_type": "landslide",
            "severity": "high",
            "lng": 105.82,
            "lat": 21.04,
        }, headers=coord_hdr).status_code, 201)
        self.assertEqual(self.client.get("/api/admin/users", headers=coord_hdr).status_code, 403)

        # Admin accesses /api/admin/users and /api/admin/audit-logs
        users_r = self.client.get("/api/admin/users", headers=adm_hdr)
        self.assertEqual(users_r.status_code, 200)
        logs_r = self.client.get("/api/admin/audit-logs", headers=adm_hdr)
        self.assertEqual(logs_r.status_code, 200)
        self.assertGreater(len(logs_r.json()["logs"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
