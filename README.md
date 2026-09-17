# GRIDIRON ATLAS — DEFINITIVE BUILD

The permanent data rule:
If a statistic cannot be verified from the connected live feed or the embedded verified starter/baseline dataset, display —. Never infer or fabricate it.

Added in the definitive build:
- Player Performance Center with search/filter and live stat groups
- explosive-play tracker
- contextual milestone tracker
- field-position/drive-map surface (only renders sourced field data)
- factual "What Changed?" engine
- scoring-drive cards
- source-health panel
- automatic postgame report mode
- all prior Game HQ + Analytics Lab charts and tools retained

No betting, odds, fabricated probabilities, or unsupported stats.

PATCH:
- FINAL Game Report is CSS-hidden by default.
- It becomes visible only when the live provider status explicitly contains Final / Final OT.
- Pregame, scheduled, delayed, halftime, and in-progress states cannot expose the postgame card.

BROADCAST BUILD:
- dedicated Broadcast Mode tab
- one-click distraction-free full-screen broadcast layout
- live score/clock/status strip
- field/current-drive visualization
- verified player leaders
- team snapshot
- last-five-drives panel
- automatically generated game-story timeline for scores, turnovers, and explosive plays
- live latest-play ticker
- all existing analytics preserved

The permanent verification rule remains unchanged: unavailable/unverified stats display —.

MAX BUILD:
- QB Command Center
- Skill Player Usage Center
- Trenches Center
- Defensive Leaderboard
- full Drive Efficiency table
- rolling drive-yard graph
- quarter splits
- browser-persistent pinned player panel
- global "/" command palette for pages and players
- all previous Broadcast, Game HQ, Analytics Lab, Players and Postgame functionality retained

Verification rule remains absolute: no source = —.

GRIDIRON ATLAS 1.0:
- NFL Scoreboard / universal game selector
- automatic event-ID discovery from the public scoreboard feed
- generic game dashboard for any game returned by that feed
- dynamic team names, logos, scores, stats, drives, player box score and play feed
- server-session snapshot history for verified score/yard changes
- source inspector and explicit unavailable-state handling
- original DET/BUF deep-dive suite retained as the flagship game lab
- no guessed statistics: unavailable = —

GRIDIRON ATLAS 2.0 MAXIMUM:
- persistent SQLite game archive + verified snapshots
- Season HQ / archive / watchlist / game comparison
- player watchlist persistence
- situational Red Zone, 3rd/4th Down, Explosive Play, Turnover labs
- play-by-play field playback controls
- universal team/player/game pages through game selector
- CSV export endpoint: /api/export.csv?id=GAME_ID
- print-to-PDF compatible reports via browser print
- source/provenance inspector and connection diagnostics
- keyboard shortcuts: G Game HQ, B Broadcast, P Players, S Scoreboard, / command bar
- Atlas, Broadcast Black and Scouting Light themes
- TV presentation mode
- PWA manifest + offline shell service worker
- archived games remain in SQLite across ordinary app restarts when persistent storage is available
- existing Broadcast, MAX Lab, Analytics Lab, Players, Game HQ and DET/BUF flagship retained

IMPORTANT HOSTING NOTE:
Render's filesystem may be ephemeral depending on service/storage configuration. For truly permanent cloud history across redeploys, point GRIDIRON_DB at persistent storage or migrate the same schema to a managed database.
