# GRIDIRON ATLAS 11.1 — SUNDAY READY

Reliability overhaul built on 11.0 NFL Week Engine.

## 11.1 changes
- Adaptive browser polling: live games fast, near-kickoff games moderate, distant pregame slow, final games stop polling.
- Completed games are served from the Atlas archive for normal UI reads instead of repeatedly hitting upstream providers.
- Week collector records discovered/attempted/succeeded/failed/skipped counts and isolates background errors.
- Sunday Command adds All / Live / Upcoming / Final filters and collection-state messaging.
- Final Game Center swaps live situation KPIs for final team comparisons and labels the last possession correctly.
- Week schedule cache tightened while full game hydration remains state-aware.
- Service worker cache bumped to v111.

Data integrity rule: unavailable statistics remain —. Atlas does not fabricate provider data.
