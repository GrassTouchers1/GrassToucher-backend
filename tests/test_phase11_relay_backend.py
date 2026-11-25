import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app  # noqa: E402
from app import fallback_storage  # noqa: E402


class TestPhase11BackendRelay(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = Path(self.tmp_dir.name) / 'test_p11_relay.db'
        self.patchers = [
            patch.object(fallback_storage, 'DB_PATH', self.test_db_path),
            patch('app.routers.sos.get_db_connection', side_effect=RuntimeError('Mocked PG offline')),
        ]
        for p in self.patchers:
            p.start()
        fallback_storage.init_fallback_db()
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tmp_dir.cleanup()

    def test_relay_endpoint_deduplicates_and_validates(self):
        packet = {
            'client_event_id': 'evt-relay-backend-001',
            'origin_device_id': 'dev-abc12345',
            'expires_at': '2099-12-31T23:59:59+00:00',
            'location': {'lat': 21.0285, 'lng': 105.8542, 'location_description': 'Hoan Kiem'},
            'location_source': 'gps',
            'payload': {'people_count': 2, 'priority': 'high', 'notes': 'Relayed SOS'},
            'hop_count': 1,
            'max_hops': 3,
        }
        r1 = self.client.post('/api/sos/relay', json=packet)
        self.assertEqual(r1.status_code, 201, r1.text)
        r2 = self.client.post('/api/sos/relay', json=packet)
        self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(r1.json()['properties']['id'], r2.json()['properties']['id'])
        self.assertTrue(r2.json()['properties']['idempotent_replay'])

        expired = dict(packet, expires_at='2020-01-01T00:00:00+00:00')
        self.assertEqual(self.client.post('/api/sos/relay', json=expired).status_code, 410)

        over_hop = dict(packet, hop_count=5, max_hops=3)
        self.assertEqual(self.client.post('/api/sos/relay', json=over_hop).status_code, 422)


if __name__ == '__main__':
    unittest.main(verbosity=2)
