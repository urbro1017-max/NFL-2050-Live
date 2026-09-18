# GRIDIRON ATLAS 6.3 — Live Schema Repair

Fixes verified against the user-captured live ESPN payload for game 401872932.

- Flattens live plays embedded inside ESPN drive objects.
- Deduplicates and chronologically orders plays.
- Normalizes drive time and play counts.
- Builds possession/down/distance/spot from the latest play end-state.
- Uses exact ESPN team-stat labels.
- Uses category-specific passing/rushing/receiving leaders.
- Uses official statYardage for derived explosive-play calculations.
- Keeps 5-second no-store browser polling and PostgreSQL collector persistence.
- Version UI/API updated to 6.3.

Render settings stay unchanged: build `pip install -r requirements.txt`, start `python server.py`, preserve DATABASE_URL.
