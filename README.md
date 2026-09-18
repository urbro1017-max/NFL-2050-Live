# GRIDIRON ATLAS 14.3 — Production Hardening

Built on ATLAS 14.2 Product Experience.

## 14.3 changes
- Intelligence and Research Lab bootstrap the NFL slate themselves; visiting Live first is no longer required.
- Direct retry/recovery state when the schedule provider is unavailable.
- Player Universe now has explicit progress, slow-load messaging, failure recovery, and retry instead of an indefinite importer state.
- Live/Home re-resolves the provider's current week instead of trusting a previously browsed week.
- The most recently selected game is remembered across ATLAS workspaces and browser reloads.
- Cross-workspace game selection continues to use the same selected-game state.
- Added production loading skeletons and restrained transitions without changing the 14.2 visual identity.
- Data engine and archive behavior preserved.

Validation: `node --check app/app.js` and `python -m py_compile server.py` passed.
