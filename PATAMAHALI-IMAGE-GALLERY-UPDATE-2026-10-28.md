# PataMahali photo gallery update — 28 October 2026

- Homes & rentals: 40 distinct gallery cards.
- Hotels: 15 cards. Airbnb & short stays: 15 cards.
- Shops & commercial spaces: 15; Warehouses & godowns: 15; Land & plots: 15; Property for sale: 15.
- Total: 130 photographic discovery cards. Hotel cards link to the Hotel room filter; Airbnb & short-stay cards link to the short-stay category.
- Images request 420×300 compressed CDN renditions. They are not stored in the Render service filesystem, which keeps deployment size small.
- Each image has a distinct Pexels fallback URL and a secondary photo fallback to reduce blank image cards if an individual CDN image fails.
- These are real stock photographs for category discovery, not photos of specific available properties. Exact availability and prices appear only on approved owner listings.

## Deploy

Upload the full project, or copy changed files `app.py`, `photo_rails.py`, `templates/index.html`, `templates/homes.html`, `static/css/style.css` and this note into the existing repository. Keep your production database and owner-uploaded property files. After deployment, open the homepage and test each gallery and at least one category page on mobile and desktop; external image services still depend on the visitor's network and the CDN staying available.
