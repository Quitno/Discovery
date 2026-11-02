# PataMahali house-hunting pilot update — 2 November 2026

## Product direction

The public entry point has been changed from a broad property-directory experience to a focused house-hunting flow. The first operating area is Nairobi and Kiambu. People begin with a neighbourhood, then refine by property type, monthly rent and bedrooms. When the right home is not present, they can submit a private house request.

## Included changes

- Rebuilt `templates/index.html` around a location-first search, popular area shortcuts, home types, a focused Nairobi/Kiambu section and a house-request call to action.
- Rebuilt `templates/homes.html` as a simpler home finder with area search, filters, counts and clearer empty states.
- Added ten fictional demonstration listing rows for testing search and detail-page behaviour. They use `is_sample=1`, `approval_status='demo'` and `payment_status='demo'` and are excluded from the genuine publication query.
- Allowed sample details to render while explicitly blocking sample enquiries, ratings and taken reports through the existing real-listing eligibility checks.
- Added sample-image handling for the existing representative scene assets in `static/img/property-scenes/`.
- Added an administrator action to delete one sample row or all sample rows. The `demo_inventory_seed_status` setting persists the cleanup decision and prevents automatic reseeding after restart.
- Added the house-request form and database table, plus the admin House requests queue and progress statuses.
- Added privacy and terms language for house requests and demonstration inventory.
- Added the pilot stylesheet `static/css/patamahali-pilot.css`.

## Demo inventory disclosure

The ten sample locations are Kahawa West, Zimmerman, Roysambu, Githurai 45, Ruiru, Membley, Juja, Thika Town, Ruaka and Kahawa Sukari. The rent figures and property details are fictional examples. The photos are representative scene assets supplied with the project; they are not photos of the named areas or of actual available homes. The cards are marked **DEMO — NOT AVAILABLE** and offer no owner contact, booking or enquiry.

## Admin workflow

- **Properties** shows the demo rows with a separate warning and cleanup action.
- **Delete this demo listing** removes only the selected sample row.
- **Delete all demo listings** removes every `is_sample=1` row and stores a permanent cleanup marker so the rows are not recreated on a later boot.
- **House requests** displays submissions privately to administrators and allows status changes: New, Contacted, Matched, Closed or Spam.

## Real listing workflow remains intact

No real owner listing is auto-approved. The existing checks for verified partner, confirmed payment, actual map coordinates, genuine property photo and administrator confirmation remain required before a property can be published.

## Files changed

- `app.py`
- `templates/index.html`
- `templates/homes.html`
- `templates/_listing_card.html`
- `templates/listing_detail.html`
- `templates/request_house.html` (new)
- `templates/admin_house_requests.html` (new)
- `templates/admin_base.html`
- `templates/admin_listings.html`
- `templates/privacy.html`
- `templates/terms.html`
- `static/css/patamahali-pilot.css` (new)
- `README.md`

## Validation

- Python compilation: passed.
- Python AST parse: passed for all top-level Python files.
- Jinja parsing: passed for all 73 HTML templates.
- SQLite schema and exact ten-row seed: passed in an in-memory database.
- Demo-clear persistence marker: passed; the seed function did not recreate rows after clear.
- Active template `url_for` endpoint references: passed.
- Full Flask request/response integration test: not run because Flask was not installed in the offline editing environment. Verify the deployed service after upload.
