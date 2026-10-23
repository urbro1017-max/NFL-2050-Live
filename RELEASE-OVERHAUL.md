# CAM'S STATS — Scoreboards, Box Scores, NBA Fantasy overhaul

## New
- Date-selectable NFL and NBA scoreboards. Click any game (including completed games from prior dates) to open the game review and player box score. Provider game IDs are passed directly into the existing review modal.
- Team logos displayed in scoreboards and game reviews (when returned by the provider).
- NBA Fantasy navigation tab. Select a day and view completed-game NBA fantasy performances, a top-12 bar chart and sortable-by-points leaderboard. Data comes from ESPN game box scores via a same-origin Node API, not a hardcoded list.
- NBA fantasy scoring: PTS + 1.2 REB + 1.5 AST + 3 STL + 3 BLK - TOV. This is a **simplified custom points system**, not official Yahoo/ESPN league scoring or DraftKings settlement. No double-double/triple-double bonuses.
- NFL Fantasy retains real historical game-log rankings, PPR/Half-PPR/Standard, weekly graphs and position filters.
- Server caches NBA daily fantasy requests for 5 minutes and returns errors rather than fabricated statistics.

## Limitations
- ESPN endpoints are unofficial and may change, rate-limit, or return incomplete data. This app is not a licensed statistics service.
- NBA fantasy currently ranks **a selected day's completed games**, not full-season NBA fantasy or forward projections. Missing categories are shown as unavailable; scoring treats missing categories as zero, so verify provider coverage before using scores competitively.
- NFL fantasy dataset is generated during the build. If data collection fails, the build fails rather than publishing fake rankings. It does not auto-refresh between deployments.
- Existing GM, prediction, analyst and some analytics pages are prototypes; this release does not claim those systems are validated.
- A live Render deployment and end-to-end ESPN connectivity have not been verified here.

## Deploy
Render Node Web Service: build `npm install && npm run build:with-data`, start `npm start`. Set `FANTASY_SEASON` to the season you intend to collect if different from current year. The build script requires provider data access.

## Check after deployment
- `/api/health` returns JSON.
- `/api/espn/site/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261021` returns JSON with `events`.
- `/api/fantasy/nba?date=20261021` returns JSON with `players`, `parsedGames`, `failedGames`.
- `/fantasy-data.json` returns JSON and not the HTML home page.
- On NFL/NBA pages choose an earlier game date and open a final score; confirm box-score player rows.
