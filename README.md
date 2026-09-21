# ATLAS 57.0 — Postgame Pipeline

Render-ready build focused on final-game player-stat persistence and the ATLAS AI/Weekly Recap data path.

## What changed
- Adds a normalized `player_game_stats` database table (Postgres + SQLite).
- Final-game saves now upsert one persistent row per player/game, merging ESPN box-score categories.
- Background recovery finds archived finals that lack normalized player rows and re-fetches their final box score in small batches.
- `/api/postgame-stats` exposes real pipeline diagnostics, normalized rows, and database-backed weekly performance candidates.
- Archive Intelligence prefers normalized player rows and falls back to legacy archived game JSON only when needed.
- Weekly Recap awards read the normalized postgame database instead of scoreboard objects.
- ATLAS AI projection engine bug fixed (`re` dependency) and continues to consume Archive Intelligence.
- UI diagnostics show finals with player stats, normalized row count, and repair queue.

## Deploy
Deploy the ZIP contents at repository root. Keep the existing Render Postgres `DATABASE_URL`; schema migration is automatic at startup.
