# GRIDIRON ATLAS 11.0 — NFL OPERATING SYSTEM

11.0 moves Atlas from a single-game-first product to a league-week platform.

## NFL Week Engine
- Automatically discovers the current NFL week from the schedule provider.
- Week navigation for the 2026 regular season.
- Lifecycle states: UPCOMING → LIVE → FINAL → ARCHIVED.
- Sunday Command grid shows the entire slate and drills directly into Game Center.
- Browser date requests are normalized before Core event discovery.

## Smart collector
- Discovers the whole current week on each collector cycle.
- Live games are hydrated automatically.
- Pregame games are hydrated only near kickoff.
- Completed games receive a final archival capture and are then left alone.
- Existing PostgreSQL game/archive system remains the source for Atlas-owned history.

## Existing Atlas systems retained
- Player Universe with honest archive coverage, game log, trends and splits.
- Team Universe, League, Lab, My Atlas and multi-source Game Center.
- Missing or unverifiable values remain —.
- Tracking-grade metrics remain source-gated.

No secrets or database files are included in this package.
