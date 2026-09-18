# GRIDIRON ATLAS 10.3 — BLUE PRIME

10.3 repairs team-season statistics and strengthens player-stat retrieval while consolidating the BLUE PRIME interface.

## Major changes
- Multi-source 2026 player-stat resolver: ESPN Web athlete stats -> unfiltered athlete stats -> ESPN Core season/type statistics -> season athlete statistics fallback.
- More tolerant stat normalizer for both object-based and paired-label/value ESPN schemas.
- 2026 game-log/event-log fallback surfaces.
- Player profiles now identify the stat source and keep unavailable values as `—`.
- Refined blue PRIME player interface: stronger identity hero, denser bio strip, position-aware stat blocks, game-log rail, table/interaction polish.
- All 32 team rosters/depth-chart selection from 10.1 retained.
- No secrets or local database included.

## Render
Keep the existing service, `DATABASE_URL`, build command, and start command. Upload these root files over the existing GitHub repository and let Auto-Deploy run.
