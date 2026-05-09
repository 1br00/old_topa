"""xss0r SaaS Backend — FastAPI server.

Provides:
- JWT email/password auth (register, login, logout, refresh, forgot/reset password)
- Emergent-managed Google OAuth (session_id exchange)
- Unified user session (access_token | session_token cookie | Bearer)
- License + API key + HWID activations + scan history
- Coupons (admin CRUD, user redeem -> extends license)
- Builds (admin upload to Emergent object storage, user download via backend)
- Admin endpoints (stats, users, ban/unban, coupons, builds)
- Demo seed: admin user, test user with Pro license, sample plans, sample coupons,
  sample builds (metadata only — actual files uploaded only when admin uploads).
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import jwt
import requests
import stripe
from fastapi import (
    FastAPI, APIRouter, HTTPException, Depends, Request, Response,
    UploadFile, File, Form, Header
)
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
import io

import email_service as email_svc
import paypal_service as paypal_svc

# ---------------- Config ----------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@xss0r.io")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@xss0r2026")
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", ADMIN_EMAIL).split(",")
    if e.strip()
}
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "xss0r-saas")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_AUTH_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)

# Stripe
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
stripe.api_key = STRIPE_API_KEY
if STRIPE_API_KEY and "sk_test_emergent" in STRIPE_API_KEY:
    stripe.api_base = "https://integrations.emergentagent.com/stripe"

# Plan -> price config. amount_cents charged per billing cycle.
# duration = how long one cycle covers; max_activations = devices.
PLAN_PRICES = {
    "basic": {
        "name": "xss0r Basic",
        "amount_cents": 1999,
        "max_activations": 3,
        "interval": "month", "interval_count": 1, "duration_days": 30,
    },
    "pro": {
        "name": "xss0r Pro",
        "amount_cents": 4999,
        "max_activations": 3,
        "interval": "month", "interval_count": 1, "duration_days": 30,
    },
    "diamond": {
        "name": "xss0r Diamond",
        "amount_cents": 8999,
        "max_activations": 4,
        "interval": "month", "interval_count": 3, "duration_days": 90,
    },
    "golden": {
        "name": "xss0r Golden",
        "amount_cents": 11999,
        "max_activations": 5,
        "interval": "month", "interval_count": 6, "duration_days": 180,
    },
    "business": {
        "name": "xss0r Business",
        "amount_cents": 33999,
        "max_activations": 18,
        "interval": "year", "interval_count": 1, "duration_days": 365,
    },
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("xss0r")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="xss0r SaaS API")
api = APIRouter(prefix="/api")

# ---------------- Helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": now_utc() + timedelta(minutes=60),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": now_utc() + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def set_jwt_cookies(response: Response, access: str, refresh: str) -> None:
    # samesite=none + secure=true so cookies work in cross-site preview environment
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="none", max_age=60 * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True,
                        samesite="none", max_age=7 * 24 * 60 * 60, path="/")


def clear_auth_cookies(response: Response) -> None:
    for c in ("access_token", "refresh_token", "session_token"):
        response.delete_cookie(c, path="/")


# ---------------- Object Storage ----------------
_storage_key: Optional[str] = None


def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY missing; storage disabled")
        return None
    try:
        r = requests.post(f"{STORAGE_URL}/init",
                          json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        logger.info("Object storage initialized")
        return _storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type},
                     data=data, timeout=300)
    r.raise_for_status()
    return r.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key}, timeout=120)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


# ---------------- Auth dependency ----------------
async def get_current_user(request: Request) -> dict:
    # 1) JWT access_token cookie
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
                if user and not user.get("banned"):
                    return user
        except jwt.PyJWTError:
            pass

    # 2) Authorization Bearer (JWT)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        bearer = auth[7:]
        try:
            payload = jwt.decode(bearer, JWT_SECRET, algorithms=[JWT_ALG])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
                if user and not user.get("banned"):
                    return user
        except jwt.PyJWTError:
            pass

    # 3) Emergent session_token cookie or bearer
    session_token = request.cookies.get("session_token")
    if not session_token and auth.startswith("Bearer "):
        session_token = auth[7:]
    if session_token:
        sess = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if sess:
            exp = sess.get("expires_at")
            if isinstance(exp, str):
                try:
                    exp = datetime.fromisoformat(exp)
                except Exception:
                    exp = None
            if exp and (exp.tzinfo is None):
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp > now_utc():
                user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
                if user and not user.get("banned"):
                    return user

    raise HTTPException(status_code=401, detail="Not authenticated")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ---------------- Models ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=6)


class GoogleSessionIn(BaseModel):
    session_id: str


class CouponIn(BaseModel):
    code: str
    percent_off: int = Field(ge=0, le=100)
    max_uses: int = Field(ge=1, default=100)
    expires_at: Optional[str] = None
    extends_days: int = Field(ge=0, default=30)


class CouponRedeemIn(BaseModel):
    code: str


class BanIn(BaseModel):
    banned: bool


# ---------------- Auth endpoints ----------------
async def _ensure_license(user_id: str, plan: str = "free", days: int = 0) -> dict:
    existing = await db.licenses.find_one({"user_id": user_id}, {"_id": 0})
    if existing:
        return existing
    expiry = now_utc() + timedelta(days=days) if days > 0 else None
    cfg = PLAN_PRICES.get(plan, {})
    max_act = cfg.get("max_activations", 1) if plan != "free" else 1
    lic = {
        "license_id": f"lic_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "plan": plan,
        "status": "active" if (days > 0 or plan == "free") else "inactive",
        "expires_at": iso(expiry) if expiry else None,
        "max_activations": max_act,
        "created_at": iso(now_utc()),
    }
    await db.licenses.insert_one(lic)
    api_key = f"xss0r_{secrets.token_urlsafe(24)}"
    await db.api_keys.insert_one({
        "key_id": f"key_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "api_key": api_key,
        "created_at": iso(now_utc()),
    })
    return lic


@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "name": payload.name,
        "password_hash": hash_password(payload.password),
        "role": "user",
        "auth_provider": "password",
        "banned": False,
        "email_verified": False,
        "picture": None,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    await _ensure_license(user_id, plan="free", days=14)

    # Email: send welcome + verification link
    verify_token = secrets.token_urlsafe(32)
    await db.email_verify_tokens.insert_one({
        "token": verify_token,
        "user_id": user_id,
        "expires_at": now_utc() + timedelta(days=7),
        "used": False,
    })
    verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
    dashboard_url = f"{FRONTEND_URL}/dashboard"
    try:
        s, h, t = email_svc.tpl_welcome(payload.name, dashboard_url)
        await email_svc.send_email(email, s, h, t)
        s, h, t = email_svc.tpl_verify_email(payload.name, verify_link)
        await email_svc.send_email(email, s, h, t)
    except Exception as e:
        logger.error(f"register email send failed: {e}")

    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_jwt_cookies(response, access, refresh)
    return {"user_id": user_id, "email": email, "name": payload.name, "role": "user"}


@api.post("/auth/verify-email")
async def verify_email(payload: dict):
    token = payload.get("token", "")
    rec = await db.email_verify_tokens.find_one({"token": token, "used": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or used token")
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc():
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one({"user_id": rec["user_id"]}, {"$set": {"email_verified": True}})
    await db.email_verify_tokens.update_one({"token": token}, {"$set": {"used": True}})
    return {"ok": True}


@api.post("/auth/resend-verification")
async def resend_verification(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    token = secrets.token_urlsafe(32)
    await db.email_verify_tokens.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "expires_at": now_utc() + timedelta(days=7),
        "used": False,
    })
    link = f"{FRONTEND_URL}/verify-email?token={token}"
    s, h, t = email_svc.tpl_verify_email(user.get("name", ""), link)
    await email_svc.send_email(user["email"], s, h, t)
    return {"ok": True}


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response, request: Request):
    email = payload.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempts_doc = await db.login_attempts.find_one({"identifier": identifier})
    if attempts_doc and attempts_doc.get("count", 0) >= 5:
        last = attempts_doc.get("last_attempt")
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last)
            except Exception:
                last = None
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last and (now_utc() - last) < timedelta(minutes=15):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"last_attempt": iso(now_utc())}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="Account banned")

    await db.login_attempts.delete_one({"identifier": identifier})
    access = create_access_token(user["user_id"], email)
    refresh = create_refresh_token(user["user_id"])
    set_jwt_cookies(response, access, refresh)
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "picture": user.get("picture"),
    }


@api.post("/auth/logout")
async def logout(response: Response, request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "picture": user.get("picture"),
        "auth_provider": user.get("auth_provider", "password"),
    }


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(rt, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user or user.get("banned"):
            raise HTTPException(status_code=401, detail="User unavailable")
        access = create_access_token(user["user_id"], user["email"])
        response.set_cookie("access_token", access, httponly=True, secure=True,
                            samesite="none", max_age=60 * 60, path="/")
        return {"ok": True}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@api.post("/auth/forgot-password")
async def forgot_password(payload: ForgotIn):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    # Always return ok to avoid user enumeration
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "expires_at": now_utc() + timedelta(hours=1),
            "used": False,
        })
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
        logger.info(f"[PASSWORD RESET] {email} -> {reset_link}")
        subject, html, text = email_svc.tpl_password_reset(user.get("name", ""), reset_link)
        await email_svc.send_email(email, subject, html, text)
    return {"ok": True, "message": "If the email exists, a reset link has been sent."}


@api.post("/auth/reset-password")
async def reset_password(payload: ResetIn):
    rec = await db.password_reset_tokens.find_one({"token": payload.token, "used": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc():
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one({"user_id": rec["user_id"]},
                              {"$set": {"password_hash": hash_password(payload.password)}})
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    return {"ok": True}


@api.post("/auth/google/session")
async def google_session(payload: GoogleSessionIn, response: Response):
    """Exchange Emergent OAuth session_id for an app session."""
    try:
        r = requests.get(EMERGENT_AUTH_SESSION_URL,
                         headers={"X-Session-ID": payload.session_id}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Emergent session exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid session")

    email = (data.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned")

    user = await db.users.find_one({"email": email})
    desired_role = "admin" if email in ADMIN_EMAILS else "user"
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "picture": data.get("picture"),
            "role": desired_role,
            "auth_provider": "google",
            "banned": False,
            "created_at": iso(now_utc()),
        }
        await db.users.insert_one(user)
        # Admins get an effectively unlimited license; regular users get 14d trial
        if desired_role == "admin":
            await _ensure_license(user_id, plan="business", days=3650)
        else:
            await _ensure_license(user_id, plan="free", days=14)
    else:
        if user.get("banned"):
            raise HTTPException(status_code=403, detail="Account banned")
        update = {
            "name": data.get("name") or user.get("name"),
            "picture": data.get("picture") or user.get("picture"),
        }
        # Auto-promote whitelisted emails on every login (defense in depth)
        if email in ADMIN_EMAILS and user.get("role") != "admin":
            update["role"] = "admin"
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})

    session_token = data.get("session_token") or secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": now_utc() + timedelta(days=7),
        "created_at": now_utc(),
    })
    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", max_age=7 * 24 * 60 * 60, path="/")
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "picture": user.get("picture"),
        "role": user.get("role", "user"),
    }


# ---------------- License & user data ----------------
@api.get("/license/me")
async def my_license(user: dict = Depends(get_current_user)):
    lic = await db.licenses.find_one({"user_id": user["user_id"]}, {"_id": 0})
    api_key = await db.api_keys.find_one({"user_id": user["user_id"]}, {"_id": 0})
    activations = await db.hwid_activations.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)
    return {
        "license": lic,
        "api_key": api_key.get("api_key") if api_key else None,
        "activations": activations,
    }


@api.post("/license/regenerate-api-key")
async def regenerate_api_key(user: dict = Depends(get_current_user)):
    new_key = f"xss0r_{secrets.token_urlsafe(24)}"
    await db.api_keys.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"api_key": new_key, "rotated_at": iso(now_utc())}},
        upsert=True,
    )
    return {"api_key": new_key}


@api.post("/license/reset-hwid")
async def reset_hwid(user: dict = Depends(get_current_user)):
    res = await db.hwid_activations.delete_many({"user_id": user["user_id"]})
    return {"removed": res.deleted_count}


@api.get("/scans")
async def my_scans(user: dict = Depends(get_current_user)):
    scans = await db.scans.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return scans


# ---------------- Coupons ----------------
class CouponValidateIn(BaseModel):
    code: str
    plan: Optional[str] = None


@api.post("/coupons/validate")
async def coupons_validate(payload: CouponValidateIn):
    """Public endpoint — preview discount on a given plan before checkout."""
    coupon = await _fetch_valid_coupon(payload.code)
    plan = (payload.plan or "").lower()
    cfg = PLAN_PRICES.get(plan)
    discounted = _discounted_amount(cfg, coupon) if cfg else None
    return {
        "code": coupon["code"],
        "percent_off": coupon["percent_off"],
        "valid": True,
        "discounted_amount_cents": discounted,
        "discounted_amount_usd": (discounted / 100) if discounted is not None else None,
        "extends_days": coupon.get("extends_days"),
    }


@api.post("/coupons/redeem")
async def redeem_coupon(payload: CouponRedeemIn, user: dict = Depends(get_current_user)):
    code = payload.code.strip().upper()
    coupon = await db.coupons.find_one({"code": code}, {"_id": 0})
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    if coupon.get("used_count", 0) >= coupon.get("max_uses", 0):
        raise HTTPException(status_code=400, detail="Coupon exhausted")
    if coupon.get("expires_at"):
        exp = datetime.fromisoformat(coupon["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now_utc():
            raise HTTPException(status_code=400, detail="Coupon expired")
    redeem_log = await db.coupon_redemptions.find_one({"code": code, "user_id": user["user_id"]})
    if redeem_log:
        raise HTTPException(status_code=400, detail="Coupon already redeemed by this user")

    extends_days = coupon.get("extends_days", 30)
    lic = await db.licenses.find_one({"user_id": user["user_id"]}, {"_id": 0})
    base = now_utc()
    if lic and lic.get("expires_at"):
        cur = datetime.fromisoformat(lic["expires_at"])
        if cur.tzinfo is None:
            cur = cur.replace(tzinfo=timezone.utc)
        if cur > base:
            base = cur
    new_expiry = base + timedelta(days=extends_days)
    await db.licenses.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"plan": "pro", "status": "active", "expires_at": iso(new_expiry), "max_activations": 3}},
        upsert=False,
    )
    await db.coupons.update_one({"code": code}, {"$inc": {"used_count": 1}})
    await db.coupon_redemptions.insert_one({
        "code": code, "user_id": user["user_id"], "redeemed_at": iso(now_utc())
    })
    return {"ok": True, "new_expiry": iso(new_expiry), "extended_days": extends_days}


# ---------------- Builds (downloads) ----------------
@api.get("/builds")
async def list_builds(user: dict = Depends(get_current_user)):
    builds = await db.builds.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return builds


@api.get("/builds/{build_id}/download")
async def download_build(build_id: str, user: dict = Depends(get_current_user)):
    lic = await db.licenses.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not lic or lic.get("status") != "active":
        raise HTTPException(status_code=403, detail="Active license required")
    build = await db.builds.find_one({"build_id": build_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if not build.get("storage_path"):
        raise HTTPException(status_code=404, detail="Build file not uploaded")
    data, ctype = get_object(build["storage_path"])
    await db.builds.update_one({"build_id": build_id}, {"$inc": {"download_count": 1}})
    return StreamingResponse(io.BytesIO(data), media_type=build.get("content_type", ctype),
        headers={"Content-Disposition": f'attachment; filename="{build.get("filename","build.bin")}"'})


# ---------------- Admin ----------------
@api.get("/admin/stats")
async def admin_stats(user: dict = Depends(require_admin)):
    total_users = await db.users.count_documents({})
    active_licenses = await db.licenses.count_documents({"status": "active"})
    total_scans = await db.scans.count_documents({})
    total_coupons = await db.coupons.count_documents({})
    total_builds = await db.builds.count_documents({"is_deleted": {"$ne": True}})
    banned_users = await db.users.count_documents({"banned": True})
    downloads_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$download_count"}}}]
    dl_cursor = db.builds.aggregate(downloads_pipeline)
    total_downloads = 0
    async for d in dl_cursor:
        total_downloads = d.get("total") or 0
    return {
        "total_users": total_users,
        "active_licenses": active_licenses,
        "total_scans": total_scans,
        "total_coupons": total_coupons,
        "total_builds": total_builds,
        "banned_users": banned_users,
        "total_downloads": total_downloads,
    }


@api.get("/admin/users")
async def admin_users(user: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    if not users:
        return users
    # Batch-fetch licenses to avoid N+1 query
    user_ids = [u["user_id"] for u in users]
    licenses = await db.licenses.find({"user_id": {"$in": user_ids}}, {"_id": 0}).to_list(len(user_ids))
    lic_by_user = {l["user_id"]: l for l in licenses}
    for u in users:
        u["license"] = lic_by_user.get(u["user_id"])
    return users


@api.post("/admin/users/{user_id}/ban")
async def admin_ban(user_id: str, payload: BanIn, user: dict = Depends(require_admin)):
    res = await db.users.update_one({"user_id": user_id}, {"$set": {"banned": payload.banned}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@api.get("/admin/coupons")
async def admin_list_coupons(user: dict = Depends(require_admin)):
    return await db.coupons.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/admin/coupons")
async def admin_create_coupon(payload: CouponIn, user: dict = Depends(require_admin)):
    code = payload.code.strip().upper()
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    doc = {
        "coupon_id": f"cpn_{uuid.uuid4().hex[:10]}",
        "code": code,
        "percent_off": payload.percent_off,
        "max_uses": payload.max_uses,
        "used_count": 0,
        "expires_at": payload.expires_at,
        "extends_days": payload.extends_days,
        "created_at": iso(now_utc()),
    }
    await db.coupons.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/admin/coupons/{coupon_id}")
async def admin_delete_coupon(coupon_id: str, user: dict = Depends(require_admin)):
    res = await db.coupons.delete_one({"coupon_id": coupon_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"ok": True}


@api.get("/admin/builds")
async def admin_list_builds(user: dict = Depends(require_admin)):
    return await db.builds.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/admin/builds")
async def admin_upload_build(
    file: UploadFile = File(...),
    version: str = Form(...),
    platform: str = Form(...),
    changelog: str = Form(""),
    user: dict = Depends(require_admin),
):
    if platform not in ("windows", "linux", "macos"):
        raise HTTPException(status_code=400, detail="platform must be windows|linux|macos")
    data = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    storage_path = f"{APP_NAME}/builds/{platform}/{uuid.uuid4().hex}.{ext}"
    result = put_object(storage_path, data, file.content_type or "application/octet-stream")
    doc = {
        "build_id": f"bld_{uuid.uuid4().hex[:10]}",
        "version": version,
        "platform": platform,
        "changelog": changelog,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": result.get("size", len(data)),
        "storage_path": result["path"],
        "is_deleted": False,
        "download_count": 0,
        "uploaded_by": user["user_id"],
        "created_at": iso(now_utc()),
    }
    await db.builds.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/admin/builds/{build_id}")
async def admin_delete_build(build_id: str, user: dict = Depends(require_admin)):
    res = await db.builds.update_one({"build_id": build_id}, {"$set": {"is_deleted": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Build not found")
    return {"ok": True}


# ---------------- Admin: per-user management ----------------
class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None  # "user" | "admin"


class AdminAssignPlan(BaseModel):
    plan: str  # plan key from PLAN_PRICES
    duration_days: Optional[int] = None  # default = plan's duration_days


class AdminPasswordIn(BaseModel):
    new_password: str = Field(min_length=6)


class AdminContactIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    await db.users.delete_one({"user_id": user_id})
    await db.licenses.delete_many({"user_id": user_id})
    await db.api_keys.delete_many({"user_id": user_id})
    await db.hwid_activations.delete_many({"user_id": user_id})
    await db.scans.delete_many({"user_id": user_id})
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.password_reset_tokens.delete_many({"user_id": user_id})
    await db.email_verify_tokens.delete_many({"user_id": user_id})
    return {"ok": True}


@api.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: str, payload: AdminUserUpdate, user: dict = Depends(require_admin)):
    update = {}
    if payload.name is not None:
        update["name"] = payload.name
    if payload.email is not None:
        new_email = payload.email.lower()
        clash = await db.users.find_one({"email": new_email, "user_id": {"$ne": user_id}})
        if clash:
            raise HTTPException(status_code=400, detail="Email already in use")
        update["email"] = new_email
    if payload.role is not None:
        if payload.role not in ("user", "admin"):
            raise HTTPException(status_code=400, detail="Invalid role")
        update["role"] = payload.role
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await db.users.update_one({"user_id": user_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@api.post("/admin/users/{user_id}/assign-plan")
async def admin_assign_plan(user_id: str, payload: AdminAssignPlan, user: dict = Depends(require_admin)):
    plan = payload.plan.lower()
    if plan not in PLAN_PRICES and plan != "free":
        raise HTTPException(status_code=400, detail="Invalid plan")
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    cfg = PLAN_PRICES.get(plan, {})
    days = payload.duration_days if payload.duration_days is not None else cfg.get("duration_days", 30)
    expiry = now_utc() + timedelta(days=max(1, days))
    max_act = cfg.get("max_activations", 1) if plan != "free" else 1
    await db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": plan,
            "status": "active",
            "expires_at": iso(expiry),
            "max_activations": max_act,
            "payment_provider": "manual_admin",
        }},
        upsert=True,
    )
    return {"ok": True, "plan": plan, "expires_at": iso(expiry)}


@api.post("/admin/users/{user_id}/wipe-license")
async def admin_wipe_license(user_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    lic = await db.licenses.find_one({"user_id": user_id}, {"_id": 0})
    # Best-effort cancel of upstream subscriptions so admin doesn't keep paying
    if lic:
        stripe_sub = lic.get("stripe_subscription_id")
        if stripe_sub and STRIPE_API_KEY:
            try:
                stripe.Subscription.delete(stripe_sub)
            except Exception as e:
                logger.warning(f"Stripe cancel on wipe failed: {e}")
        paypal_sub = lic.get("paypal_subscription_id")
        if paypal_sub and paypal_svc.is_configured():
            try:
                paypal_svc.cancel_subscription(paypal_sub, "Admin wipe")
            except Exception as e:
                logger.warning(f"PayPal cancel on wipe failed: {e}")
    await db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": "free", "status": "inactive", "expires_at": None,
            "max_activations": 1,
        }, "$unset": {
            "stripe_subscription_id": "", "paypal_subscription_id": "", "payment_provider": "",
        }},
        upsert=True,
    )
    return {"ok": True}


@api.post("/admin/users/{user_id}/set-password")
async def admin_set_password(user_id: str, payload: AdminPasswordIn, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    return {"ok": True}


@api.get("/admin/users/{user_id}/transactions")
async def admin_user_transactions(user_id: str, user: dict = Depends(require_admin)):
    txns = await db.payment_transactions.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    total_paid_cents = sum(
        t.get("amount_cents", 0) for t in txns
        if t.get("payment_status") in ("paid", "active")
    )
    return {
        "transactions": txns,
        "total_spent_cents": total_paid_cents,
        "total_spent_usd": round(total_paid_cents / 100, 2),
        "count": len(txns),
    }


@api.post("/admin/users/{user_id}/contact")
async def admin_contact_user(user_id: str, payload: AdminContactIn, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    safe_msg = payload.message.replace("\n", "<br/>")
    html = f"""<!doctype html><html><body style="background:#0a0a0a;color:#f0f2f5;font-family:sans-serif;padding:40px">
<table cellpadding=0 cellspacing=0 width=560 style="margin:auto;background:#121212;border:1px solid rgba(255,255,255,.1)">
<tr><td style="padding:32px"><div style="font-family:monospace;color:#4da3ff;font-weight:700">▣ xss0r support</div>
<h1 style="font-family:monospace">{payload.subject}</h1>
<div style="color:#a0a6ad;line-height:1.6;font-size:14px">{safe_msg}</div>
<hr style="border:0;border-top:1px solid rgba(255,255,255,.1);margin:32px 0"/>
<p style="font-size:11px;color:#737373;font-family:monospace">— xss0r team</p>
</td></tr></table></body></html>"""
    res = await email_svc.send_email(target["email"], payload.subject, html, payload.message)
    return {"ok": True, "delivery": res}


# ---------------- Admin: payments + sales analytics ----------------
@api.get("/admin/payments/recent")
async def admin_recent_payments(limit: int = 20, user: dict = Depends(require_admin)):
    limit = max(1, min(100, limit))
    txns = await db.payment_transactions.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    user_ids = list({t["user_id"] for t in txns if t.get("user_id")})
    if user_ids:
        users = await db.users.find(
            {"user_id": {"$in": user_ids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}
        ).to_list(len(user_ids))
        umap = {u["user_id"]: u for u in users}
        for t in txns:
            u = umap.get(t.get("user_id")) or {}
            t["user_name"] = u.get("name")
            if not t.get("email"):
                t["email"] = u.get("email")
    return txns


@api.get("/admin/sales/summary")
async def admin_sales_summary(user: dict = Depends(require_admin)):
    paid_filter = {"payment_status": {"$in": ["paid", "active"]}}
    failed_filter = {"payment_status": {"$in": ["failed", "denied"]}}

    total_pipe = [{"$match": paid_filter},
                  {"$group": {"_id": None, "total": {"$sum": "$amount_cents"}, "count": {"$sum": 1}}}]
    total_doc = await db.payment_transactions.aggregate(total_pipe).to_list(1)
    total_cents = total_doc[0]["total"] if total_doc else 0
    total_count = total_doc[0]["count"] if total_doc else 0

    now = now_utc()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    async def sum_cents(since: datetime) -> int:
        pipe = [
            {"$match": {**paid_filter, "created_at": {"$gte": iso(since)}}},
            {"$group": {"_id": None, "s": {"$sum": "$amount_cents"}}}
        ]
        doc = await db.payment_transactions.aggregate(pipe).to_list(1)
        return doc[0]["s"] if doc else 0

    revenue_24h = await sum_cents(day_ago)
    revenue_7d = await sum_cents(week_ago)
    revenue_30d = await sum_cents(month_ago)
    revenue_365d = await sum_cents(year_ago)

    series_pipe = [
        {"$match": {**paid_filter, "created_at": {"$gte": iso(month_ago)}}},
        {"$project": {"date": {"$substr": ["$created_at", 0, 10]}, "amount_cents": 1}},
        {"$group": {"_id": "$date", "revenue": {"$sum": "$amount_cents"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    series_docs = await db.payment_transactions.aggregate(series_pipe).to_list(31)
    series = [{"date": d["_id"], "revenue_cents": d["revenue"], "count": d["count"]} for d in series_docs]

    prov_pipe = [
        {"$match": paid_filter},
        {"$group": {"_id": "$provider", "revenue": {"$sum": "$amount_cents"}, "count": {"$sum": 1}}},
    ]
    prov_docs = await db.payment_transactions.aggregate(prov_pipe).to_list(10)
    by_provider = [{"provider": p["_id"] or "unknown", "revenue_cents": p["revenue"], "count": p["count"]} for p in prov_docs]

    plan_pipe = [
        {"$match": paid_filter},
        {"$group": {"_id": "$plan", "revenue": {"$sum": "$amount_cents"}, "count": {"$sum": 1}}},
    ]
    plan_docs = await db.payment_transactions.aggregate(plan_pipe).to_list(20)
    by_plan = [{"plan": p["_id"] or "unknown", "revenue_cents": p["revenue"], "count": p["count"]} for p in plan_docs]

    failed_count = await db.payment_transactions.count_documents(failed_filter)

    return {
        "total_revenue_cents": total_cents,
        "total_revenue_usd": round(total_cents / 100, 2),
        "total_paid_count": total_count,
        "revenue_24h_cents": revenue_24h,
        "revenue_7d_cents": revenue_7d,
        "revenue_30d_cents": revenue_30d,
        "revenue_365d_cents": revenue_365d,
        "failed_count": failed_count,
        "series_daily_30d": series,
        "by_provider": by_provider,
        "by_plan": by_plan,
    }


@api.get("/admin/payments/failed")
async def admin_failed_payments(limit: int = 50, user: dict = Depends(require_admin)):
    txns = await db.payment_transactions.find(
        {"payment_status": {"$in": ["failed", "denied"]}}, {"_id": 0}
    ).sort("created_at", -1).to_list(min(limit, 200))
    return txns




# ---------------- Stripe subscriptions ----------------
class CheckoutIn(BaseModel):
    plan: str  # "basic" | "pro" | "diamond" | "golden" | "business"
    origin_url: str  # window.location.origin from frontend
    coupon_code: Optional[str] = None
    guest_email: Optional[EmailStr] = None  # for unauthenticated checkout


def _validate_coupon(code: str) -> tuple[Optional[dict], int]:
    """Return (coupon_doc, percent_off). percent_off is 0 if invalid/missing.
    Used synchronously where async lookup not ideal — caller does the actual fetch."""
    return None, 0


async def _fetch_valid_coupon(code: Optional[str]) -> Optional[dict]:
    if not code:
        return None
    coupon = await db.coupons.find_one({"code": code.strip().upper()}, {"_id": 0})
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    if coupon.get("used_count", 0) >= coupon.get("max_uses", 0):
        raise HTTPException(status_code=400, detail="Coupon exhausted")
    if coupon.get("expires_at"):
        try:
            exp = datetime.fromisoformat(coupon["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now_utc():
                raise HTTPException(status_code=400, detail="Coupon expired")
        except Exception:
            pass
    return coupon


async def _ensure_user_for_purchase(email: str, name: Optional[str] = None) -> dict:
    """Look up user by email or create a pending account for guest checkout."""
    email = email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if user:
        return user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    temp_password = secrets.token_urlsafe(20)  # user must reset
    doc = {
        "user_id": user_id,
        "email": email,
        "name": name or email.split("@")[0],
        "password_hash": hash_password(temp_password),
        "role": "user",
        "auth_provider": "purchase",
        "banned": False,
        "email_verified": False,
        "picture": None,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    await _ensure_license(user_id, plan="free", days=0)
    return {k: v for k, v in doc.items() if k != "password_hash"}


async def _send_purchase_welcome(user_id: str, email: str, name: str):
    """Send a welcome+set-password link after a successful guest purchase."""
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": user_id,
        "expires_at": now_utc() + timedelta(days=7),
        "used": False,
    })
    setup_link = f"{FRONTEND_URL}/reset-password?token={token}"
    subject = "Welcome to xss0r — set your password"
    body = (
        f"<p>Hi {name},</p><p>Thanks for subscribing to xss0r. Your account is ready.</p>"
        f"<p>Click the button below to set your password and access your dashboard.</p>"
    )
    html = f"""<!doctype html><html><body style="background:#0a0a0a;color:#f0f2f5;font-family:sans-serif;padding:40px">
<table cellpadding=0 cellspacing=0 width=560 style="margin:auto;background:#121212;border:1px solid rgba(255,255,255,.1)">
<tr><td style="padding:32px"><div style="font-family:monospace;color:#4da3ff;font-weight:700">▣ xss0r</div>
<h1 style="font-family:monospace">Welcome to xss0r</h1>{body}
<a href="{setup_link}" style="background:#4da3ff;color:#0a0a0a;padding:14px 28px;text-decoration:none;font-family:monospace;font-weight:700;display:inline-block;margin:24px 0">Set password</a>
<p style="font-size:12px;color:#737373">Or paste: {setup_link}</p>
</td></tr></table></body></html>"""
    await email_svc.send_email(email, subject, html, f"Set your password: {setup_link}")


def _discounted_amount(cfg: dict, coupon: Optional[dict]) -> int:
    if not coupon:
        return cfg["amount_cents"]
    pct = max(0, min(100, int(coupon.get("percent_off", 0))))
    return int(round(cfg["amount_cents"] * (100 - pct) / 100))


@api.post("/stripe/checkout")
async def stripe_checkout(payload: CheckoutIn, request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    plan = payload.plan.lower()
    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan")
    cfg = PLAN_PRICES[plan]
    coupon = await _fetch_valid_coupon(payload.coupon_code)
    amount = _discounted_amount(cfg, coupon)
    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing/cancel"

    # Resolve user — auth'd or guest
    try:
        user = await get_current_user(request)
    except HTTPException:
        if not payload.guest_email:
            raise HTTPException(status_code=401, detail="Authentication required (or pass guest_email)")
        user = await _ensure_user_for_purchase(payload.guest_email)

    try:
        product_name = cfg["name"]
        if coupon:
            product_name = f"{cfg['name']} ({coupon['percent_off']}% off — {coupon['code']})"
        session = stripe.checkout.Session.create(
            customer_email=user["email"],
            client_reference_id=user["user_id"],
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": product_name},
                    "unit_amount": amount,
                    "recurring": {
                        "interval": cfg["interval"],
                        "interval_count": cfg["interval_count"],
                    },
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user["user_id"],
                "plan": plan,
                "email": user["email"],
                "coupon_code": coupon["code"] if coupon else "",
            },
            subscription_data={
                "metadata": {
                    "user_id": user["user_id"],
                    "plan": plan,
                    "coupon_code": coupon["code"] if coupon else "",
                }
            },
        )

        await db.payment_transactions.insert_one({
            "provider": "stripe",
            "session_id": session.id,
            "user_id": user["user_id"],
            "email": user["email"],
            "plan": plan,
            "amount_cents": amount,
            "original_amount_cents": cfg["amount_cents"],
            "coupon_code": coupon["code"] if coupon else None,
            "currency": "usd",
            "payment_status": "initiated",
            "created_at": iso(now_utc()),
        })
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


def _ensure_stripe_customer(user: dict) -> str:
    """Return Stripe customer_id, creating one if missing or stale."""
    existing = user.get("stripe_customer_id")
    if existing:
        try:
            cust = stripe.Customer.retrieve(existing)
            if not getattr(cust, "deleted", False):
                return existing
        except stripe.error.StripeError:
            # Stale id (test env reset) — recreate below
            pass
    cust = stripe.Customer.create(
        email=user["email"],
        name=user.get("name") or user["email"],
        metadata={"user_id": user["user_id"]},
    )
    return cust.id


@api.get("/stripe/checkout-status/{session_id}")
async def stripe_checkout_status(session_id: str, user: dict = Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": session.payment_status,
                "status": session.status,
                "subscription_id": getattr(session, "subscription", None),
                "updated_at": iso(now_utc()),
            }},
        )
        # If paid and not yet processed, activate subscription
        if session.payment_status == "paid" and txn.get("payment_status") != "paid":
            await _activate_subscription(user["user_id"], txn["plan"], session.subscription)
        return {
            "payment_status": session.payment_status,
            "status": session.status,
            "amount_total": session.amount_total,
            "currency": session.currency,
        }
    except stripe.error.InvalidRequestError as e:
        # Emergent test proxy is ephemeral — session may not be retrievable.
        # Fall back to cached transaction snapshot so the UI can keep polling
        # gracefully without a 500 error.
        logger.warning(f"Stripe session {session_id} not retrievable, returning cached: {e}")
        return {
            "payment_status": txn.get("payment_status", "unpaid"),
            "status": txn.get("status", "open"),
            "amount_total": txn.get("amount_cents", 0),
            "currency": txn.get("currency", "usd"),
            "cached": True,
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout-status error for {session_id}: {e}")
        raise HTTPException(status_code=502, detail="Payment provider unavailable")


async def _activate_subscription(user_id: str, plan: str, subscription_id: Optional[str]):
    cfg = PLAN_PRICES.get(plan)
    if not cfg:
        return
    period_end = None
    customer_id = None
    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            period_end = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc)
            customer_id = sub.customer
        except Exception as e:
            logger.error(f"sub retrieve failed: {e}")
    if not period_end:
        period_end = now_utc() + timedelta(days=cfg.get("duration_days", 30))
    await db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": plan,
            "status": "active",
            "expires_at": iso(period_end),
            "max_activations": cfg["max_activations"],
            "stripe_subscription_id": subscription_id,
            "payment_provider": "stripe",
        }},
        upsert=True,
    )
    if customer_id:
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"stripe_customer_id": customer_id}},
        )
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if user:
        s, h, t = email_svc.tpl_payment_success(
            user.get("name", ""), plan, cfg["amount_cents"] / 100,
            iso(period_end), f"{FRONTEND_URL}/dashboard"
        )
        await email_svc.send_email(user["email"], s, h, t)


@api.post("/stripe/portal")
async def stripe_portal(payload: dict, user: dict = Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        # Look up most recent paid transaction to find the customer (set on webhook/status)
        lic = await db.licenses.find_one({"user_id": user["user_id"]}, {"_id": 0})
        sub_id = lic.get("stripe_subscription_id") if lic else None
        if sub_id:
            try:
                sub = stripe.Subscription.retrieve(sub_id)
                customer_id = sub.customer
            except Exception:
                pass
    if not customer_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    origin = (payload.get("origin_url") or FRONTEND_URL).rstrip("/")
    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{origin}/dashboard",
        )
        return {"url": portal.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload_bytes = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    # Without webhook secret, we still parse the event (Emergent test mode)
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload_bytes, sig, webhook_secret)
        else:
            import json
            event = json.loads(payload_bytes.decode())
    except Exception as e:
        logger.error(f"Webhook parse failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")

    event_id = event.get("id") if isinstance(event, dict) else event.id
    event_type = event.get("type") if isinstance(event, dict) else event.type
    data_obj = (event.get("data", {}) if isinstance(event, dict) else event.data).get("object") or {}

    # Idempotency
    if event_id and await db.stripe_events.find_one({"event_id": event_id}):
        return {"ok": True, "duplicate": True}
    if event_id:
        await db.stripe_events.insert_one({"event_id": event_id, "type": event_type, "received_at": iso(now_utc())})

    if event_type == "checkout.session.completed":
        meta = data_obj.get("metadata") or {}
        user_id = meta.get("user_id")
        plan = meta.get("plan")
        sub_id = data_obj.get("subscription")
        coupon_code = (meta.get("coupon_code") or "").strip().upper()
        if user_id and plan:
            await _activate_subscription(user_id, plan, sub_id)
            await db.payment_transactions.update_one(
                {"session_id": data_obj.get("id")},
                {"$set": {"payment_status": "paid", "subscription_id": sub_id,
                          "paid_at": iso(now_utc())}},
            )
            if coupon_code:
                await db.coupons.update_one({"code": coupon_code}, {"$inc": {"used_count": 1}})
            # If user was created via guest checkout (auth_provider="purchase" + no email_verified)
            user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
            if user and user.get("auth_provider") == "purchase" and not user.get("email_verified"):
                try:
                    await _send_purchase_welcome(user_id, user["email"], user.get("name", ""))
                except Exception as e:
                    logger.error(f"purchase welcome email failed: {e}")

    elif event_type == "invoice.paid":
        sub_id = data_obj.get("subscription")
        if sub_id:
            try:
                sub = stripe.Subscription.retrieve(sub_id)
                meta = sub.metadata or {}
                user_id = meta.get("user_id")
                plan = meta.get("plan")
                if user_id and plan:
                    await _activate_subscription(user_id, plan, sub_id)
            except Exception as e:
                logger.error(f"invoice.paid handling failed: {e}")

    elif event_type in ("invoice.payment_failed", "customer.subscription.deleted"):
        sub_id = data_obj.get("id") if event_type == "customer.subscription.deleted" else data_obj.get("subscription")
        if sub_id:
            lic = await db.licenses.find_one({"stripe_subscription_id": sub_id}, {"_id": 0})
            if lic:
                # Record failed transaction for analytics
                if event_type == "invoice.payment_failed":
                    await db.payment_transactions.insert_one({
                        "provider": "stripe",
                        "user_id": lic["user_id"],
                        "email": (await db.users.find_one({"user_id": lic["user_id"]}, {"email": 1}) or {}).get("email"),
                        "plan": lic.get("plan"),
                        "amount_cents": data_obj.get("amount_due", 0),
                        "currency": data_obj.get("currency", "usd"),
                        "payment_status": "failed",
                        "failure_reason": data_obj.get("last_payment_error", {}).get("message") if isinstance(data_obj.get("last_payment_error"), dict) else "card_declined",
                        "subscription_id": sub_id,
                        "created_at": iso(now_utc()),
                    })
                await db.licenses.update_one(
                    {"user_id": lic["user_id"]},
                    {"$set": {"status": "canceled" if event_type == "customer.subscription.deleted" else "past_due"}},
                )
                user = await db.users.find_one({"user_id": lic["user_id"]}, {"_id": 0, "password_hash": 0})
                if user and event_type == "customer.subscription.deleted":
                    s, h, t = email_svc.tpl_subscription_canceled(
                        user.get("name", ""), lic.get("expires_at", ""), f"{FRONTEND_URL}/dashboard"
                    )
                    await email_svc.send_email(user["email"], s, h, t)

    return {"ok": True}



# ---------------- PayPal subscriptions ----------------
class PayPalSubscribeIn(BaseModel):
    plan: str  # "basic" | "pro" | "diamond" | "golden" | "business"
    origin_url: str
    coupon_code: Optional[str] = None
    guest_email: Optional[EmailStr] = None


@api.post("/paypal/subscribe")
async def paypal_subscribe(payload: PayPalSubscribeIn, request: Request):
    if not paypal_svc.is_configured():
        raise HTTPException(
            status_code=503,
            detail="PayPal is not configured. Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to backend env.",
        )
    plan = payload.plan.lower()
    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan")
    coupon = await _fetch_valid_coupon(payload.coupon_code)
    origin = payload.origin_url.rstrip("/")

    try:
        user = await get_current_user(request)
    except HTTPException:
        if not payload.guest_email:
            raise HTTPException(status_code=401, detail="Authentication required (or pass guest_email)")
        user = await _ensure_user_for_purchase(payload.guest_email)

    return_url = f"{origin}/billing/paypal/return?plan={plan}"
    cancel_url = f"{origin}/billing/cancel"
    custom_id = f"{user['user_id']}|{plan}|{coupon['code'] if coupon else ''}"
    try:
        result = paypal_svc.create_subscription(
            plan_key=plan,
            return_url=return_url,
            cancel_url=cancel_url,
            custom_id=custom_id,
            subscriber_email=user.get("email"),
        )
    except requests.HTTPError as e:
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            pass
        logger.error(f"PayPal create subscription failed: {e} body={body}")
        raise HTTPException(status_code=502, detail="PayPal error")
    except Exception as e:
        logger.error(f"PayPal create subscription error: {e}")
        raise HTTPException(status_code=502, detail="PayPal unavailable")

    cfg = PLAN_PRICES[plan]
    amount = _discounted_amount(cfg, coupon)
    await db.payment_transactions.insert_one({
        "provider": "paypal",
        "subscription_id": result["subscription_id"],
        "user_id": user["user_id"],
        "email": user["email"],
        "plan": plan,
        "amount_cents": amount,
        "original_amount_cents": cfg["amount_cents"],
        "coupon_code": coupon["code"] if coupon else None,
        "currency": "usd",
        "payment_status": "initiated",
        "created_at": iso(now_utc()),
    })
    return {
        "subscription_id": result["subscription_id"],
        "approval_url": result["approval_url"],
    }


@api.get("/paypal/subscription-status/{subscription_id}")
async def paypal_subscription_status(subscription_id: str, user: dict = Depends(get_current_user)):
    if not paypal_svc.is_configured():
        raise HTTPException(status_code=503, detail="PayPal not configured")
    txn = await db.payment_transactions.find_one(
        {"subscription_id": subscription_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        sub = paypal_svc.get_subscription(subscription_id)
    except Exception as e:
        logger.warning(f"PayPal get_subscription failed for {subscription_id}: {e}")
        return {"status": txn.get("payment_status", "unknown"), "cached": True}

    status_str = sub.get("status", "")  # APPROVAL_PENDING | ACTIVE | SUSPENDED | CANCELLED
    await db.payment_transactions.update_one(
        {"subscription_id": subscription_id},
        {"$set": {"payment_status": status_str.lower(), "updated_at": iso(now_utc())}},
    )
    if status_str == "ACTIVE" and txn.get("payment_status") != "active":
        await _activate_paypal_subscription(user["user_id"], txn["plan"], subscription_id, sub)
    return {
        "status": status_str,
        "subscription_id": subscription_id,
        "plan": txn["plan"],
    }


async def _activate_paypal_subscription(user_id: str, plan: str, subscription_id: str, sub_data: dict):
    cfg = PLAN_PRICES.get(plan)
    if not cfg:
        return
    period_end = None
    billing_info = sub_data.get("billing_info") or {}
    next_billing = billing_info.get("next_billing_time")
    if next_billing:
        try:
            period_end = datetime.fromisoformat(next_billing.replace("Z", "+00:00"))
        except Exception:
            period_end = None
    if not period_end:
        period_end = now_utc() + timedelta(days=cfg.get("duration_days", 30))

    await db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": plan,
            "status": "active",
            "expires_at": iso(period_end),
            "max_activations": cfg["max_activations"],
            "paypal_subscription_id": subscription_id,
            "payment_provider": "paypal",
        }},
        upsert=True,
    )
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if user:
        s, h, t = email_svc.tpl_payment_success(
            user.get("name", ""), plan, cfg["amount_cents"] / 100,
            iso(period_end), f"{FRONTEND_URL}/dashboard"
        )
        await email_svc.send_email(user["email"], s, h, t)


@api.post("/paypal/cancel")
async def paypal_cancel(payload: dict, user: dict = Depends(get_current_user)):
    if not paypal_svc.is_configured():
        raise HTTPException(status_code=503, detail="PayPal not configured")
    lic = await db.licenses.find_one({"user_id": user["user_id"]}, {"_id": 0})
    sub_id = lic.get("paypal_subscription_id") if lic else None
    if not sub_id:
        raise HTTPException(status_code=400, detail="No active PayPal subscription")
    try:
        ok = paypal_svc.cancel_subscription(sub_id, payload.get("reason", "User requested"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal cancel failed: {e}")
    if ok:
        await db.licenses.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"status": "canceled"}},
        )
        u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
        if u:
            s, h, t = email_svc.tpl_subscription_canceled(
                u.get("name", ""), lic.get("expires_at", ""), f"{FRONTEND_URL}/dashboard"
            )
            await email_svc.send_email(u["email"], s, h, t)
    return {"ok": ok}


@api.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    raw = await request.body()
    raw_str = raw.decode("utf-8", errors="ignore")
    if not paypal_svc.verify_webhook(dict(request.headers), raw_str):
        logger.warning("PayPal webhook signature verification failed")
        # Still log but reject
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json as _json
    try:
        event = _json.loads(raw_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = event.get("id")
    event_type = event.get("event_type", "")
    resource = event.get("resource") or {}

    # Idempotency
    if event_id and await db.paypal_events.find_one({"event_id": event_id}):
        return {"ok": True, "duplicate": True}
    if event_id:
        await db.paypal_events.insert_one({
            "event_id": event_id, "type": event_type, "received_at": iso(now_utc())
        })

    if event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.CREATED"):
        sub_id = resource.get("id")
        custom_id = resource.get("custom_id", "")
        parts = custom_id.split("|")
        user_id = parts[0] if len(parts) > 0 else ""
        plan = parts[1] if len(parts) > 1 else ""
        coupon_code = (parts[2] if len(parts) > 2 else "").strip().upper()
        if sub_id and user_id and plan in PLAN_PRICES:
            await _activate_paypal_subscription(user_id, plan, sub_id, resource)
            await db.payment_transactions.update_one(
                {"subscription_id": sub_id},
                {"$set": {"payment_status": "active", "paid_at": iso(now_utc())}},
            )
            if coupon_code:
                await db.coupons.update_one({"code": coupon_code}, {"$inc": {"used_count": 1}})
            user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
            if user and user.get("auth_provider") == "purchase" and not user.get("email_verified"):
                try:
                    await _send_purchase_welcome(user_id, user["email"], user.get("name", ""))
                except Exception as e:
                    logger.error(f"purchase welcome email (paypal) failed: {e}")

    elif event_type == "PAYMENT.SALE.COMPLETED":
        # Extend license on each successful renewal
        sub_id = resource.get("billing_agreement_id")
        if sub_id:
            lic = await db.licenses.find_one({"paypal_subscription_id": sub_id}, {"_id": 0})
            if lic:
                try:
                    sub = paypal_svc.get_subscription(sub_id)
                    await _activate_paypal_subscription(lic["user_id"], lic["plan"], sub_id, sub)
                except Exception as e:
                    logger.error(f"PAYMENT.SALE.COMPLETED handling failed: {e}")

    elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.SUSPENDED",
                        "BILLING.SUBSCRIPTION.EXPIRED", "PAYMENT.SALE.DENIED"):
        sub_id = resource.get("id") or resource.get("billing_agreement_id")
        if sub_id:
            lic = await db.licenses.find_one({"paypal_subscription_id": sub_id}, {"_id": 0})
            if lic:
                new_status = "canceled" if event_type == "BILLING.SUBSCRIPTION.CANCELLED" else "past_due"
                await db.licenses.update_one(
                    {"user_id": lic["user_id"]},
                    {"$set": {"status": new_status}},
                )
                if event_type == "BILLING.SUBSCRIPTION.CANCELLED":
                    u = await db.users.find_one({"user_id": lic["user_id"]}, {"_id": 0, "password_hash": 0})
                    if u:
                        s, h, t = email_svc.tpl_subscription_canceled(
                            u.get("name", ""), lic.get("expires_at", ""), f"{FRONTEND_URL}/dashboard"
                        )
                        await email_svc.send_email(u["email"], s, h, t)

    return {"ok": True}



# ---------------- Plans (public) ----------------
@api.get("/plans")
async def get_plans():
    return [
        {
            "id": "basic",
            "name": "Basic",
            "tier": 1,
            "price": 19.99,
            "period": "month",
            "duration_label": "1 month",
            "color": "#737373",
            "popular": False,
            "section_title": "FLAGS / FEATURES",
            "features": [
                "Get", "Post", "Only alerts", "Reflection", "Suffix", "Prefix",
                "Fullscan", "CRLF", "FilenameXss", "Hash-XSS",
                "Screenshot (proof)", "Path Injection", "Clear URL List",
            ],
            "limits": {"Threads": "7", "Payloads": "1500", "Devices": "3", "Duration": "1 month"},
            "savings": None,
            "monthly_equiv": None,
        },
        {
            "id": "pro",
            "name": "Pro",
            "tier": 2,
            "price": 49.99,
            "period": "month",
            "duration_label": "1 month",
            "color": "#2b6cf2",
            "popular": False,
            "section_title": "Includes everything from BASIC plus:",
            "features": [
                "Recon", "Inspector", "Path", "Resume", "Cookies", "Initialize",
                "Spray", "Save Scan Sessions", "Directory Scanning",
                "Report screenshots (advanced)", "Bug Bounty Mode",
            ],
            "limits": {"Threads": "10", "Payloads": "2000", "Devices": "3", "Duration": "1 month"},
            "savings": None,
            "monthly_equiv": None,
        },
        {
            "id": "diamond",
            "name": "Diamond",
            "tier": 3,
            "price": 89.99,
            "period": "3 months",
            "duration_label": "3 months",
            "color": "#7c5cff",
            "popular": True,
            "popular_label": "MOST POPULAR",
            "section_title": "Includes everything from PRO plus:",
            "features": [
                "Stealth", "Blindusername", "Crawler", "Fuzzer", "Limit",
                "Clickme", "Wayback", "Formscan", "Subdomains",
                "ParamBrute", "Dirscan", "Filter",
            ],
            "limits": {"Threads": "13", "Payloads": "3000", "Devices": "4", "Duration": "3 months"},
            "savings": "Save: $239.92 compared to PRO plan on a yearly basis",
            "monthly_equiv": "≈ $30.00 / month (billed every 3 months)",
        },
        {
            "id": "golden",
            "name": "Golden",
            "tier": 4,
            "price": 119.99,
            "period": "6 months",
            "duration_label": "6 months",
            "color": "#f5a623",
            "popular": False,
            "section_title": "Includes everything from DIAMOND plus:",
            "features": [
                "Custom Headers", "All (combined mode)", "User Agent",
                "Include-params", "Exclude-params", "Dirscan +2",
                "Code-analysis", "Code-vuln",
            ],
            "limits": {"Threads": "15", "Payloads": "Unlimited", "Devices": "5", "Duration": "6 months"},
            "savings": "Save: $359.90 compared to PRO plan on a yearly basis",
            "monthly_equiv": "≈ $20.00 / month (billed every 6 months)",
        },
        {
            "id": "business",
            "name": "Business",
            "tier": 5,
            "price": 339.99,
            "period": "1 year",
            "duration_label": "1 year",
            "color": "#10b981",
            "popular": False,
            "popular_label": "TEAMS & ENTERPRISE",
            "section_title": "Includes everything from GOLDEN plus:",
            "features": [
                "Multi-user capability",
                "Enterprise scaling",
                "Dynamic threads",
            ],
            "limits": {
                "Threads": "Unlimited", "Payloads": "Unlimited", "Total licenses": "3",
                "Support": "24/7", "Devices": "18", "Duration": "1 year",
            },
            "savings": "Save: $259.89 compared to PRO plan on a yearly basis",
            "monthly_equiv": "≈ $28.33 / month (billed annually)",
        },
    ]


# ---------------- Seeding ----------------
async def seed_demo():
    # admin (password-based)
    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    if admin is None:
        admin_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": admin_id,
            "email": ADMIN_EMAIL,
            "name": "Admin",
            "password_hash": hash_password(ADMIN_PASSWORD),
            "role": "admin",
            "auth_provider": "password",
            "banned": False,
            "created_at": iso(now_utc()),
        })
        await _ensure_license(admin_id, plan="business", days=3650)
        logger.info(f"Seeded admin {ADMIN_EMAIL}")
    else:
        if not verify_password(ADMIN_PASSWORD, admin.get("password_hash", "")):
            await db.users.update_one(
                {"email": ADMIN_EMAIL},
                {"$set": {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin", "banned": False}},
            )

    # Whitelist Google-only admins (login via "Continue with Google")
    for whitelisted_email in ADMIN_EMAILS:
        if whitelisted_email == ADMIN_EMAIL.lower():
            continue
        existing = await db.users.find_one({"email": whitelisted_email})
        if existing is None:
            uid = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": uid,
                "email": whitelisted_email,
                "name": whitelisted_email.split("@")[0],
                "role": "admin",
                "auth_provider": "google",
                "banned": False,
                "created_at": iso(now_utc()),
                # No password_hash — must log in via Google
            })
            await _ensure_license(uid, plan="business", days=3650)
            logger.info(f"Seeded Google-admin {whitelisted_email}")
        elif existing.get("role") != "admin":
            await db.users.update_one(
                {"email": whitelisted_email}, {"$set": {"role": "admin", "banned": False}}
            )
            logger.info(f"Promoted {whitelisted_email} to admin")

    # demo user
    test_email = "user@xss0r.io"
    if not await db.users.find_one({"email": test_email}):
        uid = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": uid,
            "email": test_email,
            "name": "Demo User",
            "password_hash": hash_password("User@xss0r2026"),
            "role": "user",
            "auth_provider": "password",
            "banned": False,
            "created_at": iso(now_utc()),
        })
        await _ensure_license(uid, plan="pro", days=30)
        # one HWID activation
        await db.hwid_activations.insert_one({
            "activation_id": f"act_{uuid.uuid4().hex[:10]}",
            "user_id": uid,
            "hwid": "HW-" + secrets.token_hex(6).upper(),
            "ip": "203.0.113.42",
            "os": "Windows 11 Pro",
            "activated_at": iso(now_utc()),
        })
        # sample scans
        targets = ["https://demo.testfire.net", "https://juice-shop.local", "https://mywebshop.io/login"]
        for i, t in enumerate(targets):
            await db.scans.insert_one({
                "scan_id": f"scn_{uuid.uuid4().hex[:10]}",
                "user_id": uid,
                "target": t,
                "vulns_found": i + 1,
                "status": "completed",
                "duration_seconds": 14 + i * 9,
                "created_at": iso(now_utc() - timedelta(days=i)),
            })

    # demo coupons
    for code, pct, days, max_u in [("LAUNCH50", 50, 60, 100), ("XSS0R10", 10, 30, 1000)]:
        if not await db.coupons.find_one({"code": code}):
            await db.coupons.insert_one({
                "coupon_id": f"cpn_{uuid.uuid4().hex[:10]}",
                "code": code,
                "percent_off": pct,
                "max_uses": max_u,
                "used_count": 0,
                "expires_at": iso(now_utc() + timedelta(days=90)),
                "extends_days": days,
                "created_at": iso(now_utc()),
            })

    # demo build entry (metadata only — no file). Admin can later upload real binaries.
    if not await db.builds.find_one({}):
        for plat, ver in [("windows", "1.4.2"), ("linux", "1.4.2")]:
            await db.builds.insert_one({
                "build_id": f"bld_{uuid.uuid4().hex[:10]}",
                "version": ver,
                "platform": plat,
                "changelog": "- Improved DOM-based XSS detection\n- New header injection payloads\n- Bug fixes for HWID rotation",
                "filename": f"xss0r-{ver}-{plat}.zip",
                "content_type": "application/zip",
                "size": 0,
                "storage_path": None,
                "is_deleted": False,
                "download_count": 0,
                "uploaded_by": "system",
                "created_at": iso(now_utc()),
            })


async def setup_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.licenses.create_index("user_id", unique=True)
    await db.api_keys.create_index("user_id", unique=True)
    await db.coupons.create_index("code", unique=True)
    await db.builds.create_index("build_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.password_reset_tokens.create_index("token", unique=True)


@app.on_event("startup")
async def on_startup():
    await setup_indexes()
    await seed_demo()
    init_storage()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# health
@api.get("/")
async def root():
    return {"service": "xss0r-saas", "status": "ok", "time": iso(now_utc())}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
