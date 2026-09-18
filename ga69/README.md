# GRIDIRON ATLAS 6.9 — LEAGUE EMPIRE

A live NFL analytics platform with game-state fusion, game/players/team analytics, War Room, and expanded league intelligence.

## 6.9 additions
- Division Control Center: all 8 NFL divisions and their teams
- AFC/NFC Conference Command
- Current division and conference leaders from season standings
- Atlas Index: transparent performance rating based primarily on record, with point differential and verified stored-game efficiency as modifiers
- 32-team Team Lab
- Team Leaders grouped from season leader feeds
- NFL season leader boards
- Defensive Command
- Championship Picture: factual conference ordering only; no betting odds or outcome probabilities
- Next Gen Lab remains source-gated; unsupported tracking metrics display —

## Data integrity
Provider values are displayed as supplied. Derived metrics are labeled. Missing values remain unavailable rather than being fabricated. Early-season rankings should be interpreted with their small sample size in mind.

## Deploy
Keep the existing Render service and environment variables. Build command: `pip install -r requirements.txt`. Start command: `python server.py`.
