# PataMahali photo-first browse repair — 28 October 2026

## Fixes in this build
- Kept the root route as a separate, full-screen welcome animation with only the wordmark and Find/Post actions; public header and footer are not rendered on that route.
- Simplified the navigation drawer heading to “Categories” and removed extra “area to explore” wording from property preview cards.
- Normalized legacy Wikimedia thumbnail URLs to the canonical upload.wikimedia.org host before browser rendering and caching.
- Fixed fallback-cache eligibility: cards with a third-party primary photo can still build a local WebP backup from their reusable Pexels/Unsplash fallback, instead of skipping cache generation entirely.
- Kept non-open-licensed listing photos as remote primary images, and use cached reusable fallback images only if the remote source fails.
- Made the 40-card rental gallery use actual Kenyan apartment/estate photos as fallbacks from open-licensed Wikimedia Commons sources; other categories retain their own type-specific image fallbacks.
- Tightened the browse page styles so photo cards start immediately below the compact heading/search controls.
- Bumped CSS/JS query versions to prevent stale browser assets from masking the changes.

## Image counts
- Homes & rentals: 40
- Hotels: 15
- Airbnb & short stays: 15
- Shops & commercial spaces: 15
- Warehouses & godowns: 15
- Land & plots: 15
- Property for sale: 15
- Total: 130 discovery photo cards

## Deployment
`render.yaml` builds the compressed WebP gallery using `python cache_gallery_images.py`; `app.py` also attempts cache generation at startup when no gallery WebP exists, in case the service is configured through the Render dashboard instead of the YAML build command. The generated files are small 640×420 WebP assets, normally at or below 250 KB each. The build does not fail solely because an image source is unavailable.

The source ZIP contains the complete code and the photo-source catalogue. The image binary files are generated during Render build/startup because this execution environment cannot retrieve remote photo binaries. The application must be deployed and the first image-cache run allowed to complete to verify all hosted images live. Existing database and owner-uploaded property files should be preserved during deployment.
