# ATLAS 59.0 — Data Core Rebuild

ATLAS 59 replaces the patched archive-to-AI chain with one normalized completed-game data core.

## Data flow
ESPN ingestion → archived raw final → normalized `team_game_stats` + `player_game_stats` → Teams / Weekly Recap / ATLAS AI.

- `games` remains the raw immutable archive and migration source.
- `team_game_stats` stores one durable row per team per completed game.
- `player_game_stats` stores one durable row per player per completed game, merging stat categories.
- `data_pipeline` records per-game ingestion health (2 team rows expected; player rows when ESPN box scores provide them).
- Existing archived finals are migrated automatically at startup; missing player box scores are recovered in throttled background batches.
- Teams reads normalized completed-game rows as its primary stored-stat source.
- Weekly Recap reads normalized player-game rows.
- ATLAS AI derives team strength, player production and MVP signal from the same normalized rows.
- `/api/data-center` and `/api/stats-health` expose pipeline diagnostics without adding another top-level navigation tab.

No existing raw game archive is deleted.
