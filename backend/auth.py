"""Authentication utilities: bcrypt + JWT + user model + admin seeding."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 24 * 30  # 30-day session


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- MODELS ----------
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str = ""
    role: str = "owner"   # "admin" | "owner"
    wallet_balance: int = 0
    created_at: str = Field(default_factory=_now_iso)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str = ""
    role: str
    wallet_balance: int
    created_at: str


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = ""


class WalletTopUpPayload(BaseModel):
    user_id: str
    amount: int
    note: Optional[str] = ""


# ---------- HASH + JWT ----------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:  # noqa: BLE001
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])


# ---------- FASTAPI DEPENDENCIES ----------
def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("access_token")


def _db_from_request(request: Request):
    return request.app.state.db


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = _extract_token(request)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    db = _db_from_request(request)
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


# ---------- SEED ADMIN ----------
async def seed_admin(db) -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    name = os.environ.get("ADMIN_NAME", "Admin")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        u = User(email=email, name=name, role="admin", wallet_balance=10000)
        doc = u.model_dump()
        doc["password_hash"] = hash_password(password)
        await db.users.insert_one(doc)
    else:
        if not verify_password(password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"email": email}, {"$set": {"password_hash": hash_password(password)}}
            )
        if existing.get("role") != "admin":
            await db.users.update_one({"email": email}, {"$set": {"role": "admin"}})
