# CAM’S STATS — release checks

## Verified locally without external dependencies
- Server syntax, data collector syntax, validator syntax.
- Node smoke tests for health endpoint, restricted proxy routing, missing JSON behavior.

## Requires a successful Render build and live provider responses
- `npm install && npm run build:with-data` downloads real NFL data and runs Vite.
- `npm start` serves both frontend and proxy (do not use `vite preview`).
- `/api/health` returns the deployed fantasy dataset metadata.
- `/fantasy-data.json` returns JSON (not index.html).
- `/api/espn/site/apis/site/v2/sports/football/nfl/scoreboard` returns ESPN JSON.
- `/api/espn/site/apis/site/v2/sports/basketball/nba/scoreboard` returns ESPN JSON.
- Open a finished game and inspect player box scores.
- Test roster directory for both leagues, dark mode, charts, mobile, and fantasy scoring filters.

## Known limitations
- ESPN endpoints are undocumented; data completeness and availability cannot be guaranteed.
- Fantasy dataset is generated at build time; deploy again to refresh it.
- The GM simulator and predictions are interactive prototypes, not audited real-world contract/projection services.
- No licensed historical play-by-play/shot-chart database or live injury-adjusted forecast backend.
- No external live integration or production build was verified in this environment.
