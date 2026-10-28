# PataMahali full project — image reliability update

This archive is the complete `Discovery-main` source tree, including existing application routes, admin pages, account flows, check-ins, PWA assets, CSS, templates, and the 130-card image-gallery manifest in `photo_rails.py`.

## Gallery images and Render

`cache_gallery_images.py` runs in the Render build and converts reusable image sources (Unsplash/Pexels catalogue photos plus clearly open-licensed Wikimedia photos) into 640×420 WebP files in `static/img/gallery/`. That reduces image bytes and avoids browser dependence on third-party image hosts for those assets. Photos taken from property-agent/editorial pages without a clear reuse licence stay at their original URL and are not copied into the app bundle; those cards get a cached open-licensed image as the final visual fallback. The generated `manifest.json` records source URL, credit, licence/source note and cache status. Build does not fail solely because one host is unavailable.

The gallery contains 40 homes/rentals cards and 15 each for hotels, Airbnb/short stays, commercial spaces, warehouses, land/plots, and property for sale. Rental gallery cards are marked UNVERIFIED and are visual discovery examples, not claims of current availability. Never use preview photos as evidence that a specific property is listed.

The compressed, licence-clear gallery image files are materialized during the Render build; the downloadable ZIP carries the full application and image-source catalogue plus the cache builder. This execution environment cannot retrieve the remote image binaries to pre-populate the ZIP itself. After a successful Render build, the generated WebP assets are part of the deployed application bundle, not a persistent Render disk.

## Upload/deploy

Upload the entire `Discovery-main` folder contents to the matching GitHub repository paths, preserving folders. Keep the production database and actual owner-uploaded property files. Deploy after the commit. Render builds `cache_gallery_images.py` via `render.yaml`; if the service uses the Procfile start command instead, the Procfile also fills any missing images before Gunicorn starts.

## Attribution and reuse

See `PHOTO-CREDITS-PATA-MAHALI.md`. The manifest retains the source details for the images. Some listed Kenyan property-site images indicate that source terms apply; obtain permission or replace such sources with owner-uploaded or clearly licensed photographs before commercial use.
