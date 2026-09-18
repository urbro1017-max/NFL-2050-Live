# GRIDIRON ATLAS 6.2 — Live Sync Reliability

6.2 fixes the live-sync gate discovered in 6.1.

## Live sync changes
- Selected game now refreshes continuously at the configured cadence (5 seconds by default), instead of only when a parsed provider state exactly equals `in`.
- Provider state still controls LIVE/PREGAME/FINAL labels, but can no longer disable synchronization.
- Refreshes immediately when the browser regains focus or becomes visible.
- Prevents overlapping requests with a sync lock.
- Cache-busts selected-game requests and API JSON sends no-store headers.
- UI exposes last successful sync age / retry state.
- Server collector hydrates every game discovered for the active NFL date, avoiding state-parser mismatches that could prevent collection.
- PostgreSQL persistence remains enabled through DATABASE_URL.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep `DATABASE_URL` private.
