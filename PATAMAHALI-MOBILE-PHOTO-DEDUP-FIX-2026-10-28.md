# PataMahali mobile spacing and repeated-photo repair — 28 October 2026

## Root causes found in the source
- The homepage rendered an eight-card residential preview grid and then rendered the full Homes & Rentals photo rail, so the same starting photos were repeated before visitors reached the other gallery photos.
- `cache_gallery_images.py` copied one successful photo into every uncached slot in its section. The copied image then became that card's primary local image, making one picture appear to represent many different places.
- `photo_rails.py` supplied a shared generic local picture as the third fallback for every uncached card when there was no category cache.
- The landing hero had large viewport-based minimum heights on phones, delaying photo discovery below the first screen.

## Changes
- Removed the duplicate eight-card home preview grid from the landing page. The homepage now shows one curated gallery rail per category rather than showing the same initial set twice.
- Reduced mobile hero spacing/min-height and tightened the popular-category row, gallery intro and rail heading spacing so the first photographs appear sooner.
- Stopped copying a photo into missing gallery slots. Every card now keeps its own source plus its own two alternatives; if all fail, the card shows a neutral "Photo preview unavailable" tile instead of falsely repeating one photo.
- Removed shared third-fallback photo assignment from photo rails and generated search previews.
- Added cache-busting versions for CSS, JavaScript and the PWA shell to prevent a previously cached stylesheet from keeping the old layout.
- Kept every photo explicitly labelled UNVERIFIED; gallery imagery is not a claim of actual property availability.

## Validation
- Python modules compile.
- Jinja templates parse.
- The catalogue contains 130 cards across seven categories; repeated-source URLs were counted separately from the shared-fallback issue.
- Image downloading depends on the Render build environment and external image providers. The live deployment was not changed from this workspace, and all images have not been visually verified against production.
