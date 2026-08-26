"""Backend tests for /api/dashboard/summary (Iteration 2 - Command Center)."""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gov-client-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password="Demo@2026"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_token():
    return _login("gov.admin@neris.demo")


@pytest.fixture(scope="module")
def logistics_token():
    return _login("logistics@neris.demo")


def test_dashboard_requires_auth():
    r = requests.get(f"{API}/dashboard/summary", timeout=30)
    assert r.status_code == 401


def test_dashboard_gov_admin_shape(gov_token):
    r = requests.get(f"{API}/dashboard/summary", headers={"Authorization": f"Bearer {gov_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["provenance"] == "DEMO"
    # kpis
    kpis = d["kpis"]
    assert set(kpis.keys()) == {
        "active_vehicles", "at_risk_corridors", "blocked_roads",
        "critical_alerts", "villages_isolation_risk", "critical_supply_locations",
    }
    # roads
    roads = d["roads"]
    assert roads["type"] == "FeatureCollection"
    assert len(roads["features"]) == 10
    for f in roads["features"]:
        assert f["geometry"]["type"] == "LineString"
        assert "status" in f["properties"]
    # incidents
    incidents = d["incidents"]
    assert len(incidents) == 8
    for i in incidents:
        assert "created_at" in i
        # ISO format parseable
        datetime.fromisoformat(i["created_at"])
    # vehicles
    assert len(d["vehicles"]) == 12
    # supply
    assert len(d["supply"]) == 4


def test_dashboard_kpi_values(gov_token):
    r = requests.get(f"{API}/dashboard/summary", headers={"Authorization": f"Bearer {gov_token}"}, timeout=30)
    kpis = r.json()["kpis"]
    assert kpis["blocked_roads"] == 2
    assert kpis["critical_alerts"] == 4
    assert kpis["active_vehicles"] == 11
    assert kpis["at_risk_corridors"] == 3
    assert kpis["villages_isolation_risk"] == 4
    assert kpis["critical_supply_locations"] == 7


def test_dashboard_logistics_can_read(logistics_token):
    r = requests.get(f"{API}/dashboard/summary", headers={"Authorization": f"Bearer {logistics_token}"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["provenance"] == "DEMO"
