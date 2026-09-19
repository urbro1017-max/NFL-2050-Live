# ATLAS 27.0 — CLEAN-SLATE FRONTEND

ATLAS 27.0 removes the legacy browser application from the rendered product. The existing Python data/collector backend is retained, but `/app/index.html` now boots a new frontend written from a blank shell in `atlas27.js` + `atlas27.css`.

## Workspaces
- Home — editorial ATLAS landing page
- Game Center — schedule rail + matchup stage
- League — conference/division landscape
- Teams — team-colored command center + roster architecture
- Players — search-first scouting index
- Intelligence — game room + field + captured play tape
- Front Office — personnel-board / position-room interface
- Data — operations pipeline

No legacy `app.js`, `styles.css`, `system26.js`, or `system26.css` is loaded by the new index. They have been removed from this package.

## Render
`render.yaml` is included. Set `DATABASE_URL` in Render for persistent Postgres. Start command: `python server.py`.
