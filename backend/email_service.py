"""Resend email service.

Provides async send_email() helper plus pre-built HTML templates for:
- password reset
- email verification
- welcome
- payment confirmation
- subscription cancellation

If RESEND_API_KEY is missing or starts with "re_REPLACE_ME", emails are logged
to stdout instead of being sent (dev-friendly fallback).
"""
import os
import asyncio
import logging
from typing import Optional

import resend

logger = logging.getLogger("xss0r.email")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@xss0r.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "xss0r")

_initialized = False


def _ensure_init():
    global _initialized
    if _initialized:
        return
    if RESEND_API_KEY and not RESEND_API_KEY.startswith("re_REPLACE_ME"):
        resend.api_key = RESEND_API_KEY
        _initialized = True


def _is_live() -> bool:
    return bool(RESEND_API_KEY) and not RESEND_API_KEY.startswith("re_REPLACE_ME")


async def send_email(to: str, subject: str, html: str, text: Optional[str] = None) -> dict:
    _ensure_init()
    sender = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    if not _is_live():
        logger.info(f"[EMAIL DRY-RUN] to={to} subject='{subject}'\n{(text or html)[:500]}")
        return {"id": "dry-run", "dry_run": True}
    params = {"from": sender, "to": [to], "subject": subject, "html": html}
    if text:
        params["text"] = text
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"[EMAIL] sent to {to} (id={result.get('id')})")
        return result
    except Exception as e:
        logger.error(f"[EMAIL] send failed to {to}: {e}")
        return {"error": str(e)}


# ---------- Templates ----------
def _wrap(title: str, body_html: str, cta_label: Optional[str] = None, cta_url: Optional[str] = None) -> str:
    cta = ""
    if cta_label and cta_url:
        cta = f"""
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:32px 0">
          <tr><td>
            <a href="{cta_url}" style="background:#4da3ff;color:#0a0a0a;padding:14px 28px;text-decoration:none;font-weight:700;font-family:Menlo,Consolas,monospace;font-size:14px;letter-spacing:0.02em;display:inline-block">{cta_label}</a>
          </td></tr>
        </table>
        <p style="font-size:12px;color:#737373;font-family:Menlo,Consolas,monospace;word-break:break-all">Or copy this link:<br/>{cta_url}</p>
        """
    return f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:-apple-system,Segoe UI,Roboto,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 16px">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#121212;border:1px solid rgba(255,255,255,0.1)">
        <tr><td style="padding:32px 32px 16px">
          <div style="font-family:Menlo,Consolas,monospace;color:#4da3ff;font-weight:700;font-size:16px;letter-spacing:-0.01em">▣ xss0r</div>
        </td></tr>
        <tr><td style="padding:0 32px 8px">
          <h1 style="font-family:Menlo,Consolas,monospace;color:#f0f2f5;font-size:24px;font-weight:700;margin:0;letter-spacing:-0.01em">{title}</h1>
        </td></tr>
        <tr><td style="padding:16px 32px 32px;color:#a0a6ad;font-size:14px;line-height:1.65">
          {body_html}
          {cta}
        </td></tr>
        <tr><td style="padding:24px 32px;border-top:1px solid rgba(255,255,255,0.08);font-family:Menlo,Consolas,monospace;font-size:11px;color:#737373">
          xss0r · precision XSS scanner · <a href="https://xss0r.com" style="color:#4da3ff;text-decoration:none">xss0r.com</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def tpl_password_reset(name: str, reset_link: str) -> tuple[str, str, str]:
    subject = "Reset your xss0r password"
    body = f"""<p>Hi {name or 'operator'},</p>
<p>We received a request to reset the password on your xss0r account. The link below is valid for <strong>1 hour</strong>.</p>
<p>If you didn't request this, you can safely ignore this email — your password won't be changed.</p>"""
    html = _wrap("Reset password", body, "Reset password", reset_link)
    text = f"Reset your xss0r password: {reset_link}\n(Valid for 1 hour. Ignore if you didn't request this.)"
    return subject, html, text


def tpl_verify_email(name: str, verify_link: str) -> tuple[str, str, str]:
    subject = "Verify your xss0r email"
    body = f"""<p>Welcome to xss0r, {name or 'operator'}.</p>
<p>Please confirm your email address to activate your account and start your 14-day Pro trial.</p>"""
    html = _wrap("Verify your email", body, "Verify email", verify_link)
    text = f"Verify your xss0r email: {verify_link}"
    return subject, html, text


def tpl_welcome(name: str, dashboard_url: str) -> tuple[str, str, str]:
    subject = "Welcome to xss0r — your trial is live"
    body = f"""<p>Hi {name or 'operator'},</p>
<p>Your xss0r account is ready. You're on the <strong>14-day Pro trial</strong> — full DOM engine, custom payloads, CI/CD ready.</p>
<p>Hit the dashboard to grab your CLI build, copy your API key, and run your first scan.</p>"""
    html = _wrap("You're in.", body, "Open dashboard", dashboard_url)
    text = f"Welcome to xss0r. Open dashboard: {dashboard_url}"
    return subject, html, text


def tpl_payment_success(name: str, plan: str, amount_usd: float, expires_at: str, dashboard_url: str) -> tuple[str, str, str]:
    subject = f"Payment received — {plan.upper()} active"
    body = f"""<p>Hi {name or 'operator'},</p>
<p>We received your payment of <strong>${amount_usd:.2f} USD</strong> for the <strong>{plan.upper()}</strong> plan.</p>
<p>Your license is now active until <strong>{expires_at[:10] if expires_at else '—'}</strong>. The subscription will auto-renew monthly. You can manage or cancel it anytime from your billing page.</p>"""
    html = _wrap("Subscription active", body, "Open dashboard", dashboard_url)
    text = f"Payment received for {plan} (${amount_usd:.2f}). Expires {expires_at}. {dashboard_url}"
    return subject, html, text


def tpl_subscription_canceled(name: str, expires_at: str, dashboard_url: str) -> tuple[str, str, str]:
    subject = "Your xss0r subscription was canceled"
    body = f"""<p>Hi {name or 'operator'},</p>
<p>Your subscription has been canceled. You'll keep full access until <strong>{expires_at[:10] if expires_at else 'period end'}</strong>; after that, your license will switch back to the free trial state.</p>
<p>Changed your mind? You can re-subscribe anytime.</p>"""
    html = _wrap("Subscription canceled", body, "Resubscribe", dashboard_url)
    text = f"Subscription canceled. Access until {expires_at}. Resubscribe: {dashboard_url}"
    return subject, html, text
