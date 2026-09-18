# GRIDIRON ATLAS 12.2 — ATLAS ARCHIVE ENGINE

12.2 turns the Atlas archive from a click-to-capture side effect into an automatic recovery system.

## What changed
- Automatic final-game archival: provider-confirmed finals are captured without the user opening the game.
- Historical backfill: Atlas scans completed regular-season weeks, compares provider game IDs with PostgreSQL, and recovers missing finals in small throttled batches.
- Strict archive separation: upcoming/live stored rows cannot appear in Recent Atlas Captures.
- Archive Coverage: `/api/archive-coverage` reports expected provider-confirmed finals, archived finals, missing finals, partial-quality finals, and week-by-week coverage.
- My Atlas shows week-by-week auto-archive coverage and backfill state.
- Sunday Command telemetry reports archived finals against provider-confirmed finals rather than raw stored-row counts.
- Player coverage terminology is precise: the number is unique player identities appearing in Atlas final-game box-score rows, not a claim of full-season player coverage.
- Existing final snapshots remain local-first; automatic recovery is throttled to avoid hammering upstream sources.
- Service worker cache bumped to v122.

## Archive lifecycle
DISCOVERED / UPCOMING → LIVE → PROVIDER FINAL → CAPTURE → ARCHIVED.

A provider-confirmed final with incomplete optional sections can still be archived, but its quality score remains visible. Atlas does not invent missing player, play, drive, team, or tracking data.

## Backfill behavior
Backfill runs automatically while the Render process is awake. By default it rescans on a five-minute throttle and hydrates at most two missing finals per pass. This is intentionally bounded for reliability. If the free Render service is asleep, recovery resumes after the service wakes again.

## Data policy
Provider values are displayed as supplied. Atlas-derived values must be labeled. Unsupported fields display unavailable/— rather than fabricated values. Tracking-grade metrics remain source-gated.

## Deploy
Upload the contents of this ZIP directly to the existing GitHub repository root. Keep the existing Render service, build command, start command, and `DATABASE_URL` environment variable unchanged.
