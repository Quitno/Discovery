# PataMahali — Kenya property marketplace

PataMahali is the main property-search application intended for `https://trorinovationstech.co.ke/`. The existing two-gate homepage and the current inside-site flows are retained; the update focuses on search visibility, listing expiry/renewal, account recovery, and data retention.

## Search visibility

- PataMahali is presented publicly as a Kenya house-hunting and property-search destination. Homepage title/description target house hunting, houses and bedsitters for rent, apartments, homes for sale, land and plots, and county/constituency/ward/neighbourhood searches. The existing two-gate entrance remains intact.
- A branded 1200 × 630 share image and square PataMahali avatar are included for search/social previews and browser icons.
- `robots.txt`, `sitemap.xml`, and `llms.txt` are available. Six category hubs cover homes for rent, short stays, commercial property, warehouses/godowns, land/plots for sale, and houses/property for sale.
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

1. Extract this project so `app.py`, `requirements.txt`, `render.yaml`, `templates/`, and `static/` are at the repository root—not nested under another `bow-main/` folder.
2. Ensure the healthy Render web service serving the custom domain uses this PataMahali project, and keep its persistent data disk attached. A code upload does not automatically transfer a custom domain from another Render service.
3. Keep `PUBLIC_BASE_URL` set to `https://trorinovationstech.co.ke`, verify the homepage returns HTTP 200, and then submit `https://trorinovationstech.co.ke/sitemap.xml` in Google Search Console and Bing Webmaster Tools.

Search rankings are not guaranteed by metadata alone. Search engines need to crawl the live site, and detailed location queries are strongest when real property inventory exists for that location.
