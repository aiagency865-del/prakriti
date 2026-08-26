import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.database import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MIN = 60 * 8  # 8 hours

security = HTTPBearer(auto_error=False)

# Role sets
GOVERNMENT_ROLES = {"SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"}
FIELD_ROLES = {"FIELD_OFFICER", "DRIVER", "SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"}
VERIFY_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}
TRIPS_MONITOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}
REPORT_TYPES = {"LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT", "BLOCKAGE", "OTHER"}
SEVERITIES = {"INFO", "WARNING", "HIGH", "CRITICAL"}
ROAD_STATUSES = {"OPEN", "AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED", "UNKNOWN"}


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
