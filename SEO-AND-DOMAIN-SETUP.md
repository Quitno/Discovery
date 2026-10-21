# SEO, company visibility and custom domain setup

## 1. What is live right now

- Product site: `https://tomorrow-au2q.onrender.com/`
- Company website: `https://apps.trorinovationstech.co.ke/`
- Recommended branded product URL: `https://barcode.trorinovationstech.co.ke/`

A website being online does not guarantee it will appear in Google within a few days. The source now exposes crawlable public pages, structured company/product metadata, `robots.txt`, and a sitemap. Search engines still choose when and whether to index pages.

## 2. Publish this source update

1. Replace the current Barcode Hub project files with this updated project in its GitHub repository.
2. Commit and push the changes, then redeploy the existing Render web service.
3. Open the homepage, `/company`, `/robots.txt` and `/sitemap.xml` on the deployed URL. They should all return successfully. Search pages may be limited to a small number of catalogue results by design.
4. In the admin dashboard, check that the data-storage notice does **not** say the database is using app-local SQLite. The live Render service must have the `/var/data` disk mounted as configured in `render.yaml`; otherwise user accounts, subscriptions and visitor history can disappear after instance replacement.

## 3. Ask Google to discover the current site

1. Open Google Search Console: `https://search.google.com/search-console/`.
2. Add a **URL-prefix** property for `https://tomorrow-au2q.onrender.com/` while that is the public address. Verify the property using the HTML-tag method if offered. Copy only the verification token value into the Render environment variable `GOOGLE_SITE_VERIFICATION`, then redeploy. The HTML tag will appear on public pages.
3. In Search Console, use **URL Inspection** for the homepage and click **Request indexing** when available.
4. Open **Sitemaps**, submit `https://tomorrow-au2q.onrender.com/sitemap.xml`, and check for errors. Inspect `/company`, `/pricing` and `/docs` as well.
5. Review **Page indexing** for messages such as blocked by robots, duplicate canonical, crawled but not indexed, or server error. Do not keep repeating indexing requests; check the reported reason first.

Submitting a sitemap or requesting indexing is not a promise of immediate inclusion or high ranking. Helpful page content, internal links, consistent business details and independent mentions of the site all contribute to discovery.

## 4. Set up the branded domain

Use `barcode.trorinovationstech.co.ke` as the public address for this Barcode Hub product. Continue using `apps.trorinovationstech.co.ke` as the company portfolio. A domain name is the address; Render or another provider is the host/server.

1. In Render, open the Barcode Hub web service and add `barcode.trorinovationstech.co.ke` under **Custom Domains**.
2. In the DNS manager for `trorinovationstech.co.ke`, add the exact CNAME record/target shown by Render. Do not guess at the target. Allow DNS and managed HTTPS to finish provisioning.
3. Open `https://barcode.trorinovationstech.co.ke/`, check that it serves this app over HTTPS, and test `/robots.txt` plus `/sitemap.xml`.
4. Only then set `PUBLIC_SITE_URL=https://barcode.trorinovationstech.co.ke` as a Render environment variable and redeploy. Canonical links, structured data and the sitemap will use the branded domain. Do not set it before the domain works.
5. Add the custom URL as a property in Search Console and submit `https://barcode.trorinovationstech.co.ke/sitemap.xml`. Keep the old Render URL working during the move, and use a permanent redirect from the old host to the new one if the host configuration supports it.

A separate `api.trorinovationstech.co.ke` is optional. The current API endpoint can remain at `/api/v1/barcode/{barcode}` under `barcode.trorinovationstech.co.ke` until there is a technical reason to split it out.

## 5. Promote the product on the company portfolio

The attached source is the **Barcode Hub project**, not the separate corporate portfolio source. A suitable project card for the corporate site's **Apps & Sites** section is:

- **Name:** Kenya Barcode Hub — POS Barcode API
- **Description:** Search product barcode records or connect a POS, supermarket, inventory or retail application to a paid REST API. Designed for developers who want to reduce manual product entry in Kenyan retail workflows.
- **Primary button:** Explore Barcode Hub
- **Temporary link:** `https://tomorrow-au2q.onrender.com/`
- **Final link after DNS:** `https://barcode.trorinovationstech.co.ke/`

Also link to the product from the company homepage and relevant Services/Projects page. On both websites, use the exact registered company name consistently in page titles, footers and Organization structured data. If the visible registered name is **Toror Technology and Innovations Limited**, keep that legal name consistent and show any shorter trading/brand name separately.

## 6. Unique visitor counting

The app uses the random `kbh_visitor_id` first-party cookie for up to one year and avoids hardware fingerprinting. Repeat visits through the same browser profile should normally share one visitor ID. Clearing site data, using private browsing, switching browsers or moving to a new domain can produce a new ID. This is intentionally approximate and privacy-respecting; it cannot identify one physical device across every browser.
