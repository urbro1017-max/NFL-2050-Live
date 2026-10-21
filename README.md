# CAM'S STATS V6.0

NFL + NBA sports desk, ESPN-style presentation, and interactive analytical tools.

## Features
- NFL and NBA scoreboard and news feeds (third-party ESPN endpoints; may be blocked or unavailable)
- Fantasy rankings with scoring filters (DEMO ONLY; not real projections)
- NFL/NBA Pro Lab with searchable sample players and comparison charts
- Scenario-based NFL/NBA game predictor (user-adjustable, not a trained forecast)
- GM Center with custom roster cap hits, cap-space tracking, and trade calculator
- CAM Analyst offline rules-based Q&A (NOT connected to an LLM)

## Deploy on existing Render Web Service
Build command: `npm install && npm run build`
Start command: `npx vite preview --host 0.0.0.0 --port $PORT`
Set preview.allowedHosts in vite.config.js for your domain. Static Site is preferred: publish `dist` and use no start command.

## Local
`npm install` then `npm run dev`.

## Data transparency
Fantasy rankings, statistical leaders, Pro Lab figures, and projections are sample/demo values. GM contracts and cap limits are manually entered, not official salary data. The predictions page uses a simple what-if calculation and has not been trained or backtested. CAM Analyst uses fixed responses and does not call an AI API. Live score/news calls are attempted directly from the browser and may fail due to CORS or provider changes. Do not use model outputs for wagering or real-world financial decisions.

## Real player data (new)
The **Real Stats** navigation page fetches current NFL and NBA team rosters and season player statistics directly from ESPN's public, undocumented endpoints. Choose league, team, player, and season. It displays only returned fields and an error if unavailable. This is a live-data integration, not a cached or validated database; CORS and endpoint changes may affect it. Other fantasy rankings, predictions, GM contracts and example leaders remain illustrative. A production-quality CAM fantasy rating requires verified weekly game logs and testing before replacing the examples.
