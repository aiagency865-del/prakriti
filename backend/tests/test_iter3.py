"""Backend tests for Iteration 3 — Road control + Audit + Vehicles + Hazard ML."""
import os
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


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- Road status PATCH ---
class TestRoadControl:
    def test_patch_unauth(self):
        r = requests.patch(f"{API}/roads/rd-nh17/status",
                           json={"status": "RESTRICTED", "reason": "unauth"})
        assert r.status_code == 401

    def test_patch_forbidden_logistics(self, logistics_token):
        r = requests.patch(f"{API}/roads/rd-nh17/status",
                           headers=h(logistics_token),
                           json={"status": "RESTRICTED", "reason": "test"})
        assert r.status_code == 403
        assert "permission" in r.json().get("detail", "").lower()

    def test_patch_invalid_status(self, gov_token):
        r = requests.patch(f"{API}/roads/rd-nh17/status",
                           headers=h(gov_token),
                           json={"status": "BOGUS", "reason": "invalid test"})
        assert r.status_code == 400

    def test_patch_not_found(self, gov_token):
        r = requests.patch(f"{API}/roads/nonexistent/status",
                           headers=h(gov_token),
                           json={"status": "RESTRICTED", "reason": "not found"})
        assert r.status_code == 404

    def test_patch_success_and_persistence(self, gov_token):
        payload = {"status": "RESTRICTED", "reason": "Monsoon damage inspection",
                   "expected_duration": "1-2 days"}
        r = requests.patch(f"{API}/roads/rd-nh17/status", headers=h(gov_token), json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == "rd-nh17"
        assert d["status"] == "RESTRICTED"
        assert d["status_reason"] == "Monsoon damage inspection"
        assert d["expected_duration"] == "1-2 days"
        assert d["updated_by"] == "gov.admin@neris.demo"

        # verify via dashboard summary
        s = requests.get(f"{API}/dashboard/summary", headers=h(gov_token)).json()
        feat = next(f for f in s["roads"]["features"] if f["properties"]["id"] == "rd-nh17")
        assert feat["properties"]["status"] == "RESTRICTED"


# --- Audit ---
class TestAudit:
    def test_audit_forbidden_logistics(self, logistics_token):
        r = requests.get(f"{API}/audit", headers=h(logistics_token))
        assert r.status_code == 403

    def test_audit_gov_returns_entries(self, gov_token):
        r = requests.get(f"{API}/audit", headers=h(gov_token))
        assert r.status_code == 200
        entries = r.json()
        assert isinstance(entries, list)
        road_entries = [e for e in entries if e.get("action_type") == "ROAD_STATUS_CHANGE"]
        assert len(road_entries) >= 1
        e = road_entries[0]
        for k in ("old_state", "new_state", "reason", "official_email", "timestamp"):
            assert k in e, f"missing {k}"


# --- Vehicles ---
class TestVehicles:
    def test_list_vehicles(self, gov_token):
        r = requests.get(f"{API}/vehicles", headers=h(gov_token))
        assert r.status_code == 200
        vs = r.json()
        assert len(vs) == 12

    def test_get_vehicle(self, gov_token):
        r = requests.get(f"{API}/vehicles/veh-204", headers=h(gov_token))
        assert r.status_code == 200
        assert r.json()["number"] == "TRK-204"

    def test_get_vehicle_404(self, gov_token):
        r = requests.get(f"{API}/vehicles/bad-id", headers=h(gov_token))
        assert r.status_code == 404


# --- Hazard ML ---
class TestHazardML:
    def test_flood_predict(self, gov_token):
        feats = {"rainfall_24h": 120, "soil_moisture": 0.8, "elevation_m": 60,
                 "slope_deg": 2, "distance_to_river_m": 500,
                 "historical_flood_frequency": 7, "poor_drainage": 0.7}
        r = requests.post(f"{API}/ml/flood/predict", headers=h(gov_token), json=feats)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "flood_probability" in d
        assert d["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert "confidence" in d
        assert isinstance(d["top_features"], list)
        assert all("name" in t and "contribution" in t for t in d["top_features"])
        assert d["model_name"] == "ner-flood-rule"
        assert d["model_version"] == "v0.1"
        assert d["provenance"] == "PROTOTYPE_DEMO"
        assert "not causal" in d["disclaimer"].lower()

    def test_landslide_predict(self, gov_token):
        feats = {"slope_deg": 38, "rainfall_24h": 130, "rainfall_7d": 350,
                 "soil_moisture": 0.85, "fragile_geology": 0.85,
                 "vegetation_index": 0.3, "historical_landslide_frequency": 8, "road_cut": 0.85}
        r = requests.post(f"{API}/ml/landslide/predict", headers=h(gov_token), json=feats)
        assert r.status_code == 200
        d = r.json()
        assert "landslide_probability" in d
        assert d["risk_level"] in ("HIGH", "CRITICAL")
        assert d["model_name"] == "ner-landslide-rule"

    def test_corridor_flood_predictions(self, gov_token):
        r = requests.get(f"{API}/predictions/flood", headers=h(gov_token))
        assert r.status_code == 200
        d = r.json()
        assert d["hazard"] == "flood"
        assert d["provenance"] == "PROTOTYPE_DEMO"
        preds = d["predictions"]
        assert len(preds) >= 10
        probs = [p["flood_probability"] for p in preds]
        assert probs == sorted(probs, reverse=True)
        top_ids = [p["road_id"] for p in preds[:3]]
        assert ("rd-sh9" in top_ids) or ("rd-nh15" in top_ids)

    def test_corridor_landslide_predictions(self, gov_token):
        r = requests.get(f"{API}/predictions/landslide", headers=h(gov_token))
        assert r.status_code == 200
        preds = r.json()["predictions"]
        critical = [p for p in preds if p["risk_level"] == "CRITICAL"]
        critical_ids = [p["road_id"] for p in critical]
        # highest-risk corridors must appear as CRITICAL
        assert ("rd-nh6" in critical_ids) or ("rd-nh29" in critical_ids)

    def test_unknown_hazard_404(self, gov_token):
        r = requests.get(f"{API}/predictions/tsunami", headers=h(gov_token))
        assert r.status_code == 404


# --- Routes ---
class TestRoutes:
    def test_places(self, gov_token):
        r = requests.get(f"{API}/routes/places", headers=h(gov_token))
        assert r.status_code == 200
        places = r.json()
        assert len(places) == 17

    def test_calculate_unauth(self):
        r = requests.post(f"{API}/routes/calculate",
                          json={"origin": "tezpur", "destination": "jorhat", "vehicle_type": "TRUCK"})
        assert r.status_code == 401

    def test_calculate_clean_tezpur_jorhat(self, gov_token):
        r = requests.post(f"{API}/routes/calculate", headers=h(gov_token),
                          json={"origin": "tezpur", "destination": "jorhat", "vehicle_type": "TRUCK"})
        assert r.status_code == 200, r.text
        d = r.json()
        rec = d["recommended_route"]
        assert rec["contains_blocked"] is False
        seg_ids = [s["road_id"] for s in rec["segments"]]
        assert "rd-nh715" in seg_ids
        # ensure the rd-nh715 seg is OPEN
        seg = next(s for s in rec["segments"] if s["road_id"] == "rd-nh715")
        assert seg["status"] == "OPEN"

    def test_calculate_blocked_guwahati_shillong(self, gov_token):
        # ensure rd-nh6 is BLOCKED (seed sets it BLOCKED)
        r = requests.post(f"{API}/routes/calculate", headers=h(gov_token),
                          json={"origin": "guwahati", "destination": "shillong", "vehicle_type": "SUV"})
        assert r.status_code == 200, r.text
        d = r.json()
        rec = d["recommended_route"]
        assert rec["contains_blocked"] is True
        assert "NH-6 Guwahati–Shillong" in rec["blocked_roads"]
        seg = next(s for s in rec["segments"] if s["road_id"] == "rd-nh6")
        assert seg["status"] == "BLOCKED"

    def test_calculate_unknown_place(self, gov_token):
        r = requests.post(f"{API}/routes/calculate", headers=h(gov_token),
                          json={"origin": "atlantis", "destination": "jorhat", "vehicle_type": "TRUCK"})
        assert r.status_code == 400
        assert "valid" in r.json()["detail"].lower()

    def test_calculate_same_origin_dest(self, gov_token):
        r = requests.post(f"{API}/routes/calculate", headers=h(gov_token),
                          json={"origin": "tezpur", "destination": "tezpur", "vehicle_type": "TRUCK"})
        assert r.status_code == 400

    def test_calculate_invalid_vehicle(self, gov_token):
        r = requests.post(f"{API}/routes/calculate", headers=h(gov_token),
                          json={"origin": "tezpur", "destination": "jorhat", "vehicle_type": "SPACESHIP"})
        assert r.status_code == 400
