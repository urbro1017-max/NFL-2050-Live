NFL 2050 LIVE // DET @ BUF

QUICK START
1. Extract the ZIP completely.
2. Double-click START_NFL_2050.bat.
3. Leave the black NFL 2050 LIVE ENGINE window open.
4. Your browser opens automatically.
5. Command Center refreshes live data every 3 seconds.

REQUIREMENT
Python 3 must be installed on Windows. The launcher automatically tries 'py' first and then 'python'.

DATA
- Game state / scores / team box score / play-by-play: ESPN CDN game feeds.
- Roster refresh endpoint: ESPN team roster feed, cached for 5 minutes.
- Event ID: 401872932 (DET @ BUF, Sep 17 2026).

SECURITY
No private API key is stored in this package.

LIMITATIONS
This uses public-facing, undocumented ESPN endpoints. They can change or become unavailable. The server caches recent data and the UI shows a retry state rather than inventing values.
Advanced charted fields such as pressures/routes/personnel are not fabricated when unavailable.
