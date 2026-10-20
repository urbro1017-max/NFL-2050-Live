# CAM'S STATS

An original ESPN-inspired NFL + NBA website prototype with independent fantasy football rankings, player comparisons, league pages, and responsive design. Built with React and Vite.

## Run locally

1. Install Node.js 20+.
2. Run `npm install`.
3. Run `npm run dev` and open the local URL shown.

## Deploy to Render

Create a **Static Site** from this GitHub repository:
- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Add a rewrite rule `/*` → `/index.html` (status 200) if needed for client-side routing.

## Important: data status

This is a functional **front-end prototype**. Game scores, stat leaders, fantasy ratings, and projections are **illustrative demo data**, clearly labeled in the UI. They are not live, historical, or reliable fantasy recommendations. The app does not yet use a sports API or server. Player rankings use an illustrative CFI scale; scoring mode changes demonstration point projections.

## Next development steps

- Connect a licensed NFL/NBA data provider with an authenticated server-side proxy; never embed private API keys in the browser.
- Build a data ingestion and caching pipeline, then populate real scores, rosters, statistics, and injuries.
- Implement and backtest a documented CFI formula on historical weekly fantasy results.
- Add accounts, saved favorites, news content, team/player detail pages, and advanced comparisons.

## Fix for "no requirements.txt" on Render

That error means Render tried to deploy this JavaScript project as a **Python** web service. This project does not use Python and does not need `requirements.txt`.

**Recommended:** In Render, select **New > Static Site**, connect your GitHub repo, use build command `npm install && npm run build` and publish directory `dist`. If Render created a Python Web Service, create a new Static Site instead; changing a Python service's build command alone may not fix its runtime.

**Alternative:** Deploy using **New > Blueprint** with the included `render.yaml` in the repository root. This configures the correct static runtime automatically.
