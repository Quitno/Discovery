# PataMahali UI fix — 28 October 2026

This build keeps the root URL as a clean animated entry screen containing only the PataMahali mark/title and the Find/Post buttons. The animated landing screen no longer includes photo galleries, search stats, QR blocks, explanatory sections, or a footer.

The photo catalogue remains available after visitors choose Find and open a category page. Category results have tighter vertical spacing, previews are visible immediately below the compact search controls, repeated explanatory copy was removed, and image loading tries one remote fallback before using the included local category fallback. A CSS cache-buster was updated.

No database schema or production database was replaced by this UI change. Preserve your production SQLite database and uploaded property files when deploying. The gallery catalogue still uses external sources and the existing build-time cache script; test image availability after deploying.
