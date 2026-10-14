# Discovery Hub — Render-ready source

A standalone, mobile-first discovery landing site for linking existing websites such as House Hunter, OTravel, TRT and Oedge, with Denmart and Luxhari added as curated destinations. It is a directory and discovery layer; the existing destination applications keep their own databases, features and customer workflows.

## What's included

- Premium responsive public homepage with visible destination buttons, category pages, search suggestions, mobile sidebar and readable typography.
- Seeded links for the four supplied Render applications. Edit every URL, name, category, description and keyword in admin.
- Search across the **hub's destination directory metadata**. Optional per-site search URL templates can pass a visitor's query into a destination that genuinely supports that format.
- Admin dashboard with tracked outbound destination clicks, hub searches, top destinations and popular search phrases.
- Public website/app project brief with live, indicative KES estimate based on project type, size, features, content support and timing. Requests are saved to SQLite and can be reviewed, status-tracked and exported from admin.
- Optional business WhatsApp contact configured in Appearance; no contact number is invented or hard-coded.
- Add/edit/hide/feature/reorder/remove destinations without deleting their actual websites; assign a destination to multiple relevant categories.
- Brand name and homepage copy settings; manual themes plus automatic date-based Christmas, Valentine's, Easter, Black Friday and New Year styling.
- QR codes for the main hub and each destination; destination QR codes pass through the hub's click tracker.
- SQLite backup creation and secure database downloads from the admin area.
- PWA manifest, app icons, install prompt support, service-worker shell caching and a friendly offline page.
- Dynamic robots.txt, sitemap.xml, canonical tags, descriptive category pages, accessibility touches, security headers and health check.
- Render `requirements.txt`, `Procfile`, `runtime.txt` and `.gitignore`.

## Render deployment

1. Upload this folder to a new private GitHub repository, or push it to an existing repository intended for this independent hub.
2. In Render, create a **New Web Service** connected to that repository.
3. Set the build command to:

   ```text
   pip install -r requirements.txt
   ```

4. Set the start command to the one in `Procfile`, or use:

   ```text
   gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60
   ```

5. In Render → Environment, add exactly these two application environment variables:

   - `USER_NAME` — your chosen administrator username.
   - `USER_PASSWORD` — a long, unique administrator password.

   Do not put credentials in source code or in the SQLite database. The Flask session signing secret is generated once and saved in the database at first boot; it is not a third environment variable. Keep database storage persistent so the secret and admin configuration survive deployments.

6. Deploy and open `/admin/login`. Sign in using the values configured in `USER_NAME` and `USER_PASSWORD`.
7. In **Destinations**, verify each seeded URL, add any other existing website, enter accurate descriptions and relevant keywords, choose additional relevant categories when needed, and choose which destinations appear on the public homepage.
8. In **Appearance**, change “The Discovery Hub” to your final brand and set the headline, description and theme.
9. Open **Backups & data**, download an initial SQLite copy, then configure persistent storage as described below.

### Persistent storage is important

SQLite is appropriate for this small, low-write discovery directory, but its database must persist between deployments. For a revenue-focused public service, use a paid Render web-service plan that supports a persistent disk; free instances may sleep and do not provide the persistent-disk setup needed here. On Render, attach a persistent disk to the web service mounted at:

```text
/var/data
```

The application automatically uses `/var/data/discovery_hub.sqlite3` when that writable mount is present. Without the mount, it falls back to `instance/discovery_hub.sqlite3`, which is suitable for local testing but may not survive replacement of a hosted instance. Keep regular copies downloaded outside the hosting account. Test restoring a backup before trusting it. The app's server-side backup directory also uses the persistent mount when available.

For a much larger, concurrent, multi-instance deployment, migrate this directory database to a managed database before scaling horizontally; SQLite on one attached disk is not designed for many web instances writing concurrently.

## Connect one purchased domain to multiple Render apps

Purchase the parent domain once. Then add a different hostname to each existing Render service, for example:

- Main hub: `example.co.ke`
- House Hunter: `homes.example.co.ke`
- OTravel: `travel.example.co.ke`
- TRT: `trt.example.co.ke`
- Oedge: `oedge.example.co.ke`

Replace `example.co.ke` with your actual registered domain. In each Render service's **Settings → Custom Domains**, add its hostname; then follow Render's DNS instructions at the domain's DNS provider and verify each hostname. Each subdomain gets its own DNS record and must be assigned to the corresponding Render service. You do not purchase each subdomain separately, but your Render workspace plan may limit how many custom-domain entries are included.

Do this after the hub is deployed and tested on its `onrender.com` address. The hub links are editable in admin, so updating a destination to its branded subdomain does not require code changes. Download fresh QR images after connecting the custom domain if you want newly printed codes to point at the branded address.

## Search behaviour and honest limitations

The hub search matches the names, categories, descriptions and keywords saved for each connected destination. It does **not** search the internal inventory of every separate app automatically. If a destination has a public search URL such as `https://example.com/search?q=...`, put that full pattern in **Internal search URL template**, using `{query}` where the phrase belongs. The hostname must match the destination's main URL, and the target application must actually support that pattern. If you leave the template blank, the hub opens the destination homepage.

The included search/category pages are server-rendered and crawlable. Do not add unrelated keywords or create misleading location pages. The hub does not automatically create claims such as “near Two Rivers” from a keyword alone; those claims belong on useful, accurate property and business listings. Search Console can be configured after adding the main custom domain.

## Analytics and privacy

- An outbound click is counted when someone clicks a visible destination button or scans its QR code.
- Hub searches are counted at `/search`.
- The dashboard does not count page views or activity inside the independent destination applications. That requires analytics integration in those apps.
- The hub does not store visitor IP addresses or user-agent strings in its analytics table. Email-like and phone-number-like query text is redacted before search statistics are written. Search phrases are still stored in reduced form to build the “popular searches” summary; add a privacy notice appropriate to your actual business and jurisdiction.
- The public gateway QR at `/share-qr.png` is intentionally visitor-facing and points to the hub home page, so it can be placed on posters and shared without an admin login. Destination QR administration and database backups remain inside admin. Project requests include contact details and requirements, saved to SQLite for admin review; configure persistent storage and keep backups current. The public WhatsApp link appears only after you set a contact number in Appearance. Keep `USER_PASSWORD` private and strong.

## PWA and offline behaviour

The service worker caches the public homepage and the local interface shell so the app can open and explain its offline state after it has been visited online. When you later update cached CSS, JavaScript or icons, increment `CACHE_VERSION` in `static/js/service-worker.js` so returning installations fetch the new assets. Admin routes, tracking redirects and searches are intentionally excluded from the service-worker cache. A PWA cannot complete new bookings or access live destination data while offline; the connected sites and their own functionality remain responsible for that.

## Admin pages

- `/admin/login` — sign in
- `/admin` — analytics overview
- `/admin/sites` — destinations and visibility
- `/admin/appearance` — name, text, themes and optional WhatsApp contact number
- `/admin/requests` — read, track and export website/app project submissions
- `/admin/qr` — printable/shareable QR codes
- `/admin/backup` — create and download database backups

## Local test

Install dependencies and run `python app.py`. The local development server disables the Secure-cookie flag for local HTTP only. For production, use the `Procfile` under HTTPS. Do not publish your real administrator environment variables.

## Mobile and project-account additions

- The public phone layout uses the device's light/dark preference and a colourful, touch-friendly two-column destination directory.
- Curated destinations include House Hunter, OTravel, TRT, Oedge, Denmart and Luxhari. The retired Prime School Portal is removed during startup migration; the admin can still manage visibility and destination details.
- Visitors can create an account at `/account/register`, sign in at `/account/login`, and track project requests at `/my-projects`. Only requests submitted while signed in are linked to that account.
- Admin can set request status and write applicant-facing feedback from **Admin → Project requests**. Account pages are excluded from indexing and service-worker caching.
