# ATLAS 39.0 — GAME DAY FINAL

Render-ready game-day hardening build.

- smart 8s live / 30s upcoming / 60s idle polling
- request de-duplication to reduce duplicate API work
- live Game Room detail refresh
- persistent last-good UI during transient feed failures
- explicit LIVE / STALE / RECONNECTING feed state
- prediction snapshots remain immutable and resolve after finals
- forecast sanity filtering for malformed probabilities
- larger navigation targets and game-rail snapping
- API traffic remains network-only in the service worker
