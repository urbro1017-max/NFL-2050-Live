# ATLAS 61.0 — Production Recovery

Production-focused repair build.

- Frontend build identity corrected to 61.0 (older packages accidentally still rendered 57.0).
- Asset URLs changed to atlas61 + cache-busting query strings.
- All frontend responses are no-store; stale service workers self-destruct and clear old caches.
- `/api/build` proves which backend/frontend package is deployed.
- Final-game hydration now tries ESPN site summary then ESPN CDN game package.
- Data Core recovery rehydrates finals missing player rows OR skill-position identity.
- Data Center exposes player position counts and bootstrap migration result.
- Existing archive is preserved; normalized rows are idempotently upserted.
