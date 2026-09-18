# GRIDIRON ATLAS 12.1 — ATLAS ONE · SYSTEM PASS

12.1 is the consolidation/cleanup pass on ATLAS ONE: a repaired My Atlas Today dashboard, direct universal search, breadcrumbs/deep-link polish, request deduplication, richer archive telemetry, player coverage clarity, loading states, and UI cleanup while preserving the 11.x Week Engine and Atlas-owned archive.

Data integrity rule: unavailable provider fields remain unavailable; Atlas-derived values are labeled; tracking-grade metrics stay source-gated.

The largest consolidation release yet. 12.1 turns the Sunday Week Engine into the front door of a unified NFL analytics operating system.

## Major changes
- ATLAS ONE NFL Command Center with kickoff-window grouping, team logos, records, venue context, live/final/upcoming states, and one-click game drilldown.
- Atlas Data Core telemetry: PostgreSQL/archive coverage, final-game count, verified player coverage, teams seen, and collector state.
- Data Trust rail on the selected game showing live/final/archive lineage, feed age, player rows and play-event coverage.
- New `/api/atlas` product-level coverage endpoint and `/api/quality` game-quality endpoint.
- Adaptive background collector sleeps slower when no games are live and returns to the configured cadence during live windows.
- Upcoming games remain schedule-only until the collection window; archived finals remain local-first.
- Legacy Game Center switcher removed from the Command Center so the six-product navigation remains the product hierarchy.
- Sunday slate grouped into Thursday / Sunday Early / Sunday Late / Sunday Night / Monday Night / Completed windows.
- Passer-rating labels normalized to `PASSER RTG`; QBR is not synthesized from passer rating.
- Service worker cache bumped to v120.

## Data policy
Provider values are displayed as supplied. Atlas-derived values must be labeled. Unsupported data stays unavailable rather than being fabricated. Tracking-grade metrics remain source-gated.

## Deploy
Upload the contents of this ZIP directly to the existing GitHub repository root. Keep the existing Render service, build command, start command, and `DATABASE_URL` environment variable.