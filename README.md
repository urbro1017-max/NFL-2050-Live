# ATLAS 66.1 — Football Intelligence OS

Render-ready NFL Football OS build.

## 64 changes
- persistent ATLAS AI chatbot
- cached AI reads remain non-blocking
- clearer neon power-ranking visualization
- position boards expand to every stored position available
- duplicated Teams DNA section removed
- improved readability and neon visual hierarchy
- normalized database remains source of truth


ATLAS 65: professional neon UI, side-by-side AI intelligence boards, animated power/season graphs, and redundant team diagnostics cleanup.


## 66.1 cache synchronization
Frontend assets now use unique 66.1 filenames. The browser checks `/api/build` with no-store and performs one automatic cache-busted reload when a deployment changes server versions, instead of requiring a manual hard refresh.
