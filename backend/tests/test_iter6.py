"""
Iteration 6 tests — Routing bugfix (local connectors, A/B pins, blocked handling)
                    + Public report tokens (+10) / 24h ban flow.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

GOV = ("gov.admin@neris.demo", "Demo@2026")
FIELD = ("field@neris.demo", "Demo@2026")
LOGISTICS = ("logistics@neris.demo", "Demo@2026")
PUBLIC = ("public@neris.demo", "Demo@2026")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- Routing bugfix ----------------

@pytest.mark.parametrize("origin,destination", [
    ("guwahati", "silchar"),
    ("imphal", "agartala"),
    ("pasighat", "aizawl"),
])
def test_routes_calculate_pairs(origin, destination):
    tok = _login(*LOGISTICS)
    r = requests.post(f"{API}/routes/calculate",
                      json={"origin": origin, "destination": destination, "vehicle_type": "TRUCK"},
                      headers=_h(tok), timeout=20)
    assert r.status_code == 200, f"{origin}->{destination}: {r.status_code} {r.text}"
    data = r.json()
    assert "recommended_route" in data
    rr = data["recommended_route"]
    assert rr["distance_km"] > 0
    assert rr["eta_minutes"] > 0
    assert isinstance(rr["segments"], list) and len(rr["segments"]) >= 1


def test_routes_unknown_place_returns_400():
    tok = _login(*LOGISTICS)
    r = requests.post(f"{API}/routes/calculate",
                      json={"origin": "atlantis", "destination": "silchar"},
                      headers=_h(tok), timeout=15)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "guwahati" in detail.lower()


def test_routes_blocked_never_in_open_segments():
    """guwahati->shillong: if the recommended route contains blocked road, contains_blocked must be True."""
    tok = _login(*LOGISTICS)
    r = requests.post(f"{API}/routes/calculate",
                      json={"origin": "guwahati", "destination": "shillong", "vehicle_type": "TRUCK"},
                      headers=_h(tok), timeout=15)
    assert r.status_code == 200
    rr = r.json()["recommended_route"]
    has_blocked = any(s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED") for s in rr["segments"])
    if has_blocked:
        assert rr["contains_blocked"] is True


# ---------------- Public report token & ban flow ----------------

def _reset_public_user():
    import pymongo
    c = pymongo.MongoClient("mongodb://localhost:27017")
    db = c[os.environ.get("DB_NAME", "test_database")]
    db.users.update_one({"email": "public@neris.demo"},
                        {"$unset": {"report_ban_until": ""}, "$set": {"tokens": 0}})
    c.close()


@pytest.fixture
def clean_public():
    _reset_public_user()
    yield
    _reset_public_user()


def test_token_award_on_verify(clean_public):
    ptok = _login(*PUBLIC)
    me = requests.get(f"{API}/auth/me", headers=_h(ptok), timeout=10).json()
    baseline = me.get("tokens", 0) or 0

    r = requests.post(f"{API}/public/reports",
                      json={"type": "ROAD_DAMAGE", "description": "TEST_iter6 pothole",
                            "lat": 26.14, "lng": 91.73, "severity": "INFO"},
                      headers=_h(ptok), timeout=15)
    assert r.status_code == 201, r.text
    pr_id = r.json()["id"]

    gtok = _login(*GOV)
    incs = requests.get(f"{API}/dashboard/summary", headers=_h(gtok), timeout=15).json()["incidents"]
    inc = next((i for i in incs if i.get("public_report_id") == pr_id), None)
    assert inc is not None, "no incident created from public report"

    vr = requests.patch(f"{API}/incidents/{inc['id']}/verify", headers=_h(gtok), timeout=15)
    assert vr.status_code == 200, vr.text

    me2 = requests.get(f"{API}/auth/me", headers=_h(ptok), timeout=10).json()
    assert me2.get("tokens", 0) == baseline + 10


def test_field_officer_can_verify_public_report(clean_public):
    ptok = _login(*PUBLIC)
    r = requests.post(f"{API}/public/reports",
                      json={"type": "FLOOD", "description": "TEST_iter6 field verify",
                            "lat": 26.2, "lng": 91.7, "severity": "WARNING"},
                      headers=_h(ptok), timeout=15)
    assert r.status_code == 201, r.text
    pr_id = r.json()["id"]

    gtok = _login(*GOV)
    incs = requests.get(f"{API}/dashboard/summary", headers=_h(gtok), timeout=15).json()["incidents"]
    inc = next((i for i in incs if i.get("public_report_id") == pr_id), None)
    assert inc is not None

    ftok = _login(*FIELD)
    vr = requests.patch(f"{API}/incidents/{inc['id']}/verify", headers=_h(ftok), timeout=15)
    assert vr.status_code == 200, vr.text


def test_ban_flow_on_reject(clean_public):
    ptok = _login(*PUBLIC)
    r = requests.post(f"{API}/public/reports",
                      json={"type": "ACCIDENT", "description": "TEST_iter6 will be rejected",
                            "lat": 26.1, "lng": 91.7, "severity": "INFO"},
                      headers=_h(ptok), timeout=15)
    assert r.status_code == 201, r.text
    pr_id = r.json()["id"]

    gtok = _login(*GOV)
    incs = requests.get(f"{API}/dashboard/summary", headers=_h(gtok), timeout=15).json()["incidents"]
    inc = next((i for i in incs if i.get("public_report_id") == pr_id), None)
    assert inc is not None

    rj = requests.patch(f"{API}/incidents/{inc['id']}/reject", headers=_h(gtok), timeout=15)
    assert rj.status_code == 200, rj.text

    r2 = requests.post(f"{API}/public/reports",
                       json={"type": "ROAD_DAMAGE", "description": "TEST_iter6 blocked after ban",
                             "lat": 26.1, "lng": 91.7, "severity": "INFO"},
                       headers=_h(ptok), timeout=15)
    assert r2.status_code == 403, f"expected 403 got {r2.status_code} {r2.text}"
    assert "suspend" in r2.json().get("detail", "").lower()

    me = requests.get(f"{API}/auth/me", headers=_h(ptok), timeout=10).json()
    assert me.get("report_ban_until"), "report_ban_until should be set"
