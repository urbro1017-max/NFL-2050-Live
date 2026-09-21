# ATLAS 60.0 — FOOTBALL OS

Render-ready build.

## Core rebuild
- Dedicated completed-game hydration path uses the final ESPN summary/box score instead of relying on whichever live subfeed wins candidate selection.
- Normalized `team_game_stats` and `player_game_stats` remain the durable source of truth.
- ATLAS AI aggregates directly from normalized player rows; it no longer needs to reparse archived provider JSON.
- Team trends and Teams-page completed-game stats read normalized team rows.
- Startup migration/backfill scans existing Finals and repairs missing player rows through the dedicated final hydrator.
- Data Center exposes pipeline coverage and repair state.

## Product pass
- Football OS command center on Home.
- Team Data Core health panel.
- ATLAS AI Model Lab with database pipeline health, team strength visualization, upcoming model board, rankings, season outlook, position leaders and MVP signal.
- Existing Game Intelligence, headshots, split comparison, Field Vision, replay, weekly recap, and performance loading architecture retained.

## Truth rules
ATLAS model outputs are derived estimates, not official NFL rankings. Missing provider data remains missing and is never fabricated.
