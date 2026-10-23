# CAM’S STATS — integrated refinement release

## Data integrity
- Fantasy collector parses ESPN NFL game box scores, rejects missing game data, and enriches positions from ESPN team rosters using athlete IDs.
- UNKNOWN remains visible if an athlete cannot be matched; no positions are guessed.
- Validator checks unique player IDs, finite statistics, game coverage, and totals.
- Fantasy player rows are clickable for weekly PPR/half-PPR/standard scoring trends.
- Game review scoring chart now shows cumulative points; nonnumeric team statistics are excluded rather than plotted as zero.

## Important limitations
- ESPN site endpoints are unofficial and may change or throttle requests.
- Rosters and NBA/NFL player details are fetched on demand, not stored as a complete guaranteed league-wide historical database.
- GM simulator, predictions, and AI Analyst are interactive prototypes, not independently validated live analytics.
- Fantasy rankings are historical fantasy production, not future projections.
- Run `npm run build:with-data` on Render. Builds intentionally fail when required fantasy data cannot be validated.

## Deployment
Use Node, repo `urbro1017-max/cams-stats`, build `npm install && npm run build:with-data` and, for the existing web service, start `npx vite preview --host 0.0.0.0 --port $PORT`. A Render Static Site is preferable for a Vite-only front end, using `dist` as the publish directory.
