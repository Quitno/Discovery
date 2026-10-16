# APK discovery SEO handover — 16 October 2026

## Implemented in the Discovery Hub project

- Added stable canonical URLs using `PUBLIC_SITE_URL` (defaults to `https://trorinovationstech.co.ke`) for page canonical tags, Open Graph URLs and sitemap destinations.
- Added purpose-built landing content for the Android directory and three app pages: Tomorrow Music, Tomorrow Messages and AdShield. Each has distinct metadata, practical download/install guidance, FAQs, and SoftwareApplication structured data where applicable.
- Changed APK cards in the homepage, category-grouping, and search results to link to the Hub's public app information pages; those pages still link out to the dedicated Toror APK portal for the current release. The prominent quick link continues to open the APK portal directly.
- Expanded first-party search terms around real app names and relevant Android use cases, without making unverified feature, safety, or YouTube-affiliation claims.
- Updated the sitemap to use canonical-domain URLs and removed the empty internal downloads catalogue from the sitemap until a public release is actually published there.
- Kept existing routes, app portal destination, admin database, and service catalogue. A one-time migration updates only the exact previous factory descriptions, leaving custom admin-edited copy alone.

## Deployment and remaining work

- Deploy this Hub ZIP to the existing Discovery Hub service. This does not itself change the already-running production website.
- Set `PUBLIC_SITE_URL=https://trorinovationstech.co.ke` in the hosting environment if desired; this is non-secret configuration.
- Submit `https://trorinovationstech.co.ke/sitemap.xml` through Search Console and Bing Webmaster Tools after deployment.
- The separate live APK portal source code was not present in the project archive inspected for this update, so no changes were made directly to `https://toror-technology.onrender.com/`. The Hub now has stronger first-party discovery pages for its app links, but the portal itself should also receive its own sitemap, robots, app release pages and canonical metadata when its source is available.
- Search indexing and rank changes cannot be guaranteed or triggered solely by packaging this project.
