# GRIDIRON ATLAS 4.0 — Command Center

The largest interface overhaul so far, built on the existing live-game engine and PostgreSQL archive.

## 4.0 highlights
- New command-center shell with a fixed top context deck and redesigned left control rail.
- Real Back button with in-app page history. Alt+Left also navigates back.
- Condensed five-destination primary navigation: Game Center, NFL Games, Players, Analytics, Archive.
- Settings remains a gear at the bottom of the rail.
- NFL game sub-navigation renamed and rebuilt as a sticky segmented control: Overview, Team Stats, Player Stats, Play-by-Play, Drive Chart.
- Stronger hierarchy, larger typography, glass/obsidian surfaces, acid-lime/violet accents, ambient grid, improved cards, spacing, responsive behavior, and overflow handling.
- Quick NFL Games action in the top command deck; Alt+G opens NFL Games.
- Existing verified-feed rule, ESPN provider integration, live engine, player stats, game intelligence, archive, and PostgreSQL persistence retained.

## Data integrity
If a value cannot be mapped to a verified connected field or clearly labeled derived calculation, GRIDIRON ATLAS displays `—`. No synthetic values are generated.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep `DATABASE_URL` private and unchanged.
