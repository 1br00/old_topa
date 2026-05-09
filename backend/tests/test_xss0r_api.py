"""Comprehensive backend tests for xss0r SaaS."""
import os, io, uuid, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://api-gateway-73.preview.emergentagent.com").rstrip("/")
ADMIN = ("admin@xss0r.io", "Admin@xss0r2026")
USER = ("user@xss0r.io", "User@xss0r2026")


def _session(email=None, password=None):
    s = requests.Session()
    if email:
        r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _session(*ADMIN)


@pytest.fixture(scope="module")
def user_s():
    return _session(*USER)


# ---------------- Auth ----------------
def test_health():
    r = requests.get(f"{BASE}/api/")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_plans_public():
    r = requests.get(f"{BASE}/api/plans")
    assert r.status_code == 200
    plans = r.json()
    ids = {p["id"] for p in plans}
    assert ids == {"basic", "pro", "diamond", "golden", "business"}


def test_register_login_me_logout():
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@xss0r.io"
    r = s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "T"})
    assert r.status_code == 200
    assert r.json()["email"] == email
    assert "access_token" in s.cookies
    r = s.get(f"{BASE}/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == email
    r = s.post(f"{BASE}/api/auth/logout")
    assert r.status_code == 200
    # After logout cookies cleared -> me should fail
    s.cookies.clear()
    r = s.get(f"{BASE}/api/auth/me")
    assert r.status_code == 401


def test_login_admin_and_user(admin_s, user_s):
    r = admin_s.get(f"{BASE}/api/auth/me")
    assert r.status_code == 200 and r.json()["role"] == "admin"
    r = user_s.get(f"{BASE}/api/auth/me")
    assert r.status_code == 200 and r.json()["role"] == "user"


def test_login_bad_credentials():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": "wrong"})
    assert r.status_code == 401


def test_refresh(user_s):
    r = user_s.post(f"{BASE}/api/auth/refresh")
    assert r.status_code == 200


def test_forgot_password():
    r = requests.post(f"{BASE}/api/auth/forgot-password", json={"email": USER[0]})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_google_session_invalid():
    r = requests.post(f"{BASE}/api/auth/google/session", json={"session_id": "bad-session-xxx"})
    assert r.status_code == 400


# ---------------- License ----------------
def test_license_me(user_s):
    r = user_s.get(f"{BASE}/api/license/me")
    assert r.status_code == 200
    d = r.json()
    assert d["license"] is not None and d["api_key"] is not None
    assert d["license"]["plan"] == "pro"
    assert isinstance(d["activations"], list)


def test_regenerate_api_key(user_s):
    r1 = user_s.get(f"{BASE}/api/license/me").json()
    r = user_s.post(f"{BASE}/api/license/regenerate-api-key")
    assert r.status_code == 200
    assert r.json()["api_key"] != r1["api_key"]


def test_reset_hwid(user_s):
    r = user_s.post(f"{BASE}/api/license/reset-hwid")
    assert r.status_code == 200
    assert "removed" in r.json()


def test_scans(user_s):
    r = user_s.get(f"{BASE}/api/scans")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_builds_list(user_s):
    r = user_s.get(f"{BASE}/api/builds")
    assert r.status_code == 200 and isinstance(r.json(), list)


# ---------------- Coupons ----------------
def test_coupon_redeem_and_duplicate():
    # Create a fresh user for clean coupon redemption test
    s = requests.Session()
    email = f"cp_{uuid.uuid4().hex[:8]}@xss0r.io"
    s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "Cp"})
    r = s.post(f"{BASE}/api/coupons/redeem", json={"code": "LAUNCH50"})
    assert r.status_code == 200, r.text
    assert "new_expiry" in r.json()
    r = s.post(f"{BASE}/api/coupons/redeem", json={"code": "LAUNCH50"})
    assert r.status_code == 400  # already redeemed


def test_coupon_unknown(user_s):
    r = user_s.post(f"{BASE}/api/coupons/redeem", json={"code": "NOPE_XYZ"})
    assert r.status_code == 404


# ---------------- Admin ----------------
def test_admin_stats(admin_s):
    r = admin_s.get(f"{BASE}/api/admin/stats")
    assert r.status_code == 200
    d = r.json()
    for k in ("total_users", "active_licenses", "total_coupons", "total_builds"):
        assert k in d


def test_admin_users(admin_s):
    r = admin_s.get(f"{BASE}/api/admin/users")
    assert r.status_code == 200
    users = r.json()
    assert any(u["email"] == USER[0] for u in users)


def test_non_admin_forbidden(user_s):
    r = user_s.get(f"{BASE}/api/admin/stats")
    assert r.status_code == 403


def test_admin_coupons_crud(admin_s):
    r = admin_s.get(f"{BASE}/api/admin/coupons")
    assert r.status_code == 200
    code = f"TEST_{uuid.uuid4().hex[:6].upper()}"
    r = admin_s.post(f"{BASE}/api/admin/coupons", json={
        "code": code, "percent_off": 25, "max_uses": 10, "extends_days": 7
    })
    assert r.status_code == 200
    cid = r.json()["coupon_id"]
    r = admin_s.delete(f"{BASE}/api/admin/coupons/{cid}")
    assert r.status_code == 200


def test_admin_ban_unban(admin_s):
    # Create temp user and ban/unban
    s = requests.Session()
    email = f"ban_{uuid.uuid4().hex[:6]}@xss0r.io"
    s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "B"})
    me = s.get(f"{BASE}/api/auth/me").json()
    uid = me["user_id"]
    r = admin_s.post(f"{BASE}/api/admin/users/{uid}/ban", json={"banned": True})
    assert r.status_code == 200
    # banned user cannot access /me
    r2 = s.get(f"{BASE}/api/auth/me")
    assert r2.status_code == 401
    r = admin_s.post(f"{BASE}/api/admin/users/{uid}/ban", json={"banned": False})
    assert r.status_code == 200


def test_admin_builds_list(admin_s):
    r = admin_s.get(f"{BASE}/api/admin/builds")
    assert r.status_code == 200 and isinstance(r.json(), list)
