from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# --- Config ---
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MIN = 60 * 8  # 8 hours

# --- Database ---
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="NERIS API")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logger = logging.getLogger("neris")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


# --- Helpers ---
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MIN),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u.get("name"),
        "email": u["email"],
        "role": u["role"],
        "organization": u.get("organization"),
        "department": u.get("department"),
    }


async def get_current_user(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    token = None
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# --- Models ---
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


# --- Routes ---
@api.get("/")
async def root():
    return {"service": "NERIS", "status": "ok"}


@api.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": public_user(user)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@api.get("/auth/demo-accounts")
async def demo_accounts():
    """Return demo account emails (never passwords over API) for the login page picker."""
    return [
        {"role": "GOVERNMENT_ADMIN", "label": "Government Admin", "email": "gov.admin@neris.demo"},
        {"role": "GOVERNMENT_OFFICER", "label": "Government Officer", "email": "gov.officer@neris.demo"},
        {"role": "LOGISTICS_OPERATOR", "label": "Logistics Operator", "email": "logistics@neris.demo"},
        {"role": "FIELD_OFFICER", "label": "Field Officer", "email": "field@neris.demo"},
        {"role": "PUBLIC_USER", "label": "Public User", "email": "public@neris.demo"},
    ]


# --- Seeding ---
DEMO_ACCOUNTS = [
    {
        "email": "gov.admin@neris.demo",
        "password": "Demo@2026",
        "name": "Aditi Baruah",
        "role": "GOVERNMENT_ADMIN",
        "organization": "Government of Assam",
        "department": "Disaster Management Cell",
    },
    {
        "email": "gov.officer@neris.demo",
        "password": "Demo@2026",
        "name": "Kiran Deka",
        "role": "GOVERNMENT_OFFICER",
        "organization": "State Logistics Authority",
        "department": "District Ops — Kamrup",
    },
    {
        "email": "logistics@neris.demo",
        "password": "Demo@2026",
        "name": "NER Logistics Co.",
        "role": "LOGISTICS_OPERATOR",
        "organization": "Brahmaputra Freight Pvt Ltd",
        "department": "Fleet Ops",
    },
    {
        "email": "field@neris.demo",
        "password": "Demo@2026",
        "name": "R. Marak",
        "role": "FIELD_OFFICER",
        "organization": "Field Operations",
        "department": "West Garo Hills",
    },
    {
        "email": "public@neris.demo",
        "password": "Demo@2026",
        "name": "Public Access",
        "role": "PUBLIC_USER",
        "organization": None,
        "department": None,
    },
]


async def _upsert_user(doc: dict):
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


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    # Owner (real user)
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
    logger.info("NERIS: users seeded (owner + %d demo accounts)", len(DEMO_ACCOUNTS))
    await seed_dashboard()
    logger.info("NERIS: dashboard demo dataset ready")


# =============================
# Command Center demo dataset (all rows tagged source=DEMO)
# =============================

def _iso_mins_ago(m: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=m)).isoformat()


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
    {"id": "vil-majuli", "name": "Majuli Riverine Cluster", "district": "Majuli", "population": 12400, "isolation_risk": "CRITICAL"},
    {"id": "vil-tuting", "name": "Tuting", "district": "Upper Siang", "population": 3200, "isolation_risk": "CRITICAL"},
    {"id": "vil-cherrapunji", "name": "Sohra Outskirts", "district": "East Khasi Hills", "population": 5800, "isolation_risk": "HIGH"},
    {"id": "vil-ziro", "name": "Ziro Valley Hamlets", "district": "Lower Subansiri", "population": 9100, "isolation_risk": "MEDIUM"},
    {"id": "vil-mon", "name": "Mon Border Villages", "district": "Mon", "population": 7400, "isolation_risk": "HIGH"},
    {"id": "vil-haflong", "name": "Haflong Periphery", "district": "Dima Hasao", "population": 4200, "isolation_risk": "MEDIUM"},
    {"id": "vil-mokokchung", "name": "Mokokchung Rural", "district": "Mokokchung", "population": 11200, "isolation_risk": "LOW"},
    {"id": "vil-tezpur", "name": "Tezpur Riverside", "district": "Sonitpur", "population": 15600, "isolation_risk": "LOW"},
]

DEMO_SUPPLY = [
    {"commodity": "MEDICINE", "at_risk_count": 7, "severity": "CRITICAL"},
    {"commodity": "FOOD", "at_risk_count": 13, "severity": "HIGH"},
    {"commodity": "WATER", "at_risk_count": 8, "severity": "WARNING"},
    {"commodity": "FUEL", "at_risk_count": 3, "severity": "INFO"},
]


async def seed_dashboard():
    if await db.roads.count_documents({}) == 0:
        await db.roads.insert_many([{**r, "source": "DEMO"} for r in DEMO_ROADS])
    if await db.incidents.count_documents({}) == 0:
        await db.incidents.insert_many([{**i, "source_tag": "DEMO"} for i in DEMO_INCIDENTS])
    if await db.vehicles.count_documents({}) == 0:
        await db.vehicles.insert_many([{**v, "source": "DEMO"} for v in DEMO_VEHICLES])
    if await db.villages.count_documents({}) == 0:
        await db.villages.insert_many([{**v, "source": "DEMO"} for v in DEMO_VILLAGES])
    if await db.supply_risks.count_documents({}) == 0:
        await db.supply_risks.insert_many([{**s, "source": "DEMO"} for s in DEMO_SUPPLY])


@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    incidents = await db.incidents.find({}, {"_id": 0}).sort("created_minutes_ago", 1).to_list(100)
    vehicles = await db.vehicles.find({}, {"_id": 0}).to_list(500)
    villages = await db.villages.find({}, {"_id": 0}).to_list(500)
    supply = await db.supply_risks.find({}, {"_id": 0}).to_list(100)

    now = datetime.now(timezone.utc)
    for i in incidents:
        i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)

    kpis = {
        "active_vehicles": sum(1 for v in vehicles if v.get("status") in ("IN_TRANSIT", "DELAYED")),
        "at_risk_corridors": sum(1 for r in roads if r.get("status") in ("AT_RISK", "RESTRICTED")),
        "blocked_roads": sum(1 for r in roads if r.get("status") in ("BLOCKED", "GOVERNMENT_CLOSED")),
        "critical_alerts": sum(1 for i in incidents if i.get("severity") in ("CRITICAL", "HIGH")),
        "villages_isolation_risk": sum(1 for v in villages if v.get("isolation_risk") in ("HIGH", "CRITICAL")),
        "critical_supply_locations": sum(s.get("at_risk_count", 0) for s in supply if s.get("severity") == "CRITICAL"),
    }

    return {
        "provenance": "DEMO",
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "roads": {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": r["geometry"], "properties": {k: v for k, v in r.items() if k != "geometry"}}
                for r in roads
            ],
        },
        "incidents": incidents,
        "vehicles": vehicles,
        "supply": supply,
    }


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
