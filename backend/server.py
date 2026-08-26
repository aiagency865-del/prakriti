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
