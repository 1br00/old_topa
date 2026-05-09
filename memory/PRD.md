# xss0r SaaS — Product Requirements

## Problem statement (verbatim)
Build a complete SaaS/dashboard system for an XSS scanner tool similar to xss0r. Stack: React + FastAPI + MongoDB. MVP scope: auth + user dashboard + admin panel + license system. Both JWT email/password and Emergent Google login. No payments. Real object storage for build uploads/downloads. Demo seed data.

## Architecture
- **Backend:** FastAPI (`/app/backend/server.py`), MongoDB (motor), bcrypt + PyJWT auth, Emergent OAuth session exchange, Emergent object storage for binaries.
- **Frontend:** React 19 + react-router-dom, shadcn/ui, Phosphor Icons, Azeret Mono / IBM Plex Sans typography, dark Swiss/terminal aesthetic.
- **Auth model:** unified `get_current_user` accepts `access_token` cookie (JWT), `session_token` cookie (Google), or `Authorization: Bearer`.

## User personas
1. **Operator (user):** security pro buying license, downloads CLI build, manages HWID/API key, redeems coupons.
2. **Admin:** ops staff managing users, coupons, builds, monitoring stats.

## Core requirements (static)
- Email/password register, login, forgot/reset password, JWT cookies + refresh
- Emergent Google social login (unified session)
- License + plan + expiry + max activations per user
- API key (rotate), HWID activations (reset), scan history (read)
- Coupon redemption (extends license)
- Build downloads via object storage (admin upload, user download with active license)
- Admin: stats, users (ban/unban), coupons CRUD, builds upload/delete

## Implemented (2026-02-09)
- Full auth (register/login/logout/me/refresh/forgot/reset, Google session exchange) with brute-force lockout
- License system + API key + HWID activations + scans
- Coupons (admin CRUD + user redeem with idempotency)
- Builds (admin multipart upload to Emergent object storage + user signed download via backend)
- Admin: stats, users list+ban, coupons CRUD, builds upload/delete
- Public landing page with hero, features, pricing (3 plans), terminal-style mock
- Dashboard (overview, license, downloads, scans, coupons)
- Admin panel (stats, users, coupons, builds)
- Demo seed: admin, demo user with Pro license + 3 scans + HWID, 2 coupons (LAUNCH50/XSS0R10), 2 build entries
- 21/21 backend pytest passing; frontend e2e flows verified

## Test credentials
- Admin: `admin@xss0r.io` / `Admin@xss0r2026`
- User: `user@xss0r.io` / `User@xss0r2026`

## Backlog (P0 / P1 / P2)
**P0** — none blocking
**P1**
- Email delivery for forgot-password (currently logs link to backend logs)
- Real CLI activation endpoint + HWID lock (currently HWID list is read-only)
- Plan upgrade flow (admin can edit plans + per-user override)
**P2**
- Stripe payments + plan checkout
- Email verification on register
- Audit log for admin actions
- 2FA (TOTP) for admin accounts
- Rate-limit per API key (CLI usage)
- Per-build SHA256 + signing key display
- Webhook delivery for scan events
- Dark/light theme toggle
- i18n (Bosnian/Serbian/Croatian, English)
- Refactor server.py into routers (auth/license/admin/builds modules)

## Notes
- `server.py` is monolithic (~860 lines). Splitting into routers is recommended once feature surface stabilizes.
- Object storage gracefully reports "Storage unavailable" if `EMERGENT_LLM_KEY` missing.
- CORS uses explicit `FRONTEND_URL` from env (required for credentials).
