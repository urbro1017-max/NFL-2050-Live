# GRIDIRON ATLAS 10.1 — PRIME

All-32 roster and player-profile overhaul built on 10.0 Universe.

## New in 10.1
- All 32 NFL teams selectable in Team Universe and Roster HQ.
- Server-side roster import with six-hour cache.
- Depth-chart merge; rank-1 entries are labeled as starters only when the depth feed verifies rank 1.
- League-wide Players directory built from current team rosters.
- Player profiles with provider-supplied jersey, position, age, height, weight, experience, college, headshot, and 2026 season statistics when available.
- Team Universe starter strip with clickable player profiles.
- New PRIME interface: navy/slate, warm off-white, electric cyan, amber highlights, restrained team-color accents.
- Existing 10.0 live, league, team, lab, front-office, archive and database systems preserved.

## Data integrity
Roster/depth/profile data are fetched at runtime from the existing ESPN public JSON surfaces used by Atlas. Unsupported or missing values display —. Atlas does not infer starter status: only rank-1 depth-chart entries receive the starter label. These endpoints are unofficial/undocumented transports and may change.

## Render
Keep the existing service and DATABASE_URL. Build: `pip install -r requirements.txt`. Start: `python server.py`.
