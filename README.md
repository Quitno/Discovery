# Discovery Hub — Professional finishing release

A standalone, mobile-first discovery gateway for a growing network of independent websites, products and individual services. The network currently seeds more than 60 separate service doorways across travel, fashion, furniture, property, mobility, shopping, software and website/app development, alongside the connected platforms House Hunter, OTravel, TRT, Oedge, Denmart and Luxhari. The hub is a discovery layer: each destination application keeps its own database, booking/payment features and customer workflows.

## What's included

- Premium responsive public homepage with individually searchable service doors, service-family pages, mobile navigation, quick-search phrases and direct links to the connected platforms.
- Service entries are independently crawlable, with a unique page, descriptive text, relevant keyword metadata and a separately configurable destination URL. Public directory cards link directly to the resolved destination in the same tab. Verified feature URLs are used for OTravel ticketing, group retreats and billing, and Oedge transport services; connected platforms are the safe fallback when a more specific URL is not yet known. The website/app project request and the first-party downloads library remain on this hub.
- Search across the **hub's destination directory metadata**. Optional per-site search URL templates can pass a visitor's query into a destination that genuinely supports that format.
- Admin dashboard with tracked outbound destination clicks, hub searches, top destinations and popular search phrases.
- Public website/app project brief with live, indicative KES estimate based on project type, size, features, content support and timing. Requests are saved to SQLite and can be reviewed, status-tracked and exported from admin.
- Optional business WhatsApp contact configured in Appearance; no contact number is invented or hard-coded.
- Add/edit/hide/feature/reorder/remove destinations without deleting their actual websites; assign a destination to multiple relevant categories.
- Brand name and homepage copy settings; manual themes plus automatic date-based Christmas, Valentine's, Easter, Black Friday and New Year styling.
- QR codes for the main hub and each destination; destination QR codes pass through the hub's click tracker.
- Motion Ad Studio: multiple campaign records, six visual styles, optional image overlays, scheduled start/end times, rotating headlines, publish/hide/delete controls and an optional visitor-initiated soft sound. The preview animates, and the admin can render an actual 8-second, 720p H.264 MP4 with animated backgrounds, text transitions and optional artwork. Rendering uses the bundled `imageio-ffmpeg` dependency and does not publish or alter a campaign.
- Toror Apps & Downloads library for admin-uploaded APK/AAB/ZIP/PDF/image assets or direct download URLs, each with its own public detail page and download counter.
- Consistent SQLite snapshots (daily and after successful changing form submissions), downloadable full ZIP backups containing the database and managed advert/download assets, pre-restore snapshots, archive validation and a rollback attempt if restore fails.
- PWA manifest, app icons, install prompt support, service-worker shell caching for the gateway and visited service/category pages, and a friendly offline page. Offline cache is not a replacement for persistent server storage.
- Dynamic robots.txt and XML sitemap for crawlers (not exposed as a visitor-navigation link), canonical and Open Graph metadata, Organization/WebSite/SearchAction structured data, descriptive service landing pages, responsive accessibility refinements, security headers and health check.
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

6. Deploy and open `/qaz` (the existing `/admin/login` route also remains available). Sign in using the values configured in `USER_NAME` and `USER_PASSWORD`.
7. In **Destinations**, verify every platform URL. In **Service directory**, review rows marked “Exact page URL needed” and enter the verified route for each feature that should open a specific page. OTravel ticketing is preconnected to `https://otravel-bleg.onrender.com/register?next=/ticketing`; O Ride, O-Drive and O-Movers are preconnected to `https://oedge.onrender.com/services`. If you later change the destination in Admin, the chosen URL is retained after the one-time direct-destination migration.
8. In **Apps & downloads**, upload the actual installable `.apk` release for each Android app (or provide its verified download URL). A source-code ZIP is not itself an installable APK.
9. In **Appearance**, change “The Discovery Hub” to your final brand and set the headline, description and theme. The visible public footer carries the Toror Technology & Innovations Ltd. rights notice; the crawler sitemap remains available at `/sitemap.xml` without a visitor-facing sitemap link.
10. For search discovery, add/verify the domain in Google Search Console and Bing Webmaster Tools, then submit `https://trorinovationstech.co.ke/sitemap.xml`. Discovery and rankings take time and depend on query relevance, content quality, site health and indexing; metadata alone cannot guarantee ranking for every search phrase.
11. Open **Backups & data**, download an initial SQLite copy, then configure persistent storage as described below.

### Persistent storage is important

SQLite is appropriate for this small, low-write discovery directory, but its database must persist between deployments. For a revenue-focused public service, use a paid Render web-service plan that supports a persistent disk; free instances may sleep and do not provide the persistent-disk setup needed here. On Render, attach a persistent disk to the web service mounted at:

```text
/var/data
```

The application automatically uses `/var/data/discovery_hub.sqlite3` when that writable mount is present. Without the mount, it falls back to `instance/discovery_hub.sqlite3`, which is suitable for local testing but may not survive replacement of a hosted instance. Keep regular copies downloaded outside the hosting account. Test restoring a backup before trusting it. The app's server-side backup directory also uses the persistent mount when available.

For a much larger, concurrent, multi-instance deployment, migrate this directory database to a managed database before scaling horizontally; SQLite on one attached disk is not designed for many web instances writing concurrently.


## Individually discoverable services and Toror releases

The public directory seeds separate OTravel, Luxhari, TRT, Pata Mahali/property, O Ride, Toror downloads and development entries. It also has Airbnb-style short-stay doorways for Nairobi, Mombasa, Kisumu, Eldoret, Nakuru, Naivasha, Kitale, Bungoma, Thika, Nyeri, Embu, Machakos, Kitengela, Mlolongo, Syokimau, Taita Taveta, Lamu and Turkana. These pages are starting directories, not a claim that every independent app route has already been implemented in its parent website. On **Admin → Service directory**, set a direct URL for each feature when the real page is available; use visible wording and correct destination URLs before advertising a service.

The named Tomorrow Music, Tomorrow Messages and AdShield doorways filter the public downloads library. A release only appears after it is published in **Admin → Apps & downloads**; the directory does not fabricate APKs or certify uploaded binaries.

## Advert studio boundaries

Ads can be published/unpublished, scheduled, styled with motion gradients and artwork, and rotated through different saved headlines so the same campaign does not immediately repeat for the same visitor. Audio is offered only behind an explicit visitor click because browsers generally block unrequested autoplay sound. MP4 rendering is built into this version; it exports a real animated 8-second, 720p H.264 video. There is no connected external AI model, so the editor can automatically compose the video from the supplied message and its own motion treatments, while optional headline variants allow more variation.

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

The included service and service-family pages are server-rendered and included in the sitemap. Ad hoc search-result pages are marked noindex so the stable, relevant service pages remain the main search-engine landing pages. This makes the network easier for search engines to understand but does not guarantee a top Google ranking; domain history, useful content, genuine direct links, page speed, and external reputation still matter. Do not add unrelated keywords or create misleading location claims. Search Console can be configured after adding the main custom domain.

## Analytics and privacy

- An outbound click is counted when someone clicks a visible destination button or scans its QR code.
- Hub searches are counted at `/search`.
- The dashboard does not count page views or activity inside the independent destination applications. That requires analytics integration in those apps.
- The hub does not store visitor IP addresses or user-agent strings in its analytics table. Email-like and phone-number-like query text is redacted before search statistics are written. Search phrases are still stored in reduced form to build the “popular searches” summary; add a privacy notice appropriate to your actual business and jurisdiction.
- The public gateway QR at `/share-qr.png` is intentionally visitor-facing and points to the hub home page, so it can be placed on posters and shared without an admin login. Destination QR administration and database backups remain inside admin. Project requests include contact details and requirements, saved to SQLite for admin review; configure persistent storage and keep backups current. The public WhatsApp link appears only after you set a contact number in Appearance. Keep `USER_PASSWORD` private and strong.

## PWA and offline behaviour

The service worker caches the public homepage and the local interface shell so the app can open and explain its offline state after it has been visited online. When you later update cached CSS, JavaScript or icons, increment `CACHE_VERSION` in `static/js/service-worker.js` so returning installations fetch the new assets. Admin routes, tracking redirects and searches are intentionally excluded from the service-worker cache. A PWA cannot complete new bookings or access live destination data while offline; the connected sites and their own functionality remain responsible for that.

## Admin pages

- `/qaz` — administrator sign-in shortcut (the `/admin/login` alias also works)
- `/admin` — analytics overview
- `/admin/sites` — destination platforms and visibility
- `/admin/services` — individual service pages and direct destination routes
- `/admin/ads` — motion advertising studio and campaign scheduling
- `/admin/downloads` — APKs, apps and digital downloads
- `/admin/appearance` — name, text, themes and optional WhatsApp contact number
- `/admin/requests` — read, track and export website/app project submissions
- `/admin/qr` — printable/shareable QR codes
- `/admin/backup` — create database snapshots, download full ZIP backups and restore a known backup

## Local test

Install dependencies and run `python app.py`. The local development server disables the Secure-cookie flag for local HTTP only. For production, use the `Procfile` under HTTPS. Do not publish your real administrator environment variables.

## Mobile and project-account additions

- The public layout uses a clean white professional theme with dark readable type and restrained blue accents. On phones, links are spaced for thumb use; narrow screens switch to a single-column service list to keep names and descriptions legible.
- Curated destinations include House Hunter, OTravel, TRT, Oedge, Denmart and Luxhari. The retired Prime School Portal is removed during startup migration; the admin can still manage visibility and destination details.
- Visitors can create an account at `/account/register`, sign in at `/account/login`, and track project requests at `/my-projects`. Only requests submitted while signed in are linked to that account.
- Admin can set request status and write applicant-facing feedback from **Admin → Project requests**. Account pages are excluded from indexing and service-worker caching.
