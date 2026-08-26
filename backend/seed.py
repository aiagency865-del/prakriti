import uuid
from datetime import datetime, timezone

from core.database import db
from core.security import hash_password


def _iso_mins_ago(m: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=m)).isoformat()


from datetime import timedelta  # noqa: E402

# =============================
# Users seed
# =============================

DEMO_ACCOUNTS = [
    {"email": "gov.admin@neris.demo", "password": "Demo@2026", "name": "Aditi Baruah", "role": "GOVERNMENT_ADMIN", "organization": "Government of Assam", "department": "Disaster Management Cell"},
    {"email": "gov.officer@neris.demo", "password": "Demo@2026", "name": "Kiran Deka", "role": "GOVERNMENT_OFFICER", "organization": "State Logistics Authority", "department": "District Ops — Kamrup"},
    {"email": "logistics@neris.demo", "password": "Demo@2026", "name": "NER Logistics Co.", "role": "LOGISTICS_OPERATOR", "organization": "Brahmaputra Freight Pvt Ltd", "department": "Fleet Ops"},
    {"email": "field@neris.demo", "password": "Demo@2026", "name": "R. Marak", "role": "FIELD_OFFICER", "organization": "Field Operations", "department": "West Garo Hills"},
    {"email": "public@neris.demo", "password": "Demo@2026", "name": "Public Access", "role": "PUBLIC_USER", "organization": None, "department": None},
    {"email": "driver@neris.demo", "password": "Demo@2026", "name": "B. Singh", "role": "DRIVER", "organization": "Brahmaputra Freight Pvt Ltd", "department": "Line-haul"},
]


async def _upsert_user(doc: dict):
    import os
    email = doc["email"].strip().lower()
    existing = await db.users.find_one({"email": email})
    payload = {
        "id": existing["id"] if existing else str(uuid.uuid4()),
        "email": email,
        "name": doc["name"],
        "role": doc["role"],
        "organization": doc.get("organization"),
        "department": doc.get("department"),
        "is_active": True,
        "password_hash": hash_password(doc["password"]),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not existing:
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one(payload)
    else:
        await db.users.update_one({"email": email}, {"$set": payload})


async def seed_users():
    import os
    await db.users.create_index("email", unique=True)
    await _upsert_user({
        "email": os.environ.get("ADMIN_EMAIL", "aiagency865@gmail.com"),
        "password": os.environ.get("ADMIN_PASSWORD", "Admin@2026"),
        "name": "NERIS Owner",
        "role": "SUPER_ADMIN",
        "organization": "NERIS Platform",
        "department": "Platform Administration",
    })
    for acc in DEMO_ACCOUNTS:
        await _upsert_user(acc)


# =============================
# Dashboard demo dataset (all rows tagged source=DEMO)
# =============================

DEMO_ROADS = [
    {"id": "rd-nh27", "name": "NH-27 Guwahati–Nagaon", "road_class": "highway", "district": "Kamrup Metro", "status": "AT_RISK", "risk": 62, "geometry": {"type": "LineString", "coordinates": [[91.57, 26.12], [91.75, 26.18], [92.05, 26.23], [92.32, 26.30]]}},
    {"id": "rd-nh6", "name": "NH-6 Guwahati–Shillong", "road_class": "highway", "district": "Ri-Bhoi", "status": "BLOCKED", "risk": 91, "geometry": {"type": "LineString", "coordinates": [[91.74, 26.14], [91.65, 25.85], [91.60, 25.57]]}},
    {"id": "rd-nh15", "name": "NH-15 Mangaldai–Tezpur", "road_class": "highway", "district": "Sonitpur", "status": "RESTRICTED", "risk": 55, "geometry": {"type": "LineString", "coordinates": [[92.03, 26.44], [92.35, 26.50], [92.80, 26.63]]}},
    {"id": "rd-nh17", "name": "NH-17 Guwahati–Goalpara", "road_class": "highway", "district": "Goalpara", "status": "OPEN", "risk": 18, "geometry": {"type": "LineString", "coordinates": [[91.74, 26.15], [91.35, 26.10], [90.97, 26.07]]}},
    {"id": "rd-nh715", "name": "NH-715 Tezpur–Jorhat", "road_class": "highway", "district": "Jorhat", "status": "OPEN", "risk": 22, "geometry": {"type": "LineString", "coordinates": [[92.80, 26.63], [93.30, 26.72], [94.20, 26.75]]}},
    {"id": "rd-sh9", "name": "SH-9 Silchar–Aizawl", "road_class": "secondary", "district": "Cachar", "status": "AT_RISK", "risk": 47, "geometry": {"type": "LineString", "coordinates": [[92.78, 24.83], [92.75, 24.20], [92.90, 23.73]]}},
    {"id": "rd-nh29", "name": "NH-29 Dimapur–Kohima", "road_class": "highway", "district": "Kohima", "status": "GOVERNMENT_CLOSED", "risk": 88, "geometry": {"type": "LineString", "coordinates": [[93.73, 25.91], [94.05, 25.70]]}},
    {"id": "rd-nh13", "name": "NH-13 Itanagar–Pasighat", "road_class": "highway", "district": "East Siang", "status": "OPEN", "risk": 15, "geometry": {"type": "LineString", "coordinates": [[93.61, 27.10], [94.30, 27.80], [95.33, 28.06]]}},
    {"id": "rd-nh502", "name": "NH-502 Imphal–Ukhrul", "road_class": "secondary", "district": "Ukhrul", "status": "UNKNOWN", "risk": 40, "geometry": {"type": "LineString", "coordinates": [[93.94, 24.82], [94.35, 24.98]]}},
    {"id": "rd-nh108", "name": "NH-108 Agartala–Udaipur", "road_class": "highway", "district": "Gomati", "status": "OPEN", "risk": 12, "geometry": {"type": "LineString", "coordinates": [[91.28, 23.83], [91.49, 23.53]]}},
    {"id": "rd-nh15w", "name": "NH-15 Guwahati–Mangaldai", "road_class": "highway", "district": "Darrang", "status": "OPEN", "risk": 20, "geometry": {"type": "LineString", "coordinates": [[91.75, 26.18], [91.90, 26.32], [92.03, 26.44]]}},
    {"id": "rd-nh27e", "name": "NH-27 Nagaon–Dimapur", "road_class": "highway", "district": "Karbi Anglong", "status": "OPEN", "risk": 25, "geometry": {"type": "LineString", "coordinates": [[92.32, 26.30], [93.10, 26.05], [93.73, 25.91]]}},
]

DEMO_INCIDENTS = [
    {"id": "NER-20481", "type": "LANDSLIDE", "severity": "CRITICAL", "title": "Landslide Risk", "location": "NH-6, near Sonapur", "lat": 26.07, "lng": 91.63, "source": "AI+GPS", "confidence": 91, "status": "PROVISIONALLY_BLOCKED", "created_minutes_ago": 12},
    {"id": "NER-20479", "type": "FLOOD", "severity": "HIGH", "title": "Flood Probability Rising", "location": "NH-15, Tezpur approach", "lat": 26.55, "lng": 92.55, "source": "AI", "confidence": 78, "status": "UNVERIFIED", "created_minutes_ago": 24},
    {"id": "NER-20477", "type": "TRAFFIC", "severity": "HIGH", "title": "Fleet Anomaly Detected", "location": "NH-27, Baihata stretch — 8 vehicles slowed", "lat": 26.22, "lng": 91.72, "source": "GPS", "confidence": 84, "status": "UNVERIFIED", "created_minutes_ago": 31},
    {"id": "NER-20475", "type": "ROAD_DAMAGE", "severity": "WARNING", "title": "Road Damage Reported", "location": "NH-29, Kohima bypass", "lat": 25.78, "lng": 93.90, "source": "FIELD", "confidence": 72, "status": "VERIFIED", "created_minutes_ago": 47},
    {"id": "NER-20467", "type": "FLOOD", "severity": "HIGH", "title": "River Level Above Threshold", "location": "SH-9, Barak valley", "lat": 24.55, "lng": 92.77, "source": "AI", "confidence": 81, "status": "UNVERIFIED", "created_minutes_ago": 66},
    {"id": "NER-20473", "type": "WEATHER", "severity": "WARNING", "title": "Heavy Rainfall Warning", "location": "Meghalaya hills, NH-6 corridor", "lat": 25.70, "lng": 91.62, "source": "AI", "confidence": 69, "status": "UNVERIFIED", "created_minutes_ago": 58},
    {"id": "NER-20471", "type": "BRIDGE_DAMAGE", "severity": "INFO", "title": "Bridge Inspection Scheduled", "location": "NH-17, Bridge B-17", "lat": 26.10, "lng": 91.35, "source": "GOVERNMENT", "confidence": 100, "status": "VERIFIED", "created_minutes_ago": 132},
    {"id": "NER-20469", "type": "ACCIDENT", "severity": "INFO", "title": "Minor Accident Cleared", "location": "NH-715, near Jorhat", "lat": 26.72, "lng": 93.30, "source": "PUBLIC", "confidence": 55, "status": "RESOLVED", "created_minutes_ago": 188},
]

DEMO_VEHICLES = [
    {"id": "veh-204", "number": "TRK-204", "type": "TRUCK", "lat": 26.19, "lng": 91.80, "heading": 72, "speed": 34, "status": "IN_TRANSIT", "destination": "Nagaon DC", "eta_minutes": 192, "risk": 32, "commodity": "MEDICINE"},
    {"id": "veh-118", "number": "TRK-118", "type": "TRUCK", "lat": 26.46, "lng": 92.30, "heading": 80, "speed": 41, "status": "IN_TRANSIT", "destination": "Tezpur Depot", "eta_minutes": 78, "risk": 55, "commodity": "FOOD"},
    {"id": "veh-332", "number": "LTV-332", "type": "LIGHT", "lat": 26.11, "lng": 91.42, "heading": 262, "speed": 48, "status": "IN_TRANSIT", "destination": "Goalpara", "eta_minutes": 95, "risk": 18, "commodity": "WATER"},
    {"id": "veh-090", "number": "EMG-090", "type": "EMERGENCY", "lat": 26.15, "lng": 91.70, "heading": 190, "speed": 62, "status": "IN_TRANSIT", "destination": "GMCH Guwahati", "eta_minutes": 14, "risk": 12, "commodity": "EMERGENCY_EQUIPMENT"},
    {"id": "veh-451", "number": "TRK-451", "type": "TRUCK", "lat": 26.22, "lng": 91.71, "heading": 75, "speed": 8, "status": "DELAYED", "destination": "Baihata Chariali", "eta_minutes": 240, "risk": 71, "commodity": "FUEL"},
    {"id": "veh-517", "number": "SUV-517", "type": "SUV", "lat": 24.40, "lng": 92.76, "heading": 350, "speed": 29, "status": "IN_TRANSIT", "destination": "Silchar", "eta_minutes": 66, "risk": 47, "commodity": "MEDICINE"},
    {"id": "veh-620", "number": "TRK-620", "type": "TRUCK", "lat": 25.85, "lng": 93.85, "heading": 10, "speed": 0, "status": "DELAYED", "destination": "Kohima", "eta_minutes": 310, "risk": 88, "commodity": "CONSTRUCTION"},
    {"id": "veh-733", "number": "LTV-733", "type": "LIGHT", "lat": 26.68, "lng": 93.10, "heading": 95, "speed": 44, "status": "IN_TRANSIT", "destination": "Jorhat", "eta_minutes": 120, "risk": 22, "commodity": "FOOD"},
    {"id": "veh-842", "number": "2W-842", "type": "TWO_WHEELER", "lat": 27.30, "lng": 94.60, "heading": 40, "speed": 38, "status": "IN_TRANSIT", "destination": "Pasighat", "eta_minutes": 150, "risk": 15, "commodity": "AGRICULTURAL"},
    {"id": "veh-905", "number": "TRK-905", "type": "TRUCK", "lat": 23.70, "lng": 91.40, "heading": 185, "speed": 52, "status": "IN_TRANSIT", "destination": "Udaipur", "eta_minutes": 42, "risk": 12, "commodity": "FOOD"},
    {"id": "veh-011", "number": "SUV-011", "type": "SUV", "lat": 24.90, "lng": 94.10, "heading": 30, "speed": 0, "status": "IDLE", "destination": "—", "eta_minutes": None, "risk": 40, "commodity": None},
    {"id": "veh-156", "number": "EMG-156", "type": "EMERGENCY", "lat": 26.60, "lng": 92.75, "heading": 270, "speed": 55, "status": "IN_TRANSIT", "destination": "Tezpur MC", "eta_minutes": 9, "risk": 55, "commodity": "MEDICINE"},
]

DEMO_VILLAGES = [
    {"id": "vil-majuli", "name": "Majuli Riverine Cluster", "district": "Majuli", "population": 12400, "isolation_risk": "CRITICAL", "days_to_stockout": 2, "primary_commodity": "MEDICINE"},
    {"id": "vil-tuting", "name": "Tuting", "district": "Upper Siang", "population": 3200, "isolation_risk": "CRITICAL", "days_to_stockout": 3, "primary_commodity": "FOOD"},
    {"id": "vil-cherrapunji", "name": "Sohra Outskirts", "district": "East Khasi Hills", "population": 5800, "isolation_risk": "HIGH", "days_to_stockout": 5, "primary_commodity": "FOOD"},
    {"id": "vil-ziro", "name": "Ziro Valley Hamlets", "district": "Lower Subansiri", "population": 9100, "isolation_risk": "MEDIUM", "days_to_stockout": 9, "primary_commodity": "FUEL"},
    {"id": "vil-mon", "name": "Mon Border Villages", "district": "Mon", "population": 7400, "isolation_risk": "HIGH", "days_to_stockout": 6, "primary_commodity": "MEDICINE"},
    {"id": "vil-haflong", "name": "Haflong Periphery", "district": "Dima Hasao", "population": 4200, "isolation_risk": "MEDIUM", "days_to_stockout": 11, "primary_commodity": "FOOD"},
    {"id": "vil-mokokchung", "name": "Mokokchung Rural", "district": "Mokokchung", "population": 11200, "isolation_risk": "LOW", "days_to_stockout": 18, "primary_commodity": "FOOD"},
    {"id": "vil-tezpur", "name": "Tezpur Riverside", "district": "Sonitpur", "population": 15600, "isolation_risk": "LOW", "days_to_stockout": 21, "primary_commodity": "WATER"},
]

DEMO_DELIVERIES = [
    {"id": "DEL-8801", "vehicle": "TRK-204", "origin": "Guwahati", "destination": "Nagaon", "commodity": "MEDICINE", "status": "ON_TRACK", "eta_minutes": 192, "risk": 32, "road": "NH-27"},
    {"id": "DEL-8802", "vehicle": "TRK-118", "origin": "Mangaldai", "destination": "Tezpur", "commodity": "FOOD", "status": "DELAYED", "eta_minutes": 78, "risk": 55, "road": "NH-15"},
    {"id": "DEL-8803", "vehicle": "LTV-332", "origin": "Guwahati", "destination": "Goalpara", "commodity": "WATER", "status": "ON_TRACK", "eta_minutes": 95, "risk": 18, "road": "NH-17"},
    {"id": "DEL-8804", "vehicle": "TRK-451", "origin": "Guwahati", "destination": "Nagaon", "commodity": "FUEL", "status": "AT_RISK", "eta_minutes": 240, "risk": 71, "road": "NH-27"},
    {"id": "DEL-8805", "vehicle": "SUV-517", "origin": "Silchar", "destination": "Aizawl", "commodity": "MEDICINE", "status": "ON_TRACK", "eta_minutes": 66, "risk": 47, "road": "SH-9"},
    {"id": "DEL-8806", "vehicle": "TRK-620", "origin": "Dimapur", "destination": "Kohima", "commodity": "CONSTRUCTION", "status": "DELAYED", "eta_minutes": 310, "risk": 88, "road": "NH-29"},
    {"id": "DEL-8807", "vehicle": "LTV-733", "origin": "Tezpur", "destination": "Jorhat", "commodity": "FOOD", "status": "ON_TRACK", "eta_minutes": 120, "risk": 22, "road": "NH-715"},
    {"id": "DEL-8808", "vehicle": "TRK-905", "origin": "Agartala", "destination": "Udaipur", "commodity": "FOOD", "status": "ON_TRACK", "eta_minutes": 42, "risk": 12, "road": "NH-108"},
]

DEMO_FIELD_REPORTS = [
    {"id": "FR-1002", "officer_email": "field@neris.demo", "officer_name": "R. Marak", "type": "ROAD_DAMAGE", "description": "Asphalt scouring near culvert, single lane passable", "road_id": "rd-sh9", "location": "SH-9, Barak valley", "lat": 24.55, "lng": 92.77, "severity": "WARNING", "status": "VERIFIED", "created_minutes_ago": 95},
    {"id": "FR-1001", "officer_email": "field@neris.demo", "officer_name": "R. Marak", "type": "LANDSLIDE", "description": "Fresh debris slide onto shoulder, work crew on site", "road_id": "rd-nh6", "location": "NH-6, near Sonapur", "lat": 26.07, "lng": 91.63, "severity": "HIGH", "status": "SUBMITTED", "created_minutes_ago": 40},
]

DEMO_ENVIRONMENT = [
    {"id": "rain-shillong", "kind": "RAIN", "name": "Meghalaya Hills rain cell", "lat": 25.60, "lng": 91.62, "base_intensity_mm_h": 28, "base_radius_km": 40},
    {"id": "rain-tezpur", "kind": "RAIN", "name": "Tezpur valley rain", "lat": 26.63, "lng": 92.80, "base_intensity_mm_h": 14, "base_radius_km": 30},
    {"id": "rain-barak", "kind": "RAIN", "name": "Barak valley monsoon band", "lat": 24.60, "lng": 92.75, "base_intensity_mm_h": 22, "base_radius_km": 35},
    {"id": "ls-sonapur", "kind": "LANDSLIDE", "name": "Sonapur slope", "lat": 26.07, "lng": 91.63, "slide_type": "DEBRIS_FLOW", "probability": 0.78},
    {"id": "ls-kohima", "kind": "LANDSLIDE", "name": "Kohima bypass cut slope", "lat": 25.78, "lng": 93.90, "slide_type": "ROCKFALL", "probability": 0.66},
    {"id": "ls-aizawl", "kind": "LANDSLIDE", "name": "Aizawl–Silchar road cut", "lat": 24.00, "lng": 92.80, "slide_type": "SHALLOW_SLIDE", "probability": 0.58},
]


def _current_environment(events):
    """Simulated live weather: intensity oscillates over time so the map visibly updates (DEMO)."""
    import math
    now = datetime.now(timezone.utc)
    t = now.hour * 60 + now.minute + now.second / 60.0
    rain = []
    landslides = []
    for e in events:
        if e["kind"] == "RAIN":
            phase = (sum(ord(c) for c in e["id"]) % 100) / 100.0 * 6.283
            factor = 1 + 0.35 * math.sin(t * 0.35 + phase)
            intensity = round(e["base_intensity_mm_h"] * factor, 1)
            radius = round(e["base_radius_km"] * (0.7 + 0.3 * factor), 1)
            rain.append({
                "id": e["id"], "kind": "RAIN", "name": e["name"], "lat": e["lat"], "lng": e["lng"],
                "intensity_mm_h": intensity, "radius_km": radius,
                "level": "HEAVY" if intensity >= 20 else "MODERATE",
            })
        elif e["kind"] == "LANDSLIDE":
            landslides.append({
                "id": e["id"], "kind": "LANDSLIDE", "name": e["name"], "lat": e["lat"], "lng": e["lng"],
                "slide_type": e["slide_type"], "probability": e["probability"],
            })
    return {"rain": rain, "landslides": landslides}


DEMO_SUPPLY = [
    {"commodity": "MEDICINE", "at_risk_count": 7, "severity": "CRITICAL"},
    {"commodity": "FOOD", "at_risk_count": 13, "severity": "HIGH"},
    {"commodity": "WATER", "at_risk_count": 8, "severity": "WARNING"},
    {"commodity": "FUEL", "at_risk_count": 3, "severity": "INFO"},
]

SEED_VERSION = 5


async def seed_dashboard():
    meta = await db.meta.find_one({"key": "seed_version"})
    current = meta["value"] if meta else 0
    if current >= SEED_VERSION:
        return
    for coll in ["roads", "incidents", "vehicles", "villages", "supply_risks", "deliveries", "field_reports", "environment_events"]:
        await db[coll].delete_many({})
    await db.roads.insert_many([{**r, "source": "DEMO"} for r in DEMO_ROADS])
    await db.incidents.insert_many([{**i, "source_tag": "DEMO"} for i in DEMO_INCIDENTS])
    await db.vehicles.insert_many([{**v, "source": "DEMO"} for v in DEMO_VEHICLES])
    await db.villages.insert_many([{**v, "source": "DEMO"} for v in DEMO_VILLAGES])
    await db.supply_risks.insert_many([{**s, "source": "DEMO"} for s in DEMO_SUPPLY])
    await db.deliveries.insert_many([{**d, "source": "DEMO"} for d in DEMO_DELIVERIES])
    await db.field_reports.insert_many([{**f, "source": "DEMO"} for f in DEMO_FIELD_REPORTS])
    await db.environment_events.insert_many([{**e, "source": "DEMO"} for e in DEMO_ENVIRONMENT])
    await db.meta.update_one({"key": "seed_version"}, {"$set": {"value": SEED_VERSION}}, upsert=True)
