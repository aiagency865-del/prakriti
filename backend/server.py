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
import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from ml.hazard_models import (
    predict_flood,
    predict_landslide,
    CORRIDOR_FEATURES,
    MODEL_VERSION,
)


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
        "tokens": u.get("tokens", 0),
        "report_ban_until": u.get("report_ban_until"),
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


# =============================
# WebSocket push (true realtime events)
# =============================

class ConnectionManager:
    def __init__(self):
        self.connections = {}  # email -> set of websockets

    async def connect(self, websocket: WebSocket, email: str):
        await websocket.accept()
        self.connections.setdefault(email, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, email: str):
        conns = self.connections.get(email)
        if conns:
            conns.discard(websocket)
            if not conns:
                self.connections.pop(email, None)

    async def broadcast(self, message: dict):
        for conns in list(self.connections.values()):
            for ws in list(conns):
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def send_to_user(self, email: str, message: dict):
        for ws in list(self.connections.get(email, set())):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@api.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
    except Exception:
        await websocket.close(code=4401)
        return
    if not email:
        await websocket.close(code=4401)
        return
    await manager.connect(websocket, email)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket, email)


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
        "villages": villages,
    }


# =============================
# Government road control + audit
# =============================

GOVERNMENT_ROLES = {"SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"}
ROAD_STATUSES = {"OPEN", "AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED", "UNKNOWN"}


class RoadStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str
    reason: str = Field(min_length=3, max_length=500)
    expected_duration: Optional[str] = None


async def _reroute_trips_on_road(road_id: str, road_name: str, new_status: str):
    """Push REROUTE_REQUIRED to every driver with an active trip through this road."""
    now_iso = datetime.now(timezone.utc).isoformat()
    trips = await db.trips.find({"status": "ACTIVE", "road_ids": road_id}).to_list(50)
    for t in trips:
        new_route = await compute_route(t["origin"], t["destination"], t.get("vehicle_type", "TRUCK"))
        await db.trips.update_one(
            {"id": t["id"]},
            {"$set": {"route": new_route, "rerouted_at": now_iso, "reroute_reason": f"{road_name} is now {new_status.replace('_', ' ')}"}},
        )
        await manager.send_to_user(t["driver_email"], {
            "type": "REROUTE_REQUIRED",
            "trip_id": t["id"],
            "road_id": road_id,
            "road_name": road_name,
            "new_status": new_status,
            "route": new_route,
        })


@api.patch("/roads/{road_id}/status")
async def update_road_status(road_id: str, body: RoadStatusUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    new_status = body.status.upper()
    if new_status not in ROAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(ROAD_STATUSES)}")
    road = await db.roads.find_one({"id": road_id}, {"_id": 0})
    if not road:
        raise HTTPException(status_code=404, detail="Road not found")
    old_status = road["status"]
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = {
        "status": new_status,
        "status_reason": body.reason,
        "expected_duration": body.expected_duration,
        "updated_at": now_iso,
        "updated_by": user["email"],
    }
    await db.roads.update_one({"id": road_id}, {"$set": updates})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"],
        "official_email": user["email"],
        "official_name": user.get("name"),
        "action_type": "ROAD_STATUS_CHANGE",
        "target_type": "road",
        "target_id": road_id,
        "target_name": road.get("name"),
        "old_state": old_status,
        "new_state": new_status,
        "reason": body.reason,
        "timestamp": now_iso,
    })
    road.update(updates)

    if new_status in ("BLOCKED", "GOVERNMENT_CLOSED"):
        await _reroute_trips_on_road(road_id, road.get("name") or road_id, new_status)
    await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": road_id, "status": new_status, "road_name": road.get("name")})
    return road


@api.get("/audit")
async def get_audit(limit: int = 50, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    return await db.government_actions.find({}, {"_id": 0}).sort("timestamp", -1).to_list(min(limit, 200))


# =============================
# Vehicles
# =============================

@api.get("/vehicles")
async def list_vehicles(user: dict = Depends(get_current_user)):
    return await db.vehicles.find({}, {"_id": 0}).to_list(500)


@api.get("/vehicles/{vehicle_id}")
async def get_vehicle(vehicle_id: str, user: dict = Depends(get_current_user)):
    v = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


# =============================
# Hazard predictions (NER prototype models — ml/hazard_models.py)
# =============================

class HazardFeatures(BaseModel):
    model_config = ConfigDict(extra="allow")
    prediction_window_hours: int = 24


@api.post("/ml/flood/predict")
async def ml_flood_predict(body: HazardFeatures, user: dict = Depends(get_current_user)):
    feats = body.model_dump(exclude={"prediction_window_hours"})
    return predict_flood(feats, body.prediction_window_hours)


@api.post("/ml/landslide/predict")
async def ml_landslide_predict(body: HazardFeatures, user: dict = Depends(get_current_user)):
    feats = body.model_dump(exclude={"prediction_window_hours"})
    return predict_landslide(feats, body.prediction_window_hours)


@api.get("/predictions/{hazard}")
async def corridor_predictions(hazard: str, user: dict = Depends(get_current_user)):
    if hazard not in ("flood", "landslide"):
        raise HTTPException(status_code=404, detail="Unknown hazard. Use flood or landslide.")
    fn = predict_flood if hazard == "flood" else predict_landslide
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    out = []
    for r in roads:
        feats = CORRIDOR_FEATURES.get(r["id"], {}).get(hazard, {})
        pred = fn(feats)
        out.append({
            "road_id": r["id"],
            "name": r.get("name"),
            "district": r.get("district"),
            "status": r.get("status"),
            **pred,
        })
    out.sort(key=lambda x: x.get("flood_probability", x.get("landslide_probability", 0)), reverse=True)
    return {
        "hazard": hazard,
        "model_version": MODEL_VERSION,
        "provenance": "PROTOTYPE_DEMO",
        "predictions": out,
    }


# =============================
# Route calculation (demo routing graph over seeded corridors)
# =============================
import math

NER_PLACES = {
    "guwahati": (91.74, 26.15), "shillong": (91.60, 25.57), "tezpur": (92.80, 26.63),
    "nagaon": (92.32, 26.30), "jorhat": (94.20, 26.75), "silchar": (92.78, 24.83),
    "aizawl": (92.90, 23.73), "kohima": (94.05, 25.70), "dimapur": (93.73, 25.91),
    "imphal": (93.94, 24.82), "ukhrul": (94.35, 24.98), "itanagar": (93.61, 27.10),
    "pasighat": (95.33, 28.06), "agartala": (91.28, 23.83), "udaipur": (91.49, 23.53),
    "goalpara": (90.97, 26.07), "mangaldai": (92.03, 26.44),
}

VEHICLE_SPEEDS = {"TWO_WHEELER": 45, "LIGHT": 55, "SUV": 60, "TRUCK": 40, "EMERGENCY": 75}
STATUS_MULTIPLIER = {"OPEN": 1.0, "AT_RISK": 3.0, "RESTRICTED": 5.0, "UNKNOWN": 1.5}


def _haversine_km(a, b):
    lng1, lat1 = a
    lng2, lat2 = b
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _line_length_km(coords):
    return sum(_haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def _snap_places(point, max_km=25.0):
    return [name for name, coord in NER_PLACES.items() if _haversine_km(point, coord) <= max_km]


def _build_graph(roads, exclude_blocked=True):
    adj = {}
    for r in roads:
        if exclude_blocked and r["status"] in ("BLOCKED", "GOVERNMENT_CLOSED"):
            continue
        coords = r["geometry"]["coordinates"]
        starts = _snap_places(coords[0])
        ends = _snap_places(coords[-1])
        length = _line_length_km(coords)
        for a in starts:
            for b in ends:
                if a == b:
                    continue
                cost = length * STATUS_MULTIPLIER.get(r["status"], 1.5)
                adj.setdefault(a, []).append((b, r, cost))
                adj.setdefault(b, []).append((a, r, cost))
    # Local-road connectors: link each town to its 3 nearest towns so any OD pair routes (demo network)
    names = list(NER_PLACES.keys())
    for a in names:
        dists = sorted((_haversine_km(NER_PLACES[a], NER_PLACES[b]), b) for b in names if b != a)
        for d, b in dists[:3]:
            pseudo = {
                "id": f"local-{a}-{b}", "name": f"Local roads {a.title()}–{b.title()}",
                "status": "LOCAL", "risk": 25, "district": "—",
                "geometry": {"type": "LineString", "coordinates": [list(NER_PLACES[a]), list(NER_PLACES[b])]},
            }
            cost = d * 1.3 * 2.0
            adj.setdefault(a, []).append((b, pseudo, cost))
            adj.setdefault(b, []).append((a, pseudo, cost))
    return adj


def _dijkstra(adj, start, end):
    dist = {start: 0.0}
    prev = {}
    visited = set()
    while True:
        cur = None
        best = float("inf")
        for n, d in dist.items():
            if n not in visited and d < best:
                cur, best = n, d
        if cur is None:
            return None
        if cur == end:
            break
        visited.add(cur)
        for nb, road, cost in adj.get(cur, []):
            nd = best + cost
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = (cur, road)
    if end not in prev and end != start:
        return None
    edges = []
    cur = end
    while cur != start:
        p, road = prev[cur]
        edges.append((p, cur, road))
        cur = p
    edges.reverse()
    return edges


def _assemble_route(edges, start):
    segments = []
    polyline = []
    cur_node = start
    for a, b, road in edges:
        coords = road["geometry"]["coordinates"]
        if _haversine_km(coords[-1], NER_PLACES[cur_node]) < _haversine_km(coords[0], NER_PLACES[cur_node]):
            coords = list(reversed(coords))
        if polyline and coords:
            polyline.extend(coords[1:])
        else:
            polyline.extend(coords)
        segments.append({
            "road_id": road["id"],
            "name": road.get("name"),
            "status": road.get("status"),
            "risk": road.get("risk"),
            "district": road.get("district"),
            "distance_km": round(_line_length_km(road["geometry"]["coordinates"]), 1),
            "geometry": road["geometry"],
        })
        cur_node = b
    return segments, polyline


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    origin: str
    destination: str
    vehicle_type: str = "TRUCK"


@api.get("/routes/places")
async def route_places(user: dict = Depends(get_current_user)):
    return sorted(NER_PLACES.keys())


async def _osrm_route(o, d):
    """Real road-network routing via the public OSRM demo server (OpenStreetMap data)."""
    try:
        async with httpx.AsyncClient(timeout=6.0) as http_client:
            resp = await http_client.get(
                f"https://router.project-osrm.org/route/v1/driving/{o[0]},{o[1]};{d[0]},{d[1]}",
                params={"overview": "full", "geometries": "geojson"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("routes"):
                    rt = data["routes"][0]
                    return rt["geometry"]["coordinates"], rt["distance"] / 1000.0, rt["duration"] / 60.0
    except Exception:
        pass
    return None


def _corridors_near(coords, roads, max_km=12.0):
    sample = coords[:: max(1, len(coords) // 200)]
    near = []
    for r in roads:
        rcoords = r["geometry"]["coordinates"]
        if any(_haversine_km(p, q) <= max_km for p in rcoords for q in sample):
            near.append(r)
    return near


async def compute_route(origin: str, destination: str, vehicle: str) -> dict:
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    speed = VEHICLE_SPEEDS[vehicle]
    osrm = await _osrm_route(NER_PLACES[origin], NER_PLACES[destination])

    if osrm:
        coords, dist_km, dur_min = osrm
        near = _corridors_near(coords, roads)
        segments = [
            {"road_id": r["id"], "name": r.get("name"), "status": r.get("status"), "risk": r.get("risk"),
             "district": r.get("district"), "distance_km": round(_line_length_km(r["geometry"]["coordinates"]), 1),
             "geometry": r["geometry"]}
            for r in near
        ]
        blocked_roads = [s["name"] for s in segments if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]
        at_risk_names = [s["name"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED")]
        risky_len = sum(s["distance_km"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED"))
        eta_minutes = round(dur_min * (1 + 0.5 * (risky_len / max(dist_km, 1))))
        risk_score = max([s["risk"] or 0 for s in segments], default=15)
        reason = ["Real road-network routing (OpenStreetMap via OSRM)"]
        reason.append(f"Corridor includes government-blocked road(s): {', '.join(blocked_roads)}" if blocked_roads else "No government closures near this route")
        if at_risk_names:
            reason.append(f"Elevated hazard on: {', '.join(at_risk_names)}")
        reason.append(f"Suitable for {vehicle.replace('_', ' ').title()}")
        return {
            "provenance": "OSM_ROAD_NETWORK + LIVE_CORRIDOR_STATUS",
            "origin": {"name": origin, "lng": NER_PLACES[origin][0], "lat": NER_PLACES[origin][1]},
            "destination": {"name": destination, "lng": NER_PLACES[destination][0], "lat": NER_PLACES[destination][1]},
            "vehicle_type": vehicle,
            "recommended_route": {
                "segments": segments,
                "polyline": coords,
                "distance_km": round(dist_km, 1),
                "eta_minutes": eta_minutes,
                "risk_score": risk_score,
                "contains_blocked": len(blocked_roads) > 0,
                "blocked_roads": blocked_roads,
                "road_ids": [r["id"] for r in near],
            },
            "reason": reason,
            "alternative_route": None,
        }

    # Fallback: demo corridor graph (offline / OSRM unreachable)
    adj = _build_graph(roads, exclude_blocked=True)
    edges = _dijkstra(adj, origin, destination)
    if edges is None:
        adj_all = _build_graph(roads, exclude_blocked=False)
        edges = _dijkstra(adj_all, origin, destination)
    if edges is None:
        pseudo = {
            "id": f"direct-{origin}-{destination}", "name": f"Direct route {origin.title()}–{destination.title()} (off-network)",
            "status": "LOCAL", "risk": 35, "district": "—",
            "geometry": {"type": "LineString", "coordinates": [list(NER_PLACES[origin]), list(NER_PLACES[destination])]},
        }
        edges = [(origin, destination, pseudo)]

    segments, polyline = _assemble_route(edges, origin)
    distance_km = round(_line_length_km(polyline), 1)
    risky_len = sum(s["distance_km"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED"))
    delay_factor = 1 + 0.5 * (risky_len / max(distance_km, 1))
    eta_minutes = round(distance_km / speed * 60 * delay_factor)
    risk_score = max((s["risk"] or 0) for s in segments)
    blocked_roads = [s["name"] for s in segments if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]

    reason = ["Demo corridor-graph routing (offline mode)"]
    reason.append(f"Corridor includes government-blocked road(s): {', '.join(blocked_roads)}" if blocked_roads else "No government closures on this route")
    at_risk_names = [s["name"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED")]
    if at_risk_names:
        reason.append(f"Elevated hazard on: {', '.join(at_risk_names)}")
    reason.append(f"Suitable for {vehicle.replace('_', ' ').title()}")

    alternative = None
    if not blocked_roads:
        adj_naive = _build_graph(roads, exclude_blocked=False)
        naive_edges = _dijkstra(adj_naive, origin, destination)
        if naive_edges and [e[2]["id"] for e in naive_edges] != [e[2]["id"] for e in edges]:
            nseg, npoly = _assemble_route(naive_edges, origin)
            n_blocked = [s["name"] for s in nseg if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]
            if n_blocked:
                nd = round(_line_length_km(npoly), 1)
                alternative = {
                    "segments": nseg,
                    "polyline": npoly,
                    "distance_km": nd,
                    "eta_minutes": round(nd / speed * 60),
                    "risk_score": max((s["risk"] or 0) for s in nseg),
                    "rejected_because": [f"Government closure: {', '.join(n_blocked)}"] + ([f"Risk score {max((s['risk'] or 0) for s in nseg)}"] if max((s["risk"] or 0) for s in nseg) >= 60 else []),
                }

    return {
        "provenance": "DEMO",
        "origin": {"name": origin, "lng": NER_PLACES[origin][0], "lat": NER_PLACES[origin][1]},
        "destination": {"name": destination, "lng": NER_PLACES[destination][0], "lat": NER_PLACES[destination][1]},
        "vehicle_type": vehicle,
        "recommended_route": {
            "segments": segments,
            "polyline": polyline,
            "distance_km": distance_km,
            "eta_minutes": eta_minutes,
            "risk_score": risk_score,
            "contains_blocked": len(blocked_roads) > 0,
            "blocked_roads": blocked_roads,
            "road_ids": [s["road_id"] for s in segments if not s["road_id"].startswith(("local-", "direct-"))],
        },
        "reason": reason,
        "alternative_route": alternative,
    }


@api.post("/routes/calculate")
async def calculate_route(body: RouteRequest, user: dict = Depends(get_current_user)):
    origin = body.origin.strip().lower()
    destination = body.destination.strip().lower()
    if origin not in NER_PLACES or destination not in NER_PLACES:
        raise HTTPException(status_code=400, detail=f"Unknown place. Valid: {sorted(NER_PLACES.keys())}")
    if origin == destination:
        raise HTTPException(status_code=400, detail="Origin and destination must be different")
    vehicle = body.vehicle_type.upper()
    if vehicle not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid vehicle type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    return await compute_route(origin, destination, vehicle)


# =============================
# Deliveries, field reports, alerts, public advisories
# =============================

FIELD_ROLES = {"FIELD_OFFICER", "DRIVER", "SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"}
REPORT_TYPES = {"LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT", "BLOCKAGE", "OTHER"}
SEVERITIES = {"INFO", "WARNING", "HIGH", "CRITICAL"}


class FieldReportCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    description: str = Field(min_length=5, max_length=1000)
    road_id: Optional[str] = None
    lat: float
    lng: float
    severity: str


@api.post("/field/reports", status_code=201)
async def create_field_report(body: FieldReportCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in FIELD_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    rtype = body.type.upper()
    severity = body.severity.upper()
    if rtype not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(REPORT_TYPES)}")
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = "Field location"
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": f"FR-{uuid.uuid4().hex[:6].upper()}",
        "officer_email": user["email"],
        "officer_name": user.get("name"),
        "type": rtype,
        "description": body.description,
        "road_id": body.road_id,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "severity": severity,
        "status": "SUBMITTED",
        "created_at": now_iso,
        "source": "FIELD",
    }
    await db.field_reports.insert_one({**report})

    # Propagate: a field report becomes an unverified incident visible to gov + logistics immediately
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": rtype if rtype in ("LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT") else "UNKNOWN",
        "severity": severity,
        "title": body.description[:80],
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "FIELD",
        "confidence": 60,
        "status": "UNVERIFIED",
        "created_at": now_iso,
        "source_tag": "FIELD_REPORT",
        "field_report_id": report["id"],
    }
    await db.incidents.insert_one({**incident})
    await manager.broadcast({"type": "FIELD_REPORT", "id": report["id"], "title": report["description"][:80], "severity": severity})
    report.pop("_id", None)
    return report


@api.get("/field/reports")
async def list_field_reports(user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] in ("FIELD_OFFICER", "DRIVER"):
        q = {"officer_email": user["email"]}
    reports = await db.field_reports.find(q, {"_id": 0}).to_list(500)

    def key(r):
        return r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0))
    reports.sort(key=key, reverse=True)
    for r in reports:
        if "created_at" not in r:
            r["created_at"] = _iso_mins_ago(r.get("created_minutes_ago", 0))
        r.pop("created_minutes_ago", None)
    return reports


VERIFY_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}


@api.patch("/incidents/{incident_id}/verify")
async def verify_incident(incident_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in VERIFY_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc.get("status") == "VERIFIED":
        raise HTTPException(status_code=400, detail="Incident already verified")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.incidents.update_one({"id": incident_id}, {"$set": {"status": "VERIFIED", "verified_by": user["email"], "verified_at": now_iso}})
    if inc.get("field_report_id"):
        await db.field_reports.update_one({"id": inc["field_report_id"]}, {"$set": {"status": "VERIFIED"}})
    if inc.get("public_report_id"):
        await db.public_reports.update_one({"id": inc["public_report_id"]}, {"$set": {"status": "VERIFIED"}})
        rep = await db.public_reports.find_one({"id": inc["public_report_id"]})
        if rep:
            await db.users.update_one({"email": rep["reporter_email"]}, {"$inc": {"tokens": 10}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"],
        "official_email": user["email"],
        "official_name": user.get("name"),
        "action_type": "INCIDENT_VERIFIED",
        "target_type": "incident",
        "target_id": incident_id,
        "target_name": inc.get("title"),
        "old_state": inc.get("status"),
        "new_state": "VERIFIED",
        "reason": "Government verification",
        "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_VERIFIED", "id": incident_id, "title": inc.get("title")})
    return {"id": incident_id, "status": "VERIFIED"}


@api.patch("/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in VERIFY_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc.get("status") in ("VERIFIED", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"Incident already {inc['status'].lower()}")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.incidents.update_one({"id": incident_id}, {"$set": {"status": "REJECTED", "rejected_by": user["email"], "rejected_at": now_iso}})
    if inc.get("field_report_id"):
        await db.field_reports.update_one({"id": inc["field_report_id"]}, {"$set": {"status": "REJECTED"}})
    if inc.get("public_report_id"):
        await db.public_reports.update_one({"id": inc["public_report_id"]}, {"$set": {"status": "REJECTED"}})
        rep = await db.public_reports.find_one({"id": inc["public_report_id"]})
        if rep:
            ban_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            await db.users.update_one({"email": rep["reporter_email"]}, {"$set": {"report_ban_until": ban_until}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "INCIDENT_REJECTED", "target_type": "incident", "target_id": incident_id,
        "target_name": inc.get("title"), "old_state": inc.get("status"), "new_state": "REJECTED",
        "reason": "Rejected after review", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_REJECTED", "id": incident_id, "title": inc.get("title")})
    return {"id": incident_id, "status": "REJECTED"}


@api.get("/environment")
async def get_environment(user: dict = Depends(get_current_user)):
    events = await db.environment_events.find({}, {"_id": 0}).to_list(100)
    env = _current_environment(events)
    return {"provenance": "DEMO", **env}


@api.get("/deliveries")
async def list_deliveries(user: dict = Depends(get_current_user)):
    return await db.deliveries.find({}, {"_id": 0}).to_list(500)


@api.get("/alerts")
async def list_alerts(user: dict = Depends(get_current_user)):
    # Verification pipeline: unverified reports/incidents are visible only to
    # government & field roles; logistics and public see only VERIFIED items,
    # plus government notifications and emergency zones.
    privileged = user["role"] in (GOVERNMENT_ROLES | {"FIELD_OFFICER", "DRIVER"})
    inc_q = {"status": {"$ne": "RESOLVED"}} if privileged else {"status": "VERIFIED"}
    rep_q = {} if privileged else {"status": "VERIFIED"}
    incidents = await db.incidents.find(inc_q, {"_id": 0}).to_list(200)
    reports = await db.field_reports.find(rep_q, {"_id": 0}).to_list(200)
    public_reports = await db.public_reports.find(rep_q, {"_id": 0}).to_list(200)
    notifications = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    zones = await db.emergency_zones.find({"active": True}, {"_id": 0}).to_list(20)
    actions = await db.government_actions.find({}, {"_id": 0}).sort("timestamp", -1).to_list(20)

    feed = []
    for i in incidents:
        feed.append({
            "kind": "INCIDENT", "id": i["id"], "title": i.get("title"), "severity": i.get("severity"),
            "location": i.get("location"), "source": i.get("source"), "status": i.get("status"),
            "created_at": i.get("created_at") or _iso_mins_ago(i.get("created_minutes_ago", 0)),
        })
    for r in reports:
        feed.append({
            "kind": "FIELD_REPORT", "id": r["id"], "title": r.get("description", "")[:80], "severity": r.get("severity"),
            "location": r.get("location"), "source": f"FIELD · {r.get('officer_name', 'Officer')}", "status": r.get("status"),
            "created_at": r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0)),
        })
    for r in public_reports:
        feed.append({
            "kind": "PUBLIC_REPORT", "id": r["id"], "title": r.get("description", "")[:80], "severity": r.get("severity", "INFO"),
            "location": r.get("location"), "source": f"PUBLIC · {r.get('reporter_name', 'Citizen')}", "status": r.get("status"),
            "created_at": r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0)),
        })
    for n in notifications:
        feed.append({
            "kind": "NOTIFICATION", "id": n["id"], "title": n.get("title"), "severity": n.get("severity", "INFO"),
            "location": "Broadcast to all users", "source": "GOVERNMENT", "status": "VERIFIED",
            "message": n.get("message"),
            "created_at": n.get("created_at"),
        })
    for z in zones:
        feed.append({
            "kind": "EMERGENCY", "id": z["id"],
            "title": f"Emergency declared: {z.get('name')} ({z.get('radius_km')} km radius)",
            "severity": "CRITICAL", "location": z.get("name"), "source": "GOVERNMENT", "status": "VERIFIED",
            "message": z.get("message"),
            "created_at": z.get("created_at"),
        })
    env_events = await db.environment_events.find({}, {"_id": 0}).to_list(100)
    env = _current_environment(env_events)
    now_iso_env = datetime.now(timezone.utc).isoformat()
    for r in env["rain"]:
        if r["level"] == "HEAVY":
            feed.append({
                "kind": "WEATHER", "id": r["id"],
                "title": f"Heavy rainfall: {r['name']} ({r['intensity_mm_h']} mm/h)",
                "severity": "HIGH", "location": r["name"], "source": "AI/WEATHER", "status": "VERIFIED",
                "message": f"Active rain cell, ~{r['radius_km']} km radius. Roads in the area may degrade.",
                "created_at": now_iso_env,
            })
    for l in env["landslides"]:
        if l["probability"] >= 0.6:
            feed.append({
                "kind": "HAZARD", "id": l["id"],
                "title": f"Landslide watch: {l['name']} ({l['slide_type'].replace('_', ' ').title()}, {int(l['probability'] * 100)}%)",
                "severity": "HIGH", "location": l["name"], "source": "AI", "status": "VERIFIED",
                "created_at": now_iso_env,
            })
    for a in actions:
        feed.append({
            "kind": "GOVERNMENT_ACTION", "id": a["id"],
            "title": f"{a.get('official_name', 'Official')} set {a.get('target_name', a.get('target_id'))}: {a.get('old_state')} → {a.get('new_state')}",
            "severity": "GOV", "location": a.get("target_name"), "source": "GOVERNMENT", "status": "VERIFIED",
            "created_at": a.get("timestamp"),
        })
    feed.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return feed


@api.get("/public/advisories")
async def public_advisories(user: dict = Depends(get_current_user)):
    roads = await db.roads.find({"status": {"$nin": ["OPEN", "UNKNOWN"]}}, {"_id": 0}).to_list(200)
    incidents = await db.incidents.find({"status": "VERIFIED"}, {"_id": 0}).to_list(100)
    verified_reports = await db.field_reports.find({"status": "VERIFIED"}, {"_id": 0}).to_list(100)
    for i in incidents:
        if "created_at" not in i:
            i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)
    for r in verified_reports:
        if "created_at" not in r:
            r["created_at"] = _iso_mins_ago(r.get("created_minutes_ago", 0))
        r.pop("created_minutes_ago", None)
    return {
        "provenance": "DEMO",
        "road_advisories": [
            {"id": r["id"], "name": r["name"], "district": r.get("district"), "status": r["status"],
             "reason": r.get("status_reason"), "expected_duration": r.get("expected_duration"),
             "updated_at": r.get("updated_at")}
            for r in roads
        ],
        "verified_incidents": incidents,
        "verified_field_reports": verified_reports,
    }


# =============================
# Public reports, government notifications, emergency zones
# =============================

class PublicReportCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    description: str = Field(min_length=5, max_length=1000)
    road_id: Optional[str] = None
    lat: float
    lng: float
    severity: str = "INFO"


@api.post("/public/reports", status_code=201)
async def create_public_report(body: PublicReportCreate, user: dict = Depends(get_current_user)):
    ban = user.get("report_ban_until")
    if ban:
        try:
            ban_dt = datetime.fromisoformat(ban)
            if ban_dt.tzinfo is None:
                ban_dt = ban_dt.replace(tzinfo=timezone.utc)
            if ban_dt > datetime.now(timezone.utc):
                hours_left = round((ban_dt - datetime.now(timezone.utc)).total_seconds() / 3600, 1)
                raise HTTPException(status_code=403, detail=f"Reporting suspended for 24h after a rejected report. Try again in ~{hours_left}h.")
        except ValueError:
            pass
    rtype = body.type.upper()
    if rtype not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(REPORT_TYPES)}")
    severity = body.severity.upper() if body.severity else "INFO"
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = "Reported location"
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": f"PR-{uuid.uuid4().hex[:6].upper()}",
        "reporter_email": user["email"],
        "reporter_name": user.get("name"),
        "type": rtype,
        "description": body.description,
        "road_id": body.road_id,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "severity": severity,
        "status": "PENDING",  # becomes VERIFIED only after gov/field verification
        "created_at": now_iso,
        "source": "PUBLIC",
    }
    await db.public_reports.insert_one({**report})
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": rtype if rtype in ("LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT") else "UNKNOWN",
        "severity": severity,
        "title": body.description[:80],
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "PUBLIC",
        "confidence": 40,
        "status": "UNVERIFIED",
        "created_at": now_iso,
        "source_tag": "PUBLIC_REPORT",
        "public_report_id": report["id"],
    }
    await db.incidents.insert_one({**incident})
    await manager.broadcast({"type": "PUBLIC_REPORT", "id": report["id"], "title": report["description"][:80]})
    report.pop("_id", None)
    return report


@api.get("/public/reports")
async def list_my_public_reports(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in GOVERNMENT_ROLES else {"reporter_email": user["email"]}
    reports = await db.public_reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return reports


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5, max_length=1000)
    severity: str = "INFO"


@api.post("/notifications", status_code=201)
async def create_notification(body: NotificationCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    severity = body.severity.upper()
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")
    now_iso = datetime.now(timezone.utc).isoformat()
    notif = {
        "id": f"NT-{uuid.uuid4().hex[:6].upper()}",
        "title": body.title,
        "message": body.message,
        "severity": severity,
        "issued_by": user["email"],
        "issued_by_name": user.get("name"),
        "created_at": now_iso,
    }
    await db.notifications.insert_one({**notif})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "NOTIFICATION_BROADCAST", "target_type": "all_users", "target_id": "all",
        "target_name": body.title, "old_state": None, "new_state": severity,
        "reason": body.message[:200], "timestamp": now_iso,
    })
    await manager.broadcast({"type": "NOTIFICATION", "id": notif["id"], "title": notif["title"], "severity": severity, "message": notif["message"]})
    notif.pop("_id", None)
    return notif


@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)


class EmergencyZoneCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=3, max_length=200)
    lat: float
    lng: float
    radius_km: float = Field(gt=0.1, le=200)
    message: str = Field(min_length=5, max_length=1000)


@api.post("/emergency-zones", status_code=201)
async def create_emergency_zone(body: EmergencyZoneCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    now_iso = datetime.now(timezone.utc).isoformat()
    zone = {
        "id": f"EZ-{uuid.uuid4().hex[:6].upper()}",
        "name": body.name,
        "lat": body.lat,
        "lng": body.lng,
        "radius_km": body.radius_km,
        "message": body.message,
        "active": True,
        "declared_by": user["email"],
        "declared_by_name": user.get("name"),
        "created_at": now_iso,
    }
    await db.emergency_zones.insert_one({**zone})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "EMERGENCY_DECLARED", "target_type": "zone", "target_id": zone["id"],
        "target_name": body.name, "old_state": None, "new_state": f"{body.radius_km} km radius",
        "reason": body.message[:200], "timestamp": now_iso,
    })
    await manager.broadcast({"type": "EMERGENCY_DECLARED", "id": zone["id"], "name": zone["name"], "radius_km": zone["radius_km"], "message": zone["message"]})
    zone.pop("_id", None)
    return zone


@api.get("/emergency-zones")
async def list_emergency_zones(user: dict = Depends(get_current_user)):
    return await db.emergency_zones.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(50)


# =============================
# Direct incident creation, vehicle registration, accidents, emergency end
# =============================

INCIDENT_CREATOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}
VEHICLE_CREATOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER", "LOGISTICS_OPERATOR"}


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    title: str = Field(min_length=5, max_length=200)
    road_id: Optional[str] = None
    location: Optional[str] = None
    lat: float
    lng: float
    severity: str


@api.post("/incidents", status_code=201)
async def create_incident(body: IncidentCreate, user: dict = Depends(get_current_user)):
    """Government officials and field officers create incidents directly — broadcast to all roles immediately."""
    if user["role"] not in INCIDENT_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    itype = body.type.upper()
    severity = body.severity.upper()
    valid_types = REPORT_TYPES | {"TRAFFIC", "WEATHER", "UNKNOWN"}
    if itype not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(valid_types)}")
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = body.location
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]
    if not location:
        location = "Specified location"

    is_gov = user["role"] in GOVERNMENT_ROLES
    now_iso = datetime.now(timezone.utc).isoformat()
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": itype,
        "severity": severity,
        "title": body.title,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "GOVERNMENT" if is_gov else "FIELD",
        "confidence": 100 if is_gov else 90,
        "status": "VERIFIED",  # trusted roles broadcast immediately
        "created_at": now_iso,
        "verified_by": user["email"],
        "verified_at": now_iso,
    }
    await db.incidents.insert_one({**incident})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "INCIDENT_CREATED", "target_type": "incident", "target_id": incident["id"],
        "target_name": body.title, "old_state": None, "new_state": "VERIFIED",
        "reason": f"Created by {'government official' if is_gov else 'field officer'}", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_CREATED", "id": incident["id"], "title": incident["title"], "severity": severity, "source": incident["source"]})
    incident.pop("_id", None)
    return incident


@api.get("/accidents")
async def list_accidents(user: dict = Depends(get_current_user)):
    """Verified accidents only — shown to public and logistics after field/gov verification."""
    incidents = await db.incidents.find(
        {"type": "ACCIDENT", "status": {"$in": ["VERIFIED", "PROVISIONALLY_BLOCKED"]}}, {"_id": 0}
    ).to_list(100)
    for i in incidents:
        if "created_at" not in i:
            i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)
    incidents.sort(key=lambda x: x["created_at"], reverse=True)
    return incidents


@api.patch("/emergency-zones/{zone_id}/end")
async def end_emergency_zone(zone_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    zone = await db.emergency_zones.find_one({"id": zone_id}, {"_id": 0})
    if not zone:
        raise HTTPException(status_code=404, detail="Emergency zone not found")
    if not zone.get("active"):
        raise HTTPException(status_code=400, detail="Emergency already ended")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.emergency_zones.update_one({"id": zone_id}, {"$set": {"active": False, "ended_by": user["email"], "ended_at": now_iso}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "EMERGENCY_ENDED", "target_type": "zone", "target_id": zone_id,
        "target_name": zone.get("name"), "old_state": "ACTIVE", "new_state": "ENDED",
        "reason": "Emergency lifted", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "EMERGENCY_ENDED", "id": zone_id, "name": zone.get("name")})
    return {"id": zone_id, "active": False}


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    number: str = Field(min_length=3, max_length=20)
    type: str
    lat: float
    lng: float
    destination: Optional[str] = None
    commodity: Optional[str] = None


@api.post("/vehicles", status_code=201)
async def create_vehicle(body: VehicleCreate, user: dict = Depends(get_current_user)):
    """Field officers (and government/logistics) can register vehicles on the network."""
    if user["role"] not in VEHICLE_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    vtype = body.type.upper()
    if vtype not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    number = body.number.strip().upper()
    if await db.vehicles.find_one({"number": number}):
        raise HTTPException(status_code=400, detail=f"Vehicle {number} already registered")
    now_iso = datetime.now(timezone.utc).isoformat()
    vehicle = {
        "id": f"veh-{uuid.uuid4().hex[:6]}",
        "number": number,
        "type": vtype,
        "lat": body.lat,
        "lng": body.lng,
        "heading": 0,
        "speed": 0,
        "status": "IDLE",
        "destination": body.destination or "—",
        "eta_minutes": None,
        "risk": 10,
        "commodity": body.commodity.upper() if body.commodity else None,
        "added_by": user["email"],
        "created_at": now_iso,
        "source": "FIELD" if user["role"] == "FIELD_OFFICER" else "GOVERNMENT",
    }
    await db.vehicles.insert_one({**vehicle})
    await manager.broadcast({"type": "VEHICLE_ADDED", "id": vehicle["id"], "number": number})
    vehicle.pop("_id", None)
    return vehicle


# =============================
# Driver trips + push rerouting
# =============================

class TripCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    origin: str
    destination: str
    vehicle_type: str = "TRUCK"


@api.post("/trips", status_code=201)
async def start_trip(body: TripCreate, user: dict = Depends(get_current_user)):
    origin = body.origin.strip().lower()
    destination = body.destination.strip().lower()
    if origin not in NER_PLACES or destination not in NER_PLACES:
        raise HTTPException(status_code=400, detail=f"Unknown place. Valid: {sorted(NER_PLACES.keys())}")
    if origin == destination:
        raise HTTPException(status_code=400, detail="Origin and destination must be different")
    vehicle = body.vehicle_type.upper()
    if vehicle not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid vehicle type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    route = await compute_route(origin, destination, vehicle)
    trip = {
        "id": f"TRIP-{uuid.uuid4().hex[:6].upper()}",
        "driver_email": user["email"],
        "driver_name": user.get("name"),
        "origin": origin,
        "destination": destination,
        "vehicle_type": vehicle,
        "status": "ACTIVE",
        "road_ids": route["recommended_route"].get("road_ids", []),
        "route": route,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.trips.insert_one({**trip})
    trip.pop("_id", None)
    return trip


@api.get("/trips")
async def list_trips(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in GOVERNMENT_ROLES else {"driver_email": user["email"]}
    return await db.trips.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)


@api.patch("/trips/{trip_id}/end")
async def end_trip(trip_id: str, user: dict = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip["driver_email"] != user["email"] and user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    await db.trips.update_one({"id": trip_id}, {"$set": {"status": "ENDED", "ended_at": datetime.now(timezone.utc).isoformat()}})
    return {"id": trip_id, "status": "ENDED"}


# =============================
# Trips monitoring (gov/field only) + AI escalation auto-block pipeline
# =============================

TRIPS_MONITOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}
AI_ESCALATION_THRESHOLD = 0.75
AI_ESCALATION_WINDOW_MIN = 5


def _trip_live_position(trip, now):
    route = trip.get("route", {}).get("recommended_route", {})
    poly = route.get("polyline") or []
    eta = route.get("eta_minutes") or 60
    try:
        created_dt = datetime.fromisoformat(trip["created_at"])
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        elapsed = (now - created_dt).total_seconds() / 60.0
    except Exception:
        elapsed = 0
    progress = min(0.95, max(0.0, elapsed / max(eta, 1)))
    if poly:
        idx = min(len(poly) - 1, int(progress * (len(poly) - 1)))
        lng, lat = poly[idx]
    else:
        lng, lat = NER_PLACES.get(trip["origin"], (0, 0))
    return progress, lat, lng


@api.get("/trips/summary")
async def trips_summary(user: dict = Depends(get_current_user)):
    """Live trip positions + per-corridor counts — government and field roles only."""
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    trips = await db.trips.find({"status": "ACTIVE"}, {"_id": 0}).to_list(100)
    now = datetime.now(timezone.utc)
    by_road = {}
    out = []
    for t in trips:
        progress, lat, lng = _trip_live_position(t, now)
        out.append({
            "id": t["id"], "driver_name": t.get("driver_name"), "driver_email": t["driver_email"],
            "origin": t["origin"], "destination": t["destination"], "vehicle_type": t["vehicle_type"],
            "progress": round(progress, 2), "current_lat": lat, "current_lng": lng,
            "eta_minutes": t.get("route", {}).get("recommended_route", {}).get("eta_minutes"),
            "reroute_reason": t.get("reroute_reason"),
        })
        for rid in t.get("road_ids", []):
            by_road.setdefault(rid, {"count": 0, "vehicles": []})
            by_road[rid]["count"] += 1
            by_road[rid]["vehicles"].append(t["vehicle_type"])
    road_names = {r["id"]: r["name"] for r in await db.roads.find({}, {"_id": 0}).to_list(1000)}
    by_road_named = {rid: {"name": road_names.get(rid, rid), **v} for rid, v in by_road.items()}
    return {"active_count": len(trips), "by_road": by_road_named, "trips": out}


async def _evaluate_escalations():
    """Create pending escalations for corridors crossing the hazard threshold and
    auto-block roads whose escalation went unanswered for AI_ESCALATION_WINDOW_MIN minutes."""
    now = datetime.now(timezone.utc)
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    for r in roads:
        if r["status"] in ("BLOCKED", "GOVERNMENT_CLOSED"):
            continue
        feats = CORRIDOR_FEATURES.get(r["id"], {})
        if not feats:
            continue
        flood = predict_flood(feats.get("flood", {}))["flood_probability"]
        land = predict_landslide(feats.get("landslide", {}))["landslide_probability"]
        hazard, prob = ("FLOOD", flood) if flood >= land else ("LANDSLIDE", land)
        if prob >= AI_ESCALATION_THRESHOLD:
            recent = await db.ai_escalations.find_one({"road_id": r["id"], "status": {"$in": ["PENDING", "ACKED"]}})
            if not recent:
                esc = {
                    "id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
                    "road_id": r["id"], "road_name": r["name"], "hazard": hazard,
                    "probability": prob, "status": "PENDING",
                    "created_at": now.isoformat(),
                    "deadline_at": (now + timedelta(minutes=AI_ESCALATION_WINDOW_MIN)).isoformat(),
                }
                await db.ai_escalations.insert_one({**esc})
                esc.pop("_id", None)
                await manager.broadcast({
                    "type": "AI_ESCALATION", "id": esc["id"], "road_name": esc["road_name"],
                    "hazard": hazard, "probability": prob, "deadline_at": esc["deadline_at"],
                })
    # sweep: auto-block expired pending escalations
    expired = await db.ai_escalations.find({"status": "PENDING"}).to_list(50)
    for e in expired:
        try:
            deadline = datetime.fromisoformat(e["deadline_at"])
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if deadline <= now:
            now_iso = now.isoformat()
            road = await db.roads.find_one({"id": e["road_id"]}, {"_id": 0})
            if road and road["status"] not in ("BLOCKED", "GOVERNMENT_CLOSED"):
                reason = f"Auto-blocked: AI {e['hazard'].lower()} risk {int(e['probability'] * 100)}% unanswered for {AI_ESCALATION_WINDOW_MIN} min"
                await db.roads.update_one({"id": e["road_id"]}, {"$set": {
                    "status": "BLOCKED", "status_reason": reason,
                    "updated_at": now_iso, "updated_by": "neris-ai",
                }})
                await db.government_actions.insert_one({
                    "id": str(uuid.uuid4()), "official_id": "neris-ai", "official_email": "ai@neris.system",
                    "official_name": "NERIS AI", "action_type": "ROAD_AUTO_BLOCKED", "target_type": "road",
                    "target_id": e["road_id"], "target_name": e["road_name"],
                    "old_state": road["status"], "new_state": "BLOCKED", "reason": reason, "timestamp": now_iso,
                })
                await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": e["road_id"], "status": "BLOCKED", "road_name": e["road_name"]})
                await _reroute_trips_on_road(e["road_id"], e["road_name"], "BLOCKED")
            await db.ai_escalations.update_one({"id": e["id"]}, {"$set": {"status": "AUTO_BLOCKED"}})


@api.get("/ai/escalations")
async def list_escalations(user: dict = Depends(get_current_user)):
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    await _evaluate_escalations()
    rows = await db.ai_escalations.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"threshold": AI_ESCALATION_THRESHOLD, "window_minutes": AI_ESCALATION_WINDOW_MIN, "escalations": rows}


class EscalationAck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str


@api.post("/ai/escalations/{esc_id}/ack")
async def ack_escalation(esc_id: str, body: EscalationAck, user: dict = Depends(get_current_user)):
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    esc = await db.ai_escalations.find_one({"id": esc_id})
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Escalation already handled ({esc['status']})")
    now_iso = datetime.now(timezone.utc).isoformat()
    if body.action == "BLOCK_NOW":
        reason = f"Blocked by {user.get('name')}: AI {esc['hazard'].lower()} risk {int(esc['probability'] * 100)}%"
        road = await db.roads.find_one({"id": esc["road_id"]}, {"_id": 0})
        if road:
            await db.roads.update_one({"id": esc["road_id"]}, {"$set": {
                "status": "BLOCKED", "status_reason": reason, "updated_at": now_iso, "updated_by": user["email"],
            }})
            await db.government_actions.insert_one({
                "id": str(uuid.uuid4()), "official_id": user["id"], "official_email": user["email"],
                "official_name": user.get("name"), "action_type": "ROAD_STATUS_CHANGE", "target_type": "road",
                "target_id": esc["road_id"], "target_name": esc["road_name"],
                "old_state": road["status"], "new_state": "BLOCKED", "reason": reason, "timestamp": now_iso,
            })
            await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": esc["road_id"], "status": "BLOCKED", "road_name": esc["road_name"]})
            await _reroute_trips_on_road(esc["road_id"], esc["road_name"], "BLOCKED")
        await db.ai_escalations.update_one({"id": esc_id}, {"$set": {"status": "BLOCKED_MANUAL", "acked_by": user["email"], "acked_at": now_iso}})
        return {"id": esc_id, "status": "BLOCKED_MANUAL"}
    if body.action == "MONITOR":
        await db.ai_escalations.update_one({"id": esc_id}, {"$set": {"status": "ACKED", "acked_by": user["email"], "acked_at": now_iso}})
        return {"id": esc_id, "status": "ACKED"}
    raise HTTPException(status_code=400, detail="action must be MONITOR or BLOCK_NOW")


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
