import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from core.database import db
from core.security import create_token, get_current_user, public_user, verify_password
from pydantic import BaseModel, ConfigDict, EmailStr

router = APIRouter()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.get("/")
async def root():
    return {"service": "NERIS", "status": "ok"}


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.get("is_active", True):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Account is inactive")
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": public_user(user)}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.get("/auth/demo-accounts")
async def demo_accounts():
    """Return demo account emails (never passwords over API) for the login page picker."""
    return [
        {"role": "GOVERNMENT_ADMIN", "label": "Government Admin", "email": "gov.admin@neris.demo"},
        {"role": "GOVERNMENT_OFFICER", "label": "Government Officer", "email": "gov.officer@neris.demo"},
        {"role": "LOGISTICS_OPERATOR", "label": "Logistics Operator", "email": "logistics@neris.demo"},
        {"role": "FIELD_OFFICER", "label": "Field Officer", "email": "field@neris.demo"},
        {"role": "PUBLIC_USER", "label": "Public User", "email": "public@neris.demo"},
        {"role": "DRIVER", "label": "Driver (via Logistics)", "email": "driver@neris.demo"},
    ]
