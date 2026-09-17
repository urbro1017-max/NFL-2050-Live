# GRIDIRON ATLAS 3.6 — Nightshift UI

A visual-polish release built on the 3.5 Live Game Engine.

## 3.6 UI changes
- New midnight / indigo / ice / coral color system.
- Glassy sticky header and cleaner active navigation.
- Navigation scrolls instead of crushing labels into tiny boxes.
- Responsive matchup hero with improved typography and logo sizing.
- Cards, KPIs, tables, forms, matrices, drive rows, and player tiles redesigned for readability.
- Long labels and live values wrap safely instead of overflowing their containers.
- Improved tablet/mobile layouts and keyboard focus states.
- Existing 3.5 live engine, ESPN feed integration, PostgreSQL archive, player center, analytics, replay, and scouting logic retained.

## Data integrity
UI changes do not invent missing data. Unavailable verified values remain `—`.

## Render
Build: `pip install -r requirements.txt`
Start: `python server.py`
Keep the existing `DATABASE_URL` private.
