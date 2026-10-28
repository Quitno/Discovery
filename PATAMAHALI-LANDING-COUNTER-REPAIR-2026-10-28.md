PataMahali repair — 2026-10-28

Changes in this build:
- Landing route `/` is now only the logo/particle wordmark animation and Find/Post actions. Category rails, check-in count, QR, ratings and footer are not rendered on the splash route.
- Public visitor counter starts at the configured launch baseline of 1,103 and adds newly recorded unique public browser sessions after the baseline offset is first saved in settings. The admin analytics continue to query real visitor records; admin routes are excluded from public session tracking.
- The rentals photo catalogue in `photo_rails.py` contains 40 unique source URLs. The full site project and all existing templates, admin, account, QR/PWA and gallery code are retained.

Deploy note: preserve the production database and uploads. The public counter offset is stored in the existing settings table; admin analytics remain actual recorded totals.
