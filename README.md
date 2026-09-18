# GRIDIRON ATLAS 10.0 — UNIVERSE

Depth-first overhaul of GRIDIRON ATLAS. The primary navigation is consolidated to LIVE, LEAGUE, TEAMS, PLAYERS, LAB, FRONT OFFICE, and MY ATLAS while preserving legacy deep workspaces as contextual tools.

## 10.0 additions
- Team Universe with all-32 selection, season context, stored-game production, team leaders, roster/matchup/trend jumps
- Atlas Lab with Play Explorer, Drive Lab, Situational Matrix, Scoring Anatomy, and consolidated deep-tool launcher
- Play filtering by text, team, play type, down, and explosive threshold
- CSV export for captured game play-by-play
- Existing Week Center, Season Center, Roster HQ, Matchup Lab, Data Quality, War Room, Film Room, Stat Studio, Game DNA, Situation Lab, Archive, universal command search, density modes, TV mode and PWA retained
- 9.1 runtime bug involving undefined legacy render wrappers removed
- Service worker cache bumped to v100

## Data integrity
Provider values remain provider-supplied. Atlas-derived metrics are labeled. Unsupported metrics display —. Tracking-grade advanced metrics remain source-gated.

## Deploy
Upload the contents of this package directly to the existing GitHub repository root. Keep the existing Render service and DATABASE_URL unchanged.
