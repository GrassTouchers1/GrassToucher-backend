import contextlib
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app  # noqa: E402
from app import fallback_storage  # noqa: E402
from app.db import is_db_available  # noqa: E402


class TestPhase4FallbackIdempotency(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = Path(self.tmp_dir.name) / 'test_fallback.db'
        self.patchers = [
            patch.object(fallback_storage, 'DB_PATH', self.test_db_path),
            patch('app.routers.sos.get_db_connection', side_effect=RuntimeError('Mocked PG offline')),
            patch('app.routers.reports.get_db_connection', side_effect=RuntimeError('Mocked PG offline')),
        ]
        for p in self.patchers:
            p.start()
        fallback_storage.init_fallback_db()
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tmp_dir.cleanup()

    def test_sos_idempotent_replay_returns_existing_id(self):
        cid = str(uuid.uuid4())
        payload = {
            'lat': 21.0285,
            'lng': 105.8542,
            'location_source': 'gps',
            'location_confirmed': True,
            'priority': 'high',
            'people_count': 3,
            'has_elderly_or_children': True,
            'water_level_cm': 45,
            'notes': 'Mắc kẹt tầng 2',
            'contact_name': 'Nguyen Van A',
            'phone': '0912345678',
            'client_event_id': cid,
        }

        r1 = self.client.post('/api/sos', json=payload)
        self.assertIn(r1.status_code, (200, 201), r1.text)
        d1 = r1.json()
        id1 = d1['properties']['id']
        self.assertFalse(d1['properties'].get('idempotent_replay', False))

        r2 = self.client.post('/api/sos', json=payload)
        self.assertIn(r2.status_code, (200, 201), r2.text)
        d2 = r2.json()
        self.assertEqual(d2['properties']['id'], id1)
        self.assertTrue(d2['properties'].get('idempotent_replay'))

        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            cnt = conn.execute('SELECT COUNT(*) FROM fallback_sos WHERE client_event_id = ?', (cid,)).fetchone()[0]
        self.assertEqual(cnt, 1)

    def test_sos_idempotency_conflict_returns_409(self):
        cid = str(uuid.uuid4())
        payload1 = {
            'lat': 21.0285,
            'lng': 105.8542,
            'location_source': 'gps',
            'location_confirmed': True,
            'priority': 'high',
            'people_count': 2,
            'contact_name': 'Nguyen Van A',
            'phone': '0912345678',
            'client_event_id': cid,
        }
        r1 = self.client.post('/api/sos', json=payload1)
        self.assertIn(r1.status_code, (200, 201), r1.text)
        id1 = r1.json()['properties']['id']

        payload2 = dict(payload1)
        payload2['people_count'] = 5
        r2 = self.client.post('/api/sos', json=payload2)
        self.assertEqual(r2.status_code, 409, r2.text)

        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            rows = conn.execute('SELECT id, people_count FROM fallback_sos WHERE client_event_id = ?', (cid,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], id1)
        self.assertEqual(rows[0][1], 2)

    def test_sos_concurrent_same_client_event_id(self):
        cid = str(uuid.uuid4())
        payload = {
            'lat': 21.031,
            'lng': 105.851,
            'location_source': 'manual',
            'location_confirmed': True,
            'priority': 'critical',
            'people_count': 4,
            'contact_name': 'Tran Thi B',
            'phone': '0987654321',
            'client_event_id': cid,
        }

        def send_once():
            return self.client.post('/api/sos', json=payload)

        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(lambda _: send_once(), range(6)))

        ids = set()
        for resp in responses:
            self.assertIn(resp.status_code, (200, 201), resp.text)
            ids.add(resp.json()['properties']['id'])

        self.assertEqual(len(ids), 1)
        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            cnt = conn.execute('SELECT COUNT(*) FROM fallback_sos WHERE client_event_id = ?', (cid,)).fetchone()[0]
        self.assertEqual(cnt, 1)

    def test_report_idempotent_replay_and_conflict(self):
        cid = str(uuid.uuid4())
        payload = {
            'lat': 21.0285,
            'lng': 105.8030,
            'level': 'heavy',
            'photo_url': None,
            'user_id': None,
            'client_event_id': cid,
        }

        r1 = self.client.post('/api/reports', json=payload)
        self.assertIn(r1.status_code, (200, 201), r1.text)
        d1 = r1.json()
        self.assertFalse(d1.get('idempotent_replay', False))

        r2 = self.client.post('/api/reports', json=payload)
        self.assertIn(r2.status_code, (200, 201), r2.text)
        d2 = r2.json()
        self.assertEqual(d2['id'], d1['id'])
        self.assertTrue(d2.get('idempotent_replay'))

        conflict_payload = dict(payload)
        conflict_payload['level'] = 'light'
        r3 = self.client.post('/api/reports', json=conflict_payload)
        self.assertEqual(r3.status_code, 409, r3.text)

        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            rows = conn.execute('SELECT level FROM fallback_reports WHERE client_event_id = ?', (cid,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'heavy')

    def test_report_concurrent_same_client_event_id(self):
        cid = str(uuid.uuid4())
        payload = {
            'lat': 21.029,
            'lng': 105.804,
            'level': 'medium',
            'photo_url': None,
            'user_id': None,
            'client_event_id': cid,
        }

        def send_once():
            return self.client.post('/api/reports', json=payload)

        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(lambda _: send_once(), range(6)))

        ids = {resp.json()['id'] for resp in responses}
        for resp in responses:
            self.assertIn(resp.status_code, (200, 201), resp.text)
        self.assertEqual(len(ids), 1)

        with contextlib.closing(sqlite3.connect(self.test_db_path)) as conn:
            cnt = conn.execute('SELECT COUNT(*) FROM fallback_reports WHERE client_event_id = ?', (cid,)).fetchone()[0]
        self.assertEqual(cnt, 1)


class TestPhase4PostgresLiveIdempotency(unittest.TestCase):
    def test_postgres_live_idempotency(self):
        if not is_db_available():
            self.skipTest('PostgreSQL live DB is unavailable in local environment (.env auth/connection)')
        client = TestClient(app)
        cid = str(uuid.uuid4())
        payload = {
            'lat': 21.0285,
            'lng': 105.8542,
            'location_source': 'gps',
            'location_confirmed': True,
            'priority': 'high',
            'people_count': 1,
            'contact_name': 'PG Test',
            'phone': '0900000001',
            'client_event_id': cid,
        }
        r1 = client.post('/api/sos', json=payload)
        self.assertIn(r1.status_code, (200, 201), r1.text)
        r2 = client.post('/api/sos', json=payload)
        self.assertIn(r2.status_code, (200, 201), r2.text)
        self.assertEqual(r1.json()['properties']['id'], r2.json()['properties']['id'])
        self.assertTrue(r2.json()['properties'].get('idempotent_replay'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
