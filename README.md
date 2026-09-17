# GRIDIRON ATLAS 3.12 — Control Deck

Navigation cleanup and consolidation on top of the 3.11 Game Intelligence build.

## Changes
- Sidebar condensed to five plain-language destinations: GAME, SCOREBOARD, PLAYERS, ANALYSIS, HISTORY.
- Settings remains the gear at the bottom of the rail.
- Season and Replay are consolidated under HISTORY; Game Replay remains reachable from the History screen.
- NFL Scoreboard sub-navigation reduced to five direct destinations: GAME LIVE, TEAM BOX, PLAYER BOX, PLAYS, DRIVES.
- Removed duplicate Situational/Analytics buttons from the Scoreboard sub-nav; those tools remain accessible from Analysis.
- Command palette labels updated to match the clearer navigation language.
- All existing live-game, ESPN feed, PostgreSQL, player, scoring summary, and Game Intelligence functionality retained.

## Data integrity
Feed-backed or clearly derived values only. Unknown/unavailable values remain `—`.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep `DATABASE_URL` private.
