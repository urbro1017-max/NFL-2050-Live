# GRIDIRON ATLAS 3.2 — Scoreboard Discovery Fix

## What changed
- NFL game discovery now uses ESPN Core `events` references.
- Each discovered event is hydrated from the ESPN CDN game package used by Game HQ.
- Fixes the 3.1 bug where `/api/games` returned an empty list because different ESPN response shapes were treated as interchangeable.
- `/api/games?date=YYYYMMDD` supports explicit date discovery.
- PostgreSQL, collector, archive, scouting, replay, Front Office, CSV, and PWA behavior are retained.
- Diagnostics identify the Core discovery/CDN game transport and preserve archive fallback.

## Render
Build command:
`pip install -r requirements.txt`

Start command:
`python server.py`

Keep `DATABASE_URL` configured in Render Environment. Never commit credentials.

## Data integrity
Connected public-feed values are displayed as sourced values. Missing fields remain unavailable rather than being fabricated. User-authored scouting notes remain separate from sourced stats.
