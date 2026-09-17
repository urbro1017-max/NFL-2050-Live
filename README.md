# GRIDIRON ATLAS 3.1 — Football Intelligence Platform

Render-ready NFL analytics platform.

## External architecture now included
- ESPN public game/scoreboard provider adapter.
- Automatic collector thread (default 30 seconds) for active/final games.
- PostgreSQL support through `DATABASE_URL` using psycopg.
- Automatic SQLite fallback for local use.
- Persistent game, player-stat and snapshot archive when PostgreSQL is connected.
- Provider/data-health diagnostics.
- Generic player and team indexes generated from archived games.
- CSV game export.
- PWA/offline shell retained.

## Football intelligence modules
All previous Game HQ, Broadcast, MAX Lab, Analytics Lab, Player Center, Season HQ, situational labs, comparison, themes and TV mode remain.

3.0 additionally adds:
- Replay Center with speed controls and field movement.
- Scouting Notebook with user-authored player grades/notes.
- Film notebook/tags.
- Front Office Mode.
- Archived player database and position rooms.
- Archived team database.
- External-module slots for cap, depth/availability, personnel/formation and draft data.

## Data integrity
Provider facts are displayed as sourced data. User scouting grades are explicitly user-authored. Missing external data stays `—`; it is never generated.

## PostgreSQL
The app checks `DATABASE_URL`. If it is present and reachable it uses PostgreSQL; otherwise it falls back to SQLite.

On Render, connect a Render Postgres database and provide its internal database URL as `DATABASE_URL`. Never commit database credentials to GitHub.

## Hosting
Build: `pip install -r requirements.txt`
Start: `python server.py`


## 3.1 provider reliability update
- ESPN CDN scoreboard/game endpoints are now primary.
- Site API is fallback only.
- Diagnostics identify the failing provider endpoint instead of reporting only a generic HTTP error.
- `/api/health` reports version `3.1`.
