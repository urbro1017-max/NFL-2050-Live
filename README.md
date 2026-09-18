# GRIDIRON ATLAS 5.0 — Clean System Overhaul

A stability-first overhaul of the 4.0 Command Center.

## What changed
- Cleaner, denser command-center UI with improved typography, spacing, responsive cards, and stronger selected states.
- Performance Deck adds verified 3rd-down, 4th-down, penalties, possession, yards/play, and red-zone fields when the connected feed supplies them.
- Team comparison expanded beyond basic yardage while preserving exact stat aliases.
- Pregame/live/final phase labeling so available context is not automatically presented as live game data.
- Scoreboard discovery now uses the Eastern Time calendar date rather than the server's local/UTC date.
- Short scoreboard cache reduces repeated ESPN hydration calls on busy game windows.
- Additional HTTP security headers.
- Manual collection through GET `/api/collect` is disabled; the automatic collector remains active.
- Dynamic play, drive, and scoring text is escaped before rendering in the main live surfaces.
- Existing PostgreSQL archive, player box score, scoring summary, replay, history, back navigation, and live refresh remain intact.

## Data rule
If a field cannot be mapped to a verified connected value, GRIDIRON ATLAS displays `—`. Derived displays must be clearly labeled and use only connected values.

## Render
Build command: `pip install -r requirements.txt`
Start command: `python server.py`
Keep `DATABASE_URL` private and in Render Environment only.
