# GRIDIRON ATLAS 3.7 — Voltage Rail UI

A visual redesign of 3.6 with the existing live-game engine preserved.

## 3.7 changes
- Desktop navigation moved to a fixed vertical left rail.
- New obsidian / acid-lime / violet color system while preserving team-specific DET/BUF accents.
- More horizontal room for football data and cleaner content hierarchy.
- Stronger text wrapping and overflow handling for KPI cards, tables, drives, and navigation.
- Responsive compact navigation behavior for smaller screens.
- Existing live feed, player stats, PostgreSQL archive, ESPN discovery/CDN parsing, replay, scouting, and Front Office modules retained.

## Data integrity
Unavailable connected-feed values remain `—`; the UI does not invent missing statistics.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep `DATABASE_URL` private and unchanged.
