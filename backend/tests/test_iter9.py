"""Iteration 9 — refactor regression + WS + fleet map role gating"""
import os
import json
import time
import asyncio
import pytest
import requests
import websockets

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"

CREDS = {
    "gov": ("gov.admin@neris.demo", "Demo@2026"),
    "field": ("field@neris.demo", "Demo@2026"),
    "logistics": ("logistics@neris.demo", "Demo@2026"),
    "driver": ("driver@neris.demo", "Demo@2026"),
    "public": ("public@neris.demo", "Demo@2026"),
    "owner": ("aiagency865@gmail.com", "Admin@2026"),
}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(e, p) for k, (e, p) in CREDS.items()}


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ---- All 6 accounts login ----
def test_all_accounts_login(tokens):
    assert len(tokens) == 6
    for k, t in tokens.items():
        assert t, f"missing token for {k}"


# ---- Dashboard shape ----
def test_dashboard_summary(tokens):
    r = requests.get(f"{BASE_URL}/api/dashboard/summary", headers=_h(tokens["gov"]))
    assert r.status_code == 200
    d = r.json()
    for key in ["kpis", "vehicles", "roads", "incidents"]:
        assert key in d, f"missing {key} in dashboard summary"
    assert isinstance(d["kpis"], dict)


# ---- Road status (gov 200, logistics 403) ----
def test_road_status_rbac(tokens):
    r = requests.patch(f"{BASE_URL}/api/roads/rd-nh17/status",
                       headers=_h(tokens["logistics"]),
                       json={"status": "BLOCKED", "reason": "TEST_iter9"})
    assert r.status_code == 403
    r = requests.patch(f"{BASE_URL}/api/roads/rd-nh17/status",
                       headers=_h(tokens["gov"]),
                       json={"status": "BLOCKED", "reason": "TEST_iter9"})
    assert r.status_code == 200
    # restore
    requests.patch(f"{BASE_URL}/api/roads/rd-nh17/status",
                   headers=_h(tokens["gov"]),
                   json={"status": "OPEN", "reason": "TEST_iter9 restore"})


# ---- Audit gov ----
def test_audit(tokens):
    r = requests.get(f"{BASE_URL}/api/audit", headers=_h(tokens["gov"]))
    assert r.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/audit", headers=_h(tokens["logistics"]))
    assert r2.status_code == 403


# ---- Vehicles CRUD + rbac ----
def test_vehicles_rbac(tokens):
    r = requests.get(f"{BASE_URL}/api/vehicles", headers=_h(tokens["gov"]))
    assert r.status_code == 200
    payload = {"number": "TEST9-01", "type": "TRUCK", "lat": 26.15, "lng": 91.74, "commodity": "FOOD"}
    r_pub = requests.post(f"{BASE_URL}/api/vehicles", headers=_h(tokens["public"]), json=payload)
    assert r_pub.status_code == 403
    r_field = requests.post(f"{BASE_URL}/api/vehicles", headers=_h(tokens["field"]), json=payload)
    assert r_field.status_code in (200, 201), r_field.text


# ---- Predictions ----
def test_predictions(tokens):
    for h in ["flood", "landslide"]:
        r = requests.get(f"{BASE_URL}/api/predictions/{h}", headers=_h(tokens["gov"]))
        assert r.status_code == 200
    r = requests.post(f"{BASE_URL}/api/ml/flood/predict", headers=_h(tokens["gov"]),
                      json={"rainfall_mm": 200, "river_level_m": 4.5, "soil_saturation": 0.7})
    assert r.status_code == 200, r.text
    assert "probability" in r.json() or "risk_level" in r.json()


# ---- Routing ----
def test_routing(tokens):
    r = requests.post(f"{BASE_URL}/api/routes/calculate", headers=_h(tokens["gov"]),
                      json={"origin": "guwahati", "destination": "tezpur", "vehicle_type": "TRUCK"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("provenance"), "route response missing provenance"
    assert "origin" in d and "destination" in d


# ---- Notifications ----
def test_notifications_rbac(tokens):
    body = {"title": "TEST_iter9", "message": "iter9 notice broadcast", "severity": "INFO"}
    r = requests.post(f"{BASE_URL}/api/notifications", headers=_h(tokens["public"]), json=body)
    assert r.status_code == 403
    r = requests.post(f"{BASE_URL}/api/notifications", headers=_h(tokens["gov"]), json=body)
    assert r.status_code == 201, r.text
    r = requests.get(f"{BASE_URL}/api/notifications", headers=_h(tokens["gov"]))
    assert r.status_code == 200


# ---- Trips ----
def test_trips_rbac(tokens):
    r = requests.get(f"{BASE_URL}/api/trips/summary", headers=_h(tokens["gov"]))
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/trips/summary", headers=_h(tokens["logistics"]))
    assert r.status_code == 403
    r = requests.get(f"{BASE_URL}/api/trips", headers=_h(tokens["field"]))
    assert r.status_code == 200


# ---- Escalations ----
def test_escalations_rbac(tokens):
    r = requests.get(f"{BASE_URL}/api/ai/escalations", headers=_h(tokens["gov"]))
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/ai/escalations", headers=_h(tokens["public"]))
    assert r.status_code == 403


# ---- Feeds ----
def test_feeds(tokens):
    for path in ["/api/alerts", "/api/public/advisories", "/api/accidents", "/api/environment"]:
        r = requests.get(f"{BASE_URL}{path}", headers=_h(tokens["gov"]))
        assert r.status_code == 200, f"{path}: {r.status_code}"


# ---- WS after refactor ----
@pytest.mark.asyncio
async def test_ws_road_status_broadcast(tokens):
    gov = tokens["gov"]
    driver = tokens["driver"]
    uri = f"{WS_URL}?token={driver}"
    async with websockets.connect(uri, open_timeout=10) as ws:
        # trigger PATCH from gov (via requests, sync)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.patch(
            f"{BASE_URL}/api/roads/rd-nh17/status",
            headers=_h(gov),
            json={"status": "BLOCKED", "reason": "TEST_iter9 ws"},
        ))
        got = False
        try:
            for _ in range(10):
                msg = await asyncio.wait_for(ws.recv(), timeout=6)
                data = json.loads(msg)
                ev = data.get("event") or data.get("type")
                if ev == "ROAD_STATUS_CHANGED":
                    got = True
                    break
        finally:
            # restore
            requests.patch(f"{BASE_URL}/api/roads/rd-nh17/status",
                           headers=_h(gov),
                           json={"status": "OPEN", "reason": "TEST_iter9 ws restore"})
        assert got, "did not receive ROAD_STATUS_CHANGED via WS"
