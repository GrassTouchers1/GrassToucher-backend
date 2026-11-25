import contextlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app  # noqa: E402
from app import fallback_storage  # noqa: E402
from app.routers import sos as sos_router  # noqa: E402


class TestPhase9SOSTrackingSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = Path(self.tmp_dir.name) / 'test_p9_fallback.db'
        sos_router._TRACK_RATE_BUCKETS.clear()
        self.patchers = [
            patch.object(fallback_storage, 'DB_PATH', self.test_db_path),
            patch('app.routers.sos.get_db_connection', side_effect=RuntimeError('Mocked PG offline')),
        ]
        for p in self.patchers:
            p.start()
        fallback_storage.init_fallback_db()
        self.client = TestClient(app)

    def tearDown(self):
        sos_router._TRACK_RATE_BUCKETS.clear()
        for p in reversed(self.patchers):
            p.stop()
        self.tmp_dir.cleanup()

    def _create_sample_sos(self, phone='0912345678', name='Nguyen Van Bi Mat'):
        res = self.client.post('/api/sos', json={
            'contact_name': name,
            'phone': phone,
            'lat': 21.0285,
            'lng': 105.8542,
            'location_source': 'gps',
            'location_confirmed': True,
            'people_count': 3,
            'has_elderly_or_children': True,
            'water_level_cm': 60,
            'priority': 'high',
            'notes': 'Can cuu gap',
        })
        self.assertIn(res.status_code, (200, 201), res.text)
        return res.json()

    def test_track_01_07_08_09_10_valid_token_no_pii_and_real_status(self):
        created = self._create_sample_sos()
        props = created['properties']
        sos_id = props['id']
        token = props.get('tracking_token')
        self.assertIsNotNone(token)
        self.assertGreaterEqual(len(token), 24)

        # Token must be stored as hash, NOT raw plaintext in DB
        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            row = conn.execute('SELECT tracking_token_hash FROM fallback_sos WHERE id = ?', (sos_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], token)
        self.assertEqual(len(row[0]), 64)

        # TRACK-09: Initially RECEIVED, not DISPATCHED
        r1 = self.client.get(f'/api/sos/track/{token}')
        self.assertEqual(r1.status_code, 200, r1.text)
        d1 = r1.json()
        self.assertEqual(d1['status'], 'RECEIVED')
        self.assertFalse(d1['progress_confirmed'])

        # TRACK-07 & TRACK-08: Strict PII minimization
        serialized = str(d1)
        self.assertNotIn('0912345678', serialized)
        self.assertNotIn('Nguyen Van Bi Mat', serialized)
        self.assertNotIn('21.0285', serialized)
        self.assertNotIn('Can cuu gap', serialized)
        for forbidden_key in ('phone', 'contact_name', 'lat', 'lng', 'notes', 'people_count'):
            self.assertNotIn(forbidden_key, d1)

        # TRACK-10: Status updates reflect real PATCH /api/sos/{id}/status (authenticated as coordinator)
        login_res = self.client.post('/api/auth/login', json={
            'username': 'coordinator_demo',
            'password': os.getenv('NORTHSTAR_DEMO_PASSWORD', 'NorthStarDemo@2026'),
        })
        self.assertEqual(login_res.status_code, 200, login_res.text)
        coord_headers = {'Authorization': f"Bearer {login_res.json()['access_token']}"}
        p_res = self.client.patch(f'/api/sos/{sos_id}/status', json={'status': 'dispatched'}, headers=coord_headers)
        self.assertEqual(p_res.status_code, 200, p_res.text)
        r2 = self.client.get(f'/api/sos/track/{token}')
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertEqual(d2['status'], 'DISPATCHED')
        self.assertTrue(d2['progress_confirmed'])

    def test_track_02_and_06_invalid_token_sequential_id_and_citizen_list_block(self):
        self._create_sample_sos()
        # TRACK-02: Unknown token
        self.assertEqual(self.client.get('/api/sos/track/invalid_token_1234567890').status_code, 404)
        # TRACK-06: Sequential ID rejected
        self.assertEqual(self.client.get('/api/sos/track/1').status_code, 404)
        self.assertEqual(self.client.get('/api/sos/track/SOS-2026-0001').status_code, 404)
        # Citizen header blocked from GET /api/sos
        r_list = self.client.get('/api/sos', headers={'X-NorthStar-Client': 'citizen'})
        self.assertEqual(r_list.status_code, 403)

    def test_track_03_expired_token(self):
        created = self._create_sample_sos()
        sos_id = created['properties']['id']
        token = created['properties']['tracking_token']
        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            conn.execute("UPDATE fallback_sos SET tracking_token_expires_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (sos_id,))
            conn.commit()
        r = self.client.get(f'/api/sos/track/{token}')
        self.assertEqual(r.status_code, 410)

    def test_track_04_revoked_token(self):
        created = self._create_sample_sos()
        token = created['properties']['tracking_token']
        rev = self.client.post(f'/api/sos/track/{token}/revoke')
        self.assertEqual(rev.status_code, 200)
        self.assertTrue(rev.json()['revoked'])
        r = self.client.get(f'/api/sos/track/{token}')
        self.assertEqual(r.status_code, 404)

    def test_track_05_rate_limit(self):
        created = self._create_sample_sos()
        token = created['properties']['tracking_token']
        for _ in range(sos_router._TRACK_RATE_LIMIT_MAX):
            r = self.client.get(f'/api/sos/track/{token}')
            self.assertEqual(r.status_code, 200)
        r_over = self.client.get(f'/api/sos/track/{token}')
        self.assertEqual(r_over.status_code, 429)
        self.assertIn('Retry-After', r_over.headers)


if __name__ == '__main__':
    unittest.main(verbosity=2)
