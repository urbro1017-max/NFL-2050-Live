# ATLAS 75.6 — Refined Visual Intelligence

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


## 75.6 refinement
Removed redundant visual layers from Home, Teams, and ATLAS AI so each metric has one primary home. Game, Game Graphs, and Weekly Recap retain supplemental visuals where they add distinct information. Homepage model-leader duplication was removed and spacing/hierarchy tightened.


ATLAS 75.6 adds Visual Intelligence charts and command search while preserving the 71.0 clean-slate interface.


ATLAS 75.6 adds live animated field position, auto-reordering live player production, useful live game comparisons, and a clean warm amber/coral/plum palette replacing the blue-heavy theme.


ATLAS 75.6 Connected Intelligence: contextual grounded OpenAI reasoning, player intelligence drawer, Compare Lab, live game pulse/game-day mode, position-aware impact ordering, team timeline, prediction receipts, confidence badges, favorite team, command search 2.0, and mobile refinements.


75.6 Production Recovery: player profile endpoint is resilient to ESPN profile/stat/gamelog failures, falls back to ATLAS roster/archive data, drawer accepts list/object stats, and duplicate simultaneous API requests are coalesced.


75.6: player drawer passes known roster name/team into the backend; player profiles can render from team roster + ATLAS archive without requiring ESPN athlete-profile success. Stale bundled SQLite DB removed.


75.6 Player Intelligence: position-aware production filtering and readable archived game context (opponent/date/result when stored). Irrelevant QB stats are no longer shown on TE/WR/RB profiles.


75.6: browser title corrected to ATLAS 75.6; player production uses exact position-aware semantic stat matching and deduplication so TE profiles no longer surface passing/rushing fumble variants as receiving production.


75.6 GAME NIGHT: larger typography, warm-only neon palette, streamlined live box score, two additional live game graphs with 5-second graph refresh, and clearer OpenAI API diagnostics without exposing secrets.


75.6: ATLAS AI reasoning provider migrated from OpenAI to Gemini. Configure GEMINI_API_KEY in Render; optional GEMINI_MODEL defaults to gemini-3.5-flash. Key remains server-side.


75.6 visual correction: full stylesheet color audit/remap removes remaining cool blue/cyan legacy colors and globally raises interface typography sizes while preserving Game Night box score, live graphs, and Gemini integration.


75.6 instant-boot recovery: HTTP server binds before database bootstrap, AI snapshot, or collector work so Render can serve the UI immediately even if a provider/database repair is slow.


75.6 loading recovery: the browser no longer waits indefinitely for core data before rendering. Core API calls begin in parallel with a 1.2s first-paint budget, so the ATLAS shell renders even while background ingestion/database endpoints are busy. Also corrects remaining OpenAI UI labels to Gemini and hard-coded graph colors to the warm palette.


75.6 boot recovery: HTML now contains a guaranteed visible first-paint ATLAS boot screen before JavaScript executes, plus browser startup-error reporting. The JS bundle also paints synchronously before any API work. This prevents an unexplained blank black page and surfaces any browser-side startup failure visibly.


75.6 runtime fix: fixes a top-level ReferenceError (`g is not defined`) caused by the Game Graphs live-refresh block being outside `graphs()`. This error prevented the entire browser bundle from starting and produced the blank black page.
