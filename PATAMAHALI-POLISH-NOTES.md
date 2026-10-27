# Pata Mahali polish pass — 27 October 2026

## Included
- Added seven clearly marked illustrative property examples across rentals, short stays, land, commercial space, warehouses and property sales.
- Examples use local property-scene imagery and realistic example KES prices, but do not receive account/property verification badges and their detail pages are marked noindex.
- Genuine listings remain category-specific and rank ahead of illustrative examples; paid boosts keep their ranking, and a private admin priority action can place a selected listing first in its category.
- Added a property showcase to the welcome page and refined the two main entry buttons for touch use.
- Added letter-by-letter welcome motion with reduced-motion accessibility support.
- Added admin-selectable public themes: Signature, Winter glow (subtle seasonal look), Warm residence and High contrast.
- Improved the default SVG brand mark.
- Removed mandatory ID-card uploads from partner registration. New accounts remain unverified until an administrator reviews contact and property-related evidence.
- Existing image uploads already resize and encode images as WebP; promotional video support remains supported-host links (YouTube/Vimeo), not local video transcoding.

## Deployment notes
- Upload the updated project files to the existing repository and redeploy.
- Database migration is additive (`is_sample`, `admin_rank`); it preserves existing listing records.
- The app seeds illustrative records once and stores their optimized images in the configured data directory.
- Run a backup before deploying to a production database. Verify the deployed pages, admin theme selector, listing approval workflow and existing account flows after deployment.
