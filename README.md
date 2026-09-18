# GRIDIRON ATLAS 13.0 — INTELLIGENCE ENGINE

12.3 is a read-only analytics and archive-experience release built on top of the proven 12.2 Archive Engine. It deliberately does not alter the collector/backfill lifecycle.

## Added
- Archive Intelligence endpoint over Atlas-owned final-game data.
- Archive Explorer with capture quality, player/play/drive counts, and direct game drilldown.
- Atlas Timeline for captured finals.
- Sample Leaders for passing, rushing, receiving, and defensive counting stats.
- Team scoring-differential trend board with captured-game sample sizes.
- Dataset telemetry: finals, unique player entities, teams, plays, drives.
- League navigation consolidation: six primary league tools plus a More menu for advanced/legacy tools.
- Responsive analytics layouts.

## Integrity rules
- Analytics use final-game Atlas archives only.
- Sample sizes are shown.
- Only unambiguous counting statistics are aggregated. Rates, averages, long plays, QBR/pass rating, percentages, and compound values are not summed.
- Missing values remain unavailable.
- No tracking/NGS values are fabricated.

## Deployment
Upload the contents of this package to the existing repository root. Keep the existing Render service, build/start commands, and DATABASE_URL unchanged.


## 13.0 additions
- Dedicated Game Intelligence workspace with live narrative from captured game state.
- Clearly labeled Atlas score/time win-probability model and snapshot timeline.
- Position-aware 0–99 Atlas Impact model and live MVP race.
- Drive Analyzer with plays, yards, time, result, and yards/play when available.
- Feed-age status surfaced in the intelligence workspace.
- Direct player drilldowns from the MVP race.
- Professional visual pass: quieter surfaces, tighter borders, glass header, stronger hierarchy, and responsive intelligence cards.
- Existing player profiles, team universe, archive intelligence, compare lab, command search, historical archive/backfill, and auto-collection remain intact.

All new computed metrics are explicitly marked as Atlas-derived. Missing provider data is never fabricated.
