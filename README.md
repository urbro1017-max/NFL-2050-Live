# ATLAS 75.2 — Refined Visual Intelligence

A visual overhaul built on the working ATLAS 67.1 data pipeline.

## Visual changes
- New animated, data-driven neon visualization layer on Home, Games, Teams, Game Graphs, Weekly Recap, and ATLAS AI.
- Cyan, electric blue, violet, magenta, orange, and aqua accents on a restrained dark interface.
- Larger page typography and clearer chart labels.
- Home adds league power spectrum, strength landscape, and player-model coverage.
- Games adds slate scoring and slate-state visuals.
- Teams adds performance profile and roster architecture visuals.
- Game Graphs adds quarter rhythm and drive-flow visuals.
- Weekly Recap adds scoring pulse and margin map.
- ATLAS AI adds elite power band and projected-finish visual boards while retaining the side-by-side hierarchy layout.
- Visuals use returned/stored data only; unavailable data renders an honest empty state.

## Deployment
Upload the extracted repository contents to GitHub/Render. Do not commit a local SQLite database or an OpenAI API key.


## 75.2 refinement
Removed redundant visual layers from Home, Teams, and ATLAS AI so each metric has one primary home. Game, Game Graphs, and Weekly Recap retain supplemental visuals where they add distinct information. Homepage model-leader duplication was removed and spacing/hierarchy tightened.


ATLAS 75.2 adds Visual Intelligence charts and command search while preserving the 71.0 clean-slate interface.


ATLAS 75.2 adds live animated field position, auto-reordering live player production, useful live game comparisons, and a clean warm amber/coral/plum palette replacing the blue-heavy theme.


ATLAS 75.2 Connected Intelligence: contextual grounded OpenAI reasoning, player intelligence drawer, Compare Lab, live game pulse/game-day mode, position-aware impact ordering, team timeline, prediction receipts, confidence badges, favorite team, command search 2.0, and mobile refinements.


75.2 Production Recovery: player profile endpoint is resilient to ESPN profile/stat/gamelog failures, falls back to ATLAS roster/archive data, drawer accepts list/object stats, and duplicate simultaneous API requests are coalesced.


75.2: player drawer passes known roster name/team into the backend; player profiles can render from team roster + ATLAS archive without requiring ESPN athlete-profile success. Stale bundled SQLite DB removed.


75.2 Player Intelligence: position-aware production filtering and readable archived game context (opponent/date/result when stored). Irrelevant QB stats are no longer shown on TE/WR/RB profiles.


75.2: browser title corrected to ATLAS 75.2; player production uses exact position-aware semantic stat matching and deduplication so TE profiles no longer surface passing/rushing fumble variants as receiving production.


75.2 GAME NIGHT: larger typography, warm-only neon palette, streamlined live box score, two additional live game graphs with 5-second graph refresh, and clearer OpenAI API diagnostics without exposing secrets.


75.2: ATLAS AI reasoning provider migrated from OpenAI to Gemini. Configure GEMINI_API_KEY in Render; optional GEMINI_MODEL defaults to gemini-3.5-flash. Key remains server-side.


75.2 visual correction: full stylesheet color audit/remap removes remaining cool blue/cyan legacy colors and globally raises interface typography sizes while preserving Game Night box score, live graphs, and Gemini integration.
