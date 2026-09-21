# ATLAS 58.0 — Unified Stats Pipeline

Render-ready build focused on one durable path: completed game -> persistent database -> Teams / Weekly Recap / ATLAS AI.

## Changes
- Normalizes team abbreviations before final-game persistence.
- Persists normalized player game rows for completed games and merges a player's categories by game.
- Adds archive-derived team season totals so the Teams tab is populated from ATLAS-owned completed games when ESPN's season-stat endpoint is unavailable or delayed.
- Weekly Recap and ATLAS AI consume the same normalized player-game database.
- ATLAS AI continues to model all 32 teams and builds fantasy/MVP signals from stored final-game player production.
- Adds `/api/stats-health` to expose postgame coverage and per-team stored-game coverage.
- Cache-busted frontend assets to atlas58.

## Validation performed
- JavaScript syntax check.
- Python compile check.
- Synthetic completed-game test verified: final -> database -> merged player rows -> KC team totals -> 32-team projection engine -> fantasy/MVP output -> stats-health.
