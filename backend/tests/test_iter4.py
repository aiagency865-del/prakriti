"""Backend tests for Iteration 4 — Field report → Alerts → Public advisories propagation + role pages."""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password="Demo@2026"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_token():
    return _login("gov.admin@neris.demo")


@pytest.fixture(scope="module")
def logistics_token():
    return _login("logistics@neris.demo")


@pytest.fixture(scope="module")
def field_token():
    return _login("field@neris.demo")


@pytest.fixture(scope="module")
def public_token():
    return _login("public@neris.demo")


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- Alerts feed ---
class TestAlerts:
    def test_alerts_gov(self, gov_token):
        r = requests.get(f"{API}/alerts", headers=h(gov_token))
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        kinds = {a.get("kind") for a in d}
        assert kinds.issubset({"INCIDENT", "FIELD_REPORT", "GOVERNMENT_ACTION"})
        # verify all three kinds exist in seeded data
        assert "INCIDENT" in kinds
        assert "GOVERNMENT_ACTION" in kinds

    def test_alerts_logistics(self, logistics_token):
        r = requests.get(f"{API}/alerts", headers=h(logistics_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --- Public advisories ---
class TestPublicAdvisories:
    def test_public_advisories_shape(self, public_token):
        r = requests.get(f"{API}/public/advisories", headers=h(public_token))
        assert r.status_code == 200
        d = r.json()
        assert "road_advisories" in d
        assert "verified_incidents" in d
        assert "verified_field_reports" in d
        # advisories are only non-OPEN roads
        for road in d["road_advisories"]:
            assert road["status"] != "OPEN"
        # only VERIFIED incidents should appear in public
        for inc in d["verified_incidents"]:
            assert inc.get("status") == "VERIFIED"


# --- Deliveries (logistics) ---
class TestDeliveries:
    def test_list_deliveries_logistics(self, logistics_token):
        r = requests.get(f"{API}/deliveries", headers=h(logistics_token))
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        assert len(d) >= 8


# --- Full propagation flow ---
class TestPropagation:
    def test_field_report_alerts_verify_public(
        self, field_token, logistics_token, public_token, gov_token
    ):
        # 1) create field report
        payload = {
            "type": "BLOCKAGE",
            "road_id": "rd-nh27",
            "severity": "WARNING",
            "description": "TEST_iter4 propagation report - please verify",
            "lat": 26.1,
            "lng": 91.7,
        }
        r = requests.post(f"{API}/field/reports", headers=h(field_token), json=payload)
        assert r.status_code == 201, r.text
        rep = r.json()
        rep_id = rep["id"]
        assert rep_id.startswith("FR-")
        assert rep["status"] == "SUBMITTED"

        # 2) logistics sees it in alerts as FIELD_REPORT
        time.sleep(0.5)
        alerts = requests.get(f"{API}/alerts", headers=h(logistics_token)).json()
        fr_alerts = [a for a in alerts if a.get("kind") == "FIELD_REPORT" and a.get("id") == rep_id]
        assert len(fr_alerts) >= 1, "logistics should see new FIELD_REPORT in alerts"

        # 3) public advisories should NOT contain unverified field report
        pub = requests.get(f"{API}/public/advisories", headers=h(public_token)).json()
        pub_fr_ids = [f.get("id") for f in pub["verified_field_reports"]]
        assert rep_id not in pub_fr_ids, "unverified field-report leaked to public"

        # 4) find the auto-created incident and verify it
        summary = requests.get(f"{API}/dashboard/summary", headers=h(gov_token)).json()
        candidate = None
        for i in summary["incidents"]:
            if i.get("field_report_id") == rep_id:
                candidate = i
                break
        assert candidate, "no incident auto-created from field report"
        assert candidate["status"] == "UNVERIFIED"
        inc_id = candidate["id"]

        vr = requests.patch(f"{API}/incidents/{inc_id}/verify", headers=h(gov_token))
        assert vr.status_code == 200, vr.text
        assert vr.json()["status"] == "VERIFIED"

        # 5) public advisories should now contain the verified field report + incident
        time.sleep(0.5)
        pub2 = requests.get(f"{API}/public/advisories", headers=h(public_token)).json()
        pub2_fr_ids = [f.get("id") for f in pub2["verified_field_reports"]]
        pub2_inc_ids = [i.get("id") for i in pub2["verified_incidents"]]
        assert rep_id in pub2_fr_ids, "verified field report should appear in public advisories"
        assert inc_id in pub2_inc_ids, "verified incident should appear in public advisories"

        # 6) A GOVERNMENT_ACTION alert should be logged for the verify
        alerts2 = requests.get(f"{API}/alerts", headers=h(gov_token)).json()
        gov_actions = [a for a in alerts2 if a.get("kind") == "GOVERNMENT_ACTION"]
        assert any(inc_id in (a.get("title") or "") or "VERIFIED" in (a.get("title") or "")
                   for a in gov_actions)
