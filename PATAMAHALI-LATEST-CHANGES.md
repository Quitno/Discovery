# Pata Mahali overlay patch — October 28, 2026

This patch overlays the existing GitHub project; it is not a standalone replacement.

## Corrected in this version
- `templates/homes.html`: category navigation now lists all enabled property categories as visible, direct links. The `<details>/<summary>` accordion groups that produced plus/minus indicators have been removed.
- `app.py`: added a shared search-ranked category shortcut builder. Search details split `short_stay` into Hotels (Hotel room searches) and Airbnb & stays, where data supports it. The highest-ranked five candidates rotate daily while only four buttons display.
- `templates/base.html`: places the four compact dynamic category buttons below the maroon header on app pages, not only on the landing page.
- `static/css/style.css`: styling for the four-button category strip and flat sidebar links.

## Image rails
`photo_rails.py` defines 62 photo links: 25 homes/rentals, 25 hotels/short stays, and 3 each for commercial, industrial, land, and property sale. Images are served as compressed Unsplash CDN URLs to avoid adding image files to Render. They are category discovery photographs, not actual available listing records.

## Safety
Back up the production database/uploads before deploying. Do not overwrite a live database with a fresh project database. The optional GitHub feature stores backup snapshots; it is not a live concurrent database. Python compilation and Jinja template parsing passed in this working session; the whole Flask application was not runtime-tested here.
