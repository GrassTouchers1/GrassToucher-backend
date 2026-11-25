import base64
import hashlib
import json
import time
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from fastapi.testclient import TestClient

from app.main import app


def _int_to_b64url(val: int) -> str:
    b = val.to_bytes(32, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _build_signed_relay_packet(client_event_id: str, hop_count: int = 1, max_hops: int = 5, expired: bool = False):
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_nums = priv.public_key().public_numbers()
    pub_jwk = {"kty": "EC", "crv": "P-256", "x": _int_to_b64url(pub_nums.x), "y": _int_to_b64url(pub_nums.y)}
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=48)
    packet = {
        "schema": "northstar.sos.relay.v1",
        "message_id": f"msg-{client_event_id}",
        "client_event_id": client_event_id,
        "origin_device_id": "dev-origin-01",
        "created_at": now.isoformat(),
        "expires_at": exp.isoformat(),
        "location": {"lat": 21.0285, "lng": 105.8542, "location_description": "Hoan Kiem", "location_landmark": None},
        "location_source": "gps",
        "payload": {
            "people_count": 3,
            "has_elderly_or_children": True,
            "water_level_cm": 150,
            "priority": "critical",
            "notes": "Test relay unit",
            "contact_phone_masked": "***5678",
        },
        "hop_count": hop_count,
        "max_hops": max_hops,
        "relay_history": [{"relayer_device_id": "relay-B", "hop": hop_count}],
    }
    core_obj = {
        "message_id": packet["message_id"],
        "client_event_id": packet["client_event_id"],
        "origin_device_id": packet["origin_device_id"],
        "created_at": packet["created_at"],
        "expires_at": packet["expires_at"],
        "location": packet["location"],
        "location_source": packet["location_source"],
        "payload": packet["payload"],
    }
    content_hash = hashlib.sha256(
        json.dumps(core_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    der_sig = priv.sign(content_hash.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    r_int, s_int = decode_dss_signature(der_sig)
    raw_sig = r_int.to_bytes(32, "big") + s_int.to_bytes(32, "big")
    packet["integrity_metadata"] = {"algorithm": "SHA-256", "content_hash": content_hash}
    packet["authentication_metadata"] = {
        "scheme": "ECDSA-P256",
        "public_key_jwk": pub_jwk,
        "signature": base64.b64encode(raw_sig).decode("ascii"),
    }
    return packet


class TestPhase12RelayAndGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_valid_relay_packet_returns_201_and_metadata(self):
        evt = f"p12-relay-ok-{int(time.time() * 1000)}"
        pkt = _build_signed_relay_packet(evt, hop_count=1, max_hops=5)
        res = self.client.post("/api/sos/relay", json=pkt)
        self.assertEqual(res.status_code, 201, res.text)
        props = res.json()["properties"]
        self.assertEqual(props["ingest_channel"], "dtn_relay")
        self.assertEqual(props["hop_count"], 1)
        self.assertTrue(props["signature_verified"])

    def test_02_tampered_payload_rejected_422(self):
        evt = f"p12-relay-tamper-{int(time.time() * 1000)}"
        pkt = _build_signed_relay_packet(evt)
        pkt["payload"]["notes"] = "Tampered!"
        res = self.client.post("/api/sos/relay", json=pkt)
        self.assertIn(res.status_code, (400, 422))

    def test_03_duplicate_client_event_id_deduplicated(self):
        evt = f"p12-relay-dup-{int(time.time() * 1000)}"
        pkt1 = _build_signed_relay_packet(evt, hop_count=1)
        pkt2 = dict(pkt1)
        pkt2["relay_history"] = [{"relayer_device_id": "relay-C", "hop": 2}]
        r1 = self.client.post("/api/sos/relay", json=pkt1)
        r2 = self.client.post("/api/sos/relay", json=pkt2)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.json()["properties"]["id"], r2.json()["properties"]["id"])
        self.assertTrue(r2.json()["properties"]["deduplicated"])

    def test_04_exceeded_max_hops_or_expired_rejected(self):
        evt1 = f"p12-relay-hops-{int(time.time() * 1000)}"
        pkt_hops = _build_signed_relay_packet(evt1, hop_count=6, max_hops=5)
        r_hops = self.client.post("/api/sos/relay", json=pkt_hops)
        self.assertIn(r_hops.status_code, (400, 422))

        evt2 = f"p12-relay-exp-{int(time.time() * 1000)}"
        pkt_exp = _build_signed_relay_packet(evt2, expired=True)
        r_exp = self.client.post("/api/sos/relay", json=pkt_exp)
        self.assertEqual(r_exp.status_code, 410)

    def test_05_gateway_inbound_compact_frame_and_sms(self):
        body = "NS1|21.0285,105.8542|4|220|C|AB12CD34"
        crc = 0
        for ch in body:
            crc = (crc ^ ord(ch)) & 0xFF
        frame = f"{body}|{crc:02X}"
        res = self.client.post(
            "/api/sos/gateway/inbound",
            json={"compact_frame": frame, "simulated": True, "client_event_id": f"gw-sim-{int(time.time() * 1000)}"},
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertEqual(data["geometry"]["coordinates"], [105.8542, 21.0285])
        self.assertEqual(data["properties"]["people_count"], 4)
        self.assertEqual(data["properties"]["water_level_cm"], 220.0)
        self.assertEqual(data["properties"]["priority"], "critical")
        self.assertEqual(data["properties"]["ingest_channel"], "satellite_simulated")


if __name__ == "__main__":
    unittest.main()
