# Auth Testing Playbook (xss0r SaaS)

Both flows should be tested:

## 1. JWT Email/Password
```
curl -c /tmp/cookies.txt -X POST $BACKEND/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@xss0r.io","password":"Admin@xss0r2026"}'

curl -b /tmp/cookies.txt $BACKEND/api/auth/me
```
Expect: 200 with user object containing `role: "admin"`. Cookies `access_token` and `refresh_token` set.

## 2. Emergent Google Login
- Browser navigates to `https://auth.emergentagent.com/?redirect=<frontend>/auth/callback`.
- After Google auth, user lands at `<frontend>/auth/callback#session_id=...`.
- Frontend POSTs the `session_id` to `/api/auth/google/session`.
- Backend exchanges with `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`.
- Backend stores user, sets `session_token` cookie (httpOnly, samesite=none, secure=true).
- `/api/auth/me` should return the user.

## 3. Admin endpoints (admin role only)
- GET `/api/admin/stats`
- GET `/api/admin/users`
- POST `/api/admin/users/{id}/ban`
- POST `/api/admin/coupons` (create)
- GET `/api/admin/coupons`
- DELETE `/api/admin/coupons/{id}`
- POST `/api/admin/builds` (multipart file upload)
- DELETE `/api/admin/builds/{id}`

## 4. User endpoints
- GET `/api/license/me`
- POST `/api/license/regenerate-api-key`
- POST `/api/license/reset-hwid`
- GET  `/api/scans`
- GET  `/api/builds` (list available builds)
- GET  `/api/builds/{id}/download` (returns binary)
- POST `/api/coupons/redeem` (apply coupon to extend license)

## Mongo collections
`users`, `user_sessions`, `licenses`, `api_keys`, `hwid_activations`, `scans`, `coupons`, `builds`, `password_reset_tokens`, `login_attempts`.
