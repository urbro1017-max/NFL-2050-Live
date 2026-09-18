# GRIDIRON ATLAS 6.1 — Stability + Players Frontend

6.1 replaces the accumulated legacy dashboard with one coherent application shell while preserving the ESPN/PostgreSQL backend.

## Major changes
- Browser-native internal routing with Back/Forward history for page + game + subtab + scroll state.
- Five primary destinations only: Game Center, NFL Games, Players, Analytics, Archive; Settings stays in a bottom gear drawer.
- NFL Games is a real workspace: Overview, Team Stats, Player Stats, Drive Chart, Play-by-Play swap content rather than scrolling through one giant page.
- One structured provider game state controls Pregame / Live / Final presentation.
- Game Center is intentionally compact: matchup, situation KPIs, leaders, current drive, latest play.
- Player database with team/position filters, player profiles, verified game stat lines, and ESPN-hosted headshot fallback using provider athlete IDs.
- Visualizations: cumulative scoring flow, scoring by quarter, drive chart.
- Analytics: yards/play, points/drive, explosive-play rate, three-and-out rate. Derived metrics are explicitly marked `ƒ DERIVED` and show unavailable when inputs are missing.
- Archive reconstructs stored games and saved score progression from PostgreSQL snapshots.
- Feed text is HTML-escaped before dynamic rendering.
- Live polling only runs while the selected game is in the provider's `in` state.
- Collector uses structured provider state instead of matching status text.
- Frontend split into `index.html`, `styles.css`, and `app.js` rather than one giant HTML file.

## Data integrity
No synthetic football values are inserted. Feed values are marked/treated as connected data; calculated values are labeled derived. Missing inputs render as unavailable.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep `DATABASE_URL` private.


## 6.1 fixes
- Fixed missing datetime/ZoneInfo imports that could break /api/games at runtime.
- Players page now always includes the verified embedded DET/BUF matchup roster before live box-score rows arrive.
- Player box score clearly falls back to BASELINE roster data pregame instead of appearing empty.
- Back/Forward preserves the current internal tab route and direct hash routes survive refresh.
- Live player rows remain feed-only; baseline rows are never mislabeled as live.
