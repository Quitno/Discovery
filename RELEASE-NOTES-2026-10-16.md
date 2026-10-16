# Discovery Hub update — 16 October 2026

## What changed

- Added `/availability`, a public availability centre with live HTTP checks for a fixed list of connected platforms: House Hunter, OTravel, TRT Furniture, Luxhari, Oedge Mobility, Denmart and the Toror APK site.
- Added `/api/availability` as the JSON endpoint consumed by the page. Checks run concurrently, have short timeouts, include measured response time, and are cached for 75 seconds. Simultaneous refreshes are coalesced so multiple visitors do not create repeated probe bursts.
- Availability statuses are deliberately cautious: any HTTP response means the host is responding; 5xx responses are shown as server issues; timeouts/network restrictions are reported as inconclusive, not as proof that a service is offline. The checker does not accept visitor-supplied URLs.
- Added a device-local display tool for text size, higher contrast, underlined links and reduced motion. Choices can be reset and are saved only in the visitor's browser storage.
- Added homepage quick tools for platform availability, project estimating and the APK portal.
- Changed the Toror APK doorway plus Tomorrow Music, Tomorrow Messages and AdShield to open `https://toror-technology.onrender.com/` directly. A versioned startup migration updates existing SQLite records so the Admin destination fields align with this route.
- Updated the service-worker cache version, excluded the live availability API from offline caching, and included the availability centre in the sitemap.
- Updated the route/SEO documentation.

## Deployment

Deploy the ZIP's `Discovery-main` project as the current Flask app using the existing `Procfile` and `requirements.txt`. No extra package was added. Existing SQLite data and administrator edits outside the four explicit APK portal destinations are preserved. The first start runs the `direct_destinations_v6_done` migration once.

## Validation performed

- Python syntax compilation passed.
- All Jinja templates parse.
- Static `url_for` endpoint checks passed; no duplicate route paths were found.
- JavaScript syntax checks passed for the app and service worker.
- CSS braces are balanced.
- Direct APK routing and the availability checker/cache logic were exercised with local deterministic test doubles.

A full Flask test-client run was not possible in the packaging sandbox because Flask and Werkzeug are not installed there and network access needed to fetch dependencies is unavailable. The project still declares Flask and Gunicorn in its existing requirements for deployment.
