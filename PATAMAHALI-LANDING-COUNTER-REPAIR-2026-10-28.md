PataMahali repairs — 2026-10-28

Current landing-page behavior:
- The landing page retains the animated PataMahali logo and Find/Post buttons, then moves directly into the category shortcuts and curated photo rails.
- The duplicated eight-card residential preview grid has been removed from the landing page. Homes & rentals are shown once in the 40-photo rail, followed by the separate hotel, short-stay, commercial, warehouse, land and property-sale rails.
- Mobile hero height and spacing have been tightened so the photos appear much sooner instead of after a mostly empty viewport.
- Failed photo downloads no longer cause one local apartment/interior/land photograph to be copied into many gallery slots. Cards keep their own original source and two alternatives; if those fail, a neutral unavailable-photo tile appears rather than an identical misleading picture.
- Cache-busting versions were updated for the CSS/JS and PWA shell.
- The public visitor counter uses a configured launch baseline of 1,103 plus newly recorded unique public browser sessions after a baseline offset is stored. Admin analytics remain based on actual visitor rows.

Deploy note: the source code has been corrected in this package, but this does not itself deploy changes to the live Render service. Preserve the production database and uploaded listing photos during deployment.

Validation performed: Python compilation passed; 69 Jinja templates parsed; the gallery catalogue reports 130 cards across seven categories. The Render build environment must still download/cache images successfully for them to be visually verified in production.
