# GRIDIRON ATLAS 3.3 — Data Integrity & Live Game Cleanup

This release focuses on correctness and live-game usability rather than adding empty modules.

## 3.3 changes
- Exact team-stat alias matching. Passing/rushing/total yards can no longer match one another through fuzzy substring lookup.
- ESPN team-logo fallback when a game package omits `team.logo`.
- Missing drives and play-by-play now have explicit unavailable states instead of blank/broken panels.
- Current drive is included when ESPN exposes it separately from previous drives.
- Stale Universal Game Center version label updated to 3.3.
- Archive copy no longer incorrectly claims SQLite when PostgreSQL is connected.
- Existing PostgreSQL, ESPN Core discovery, ESPN CDN game feed, collector, replay, scouting, and Front Office functionality retained.

## Data integrity rule
If a value cannot be mapped to a verified field from the connected feed, GRIDIRON ATLAS displays `—`. It does not substitute a similar statistic.

## Render
Build command: `pip install -r requirements.txt`

Start command: `python server.py`

Keep the existing `DATABASE_URL` environment variable private. Never commit it to GitHub.
