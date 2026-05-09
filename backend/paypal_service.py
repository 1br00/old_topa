"""PayPal Subscriptions API client.

Direct REST API integration (no SDK dependency for subscription mode).
Supports sandbox + live.

Lifecycle:
- ensure_plan(plan_id) -> creates Product + Plan if missing, caches Plan ID
- create_subscription(plan_id, return_url, cancel_url, custom_id) -> approval URL
- get_subscription(sub_id)
- cancel_subscription(sub_id, reason)
- verify_webhook(headers, body) -> bool
"""
import os
import logging
import time
import requests
from typing import Optional

logger = logging.getLogger("xss0r.paypal")

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox").lower()
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")

API_BASE = (
    "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox"
    else "https://api-m.paypal.com"
)

PLAN_CONFIG = {
    "pro": {"name": "xss0r Pro", "description": "xss0r Pro monthly subscription", "price": "29.00"},
    "enterprise": {"name": "xss0r Enterprise", "description": "xss0r Enterprise monthly subscription", "price": "99.00"},
}

# Cache: plan_key -> paypal_plan_id, fetched/created lazily
_plan_cache: dict = {}
_token_cache: dict = {"token": None, "expires_at": 0}


def is_configured() -> bool:
    return bool(PAYPAL_CLIENT_ID) and bool(PAYPAL_CLIENT_SECRET) \
        and not PAYPAL_CLIENT_ID.startswith("REPLACE_") \
        and not PAYPAL_CLIENT_SECRET.startswith("REPLACE_")


def _get_access_token() -> str:
    if not is_configured():
        raise RuntimeError("PayPal credentials missing")
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    r = requests.post(
        f"{API_BASE}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _token_cache["token"]


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }


def ensure_plan(plan_key: str) -> str:
    """Return PayPal plan_id for the given key. Creates Product+Plan if needed."""
    if plan_key in _plan_cache:
        return _plan_cache[plan_key]
    cfg = PLAN_CONFIG.get(plan_key)
    if not cfg:
        raise ValueError(f"Unknown plan key: {plan_key}")

    # 1) Create Product
    product = requests.post(
        f"{API_BASE}/v1/catalogs/products",
        headers=_auth_headers(),
        json={
            "name": cfg["name"],
            "description": cfg["description"],
            "type": "SERVICE",
            "category": "SOFTWARE",
        },
        timeout=15,
    )
    product.raise_for_status()
    product_id = product.json()["id"]

    # 2) Create monthly recurring Plan
    plan = requests.post(
        f"{API_BASE}/v1/billing/plans",
        headers=_auth_headers(),
        json={
            "product_id": product_id,
            "name": cfg["name"],
            "description": cfg["description"],
            "billing_cycles": [{
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,  # 0 = unlimited (auto-renew forever)
                "pricing_scheme": {
                    "fixed_price": {"value": cfg["price"], "currency_code": "USD"}
                },
            }],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee": {"value": "0", "currency_code": "USD"},
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 2,
            },
        },
        timeout=15,
    )
    plan.raise_for_status()
    plan_id = plan.json()["id"]
    _plan_cache[plan_key] = plan_id
    logger.info(f"PayPal plan created: {plan_key} -> {plan_id}")
    return plan_id


def create_subscription(plan_key: str, return_url: str, cancel_url: str,
                        custom_id: str, subscriber_email: Optional[str] = None) -> dict:
    plan_id = ensure_plan(plan_key)
    body = {
        "plan_id": plan_id,
        "custom_id": custom_id,  # our user_id|plan combo
        "application_context": {
            "brand_name": "xss0r",
            "locale": "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "payment_method": {
                "payer_selected": "PAYPAL",
                "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
            },
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    if subscriber_email:
        body["subscriber"] = {"email_address": subscriber_email}
    r = requests.post(
        f"{API_BASE}/v1/billing/subscriptions",
        headers=_auth_headers(),
        json=body,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    approval_url = next(
        (l["href"] for l in data.get("links", []) if l.get("rel") == "approve"),
        None,
    )
    return {"subscription_id": data["id"], "approval_url": approval_url, "status": data.get("status")}


def get_subscription(subscription_id: str) -> dict:
    r = requests.get(
        f"{API_BASE}/v1/billing/subscriptions/{subscription_id}",
        headers=_auth_headers(), timeout=15,
    )
    r.raise_for_status()
    return r.json()


def cancel_subscription(subscription_id: str, reason: str = "User requested cancellation") -> bool:
    r = requests.post(
        f"{API_BASE}/v1/billing/subscriptions/{subscription_id}/cancel",
        headers=_auth_headers(),
        json={"reason": reason},
        timeout=15,
    )
    return r.status_code == 204


def verify_webhook(headers: dict, raw_body: str) -> bool:
    """Verify PayPal webhook signature. Returns True if valid OR if no webhook id configured (dev mode)."""
    if not PAYPAL_WEBHOOK_ID:
        logger.warning("PAYPAL_WEBHOOK_ID not set — skipping signature verification")
        return True
    try:
        body = {
            "auth_algo": headers.get("paypal-auth-algo"),
            "cert_url": headers.get("paypal-cert-url"),
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "webhook_id": PAYPAL_WEBHOOK_ID,
            "webhook_event": __import__("json").loads(raw_body),
        }
        r = requests.post(
            f"{API_BASE}/v1/notifications/verify-webhook-signature",
            headers=_auth_headers(), json=body, timeout=15,
        )
        return r.json().get("verification_status") == "SUCCESS"
    except Exception as e:
        logger.error(f"PayPal webhook verify failed: {e}")
        return False
