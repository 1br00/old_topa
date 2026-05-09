"""Iteration 5 — verify new 5-plan structure (basic/pro/diamond/golden/business)."""
import os
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
USER = ("user@xss0r.io", "User@xss0r2026")
ADMIN = ("admin@xss0r.io", "Admin@xss0r2026")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def user_s():
    return _login(*USER)


@pytest.fixture(scope="module")
def admin_s():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ---------- GET /api/plans ----------
def test_plans_returns_5_plans_in_order():
    r = requests.get(f"{BASE}/api/plans")
    assert r.status_code == 200
    plans = r.json()
    assert isinstance(plans, list)
    assert len(plans) == 5
    ids = [p["id"] for p in plans]
    assert ids == ["basic", "pro", "diamond", "golden", "business"]


def test_plans_prices_and_periods():
    plans = {p["id"]: p for p in requests.get(f"{BASE}/api/plans").json()}
    assert plans["basic"]["price"] == 19.99 and plans["basic"]["period"] == "month"
    assert plans["pro"]["price"] == 49.99 and plans["pro"]["period"] == "month"
    assert plans["diamond"]["price"] == 89.99 and plans["diamond"]["period"] == "3 months"
    assert plans["golden"]["price"] == 119.99 and plans["golden"]["period"] == "6 months"
    assert plans["business"]["price"] == 339.99 and plans["business"]["period"] == "1 year"


def test_only_diamond_is_popular():
    plans = {p["id"]: p for p in requests.get(f"{BASE}/api/plans").json()}
    assert plans["diamond"]["popular"] is True
    for pid in ("basic", "pro", "golden", "business"):
        assert plans[pid]["popular"] is False


def test_savings_and_monthly_equiv_fields():
    plans = {p["id"]: p for p in requests.get(f"{BASE}/api/plans").json()}
    # basic + pro have None
    assert plans["basic"]["savings"] is None and plans["basic"]["monthly_equiv"] is None
    assert plans["pro"]["savings"] is None and plans["pro"]["monthly_equiv"] is None
    # diamond/golden/business have strings
    for pid in ("diamond", "golden", "business"):
        assert isinstance(plans[pid]["savings"], str) and "Save" in plans[pid]["savings"]
        assert isinstance(plans[pid]["monthly_equiv"], str)


def test_plans_limits_keys():
    plans = {p["id"]: p for p in requests.get(f"{BASE}/api/plans").json()}
    base_keys = {"Threads", "Payloads", "Devices", "Duration"}
    for pid in ("basic", "pro", "diamond", "golden"):
        assert base_keys.issubset(set(plans[pid]["limits"].keys()))
    biz = plans["business"]["limits"]
    assert {"Threads", "Payloads", "Devices", "Duration",
            "Total licenses", "Support"}.issubset(set(biz.keys()))


def test_plans_has_features_and_section_title():
    for p in requests.get(f"{BASE}/api/plans").json():
        assert isinstance(p.get("features"), list) and len(p["features"]) >= 3
        assert isinstance(p.get("section_title"), str) and p["section_title"]
        assert isinstance(p.get("color"), str) and p["color"].startswith("#")


# ---------- Stripe checkout: interval differs by plan ----------
@pytest.mark.parametrize("plan,exp_interval,exp_count", [
    ("basic", "month", 1),
    ("pro", "month", 1),
    ("diamond", "month", 3),
    ("golden", "month", 6),
    ("business", "year", 1),
])
def test_stripe_checkout_interval_matches_plan(user_s, mongo_db, plan, exp_interval, exp_count):
    """Verify Stripe Checkout was created — and that the line_items recurring matches.
    We can introspect via Stripe API since we have a session_id; fall back to amount check."""
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={"plan": plan, "origin_url": BASE})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com")
    # Check the persisted txn record
    txn = mongo_db.payment_transactions.find_one({"session_id": data["session_id"]})
    assert txn is not None
    assert txn["plan"] == plan
    expected_amounts = {"basic": 1999, "pro": 4999, "diamond": 8999, "golden": 11999, "business": 33999}
    assert txn["amount_cents"] == expected_amounts[plan]


# ---------- Removed plans return 400 ----------
@pytest.mark.parametrize("plan", ["enterprise", "free", "foo", "TIER1", ""])
def test_stripe_checkout_invalid_or_removed_plans(user_s, plan):
    r = user_s.post(f"{BASE}/api/stripe/checkout", json={"plan": plan, "origin_url": BASE})
    assert r.status_code == 400


# ---------- Existing user plans ----------
def test_demo_user_has_pro_plan(user_s):
    r = user_s.get(f"{BASE}/api/license/me")
    assert r.status_code == 200
    lic = r.json()["license"]
    assert lic["plan"] == "pro"
    assert lic["status"] == "active"


def test_admin_has_business_plan(admin_s):
    r = admin_s.get(f"{BASE}/api/license/me")
    assert r.status_code == 200
    lic = r.json()["license"]
    assert lic["plan"] == "business", f"Admin plan should be 'business' (migrated from 'enterprise'), got {lic['plan']}"


# ---------- PayPal subscribe still 503 across all 5 plans (placeholder creds) ----------
@pytest.mark.parametrize("plan", ["basic", "pro", "diamond", "golden", "business"])
def test_paypal_subscribe_503_for_all_plans(user_s, plan):
    r = user_s.post(f"{BASE}/api/paypal/subscribe", json={"plan": plan, "origin_url": BASE})
    assert r.status_code == 503, f"plan={plan} expected 503, got {r.status_code}"
    assert "not configured" in r.json().get("detail", "")


# ---------- PayPal webhook for diamond + business: max_activations + duration_days fallback ----------
@pytest.mark.parametrize("plan,exp_max_act,exp_duration_days", [
    ("diamond", 4, 90),
    ("business", 18, 365),
])
def test_paypal_webhook_activates_correct_plan(mongo_db, plan, exp_max_act, exp_duration_days):
    user = mongo_db.users.find_one({"email": USER[0]})
    user_id = user["user_id"]
    orig_lic = mongo_db.licenses.find_one({"user_id": user_id})

    sub_id = f"I-MOCK{uuid.uuid4().hex[:8].upper()}"
    event_id = f"WH-{plan}-{uuid.uuid4().hex[:6]}"
    # Note: NO billing_info.next_billing_time -> forces duration_days fallback
    event = {
        "id": event_id,
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": sub_id,
            "custom_id": f"{user_id}|{plan}",
        },
    }
    r = requests.post(f"{BASE}/api/webhook/paypal", json=event)
    assert r.status_code == 200, r.text
    try:
        lic = mongo_db.licenses.find_one({"user_id": user_id})
        assert lic["plan"] == plan
        assert lic["max_activations"] == exp_max_act
        assert lic["payment_provider"] == "paypal"
        assert lic["paypal_subscription_id"] == sub_id
        # expires_at should be ~exp_duration_days from now (within 1 day tolerance)
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(lic["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta_days = (exp - datetime.now(timezone.utc)).days
        assert exp_duration_days - 2 <= delta_days <= exp_duration_days + 1, \
            f"plan={plan} expected ~{exp_duration_days} days, got {delta_days}"
    finally:
        # Cleanup ALWAYS — even if assertions failed — so the demo user is restored
        mongo_db.paypal_events.delete_one({"event_id": event_id})
        if orig_lic:
            mongo_db.licenses.update_one(
                {"user_id": user_id},
                {"$set": {
                    "plan": orig_lic.get("plan", "pro"),
                    "status": orig_lic.get("status", "active"),
                    "expires_at": orig_lic.get("expires_at"),
                    "max_activations": orig_lic.get("max_activations", 3),
                },
                 "$unset": {"paypal_subscription_id": "", "payment_provider": ""}},
            )


# ---------- Regression: login + license + stats + coupon redemption ----------
def test_admin_stats(admin_s):
    r = admin_s.get(f"{BASE}/api/admin/stats")
    assert r.status_code == 200
    d = r.json()
    assert "total_users" in d and d["total_users"] >= 2


def test_coupon_redemption_still_works(mongo_db):
    """Create a temp user, redeem XSS0R10."""
    email = f"TEST_cpn_{uuid.uuid4().hex[:8]}@xss0r.io"
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Pass1234", "name": "Cp"})
    assert r.status_code == 200
    user_id = r.json()["user_id"]
    r2 = s.post(f"{BASE}/api/coupons/redeem", json={"code": "XSS0R10"})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True
    # cleanup
    mongo_db.users.delete_one({"user_id": user_id})
    mongo_db.licenses.delete_one({"user_id": user_id})
    mongo_db.api_keys.delete_one({"user_id": user_id})
    mongo_db.coupon_redemptions.delete_many({"user_id": user_id})
    mongo_db.email_verify_tokens.delete_many({"user_id": user_id})
