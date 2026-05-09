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
from fastapi import (
    FastAPI, APIRouter, HTTPException, Depends, Request, Response,
    UploadFile, File, Form, Header
)
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
import io

# ---------------- Config ----------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@xss0r.io")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@xss0r2026")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "xss0r-saas")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_AUTH_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)

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
    lic = {
        "license_id": f"lic_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "plan": plan,
        "status": "active" if (days > 0 or plan == "free") else "inactive",
        "expires_at": iso(expiry) if expiry else None,
        "max_activations": 1 if plan == "free" else 3 if plan == "pro" else 10,
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
        "picture": None,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    await _ensure_license(user_id, plan="free", days=14)
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_jwt_cookies(response, access, refresh)
    return {"user_id": user_id, "email": email, "name": payload.name, "role": "user"}


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
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "picture": data.get("picture"),
            "role": "user",
            "auth_provider": "google",
            "banned": False,
            "created_at": iso(now_utc()),
        }
        await db.users.insert_one(user)
        await _ensure_license(user_id, plan="free", days=14)
    else:
        if user.get("banned"):
            raise HTTPException(status_code=403, detail="Account banned")
        await db.users.update_one({"user_id": user["user_id"]}, {
            "$set": {
                "name": data.get("name") or user.get("name"),
                "picture": data.get("picture") or user.get("picture"),
            }
        })

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
    # attach license info
    for u in users:
        lic = await db.licenses.find_one({"user_id": u["user_id"]}, {"_id": 0})
        u["license"] = lic
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


# ---------------- Plans (public) ----------------
@api.get("/plans")
async def get_plans():
    return [
        {"id": "free", "name": "Free", "price": 0, "period": "14d trial",
         "features": ["1 device", "Basic XSS scanner", "Community support", "Limited scan history"]},
        {"id": "pro", "name": "Pro", "price": 29, "period": "month",
         "features": ["3 devices", "Full XSS engine + DOM", "API access", "Priority support",
                      "Unlimited scan history", "Auto updates"]},
        {"id": "enterprise", "name": "Enterprise", "price": 99, "period": "month",
         "features": ["10 devices", "Advanced payloads", "CI/CD integration", "Dedicated support",
                      "SLA + audit logs", "Custom payload library"]},
    ]


# ---------------- Seeding ----------------
async def seed_demo():
    # admin
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
        await _ensure_license(admin_id, plan="enterprise", days=3650)
        logger.info(f"Seeded admin {ADMIN_EMAIL}")
    else:
        if not verify_password(ADMIN_PASSWORD, admin.get("password_hash", "")):
            await db.users.update_one(
                {"email": ADMIN_EMAIL},
                {"$set": {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin", "banned": False}},
            )

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
