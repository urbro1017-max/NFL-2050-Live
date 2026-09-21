# ATLAS 62.0 — AI Engine

Production-focused AI performance rebuild.

- `/api/projections` serves a precomputed in-memory snapshot instead of calculating models during the browser request.
- AI calculations read only normalized `team_game_stats` and `player_game_stats`; no raw archive scan and no network request is allowed in the AI engine.
- Snapshot rebuilds automatically every 60 seconds and at server startup.
- Existing ATLAS 61 ingestion and per-team normalized stats pipeline is preserved.
- `/api/build` reports the exact 62.0 frontend/backend asset identity.


## 63.0 Intelligence Layer
Set `OPENAI_API_KEY` in Render Environment to enable ATLAS Intelligence. Optional: `OPENAI_MODEL` (default `gpt-5.4`) and `OPENAI_TIMEOUT` (default 25 seconds). The key is server-side only and is never exposed to the browser. Core stats/projections continue working without the key.
