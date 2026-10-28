# PataMahali preview/UI update — 28 October 2026

- The Homes/Rentals route now renders the available 40-card discovery set as visible **UNVERIFIED** preview cards when the database has no approved public listings. Other categories render 15 previews each. These cards are built in memory from `photo_rails.py`; they are not inserted into the listings database and have no owner contact flow.
- The first 16 rental gallery entries now use remote thumbnails of real Kenyan housing photographs, including Nairobi, Makongeni, Membley/Ruiru, Mirema, Hurlingham, Baringo, Siaya-region rural homes, Lamu and Kenyan community housing. See `PHOTO-CREDITS-PATA-MAHALI.md`.
- The former large “Photo inspiration / reference photo / availability not implied” block has been replaced by direct preview cards with a compact **UNVERIFIED** badge.
- The shared main navigation is no longer omitted on `/homes`. The Homes sidebar now contains About, How to use, Contact and Rate the app links; the landing footer includes the same routes.
- The home page now presents eight home preview cards below the entry shortcuts. All photo galleries keep remote compressed images/fallback URLs, so the images are not copied into Render disk storage.

No fake property records are created. Actual published listings remain subject to the existing approval and verification rules.
