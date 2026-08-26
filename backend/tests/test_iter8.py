"""Iteration 8: driver-in-logistics, trips summary live location gating, AI escalation flow, auto-block sweep."""
import os
import time
from datetime import datetime, timezone, timedelta
import uuid

import pytest
import requests
import pymongo

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

CREDS = {
    "gov": ("gov.admin@neris.demo", "Demo@2026"),
    "field": ("field@neris.demo", "Demo@2026"),
    "logistics": ("logistics@neris.demo", "Demo@2026"),
    "driver": ("driver@neris.demo", "Demo@2026"),
    "public": ("public@neris.demo", "Demo@2026"),
}


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login {email} => {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- Driver login role check ---
def test_driver_role_is_driver(tokens):
    r = requests.get(f"{BASE}/auth/me", headers=H(tokens["driver"]))
    assert r.status_code == 200
    assert r.json()["role"] == "DRIVER"


# --- Trip start / list ---
@pytest.fixture(scope="module")
def driver_trip(tokens):
    r = requests.post(f"{BASE}/trips", headers=H(tokens["driver"]),
                      json={"origin": "guwahati", "destination": "jorhat", "vehicle_type": "TRUCK"})
    assert r.status_code == 201, r.text
    return r.json()


def test_trip_created_active(driver_trip):
    assert driver_trip["status"] == "ACTIVE"
    assert driver_trip["origin"] == "guwahati"


def test_trips_list_driver_shows_own(tokens, driver_trip):
    r = requests.get(f"{BASE}/trips", headers=H(tokens["driver"]))
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert driver_trip["id"] in ids


# --- Trips summary role gating ---
def test_trips_summary_gov(tokens, driver_trip):
    r = requests.get(f"{BASE}/trips/summary", headers=H(tokens["gov"]))
    assert r.status_code == 200
    d = r.json()
    assert "active_count" in d and "by_road" in d and "trips" in d
    trip = next((t for t in d["trips"] if t["id"] == driver_trip["id"]), None)
    assert trip is not None
    assert "current_lat" in trip and "current_lng" in trip and "progress" in trip


def test_trips_summary_field(tokens):
    r = requests.get(f"{BASE}/trips/summary", headers=H(tokens["field"]))
    assert r.status_code == 200


def test_trips_summary_logistics_403(tokens):
    r = requests.get(f"{BASE}/trips/summary", headers=H(tokens["logistics"]))
    assert r.status_code == 403


def test_trips_summary_public_403(tokens):
    r = requests.get(f"{BASE}/trips/summary", headers=H(tokens["public"]))
    assert r.status_code == 403


# --- AI escalations listing ---
def test_ai_escalations_gov_creates_sh9(tokens):
    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["gov"]))
    assert r.status_code == 200
    d = r.json()
    assert d["threshold"] == 0.75
    # SH-9 escalation should be present (either PENDING or from before)
    escs = d["escalations"]
    sh9_pending = [e for e in escs if e["road_id"] == "rd-sh9" and e["status"] == "PENDING"]
    assert sh9_pending, f"no PENDING escalation for rd-sh9. escalations={escs}"


def test_ai_escalations_logistics_403(tokens):
    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["logistics"]))
    assert r.status_code == 403


def test_ai_escalations_public_403(tokens):
    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["public"]))
    assert r.status_code == 403


def test_ack_public_403(tokens):
    r = requests.post(f"{BASE}/ai/escalations/ESC-XXXXXX/ack", headers=H(tokens["public"]),
                      json={"action": "MONITOR"})
    assert r.status_code == 403


# --- MONITOR ack keeps road unblocked ---
def test_monitor_ack_does_not_block(tokens):
    # Ensure SH-9 is unblocked first
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    db.roads.update_one({"id": "rd-sh9"}, {"$set": {"status": "AT_RISK", "status_reason": "test setup"}})
    db.ai_escalations.delete_many({"road_id": "rd-sh9"})

    # trigger recreation
    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["gov"]))
    escs = r.json()["escalations"]
    pending = [e for e in escs if e["road_id"] == "rd-sh9" and e["status"] == "PENDING"]
    assert pending
    esc_id = pending[0]["id"]

    r2 = requests.post(f"{BASE}/ai/escalations/{esc_id}/ack", headers=H(tokens["gov"]),
                       json={"action": "MONITOR"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "ACKED"

    road = db.roads.find_one({"id": "rd-sh9"}, {"_id": 0})
    assert road["status"] != "BLOCKED"


# --- BLOCK_NOW ack blocks road ---
def test_block_now_ack_blocks_road(tokens):
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    # Reset road + clear escalations to force a fresh PENDING
    db.roads.update_one({"id": "rd-sh9"}, {"$set": {"status": "AT_RISK", "status_reason": "test setup"}})
    db.ai_escalations.delete_many({"road_id": "rd-sh9"})

    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["gov"]))
    escs = r.json()["escalations"]
    pending = [e for e in escs if e["road_id"] == "rd-sh9" and e["status"] == "PENDING"]
    assert pending
    esc_id = pending[0]["id"]

    r2 = requests.post(f"{BASE}/ai/escalations/{esc_id}/ack", headers=H(tokens["gov"]),
                       json={"action": "BLOCK_NOW"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "BLOCKED_MANUAL"

    road = db.roads.find_one({"id": "rd-sh9"}, {"_id": 0})
    assert road["status"] == "BLOCKED"

    # restore
    requests.patch(f"{BASE}/roads/rd-sh9/status", headers=H(tokens["gov"]),
                   json={"status": "AT_RISK", "reason": "test cleanup"})


# --- Auto-block sweep via backdated deadline ---
def test_auto_block_sweep(tokens):
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    # reset
    db.roads.update_one({"id": "rd-sh9"}, {"$set": {"status": "AT_RISK", "status_reason": "test setup"}})
    db.ai_escalations.delete_many({"road_id": "rd-sh9"})

    # insert backdated PENDING escalation
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    esc = {
        "id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
        "road_id": "rd-sh9", "road_name": "SH-9 Silchar-Aizawl",
        "hazard": "FLOOD", "probability": 0.78, "status": "PENDING",
        "created_at": (past - timedelta(minutes=5)).isoformat(),
        "deadline_at": past.isoformat(),
    }
    db.ai_escalations.insert_one(dict(esc))

    # trigger sweep
    r = requests.get(f"{BASE}/ai/escalations", headers=H(tokens["gov"]))
    assert r.status_code == 200

    updated = db.ai_escalations.find_one({"id": esc["id"]}, {"_id": 0})
    assert updated["status"] == "AUTO_BLOCKED", f"got {updated}"

    road = db.roads.find_one({"id": "rd-sh9"}, {"_id": 0})
    assert road["status"] == "BLOCKED"
    assert "Auto-blocked" in (road.get("status_reason") or "")

    # RESTORE
    rp = requests.patch(f"{BASE}/roads/rd-sh9/status", headers=H(tokens["gov"]),
                        json={"status": "AT_RISK", "reason": "test cleanup"})
    assert rp.status_code == 200, rp.text


# --- End trip cleanup ---
def test_end_trip(tokens, driver_trip):
    r = requests.patch(f"{BASE}/trips/{driver_trip['id']}/end", headers=H(tokens["driver"]))
    assert r.status_code == 200
    assert r.json()["status"] == "ENDED"
