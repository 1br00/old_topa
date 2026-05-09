"""Tests for PayPal Subscriptions integration (iteration 4).

PayPal credentials are placeholders (REPLACE_ME_...) so live PayPal API calls
short-circuit to 503. The webhook handler is testable end-to-end because
PAYPAL_WEBHOOK_ID is empty (signature verification skipped in dev mode).
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
    return MongoClient(MONGO_URL)[DB_NAME]


# -------- /api/paypal/subscribe --------
def test_paypal_subscribe_unconfigured_returns_503(user_s):
    """With placeholder PAYPAL_CLIENT_ID, must return 503 (not 500)."""
    r = user_s.post(f"{BASE}/api/paypal/subscribe", json={
        "plan": "pro",
        "origin_url": BASE,
    })
    assert r.status_code == 503, f"expected 503 got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "PayPal" in detail and "not configured" in detail


def test_paypal_subscribe_invalid_plan_short_circuits_503(user_s):
    """With placeholder creds, even invalid plan short-circuits at 503 (acceptable)."""
    r = user_s.post(f"{BASE}/api/paypal/subscribe", json={
        "plan": "foo",
        "origin_url": BASE,
    })
    # 503 (creds check first) is acceptable; 400 also acceptable. NOT 500.
    assert r.status_code in (400, 503), f"got {r.status_code}: {r.text}"


def test_paypal_subscribe_unauthed():
    r = requests.post(f"{BASE}/api/paypal/subscribe", json={"plan": "pro", "origin_url": BASE})
    assert r.status_code == 401


# -------- /api/paypal/subscription-status --------
def test_paypal_subscription_status_unconfigured(user_s):
    r = user_s.get(f"{BASE}/api/paypal/subscription-status/I-FAKE001")
    assert r.status_code == 503


# -------- /api/paypal/cancel --------
def test_paypal_cancel_no_subscription(user_s):
    r = user_s.post(f"{BASE}/api/paypal/cancel", json={"reason": "test"})
    # 503 (creds) is short-circuited first; both acceptable.
    assert r.status_code in (400, 503), r.text


# -------- /api/webhook/paypal end-to-end (signature bypassed) --------
def test_paypal_webhook_activated_then_cancelled_idempotent(mongo_db):
    user = mongo_db.users.find_one({"email": USER[0]})
    user_id = user["user_id"]

    # Snapshot original license to restore at end
    orig_lic = mongo_db.licenses.find_one({"user_id": user_id})

    sub_id = f"I-MOCK{uuid.uuid4().hex[:8].upper()}"
    activated_event_id = f"WH-test-{uuid.uuid4().hex[:6]}"
    activated_event = {
        "id": activated_event_id,
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": sub_id,
            "custom_id": f"{user_id}|pro",
            "billing_info": {"next_billing_time": "2026-04-09T00:00:00Z"},
        },
    }

    r = requests.post(f"{BASE}/api/webhook/paypal", json=activated_event)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("duplicate") is not True

    # License should now be pro/active with paypal subscription id + provider
    lic = mongo_db.licenses.find_one({"user_id": user_id})
    assert lic is not None
    assert lic.get("plan") == "pro"
    assert lic.get("status") == "active"
    assert lic.get("paypal_subscription_id") == sub_id
    assert lic.get("payment_provider") == "paypal"
    assert lic.get("expires_at", "").startswith("2026-04-09")

    # Idempotency: replay same event id -> duplicate
    r2 = requests.post(f"{BASE}/api/webhook/paypal", json=activated_event)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True

    # GET /api/license/me reflects payment_provider
    s = _login(*USER)
    rme = s.get(f"{BASE}/api/license/me")
    assert rme.status_code == 200
    licm = rme.json().get("license") or {}
    assert licm.get("payment_provider") == "paypal"
    assert licm.get("paypal_subscription_id") == sub_id

    # Cancel webhook
    cancelled_event = {
        "id": f"WH-cancel-{uuid.uuid4().hex[:6]}",
        "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
        "resource": {"id": sub_id, "custom_id": f"{user_id}|pro"},
    }
    rc = requests.post(f"{BASE}/api/webhook/paypal", json=cancelled_event)
    assert rc.status_code == 200, rc.text
    lic_after = mongo_db.licenses.find_one({"user_id": user_id})
    assert lic_after.get("status") == "canceled"

    # Cleanup events + restore license
    mongo_db.paypal_events.delete_one({"event_id": activated_event_id})
    mongo_db.paypal_events.delete_many({"type": "BILLING.SUBSCRIPTION.CANCELLED",
                                         "event_id": cancelled_event["id"]})
    if orig_lic:
        # Restore plan/status, drop paypal fields
        update_set = {
            "plan": orig_lic.get("plan", "pro"),
            "status": orig_lic.get("status", "active"),
            "expires_at": orig_lic.get("expires_at"),
            "max_activations": orig_lic.get("max_activations", 3),
        }
        mongo_db.licenses.update_one(
            {"user_id": user_id},
            {"$set": update_set,
             "$unset": {"paypal_subscription_id": "", "payment_provider": ""}},
        )


def test_paypal_webhook_invalid_json_returns_400():
    r = requests.post(f"{BASE}/api/webhook/paypal",
                      data="not-json",
                      headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_paypal_webhook_unknown_event_type_returns_200():
    """Unknown event type should be accepted (no-op) and stored for idempotency."""
    event = {
        "id": f"WH-unknown-{uuid.uuid4().hex[:6]}",
        "event_type": "SOMETHING.ELSE",
        "resource": {},
    }
    r = requests.post(f"{BASE}/api/webhook/paypal", json=event)
    assert r.status_code == 200
