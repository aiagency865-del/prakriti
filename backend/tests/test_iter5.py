"""Iteration 5 backend tests — Public reports, notifications, emergency zones, verification pipeline."""
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
def gov_token(): return _login("gov.admin@neris.demo")
@pytest.fixture(scope="module")
def field_token(): return _login("field@neris.demo")
@pytest.fixture(scope="module")
def logistics_token(): return _login("logistics@neris.demo")
@pytest.fixture(scope="module")
def public_token(): return _login("public@neris.demo")


def h(tok): return {"Authorization": f"Bearer {tok}"}


PR_PAYLOAD = {
    "type": "ROAD_DAMAGE",
    "description": "TEST_iter5 pothole causing traffic delays near market",
    "road_id": "rd-nh27",
    "lat": 26.15,
    "lng": 91.75,
    "severity": "WARNING",
}


# --- Public report creation + pipeline ---
class TestPublicReportPipeline:
    def test_public_creates_report(self, public_token, gov_token, logistics_token, field_token):
        r = requests.post(f"{API}/public/reports", headers=h(public_token), json=PR_PAYLOAD)
        assert r.status_code == 201, r.text
        rep = r.json()
        assert rep["status"] == "PENDING"
        assert rep["id"].startswith("PR-")
        assert rep["source"] == "PUBLIC"
        pr_id = rep["id"]

        # Public + logistics MUST NOT see this pending report in alerts
        time.sleep(0.4)
        pub_alerts = requests.get(f"{API}/alerts", headers=h(public_token)).json()
        assert not any(a.get("id") == pr_id for a in pub_alerts), "public sees own pending report before verification"

        log_alerts = requests.get(f"{API}/alerts", headers=h(logistics_token)).json()
        assert not any(a.get("id") == pr_id for a in log_alerts), "logistics sees unverified public report"

        # Gov and field SHOULD see it
        gov_alerts = requests.get(f"{API}/alerts", headers=h(gov_token)).json()
        assert any(a.get("id") == pr_id and a.get("kind") == "PUBLIC_REPORT" for a in gov_alerts)

        field_alerts = requests.get(f"{API}/alerts", headers=h(field_token)).json()
        assert any(a.get("id") == pr_id and a.get("kind") == "PUBLIC_REPORT" for a in field_alerts)

        # Find auto-created incident linked to this public report
        gov_incidents = [a for a in gov_alerts if a.get("kind") == "INCIDENT"]
        # Fetch incidents through dashboard/summary because alerts don't include public_report_id
        summary = requests.get(f"{API}/dashboard/summary", headers=h(gov_token)).json()
        incident = next((i for i in summary["incidents"] if i.get("public_report_id") == pr_id), None)
        assert incident is not None, "no incident auto-created from public report"
        assert incident["status"] == "UNVERIFIED"
        assert incident["source"] == "PUBLIC"
        inc_id = incident["id"]

        # RBAC: logistics/public cannot verify
        assert requests.patch(f"{API}/incidents/{inc_id}/verify", headers=h(logistics_token)).status_code == 403
        assert requests.patch(f"{API}/incidents/{inc_id}/verify", headers=h(public_token)).status_code == 403

        # Field officer CAN verify
        vr = requests.patch(f"{API}/incidents/{inc_id}/verify", headers=h(field_token))
        assert vr.status_code == 200, vr.text
        assert vr.json()["status"] == "VERIFIED"

        # Now public + logistics should see the verified public report
        time.sleep(0.4)
        pub_alerts2 = requests.get(f"{API}/alerts", headers=h(public_token)).json()
        assert any(a.get("id") == pr_id for a in pub_alerts2), "verified public report not visible to public"
        log_alerts2 = requests.get(f"{API}/alerts", headers=h(logistics_token)).json()
        assert any(a.get("id") == pr_id for a in log_alerts2), "verified public report not visible to logistics"


# --- Notifications ---
class TestNotifications:
    def test_broadcast_and_rbac(self, gov_token, public_token, logistics_token, field_token):
        # Non-gov cannot broadcast (use valid payload to isolate RBAC from validation)
        payload = {"title": "TEST_iter5 broadcast", "message": "Please avoid NH-6 tonight", "severity": "WARNING"}
        assert requests.post(f"{API}/notifications", headers=h(public_token), json=payload).status_code == 403
        assert requests.post(f"{API}/notifications", headers=h(logistics_token), json=payload).status_code == 403

        # Gov can
        r = requests.post(f"{API}/notifications", headers=h(gov_token), json=payload)
        assert r.status_code == 201, r.text
        n = r.json()
        assert n["id"].startswith("NT-")
        nid = n["id"]

        # All roles can list
        for tok in (gov_token, logistics_token, field_token, public_token):
            lst = requests.get(f"{API}/notifications", headers=h(tok)).json()
            assert any(x["id"] == nid for x in lst)

        # Notification appears in alerts feed for all roles as NOTIFICATION kind
        for tok in (gov_token, logistics_token, field_token, public_token):
            alerts = requests.get(f"{API}/alerts", headers=h(tok)).json()
            assert any(a.get("id") == nid and a.get("kind") == "NOTIFICATION" for a in alerts)


# --- Emergency zones ---
class TestEmergencyZones:
    def test_create_and_rbac_and_audit(self, gov_token, field_token, public_token, logistics_token):
        payload = {
            "name": "TEST_iter5 zone",
            "lat": 26.10, "lng": 91.60,
            "radius_km": 5.5,
            "message": "TEST_iter5 emergency zone created for testing",
        }
        # Non-gov forbidden (valid payload)
        assert requests.post(f"{API}/emergency-zones", headers=h(field_token), json=payload).status_code == 403
        assert requests.post(f"{API}/emergency-zones", headers=h(logistics_token), json=payload).status_code == 403
        assert requests.post(f"{API}/emergency-zones", headers=h(public_token), json=payload).status_code == 403

        # Gov creates
        r = requests.post(f"{API}/emergency-zones", headers=h(gov_token), json=payload)
        assert r.status_code == 201, r.text
        z = r.json()
        assert z["radius_km"] == 5.5
        assert z["active"] is True
        zid = z["id"]

        # All roles can list
        for tok in (gov_token, logistics_token, field_token, public_token):
            lst = requests.get(f"{API}/emergency-zones", headers=h(tok)).json()
            assert any(x["id"] == zid for x in lst)

        # Audit log has EMERGENCY_DECLARED
        audit = requests.get(f"{API}/audit", headers=h(gov_token)).json()
        assert any(a.get("action_type") == "EMERGENCY_DECLARED" and a.get("target_id") == zid for a in audit)

        # Alerts feed contains EMERGENCY kind
        alerts = requests.get(f"{API}/alerts", headers=h(public_token)).json()
        assert any(a.get("id") == zid and a.get("kind") == "EMERGENCY" for a in alerts)


# --- Alert kinds present in feed ---
class TestAlertKinds:
    def test_all_kinds_visible_to_gov(self, gov_token):
        alerts = requests.get(f"{API}/alerts", headers=h(gov_token)).json()
        kinds = {a.get("kind") for a in alerts}
        # After previous tests ran, we should have most kinds
        expected = {"INCIDENT", "FIELD_REPORT", "NOTIFICATION", "EMERGENCY", "GOVERNMENT_ACTION"}
        missing = expected - kinds
        assert not missing, f"missing kinds in gov alerts: {missing}. Got: {kinds}"
