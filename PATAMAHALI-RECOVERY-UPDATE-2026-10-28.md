# PataMahali recovery update — 28 October 2026

## What changed
- Kept the full existing project, photo catalogue, preview-card logic, and property database compatibility. No database or account data is bundled.
- Fixed discovery-preview data to carry its third fallback image URL into landing and browse templates. This was missing in `build_discovery_previews`, so if the primary and secondary image URLs failed, cards could be left broken.
- Restored the public visitor count strip at all recorded totals and retained its gentle count-up animation. The public number remains based on recorded visitor sessions; it does not invent a starting count of 1,103. Admin analytics continue to show the recorded numbers privately.
- Added an admin-only “Remove record” action to visitor analytics. It deletes only one visitor-session/event history, while retaining any account, property listings and enquiries.
- Added fresh CSS/JS cache-busting versions.
- Added final responsive overrides making the app header and footer participate in ordinary document scrolling on mobile and desktop. The footer appears after the page content, rather than consuming a fixed strip of the screen.
- Neutral white/soft-grey/teal styling remains; maroon overrides are neutralised.
- Shortened the landing hero so the discovery/photo sections begin sooner and visitors can see properties with less scrolling.

## Deploy safety
Upload the extracted files preserving paths. Keep the production database and uploaded listing photos. Gallery sources are mostly remote; Render's `cache_gallery_images.py` build command should populate permitted compressed WebP versions. If the deployment environment cannot reach image sources during build/start, bundled fallbacks prevent broken images but cannot replace a full set of genuine locally cached photos.

## Verification
Python syntax and Jinja template parse checks passed. A live Flask test was not run in this environment.
