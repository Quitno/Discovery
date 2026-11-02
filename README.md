# PataMahali — Kenya house-hunting platform

PataMahali is the property-search application intended for `https://trorinovationstech.co.ke/`. The public experience is centred on finding a home by neighbourhood, comparing the practical details, and submitting a house request when a suitable listing is not yet available. The first focused pilot is Nairobi and Kiambu; the wider Kenya location directory and the other property categories remain in the application.

## House-hunting pilot (2 November 2026)

- The homepage opens with a neighbourhood-first house search, popular starting areas, rental types, a Nairobi/Kiambu pilot focus, and a direct house-request path.
- `/homes` has a clearer search panel for neighbourhood, property type, rent range and bedrooms. Results distinguish genuine live listings from explicitly labelled demonstration examples.
- Ten **fictional demo records** are prepared across Kahawa West, Zimmerman, Roysambu, Githurai 45, Ruiru, Membley, Juja, Thika Town, Ruaka and Kahawa Sukari. The displayed amounts and details are examples only. Demo photos are representative scene assets from the project, not photos of those addresses or properties.
- Demo records are never treated as verified, paid or bookable. They cannot receive enquiries, ratings or taken reports. The existing real-listing publication gates remain unchanged: partner verification, reconciled payment, a real location pin, a genuine listing photo and administrator approval.
- `/request-house` saves a seeker's preferred area, home type, bedrooms, maximum budget, move date and contact details. These requests are private to the administrator under **House requests** in the control room.
- Admin → Properties has an individual **Delete this demo listing** action and a **Delete all demo listings** action. Clearing the demo inventory records a persistent setting, so a restart does not recreate it. The bulk action deletes only rows marked as demo and does not touch real partner listings, enquiries, accounts or uploaded photos.

### Suggested pilot test

1. Deploy the complete project and open the homepage on a phone.
2. Open **Find a home**, try Roysambu, Ruaka, Ruiru, Juja and Thika, then test the rent and bedroom filters. Demo cards are marked and cannot be contacted.
3. Open **Request a home** and submit a test request using a test phone number. Confirm it appears under Admin → House requests, then change its status to Contacted or Closed.
4. In Admin → Properties, review the demo labels and use **Delete all demo listings** when you are finished. It is irreversible for those demonstration rows; export or back up before using admin cleanup on production data generally.
5. Register your real owner/agent account and publish genuine properties with accurate photos, location, rent and availability. Complete the existing verification steps before approval.

Do not present the demo cards, sample figures or representative scene photos to the public as real housing inventory. They are there to prove the interface and search flow, not to suggest homes are available.

## Search visibility

- PataMahali's homepage, title and description focus on Kenyan house hunting and neighbourhood-level home searches.
- A branded 1200 × 630 share image and square PataMahali avatar are included for search/social previews and browser icons.
- `robots.txt`, `sitemap.xml`, and `llms.txt` are available. Six category hubs cover homes for rent, short stays, commercial property, warehouses/godowns, land/plots, and houses/property for sale.
- Category pages can extend through county → constituency → ward/neighbourhood. Area/category combinations enter the sitemap when there is real approved, currently published inventory. Empty specific pages stay `noindex` so the domain does not fill its index with thin duplicates.
- All public canonical URLs use `PUBLIC_BASE_URL=https://trorinovationstech.co.ke`.

## Listing renewal and owner accounts

- Published property adverts run for 30 days by default. At expiry they disappear from public search and display a renewal prompt in the owner's dashboard.
- Renewals cost the same stored fee as the original listing. The owner submits a fresh payment reference; an administrator verifies it before the next 30-day term begins.
- After a seven-day grace period, unrenewed expired adverts are privately archived. Accounts remain available for the owner to sign in later. Listing records, photos, enquiries and ratings are retained rather than hard-deleted.
- New owner accounts set a recovery question/answer. Answers are stored as password hashes. Existing owners can add/update their recovery details from their dashboard, and `/partner/recover` resets access to the same account.

## Backups and persistence

- Keep the Render persistent disk mounted at `/var/data`; the SQLite database, listing photos, private identity documents, branding and promotion uploads use `DATA_DIR` on that disk.
- Up to 14 daily database-only snapshots are retained on the host.
- Admin → Backups provides a full recovery ZIP containing the database plus uploaded photos and private documents. Download it periodically and store it outside the hosting account in a private, encrypted location. A backup held only on the same disk cannot protect against the entire disk being lost.
- The full recovery ZIP's `RECOVERY-README.txt` explains how to restore the database and media folders. Make a fresh backup of the destination before restoring.

## Deploy checklist

1. Extract this project so `app.py`, `requirements.txt`, `render.yaml`, `templates/`, and `static/` are at the repository root—not nested under another folder.
2. Ensure the healthy Render web service serving the custom domain uses this PataMahali project, and keep its persistent data disk attached. A code upload does not automatically transfer a custom domain from another Render service.
3. Keep `PUBLIC_BASE_URL` set to `https://trorinovationstech.co.ke`. Keep the existing `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables unchanged unless you are intentionally rotating credentials.
4. After deployment, verify the homepage and `/homes` return HTTP 200, test a house request and the admin request queue, then submit `https://trorinovationstech.co.ke/sitemap.xml` in Google Search Console and Bing Webmaster Tools.

Search rankings are not guaranteed by metadata alone. Search engines need to crawl the live site, and detailed location queries become more useful as genuine, current property inventory is added for each area.

## Validation note for this update

The release was checked with Python compilation/AST parsing, Jinja parsing for all templates, an in-memory SQLite schema and ten-record demo-seed test, and a clear-marker test proving demo inventory stays deleted after a simulated restart. The complete Flask server could not be started in the editing environment because Flask was not installed and package downloads were unavailable; verify the live Render deployment after uploading.
