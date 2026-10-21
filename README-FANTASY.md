# CAM'S STATS — fantasy data edition

## Deployment
The site builds normally using `yarn install && yarn build` on Render. To populate **real fantasy rankings**, configure a scheduled data update workflow or run `node scripts/update-fantasy.mjs` locally, then commit the generated `public/fantasy-data.json` file to GitHub. The site will **not invent statistics** when this file is missing.

The script pulls completed regular-season NFL game summaries from ESPN's unofficial public API, aggregates box-score stat categories, and calculates fantasy points in the browser. Endpoint availability and schema can change. Confirm the numbers against official box scores before relying on them. **Do not assume complete data when the script reports skipped games.**

For another season: `FANTASY_SEASON=2025 node scripts/update-fantasy.mjs` (on Windows PowerShell: `$env:FANTASY_SEASON=2025; node scripts/update-fantasy.mjs`).

## Features
Season PPG rankings, weekly performance rankings, QB/RB/WR/TE filters, PPR/half-PPR/standard, player search, last-three-game averages, transparent CAM Index, and data timestamps.

## Limitations
Historical performance only; no real predictive projections, injury adjustments, DST/K scoring, trade valuation or waiver roster ownership data. ESPN endpoints are undocumented and may fail or be rate limited. The dataset is generated outside the browser to avoid dozens of slow requests on each visit.
