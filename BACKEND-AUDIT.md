# CAM'S STATS — data integrity and deployment audit

## Confirmed from source inspection
- The frontend reads `/fantasy-data.json`; if absent, the SPA rewrite returns `index.html`, causing `Unexpected token '<'`. The client now checks content-type and validates the dataset shape before displaying rankings.
- The previous Render blueprint built Vite **without running the fantasy collector**. The blueprint now runs `npm run build:with-data`, which collects, validates, and builds.
- The fantasy collector reads completed NFL regular-season game summaries and extracts QB/RB/WR/TE box-score stats. Failed games now stop the build by default instead of silently publishing partial rankings.
- Existing NFL/NBA scoreboards, player rosters, game summaries and athlete stats rely on **unofficial ESPN endpoints**, not a managed/guaranteed backend.
- The legacy homepage and NFL/NBA pages contained hardcoded fantasy/leader numbers. The most prominent misleading homepage ranking and league leader panels are now hidden in favor of honest availability messages. Some other prototype tools (GM simulator, predictions, analyst, analytics) remain illustrative.

## Not verified / not guaranteed
- Live provider connectivity from this build environment (outbound network unavailable).
- A successful production build (npm dependencies unavailable offline).
- Complete current NFL/NBA rosters or complete per-player season statistics.
- That ESPN will serve every historical game, every stat category, or browser CORS on every endpoint.
- Full player and game coverage cannot be claimed until the collector is run and verified on Render.

## Deployment
1. Replace repository files with this release, keeping `render.yaml` in the repository root.
2. On Render, set build command to `npm install && npm run build:with-data` and publish directory to `dist` (Static Site recommended).
3. Build fails if any completed NFL game summary could not be fetched or if parsed data is empty. Inspect logs rather than hiding the failure.
4. Confirm `/fantasy-data.json` serves `application/json`, not the website HTML.
5. Check the generated `completeness` field and number of players in the JSON response.
6. To intentionally allow incomplete data set `ALLOW_PARTIAL_DATA=1` as a Render environment variable; the site should disclose incomplete data.
7. Run `npm run data:check` to validate an existing dataset.

## Important maintenance
- Builds refresh fantasy stats only **on deployment**. For daily refresh, schedule a daily deploy or move data collection to a scheduled backend job.
- `FANTASY_SEASON` can override the season. Do not set it to a season with zero completed games.
- This collector covers QB/RB/WR/TE only; no K/DST, no injury-adjusted projections, no guarantee of full season completeness.
