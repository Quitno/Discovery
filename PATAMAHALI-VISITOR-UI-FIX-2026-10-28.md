# PataMahali visitor display and scrolling fix — 28 October 2026

- Public visitor number is derived from recorded first-party public browser sessions. The current public browser is included during first response so the count does not lag by one request.
- Visits to `/qaz` (or the configured admin root) and `/manage-admin` are excluded from public tracking, including pre-login admin page hits.
- The admin dashboard includes a private total for recorded public browser IDs; real analytics remain in the admin area.
- Removed explanatory visitor-count text from the public UI so the counter is just a compact “Visitors” label and number.
- Changed the public shell from sticky header / fixed-height mobile scroll panes to natural page scrolling. Footer appears after content rather than occupying a permanent phone-screen strip. The floating mobile home button was removed.
- Replaced maroon/dark-navy public styling with a neutral white/soft-grey shell, charcoal text, and restrained teal accents.

The public counter deliberately is not seeded with an invented number. To display a specific historical visitor total as fact, that total must be supported by actual past analytics. The admin dashboard continues to show actual recorded figures.
