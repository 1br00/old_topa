"""Tests for Resend (dry-run) email integration and Stripe subscription flow.

Covers iteration 2 features:
- Register triggers welcome + verification (dry-run)
- Forgot password (dry-run)
- Verify-email valid/invalid token
- Resend-verification (authed)
- Stripe checkout (pro/enterprise/invalid)
- Stripe checkout-status existence
- Stripe portal returns 400 without subscription
- Webhook checkout.session.completed updates license + idempotency
"""
import os
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://api-gateway-73.preview.emergentagent.com").rstrip("/")
USER = ("user@xss0r.io", "User@xss0r2026")
ADMIN = ("admin@xss0r.io", "Admin@xss0r2026")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def user_s():
    return _login(*USER)


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


# -------- Register triggers email send (dry-run) --------
def test_register_triggers_emails(mongo_db):
    email = f"TEST_email_{uuid.uuid4().hex[:8]}@xss0r.io"
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "T"})
    assert r.status_code == 200
    # server lowercases email
    user = mongo_db.users.find_one({"email": email.lower()})
    assert user is not None
    rec = mongo_db.email_verify_tokens.find_one({"user_id": user["user_id"], "used": False})
    assert rec is not None
    # Cleanup
    mongo_db.users.delete_one({"email": email})
    mongo_db.email_verify_tokens.delete_many({"user_id": user["user_id"]})
    mongo_db.licenses.delete_many({"user_id": user["user_id"]})


# -------- Forgot password (dry-run) --------
def test_forgot_password_existing_user():
    r = requests.post(f"{BASE}/api/auth/forgot-password", json={"email": USER[0]})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_forgot_password_unknown_user_still_ok():
    # Should not leak existence (returns ok=true regardless)
    r = requests.post(f"{BASE}/api/auth/forgot-password", json={"email": "nonexistent_xyz@xss0r.io"})
    assert r.status_code == 200


# -------- Verify email --------
def test_verify_email_invalid_token():
    r = requests.post(f"{BASE}/api/auth/verify-email", json={"token": "bogus-invalid-token"})
    assert r.status_code == 400


def test_verify_email_valid_flow(mongo_db):
    email = f"TEST_verify_{uuid.uuid4().hex[:8]}@xss0r.io"
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "V"})
    assert r.status_code == 200
    user = mongo_db.users.find_one({"email": email.lower()})
    rec = mongo_db.email_verify_tokens.find_one({"user_id": user["user_id"], "used": False})
    token = rec["token"]
    r = requests.post(f"{BASE}/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    user2 = mongo_db.users.find_one({"email": email.lower()})
    assert user2.get("email_verified") is True
    # Replay -> 400 (already used)
    r2 = requests.post(f"{BASE}/api/auth/verify-email", json={"token": token})
    assert r2.status_code == 400
    # Cleanup
    mongo_db.users.delete_one({"email": email})
    mongo_db.email_verify_tokens.delete_many({"user_id": user["user_id"]})
    mongo_db.licenses.delete_many({"user_id": user["user_id"]})


# -------- Resend verification --------
def test_resend_verification_authed(mongo_db):
    email = f"TEST_resend_{uuid.uuid4().hex[:8]}@xss0r.io"
    s = requests.Session()
    s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "R"})
    r = s.post(f"{BASE}/api/auth/resend-verification")
    assert r.status_code == 200
    user = mongo_db.users.find_one({"email": email.lower()})
    tokens = list(mongo_db.email_verify_tokens.find({"user_id": user["user_id"]}))
    assert len(tokens) >= 2  # one from register, one from resend
    # Cleanup
    mongo_db.users.delete_one({"email": email})
    mongo_db.email_verify_tokens.delete_many({"user_id": user["user_id"]})
    mongo_db.licenses.delete_many({"user_id": user["user_id"]})


def test_resend_verification_unauthed():
    r = requests.post(f"{BASE}/api/auth/resend-verification")
    assert r.status_code == 401


# -------- Stripe checkout --------
def test_stripe_checkout_pro(user_s):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={
        "plan": "pro",
        "origin_url": BASE,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "checkout_url" in data
    assert data["checkout_url"].startswith("https://checkout.stripe.com")
    assert "session_id" in data


@pytest.mark.parametrize("plan", ["basic", "pro", "diamond", "golden", "business"])
def test_stripe_checkout_all_plans(user_s, plan):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={
        "plan": plan,
        "origin_url": BASE,
    })
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("https://checkout.stripe.com")


@pytest.mark.parametrize("plan", ["enterprise", "free", "foo"])
def test_stripe_checkout_removed_plans_400(user_s, plan):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={
        "plan": plan,
        "origin_url": BASE,
    })
    assert r.status_code == 400, f"plan {plan} expected 400, got {r.status_code}: {r.text}"


def test_stripe_checkout_invalid_plan(user_s):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={
        "plan": "foo",
        "origin_url": BASE,
    })
    assert r.status_code == 400


def test_stripe_checkout_unauthed():
    r = requests.post(f"{BASE}/api/stripe/checkout", json={"plan": "pro", "origin_url": BASE})
    assert r.status_code == 401


# -------- Stripe checkout-status (Pro) - must NEVER be 500 --------
def test_stripe_checkout_status_pro(user_s):
    # Create a Pro session and immediately query status
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={"plan": "pro", "origin_url": BASE})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    r2 = user_s.get(f"{BASE}/api/stripe/checkout-status/{sid}")
    # Critical: must be 200, never 500
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
    d = r2.json()
    assert "payment_status" in d
    assert "status" in d
    assert "amount_total" in d
    assert "currency" in d
    assert d["payment_status"] in ("unpaid", "paid", "no_payment_required", "open", "initiated")
    # If Stripe ephemeral proxy returned cached fallback, it should be flagged
    if d.get("cached") is True:
        assert d["currency"] in ("usd", "USD")
        # cached snapshot from initiated txn should preserve plan amount
        assert d["amount_total"] is not None


# -------- Stripe checkout-status (Enterprise) - must NEVER be 500 --------
def test_stripe_checkout_status_business(user_s):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={"plan": "business", "origin_url": BASE})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    r2 = user_s.get(f"{BASE}/api/stripe/checkout-status/{sid}")
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
    d = r2.json()
    assert "payment_status" in d
    assert d["payment_status"] in ("unpaid", "paid", "no_payment_required", "open", "initiated")


# -------- Stripe checkout-status: 404 for unknown session_id --------
def test_stripe_checkout_status_unknown_session_returns_404(user_s):
    fake_sid = "cs_test_doesnotexist_" + uuid.uuid4().hex[:12]
    r = user_s.get(f"{BASE}/api/stripe/checkout-status/{fake_sid}")
    assert r.status_code == 404, f"Expected 404 for unknown session, got {r.status_code}: {r.text}"


# -------- Stripe portal: 400 when no subscription on demo user --------
def test_stripe_portal_no_subscription(user_s):
    r = user_s.post(f"{BASE}/api/stripe/portal", json={"origin_url": BASE})
    # Demo user has license but no stripe_subscription_id (never paid via webhook)
    assert r.status_code == 400, r.text


# -------- Webhook handling + idempotency --------
def test_webhook_checkout_session_completed_and_idempotent(mongo_db):
    user = mongo_db.users.find_one({"email": USER[0]})
    user_id = user["user_id"]
    event_id = f"evt_test_{uuid.uuid4().hex[:8]}"
    session_id = f"cs_mock_{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_mock_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "metadata": {"user_id": user_id, "plan": "business"},
                "subscription": sub_id,
            }
        },
    }
    r = requests.post(f"{BASE}/api/webhook/stripe", json=payload)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    assert r.json().get("duplicate") is not True

    # License should be business + carry stripe_subscription_id
    lic = mongo_db.licenses.find_one({"user_id": user_id})
    assert lic is not None
    assert lic.get("plan") == "business"
    assert lic.get("stripe_subscription_id") == sub_id
    assert lic.get("max_activations") == 18
    assert lic.get("payment_provider") == "stripe"

    # Replay same event -> duplicate
    r2 = requests.post(f"{BASE}/api/webhook/stripe", json=payload)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True

    # Reset demo user license back to pro
    mongo_db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {"plan": "pro"}, "$unset": {"stripe_subscription_id": ""}},
    )
    mongo_db.stripe_events.delete_one({"event_id": event_id})


def test_webhook_invalid_payload():
    r = requests.post(f"{BASE}/api/webhook/stripe", data="not-json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
