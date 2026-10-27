from __future__ import annotations

import json
import math
import os
import secrets
import shutil
import sqlite3
import tempfile
import zipfile
import uuid
import hmac
import hashlib
import re
from difflib import SequenceMatcher
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse, quote_plus

import qrcode
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_file, send_from_directory, session, url_for
)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from places import (
    COUNTY_CONSTITUENCIES, COUNTY_SUMMARIES, FINE_AREAS, all_known_localities,
    county_by_slug, county_fine_areas, constituency_by_slug, selector_data,
    slugify, ward_map
)
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent
configured_data_dir = Path(os.environ.get("DATA_DIR", "/var/data" if (os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER")) else str(BASE_DIR / "instance")))
try:
    configured_data_dir.mkdir(parents=True, exist_ok=True)
    DATA_DIR = configured_data_dir
except OSError as exc:
    # Avoid failing the whole web service if a Render disk path is configured before
    # a disk is mounted. This fallback is ephemeral; see README for production setup.
    DATA_DIR = BASE_DIR / "instance"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"WARNING: Could not use DATA_DIR={configured_data_dir}: {exc}. Using {DATA_DIR}; add a persistent Render disk.")

DB_PATH = DATA_DIR / "patamahali.sqlite3"
BACKUP_DIR = DATA_DIR / "backups"
LISTING_UPLOAD_DIR = DATA_DIR / "uploads" / "listings"
PRIVATE_DOC_DIR = DATA_DIR / "private_documents"
BRANDING_DIR = DATA_DIR / "uploads" / "branding"
PROMO_DIR = DATA_DIR / "uploads" / "promotions"
for directory in (BACKUP_DIR, LISTING_UPLOAD_DIR, PRIVATE_DOC_DIR, BRANDING_DIR, PROMO_DIR):
    directory.mkdir(parents=True, exist_ok=True)

ADMIN_PATH = "promise212324"  # Fixed private admin entry; do not configure through Render variables.
ADMIN_ROOT = "/" + ADMIN_PATH
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(12 * 1024 * 1024)))
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DOC_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER")),
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)


def load_secret_key() -> str:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(48)
    key_file.write_text(value, encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return value


app.secret_key = load_secret_key()

DEFAULT_SETTINGS = {
    "site_name": "PataMahali",
    "tagline": "Find the right place.",
    "site_description": "House hunting in Kenya made easier: find houses, bedsitters and apartments for rent, homes for sale, land and plots, shops, offices, warehouses and short stays across all 47 counties. Search by county, constituency, ward and neighbourhood on PataMahali.",
    "brand_primary": "#102641",
    "brand_accent": "#C8A45D",
    "public_theme": "signature",
    "site_logo": "",
    "show_landing_qr_enabled": "1",
    "show_visitor_counter_enabled": "1",
    "show_partner_directory_enabled": "1",
    "category_enabled_residential": "1",
    "category_enabled_short_stay": "1",
    "category_enabled_commercial": "1",
    "category_enabled_industrial": "1",
    "category_enabled_land_sale": "1",
    "category_enabled_property_sale": "1",
    "market_discoveries_enabled": "0",
    "promo_enabled": "0",
    "promo_title": "",
    "promo_text": "",
    "promo_link": "",
    "promo_link_label": "Learn more",
    "promo_video_url": "",
    "promo_image": "",
    "header_links_enabled": "0",
    "header_links": "",
    "management_url": "",
    "support_phone": "",
    "support_email": "",
    "social_instagram_enabled": "0", "social_instagram_url": "",
    "social_facebook_enabled": "0", "social_facebook_url": "",
    "social_tiktok_enabled": "0", "social_tiktok_url": "",
    "social_youtube_enabled": "0", "social_youtube_url": "",
    "social_linkedin_enabled": "0", "social_linkedin_url": "",
    "social_x_enabled": "0", "social_x_url": "",
    "payment_method": "M-Pesa",
    "payment_paybill": "",
    "payment_account": "",
    "payment_phone": "",
    "payment_instructions": "Pay the listing fee using the verified details below, then enter your payment reference. Your listing stays private until the payment and property checks are approved.",
    "fee_residential": "500",
    "fee_short_stay": "700",
    "fee_commercial": "1000",
    "fee_industrial": "1500",
    "fee_land_sale": "1000",
    "fee_property_sale": "1000",
    "fee_featured": "300",
    "boost_fee_vip": "1000",
    "boost_fee_vvip": "2500",
    "boost_duration_days_vip": "7",
    "boost_duration_days_vvip": "14",
    "listing_expiry_days": "30",
    "public_base_url": os.environ.get("PUBLIC_BASE_URL", "https://trorinovationstech.co.ke"),
    "terms_notice": "Never pay a deposit before independently confirming the property and the person receiving payment.",
}

CATEGORY_META = {
    "residential": {"label": "Homes & rentals", "short": "Homes", "description": "Bedsitters, studios, apartments and family homes.", "fee": "fee_residential", "types": ["Bedsitter", "Studio", "1-bedroom apartment", "2-bedroom apartment", "3+ bedroom house", "Maisonette", "Townhouse", "Furnished apartment", "Other home"]},
    "short_stay": {"label": "Hotels & short stays", "short": "Stays", "description": "Hotels, BnBs, guest houses and furnished stays.", "fee": "fee_short_stay", "types": ["Hotel room", "BnB", "Guest house", "Holiday home", "Serviced apartment", "Other stay"]},
    "commercial": {"label": "Shops & business premises", "short": "Shops & offices", "description": "Shops, stalls, offices and business premises.", "fee": "fee_commercial", "types": ["Shop", "Stall", "Office", "Showroom", "Restaurant space", "Workshop", "Other commercial space"]},
    "industrial": {"label": "Warehouses & industrial", "short": "Warehouses", "description": "Godowns, warehouses, yards and logistics space.", "fee": "fee_industrial", "types": ["Warehouse / godown", "Storage unit", "Industrial yard", "Workshop", "Logistics facility", "Other industrial space"]},
    "land_sale": {"label": "Land & plots", "short": "Land", "description": "Plots and land listings with location and terms.", "fee": "fee_land_sale", "types": ["Residential plot", "Agricultural land", "Commercial plot", "Industrial land", "Other land"]},
    "property_sale": {"label": "Property for sale", "short": "For sale", "description": "Homes, buildings and investment property for sale.", "fee": "fee_property_sale", "types": ["House for sale", "Apartment for sale", "Commercial building", "Apartment block", "Mixed-use property", "Other property"]},
}
PRICE_PERIODS = ["per month", "per night", "per day", "per year", "total price", "per square foot"]

# Human-readable search intent hubs. Each page combines a real category with the
# existing Kenya location hierarchy; pages without live matches are kept out of
# the index until there is useful inventory, rather than manufacturing fake listings.
SEO_CATEGORY_PAGES = {
    "homes-for-rent": {"category": "residential", "label": "Houses and Homes for Rent", "short": "Rentals", "description": "Start house hunting in Kenya: search houses to rent, rooms to let, bedsitters, studio flats, apartments, furnished rentals and family homes. Narrow by county, constituency, ward, estate and neighbourhood, then compare real listing details and asking prices."},
    "hotels-and-short-stays": {"category": "short_stay", "label": "Hotels, BnBs and Short Stays", "short": "Hotels & stays", "description": "Find hotel rooms, guest houses, holiday homes, BnBs and serviced apartments across Kenya. Explore locations and review real listing details before contacting a host."},
    "shops-and-commercial-property": {"category": "commercial", "label": "Shops, Offices and Commercial Property", "short": "Commercial space", "description": "Search shops, stalls, offices, showrooms, restaurants and other business premises across Kenya. Refine by county, constituency and exact local area."},
    "warehouses-and-godowns": {"category": "industrial", "label": "Warehouses, Godowns and Industrial Space", "short": "Industrial space", "description": "Explore warehouses, godowns, storage units, industrial yards, workshops and logistics facilities in Kenya. Compare location, floor area, access and asking price."},
    "land-and-plots-for-sale": {"category": "land_sale", "label": "Land and Plots for Sale", "short": "Land & plots", "description": "Find land for sale in Kenya, buy a plot, or compare residential plots, agricultural or farm land, commercial plots and industrial land. Narrow by county, constituency, ward, estate or neighbourhood, and check location and ownership information before paying."},
    "houses-and-property-for-sale": {"category": "property_sale", "label": "Houses, Apartments and Property for Sale", "short": "Property for sale", "description": "Find a house to buy in Kenya, compare homes for sale, flats, apartments, apartment blocks, commercial buildings and investment property. Search by county, constituency, ward and neighbourhood, and compare the details supplied by each advertiser."},
}
RECOVERY_QUESTIONS = (
    "What was the name of your first school?",
    "What town or village did you grow up in?",
    "What was the name of your first employer?",
    "What is your private recovery phrase?",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL DEFAULT 'seeker',
    account_type TEXT NOT NULL DEFAULT 'seeker',
    full_name TEXT NOT NULL,
    business_name TEXT NOT NULL DEFAULT '',
    email TEXT UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    contact_preference TEXT NOT NULL DEFAULT 'whatsapp',
    website_url TEXT NOT NULL DEFAULT '',
    social_url TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    identity_type TEXT NOT NULL DEFAULT 'national_id',
    identity_front TEXT NOT NULL DEFAULT '',
    identity_back TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0,
    suspended INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_login TEXT NOT NULL DEFAULT '',
    recovery_question TEXT NOT NULL DEFAULT '',
    recovery_answer_hash TEXT NOT NULL DEFAULT '',
    recovery_updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    property_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_amount REAL NOT NULL DEFAULT 0,
    price_period TEXT NOT NULL DEFAULT 'per month',
    deposit_amount REAL,
    bedrooms INTEGER,
    bathrooms INTEGER,
    floor_area TEXT NOT NULL DEFAULT '',
    amenities TEXT NOT NULL DEFAULT '',
    water_quality TEXT NOT NULL DEFAULT '',
    location_name TEXT NOT NULL,
    county TEXT NOT NULL DEFAULT '',
    constituency TEXT NOT NULL DEFAULT '',
    ward TEXT NOT NULL DEFAULT '',
    local_area TEXT NOT NULL DEFAULT '',
    external_url TEXT NOT NULL DEFAULT '',
    boost_tier TEXT NOT NULL DEFAULT '',
    landmarks TEXT NOT NULL DEFAULT '',
    latitude REAL,
    longitude REAL,
    property_condition TEXT NOT NULL DEFAULT '',
    images TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    approval_status TEXT NOT NULL DEFAULT 'pending',
    payment_status TEXT NOT NULL DEFAULT 'pending',
    payment_reference TEXT NOT NULL DEFAULT '',
    fee_amount REAL NOT NULL DEFAULT 0,
    property_verified INTEGER NOT NULL DEFAULT 0,
    featured_until TEXT NOT NULL DEFAULT '',
    posted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_confirmed_at TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL DEFAULT '',
    renewal_payment_status TEXT NOT NULL DEFAULT 'none',
    renewal_payment_reference TEXT NOT NULL DEFAULT '',
    renewal_submitted_at TEXT NOT NULL DEFAULT '',
    renewal_count INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT NOT NULL DEFAULT '',
    is_sample INTEGER NOT NULL DEFAULT 0,
    admin_rank INTEGER NOT NULL DEFAULT 0,
    views INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(owner_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    seeker_id INTEGER,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    FOREIGN KEY(listing_id) REFERENCES listings(id)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    reporter_id INTEGER,
    reporter_name TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES listings(id)
);
CREATE TABLE IF NOT EXISTS visitor_sessions (
    visitor_key TEXT PRIMARY KEY,
    user_id INTEGER,
    role TEXT NOT NULL DEFAULT 'visitor',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_path TEXT NOT NULL DEFAULT '/',
    referrer TEXT NOT NULL DEFAULT '',
    device TEXT NOT NULL DEFAULT 'Unknown',
    page_views INTEGER NOT NULL DEFAULT 0,
    visit_count INTEGER NOT NULL DEFAULT 1,
    last_visit_at TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    latitude_approx REAL,
    longitude_approx REAL,
    location_shared INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS visitor_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor_key TEXT NOT NULL,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
    review TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(listing_id, reviewer_id),
    FOREIGN KEY(listing_id) REFERENCES listings(id),
    FOREIGN KEY(reviewer_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_attempts (
    identity_key TEXT PRIMARY KEY,
    window_started TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS boost_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('vip','vvip')),
    fee_amount REAL NOT NULL DEFAULT 0,
    payment_reference TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    admin_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(listing_id) REFERENCES listings(id),
    FOREIGN KEY(owner_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_boost_requests_status ON boost_requests(status, created_at);
CREATE TABLE IF NOT EXISTS market_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'residential',
    property_type TEXT NOT NULL DEFAULT 'Apartment',
    price_amount REAL,
    price_period TEXT NOT NULL DEFAULT 'per month',
    location_name TEXT NOT NULL DEFAULT '',
    bedrooms INTEGER,
    bathrooms INTEGER,
    summary TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    image_url TEXT NOT NULL DEFAULT '',
    social_url TEXT NOT NULL DEFAULT '',
    source_checked_at TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_listings_public ON listings(status, approval_status, payment_status, category);
CREATE INDEX IF NOT EXISTS idx_listings_owner ON listings(owner_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_interests_listing ON interests(listing_id, created_at);
CREATE INDEX IF NOT EXISTS idx_visitor_events_time ON visitor_events(created_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db() -> None:
    with connect_db() as conn:
        conn.executescript(SCHEMA)
        # Forward-only, additive schema migrations keep existing Render SQLite databases usable.
        migrations = {
            "users": {
                "contact_preference": "TEXT NOT NULL DEFAULT 'whatsapp'",
                "website_url": "TEXT NOT NULL DEFAULT ''",
                "social_url": "TEXT NOT NULL DEFAULT ''",
                "recovery_question": "TEXT NOT NULL DEFAULT ''",
                "recovery_answer_hash": "TEXT NOT NULL DEFAULT ''",
                "recovery_updated_at": "TEXT NOT NULL DEFAULT ''",
            },
            "listings": {
                "water_quality": "TEXT NOT NULL DEFAULT ''",
                "county": "TEXT NOT NULL DEFAULT ''",
                "constituency": "TEXT NOT NULL DEFAULT ''",
                "ward": "TEXT NOT NULL DEFAULT ''",
                "local_area": "TEXT NOT NULL DEFAULT ''",
                "external_url": "TEXT NOT NULL DEFAULT ''",
                "boost_tier": "TEXT NOT NULL DEFAULT ''",
                "expires_at": "TEXT NOT NULL DEFAULT ''",
                "renewal_payment_status": "TEXT NOT NULL DEFAULT 'none'",
                "renewal_payment_reference": "TEXT NOT NULL DEFAULT ''",
                "renewal_submitted_at": "TEXT NOT NULL DEFAULT ''",
                "renewal_count": "INTEGER NOT NULL DEFAULT 0",
                "archived_at": "TEXT NOT NULL DEFAULT ''",
                "is_sample": "INTEGER NOT NULL DEFAULT 0",
                "admin_rank": "INTEGER NOT NULL DEFAULT 0",
            },
            "visitor_sessions": {
                "visit_count": "INTEGER NOT NULL DEFAULT 1",
                "last_visit_at": "TEXT NOT NULL DEFAULT ''",
                "contact_name": "TEXT NOT NULL DEFAULT ''",
                "contact_phone": "TEXT NOT NULL DEFAULT ''",
            },
        }
        for table, columns in migrations.items():
            present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, declaration in columns.items():
                if column not in present:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
        # The prior default was 14 days; switch that default to the requested one-month term.
        conn.execute("UPDATE settings SET value='30' WHERE key='listing_expiry_days' AND value='14'")
        # If this database ever held the old Discovery brand, rename only that legacy value.
        previous_brand = conn.execute("SELECT value FROM settings WHERE key='site_name'").fetchone()
        if previous_brand and "discovery" in str(previous_brand[0]).casefold():
            conn.execute("UPDATE settings SET value='PataMahali' WHERE key='site_name'")
            conn.execute("UPDATE settings SET value='Find the right place.' WHERE key='tagline'")
            # Stop displaying an old-branded uploaded logo but keep its file in storage for recovery.
            conn.execute("UPDATE settings SET value='' WHERE key='site_logo'")
        conn.execute("UPDATE settings SET value=? WHERE key='site_description' AND (value='' OR value LIKE '%Find verified homes, stays%')", (DEFAULT_SETTINGS['site_description'],))
        conn.execute("UPDATE settings SET value='https://trorinovationstech.co.ke' WHERE key='public_base_url' AND (value='' OR lower(value) LIKE '%discovery%')")
        # Give every existing listing a one-month lifecycle without deleting user data.
        try:
            lifecycle_days = max(1, min(365, int(conn.execute("SELECT value FROM settings WHERE key='listing_expiry_days'").fetchone()[0])))
        except (TypeError, ValueError, IndexError):
            lifecycle_days = 30
        lifecycle_rows = conn.execute("SELECT id,status,posted_at,last_confirmed_at,expires_at FROM listings WHERE expires_at IS NULL OR expires_at='' ").fetchall()
        migration_now = datetime.now(timezone.utc).replace(microsecond=0)
        for listing_row in lifecycle_rows:
            anchor_text = (listing_row["last_confirmed_at"] or listing_row["posted_at"] or "").strip()
            try:
                anchor = datetime.fromisoformat(anchor_text)
                if anchor.tzinfo is None:
                    anchor = anchor.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                anchor = migration_now
            expiry = (anchor + timedelta(days=lifecycle_days)).astimezone(timezone.utc).replace(microsecond=0).isoformat()
            state = "expired" if listing_row["status"] == "available" and expiry <= migration_now.isoformat() else listing_row["status"]
            conn.execute("UPDATE listings SET expires_at=?,status=?,updated_at=CASE WHEN ?='expired' THEN ? ELSE updated_at END WHERE id=?",
                         (expiry, state, state, migration_now.isoformat(), listing_row["id"]))
        # Turn off the old external property feed without deleting its historical records.
        # These records remain private to the admin and can be recovered from backups, but
        # are not shown to visitors or added to the public search index.
        conn.execute("UPDATE settings SET value='0' WHERE key='market_discoveries_enabled'")
        old_brand = conn.execute("SELECT value FROM settings WHERE key='brand_primary'").fetchone()
        if old_brand and old_brand[0].strip().lower() in {"#176b4d", "#223a63", "#283a62", "#303030"}:
            conn.execute("UPDATE settings SET value='#102641' WHERE key='brand_primary'")
        old_accent = conn.execute("SELECT value FROM settings WHERE key='brand_accent'").fetchone()
        if old_accent and old_accent[0].strip().lower() in {"#d9a441", "#c88a62", "#c5a044"}:
            conn.execute("UPDATE settings SET value='#C8A45D' WHERE key='brand_accent'")
        admin = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if not admin:
            username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
            email = os.environ.get("ADMIN_EMAIL", "").strip() or None
            password = os.environ.get("ADMIN_PASSWORD")
            generated = False
            if not password:
                password = secrets.token_urlsafe(15)
                generated = True
            conn.execute(
                "INSERT INTO users(role,account_type,full_name,email,phone,password_hash,verified,created_at) VALUES('admin','admin',?,?,?,?,1,?)",
                (username, email, "", generate_password_hash(password), now_iso()),
            )
            if generated:
                print("\n=== INITIAL ADMIN LOGIN ===")
                print(f"Admin path: {ADMIN_ROOT}")
                print(f"Username: {username}")
                print(f"Password (copy now; stored as a hash): {password}")
                print("Set ADMIN_USERNAME and ADMIN_PASSWORD in Render environment variables and keep these credentials private.\n")

        # A small, clearly labelled illustrative inventory gives first-time visitors
        # something useful to browse until genuine owners publish listings.
        # These rows are never verified and are always ranked below real listings
        # unless an administrator explicitly promotes them.
        sample_email = "illustrative-listings@patamahali.invalid"
        sample_owner = conn.execute("SELECT id FROM users WHERE email=?", (sample_email,)).fetchone()
        if not sample_owner:
            cur = conn.execute(
                """INSERT INTO users(role,account_type,full_name,business_name,email,phone,password_hash,
                   identity_type,verified,suspended,created_at)
                   VALUES('owner','owner','Pata Mahali Illustrative Collection','Illustrative collection',?,?,?, 'none',0,0,?)""",
                (sample_email, "", generate_password_hash(secrets.token_urlsafe(32)), now_iso()),
            )
            sample_owner_id = cur.lastrowid
        else:
            sample_owner_id = sample_owner["id"]
        scene_dir = BASE_DIR / "static" / "img" / "property-scenes"
        sample_specs = [
            ("residential","2-bedroom apartment","Sunlit two-bedroom apartment near the heart of Kilimani",
             "Illustrative example listing. This is a design sample, not a confirmed available property. Use it to preview the kind of details owners can publish on Pata Mahali.",
             38000,"per month",2,1,"Kilimani, Nairobi","neighbourhood-hero.webp"),
            ("residential","3+ bedroom house","Quiet family home with a private garden in Ruiru",
             "Illustrative example listing with a family-friendly layout and outdoor space. Availability and price are examples only.",
             65000,"per month",3,2,"Ruiru, Kiambu","modern-interior.webp"),
            ("short_stay","Serviced apartment","A calm furnished stay for a Nairobi weekend",
             "Illustrative short-stay example. Nightly price and availability are not a live offer; this listing demonstrates the dedicated stays category.",
             6500,"per night",1,1,"Westlands, Nairobi","apartment-building.webp"),
            ("land_sale","Residential plot","Residential plot in a growing Kiambu neighbourhood",
             "Illustrative land listing. The location and price are examples only; no title or availability claim is made.",
             1850000,"total price",None,None,"Kikuyu, Kiambu","residential-land.webp"),
            ("commercial","Shop","Street-facing retail space for a growing business",
             "Illustrative commercial-space example. Confirm actual availability, lease terms and permitted use before making any commitment.",
             28000,"per month",None,None,"Rongai, Kajiado","modern-interior.webp"),
            ("industrial","Warehouse / godown","Practical storage and distribution space",
             "Illustrative warehouse example. Floor area, price and availability are placeholders for preview only.",
             120000,"per month",None,None,"Athi River, Machakos","apartment-building.webp"),
            ("property_sale","House for sale","Contemporary family home with generous natural light",
             "Illustrative property-for-sale example. This is not a verified offer and must not be treated as an available home.",
             18500000,"total price",4,3,"Syokimau, Machakos","neighbourhood-hero.webp"),
        ]
        for i, spec in enumerate(sample_specs, 1):
            category, typ, title, description, price, period, beds, baths, location, image_name = spec
            exists = conn.execute("SELECT id FROM listings WHERE is_sample=1 AND title=?", (title,)).fetchone()
            if exists:
                continue
            source_image = scene_dir / image_name
            image_filename = f"illustrative-{i}-{image_name}"
            target_image = LISTING_UPLOAD_DIR / image_filename
            if source_image.is_file() and not target_image.exists():
                try:
                    with Image.open(source_image) as opened:
                        optimized = ImageOps.exif_transpose(opened).convert("RGB")
                        optimized.thumbnail((1400, 1100), Image.Resampling.LANCZOS)
                        optimized.save(target_image, "WEBP", quality=82, method=5)
                        optimized.close()
                except (OSError, ValueError):
                    shutil.copy2(source_image, target_image)
            if not target_image.exists():
                continue
            now = now_iso()
            expiry = (datetime.now(timezone.utc) + timedelta(days=3650)).replace(microsecond=0).isoformat()
            conn.execute(
                """INSERT INTO listings(owner_id,category,property_type,title,description,price_amount,price_period,
                   bedrooms,bathrooms,location_name,county,images,status,approval_status,payment_status,
                   property_verified,posted_at,updated_at,expires_at,is_sample,admin_rank)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'available','approved','paid',0,?,?,?,1,0)""",
                (sample_owner_id, category, typ, title, description, price, period, beds, baths, location,
                 location.split(",")[-1].strip(), json.dumps([image_filename]), now, now, expiry),
            )

        conn.execute("PRAGMA journal_mode = WAL")


init_db()


def create_db_snapshot(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = connect_db()
    try:
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        source.close()
    return destination


def create_full_backup_archive(destination: Path) -> Path:
    """Create a portable ZIP of the database and uploaded property/account media."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot = destination.with_name(f".snapshot-{uuid.uuid4().hex}.sqlite3")
    try:
        create_db_snapshot(snapshot)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(snapshot, "database/patamahali.sqlite3")
            for folder in (LISTING_UPLOAD_DIR, PRIVATE_DOC_DIR, BRANDING_DIR, PROMO_DIR):
                if not folder.exists():
                    continue
                for file_path in folder.rglob("*"):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(DATA_DIR).as_posix())
            manifest = (
                "PataMahali full recovery archive\n"
                f"Created: {now_iso()}\n"
                "Contents: database/patamahali.sqlite3 plus uploads/listings, uploads/branding, "
                "uploads/promotions, and private_documents.\n"
                "Security note: this archive may contain personal data, identity documents, and account records. "
                "Keep it in a private, encrypted location.\n"
                "Restore note: first make a fresh backup of the destination. Move database/patamahali.sqlite3 to "
                "DATA_DIR/patamahali.sqlite3, then restore uploads/listings, uploads/branding, uploads/promotions, "
                "and private_documents to the same relative paths under DATA_DIR. Run application migrations after restoring.\n"
            )
            archive.writestr("RECOVERY-README.txt", manifest)
        return destination
    finally:
        snapshot.unlink(missing_ok=True)


def maybe_daily_backup() -> None:
    stamp = datetime.now().strftime("%Y-%m-%d")
    existing = list(BACKUP_DIR.glob(f"auto-{stamp}-*.sqlite3"))
    if not existing and DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        target = BACKUP_DIR / f"auto-{stamp}-{datetime.now().strftime('%H%M%S')}.sqlite3"
        try:
            create_db_snapshot(target)
            backups = sorted(BACKUP_DIR.glob("auto-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[14:]:
                old.unlink(missing_ok=True)
        except Exception as exc:
            print(f"WARNING: automatic SQLite backup failed: {exc}")


maybe_daily_backup()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            if _error is None:
                db.commit()
            else:
                db.rollback()
        finally:
            db.close()


def setting(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def visible_categories() -> dict[str, dict]:
    """Categories currently enabled for public discovery by the administrator."""
    return {key: meta for key, meta in CATEGORY_META.items()
            if setting(f"category_enabled_{key}", "1") == "1"}


def set_setting(key: str, value: str) -> None:
    get_db().execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def all_settings() -> dict[str, str]:
    return {row["key"]: row["value"] for row in get_db().execute("SELECT key,value FROM settings")}


def get_current_user():
    if not getattr(g, "_current_user_loaded", False):
        uid = session.get("user_id")
        g.current_user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None
        g._current_user_loaded = True
    return g.current_user


def refresh_current_user_cache():
    g._current_user_loaded = False
    g.current_user = None


def csrf_field() -> Markup:
    token = session.get("csrf_token", "")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


def current_visitor_key() -> str:
    return getattr(g, "visitor_key", None) or session.get("visitor_key", "")


def normalize_visitor_phone(value: str) -> str:
    """Normalize a voluntarily supplied phone number for duplicate-count reduction."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 10 and digits.startswith("0"):
        digits = "254" + digits[1:]
    return digits[:20]


@app.before_request
def prepare_request():
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(24)
    # A first-party cookie keeps the same anonymous browser identifier across
    # ordinary closes/reopens. It does not reveal a phone number or a real identity.
    stable_key = request.cookies.get("pm_visitor", "").strip()
    if not stable_key or len(stable_key) > 100:
        stable_key = session.get("visitor_key") or secrets.token_urlsafe(24)
    g.visitor_key = stable_key
    session["visitor_key"] = stable_key
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400, description="Your form session expired. Refresh the page and try again.")
    if request.endpoint not in {"static", "manifest", "service_worker", "icon_svg", "robots_txt", "sitemap_xml", "qr_platform", "promo_media"}:
        try:
            maybe_daily_backup()
        except Exception:
            pass
        try:
            expire_due_listings()
        except Exception as exc:
            print(f"WARNING: listing expiry sweep failed: {exc}")


def audit(action: str, target_type: str = "", target_id: str | int = "", details: str = "") -> None:
    user = get_current_user()
    get_db().execute(
        "INSERT INTO audit_log(actor_id,action,target_type,target_id,details,created_at) VALUES(?,?,?,?,?,?)",
        (user["id"] if user else None, action, target_type, str(target_id), details[:2000], now_iso()),
    )


def _auth_attempt_key(scope: str) -> str:
    # Store a short-lived keyed fingerprint, never the raw network address.
    address = request.remote_addr or "unknown"
    value = f"{scope}:{address}".encode("utf-8", "ignore")
    return hmac.new(app.secret_key.encode("utf-8"), value, hashlib.sha256).hexdigest()


def auth_is_limited(scope: str) -> bool:
    key = _auth_attempt_key(scope)
    row = get_db().execute("SELECT window_started,attempts FROM auth_attempts WHERE identity_key=?", (key,)).fetchone()
    if not row:
        return False
    try:
        started = datetime.fromisoformat(row["window_started"])
    except ValueError:
        return False
    if datetime.now(timezone.utc) - started > timedelta(minutes=15):
        get_db().execute("DELETE FROM auth_attempts WHERE identity_key=?", (key,))
        return False
    return row["attempts"] >= 8


def auth_failed(scope: str) -> None:
    key = _auth_attempt_key(scope)
    row = get_db().execute("SELECT window_started,attempts FROM auth_attempts WHERE identity_key=?", (key,)).fetchone()
    expired = False
    if row:
        try:
            expired = datetime.now(timezone.utc) - datetime.fromisoformat(row["window_started"]) > timedelta(minutes=15)
        except ValueError:
            expired = True
    if not row or expired:
        get_db().execute("INSERT INTO auth_attempts(identity_key,window_started,attempts) VALUES(?,?,1) ON CONFLICT(identity_key) DO UPDATE SET window_started=excluded.window_started,attempts=1", (key, now_iso()))
    else:
        get_db().execute("UPDATE auth_attempts SET attempts=attempts+1 WHERE identity_key=?", (key,))


def auth_succeeded(scope: str) -> None:
    get_db().execute("DELETE FROM auth_attempts WHERE identity_key=?", (_auth_attempt_key(scope),))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def partner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Sign in to manage your properties.", "info")
            return redirect(url_for("partner_login", next=request.path))
        if user["role"] not in {"owner", "agent", "host", "business"}:
            flash("This page is for property partners.", "warning")
            return redirect(url_for("index"))
        if user["suspended"]:
            abort(403, description="This partner account is temporarily suspended. Contact support.")
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "admin":
            flash("Administrator sign-in is required.", "warning")
            return redirect(ADMIN_ROOT)
        return view(*args, **kwargs)
    return wrapped


def money(value) -> str:
    try:
        return f"KES {float(value):,.0f}"
    except (TypeError, ValueError):
        return "Price on request"


def safe_external_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return ""
    return value


_BLOCKED_PROPERTY_PORTAL_DOMAINS = (
    "property254.co.ke", "property254.com", "property24.co.ke",
    "buyrentkenya.com", "buyrentkenya.co.ke", "jiji.co.ke",
)


def is_competitor_property_portal_url(value: str) -> bool:
    """Identify property-marketplace URLs the public site must not promote."""
    raw = safe_external_url(value)
    if not raw:
        return False
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if any(host == domain or host.endswith("." + domain)
           for domain in _BLOCKED_PROPERTY_PORTAL_DOMAINS):
        return True
    # Also prevent a Google search shortcut from bypassing the host check.
    if host in {"google.com", "www.google.com", "google.co.ke", "www.google.co.ke"}:
        search_text = (parsed.query + " " + parsed.fragment).lower()
        return any(domain in search_text for domain in _BLOCKED_PROPERTY_PORTAL_DOMAINS)
    return False


def public_base() -> str:
    # Deployment environment is authoritative so canonical links stay on the desired domain,
    # even if an older database contains an obsolete public_base_url setting.
    configured = safe_external_url(os.environ.get("PUBLIC_BASE_URL", "") or setting("public_base_url", "") or "https://trorinovationstech.co.ke")
    return configured.rstrip("/") if configured else request.url_root.rstrip("/")


def listing_lifecycle_days() -> int:
    try:
        return max(1, min(365, int(setting("listing_expiry_days", "30"))))
    except (TypeError, ValueError):
        return 30


def expiry_days_remaining(value: str | None):
    if not value:
        return None
    try:
        due = datetime.fromisoformat(value)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return math.ceil((due - datetime.now(timezone.utc)).total_seconds() / 86400)
    except (TypeError, ValueError):
        return None


def normalized_recovery_answer(value: str) -> str:
    return " ".join((value or "").strip().casefold().split())[:160]


def expire_due_listings() -> None:
    """Take expired adverts out of public search while retaining their history and media."""
    now = now_iso()
    db = get_db()
    changed = db.execute(
        "UPDATE listings SET status='expired',updated_at=? WHERE status='available' AND expires_at<>'' AND expires_at<=?",
        (now, now),
    ).rowcount
    if changed:
        print(f"PataMahali: {changed} expired listing(s) hidden from public search; records retained.")
    # After a 7-day renewal grace period, move unrenewed expiry records to a private archive.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).replace(microsecond=0).isoformat()
    db.execute("UPDATE listings SET status='archived',archived_at=CASE WHEN archived_at='' THEN ? ELSE archived_at END,updated_at=? WHERE status='expired' AND expires_at<>'' AND expires_at<=? AND renewal_payment_status<>'submitted'",
               (now, now, cutoff))


def fee_for_category(category: str) -> float:
    meta = CATEGORY_META.get(category, CATEGORY_META["residential"])
    try:
        return max(0, float(setting(meta["fee"], DEFAULT_SETTINGS[meta["fee"]])))
    except ValueError:
        return 0


def listing_images(row) -> list[str]:
    try:
        return json.loads(row["images"] or "[]")
    except (TypeError, json.JSONDecodeError):
        return []


def freshness_threshold() -> str:
    # Kept for compatibility with any older local integrations; expiry is now
    # controlled by the explicit expires_at field instead of a 14-day heartbeat.
    return (datetime.now(timezone.utc) - timedelta(days=listing_lifecycle_days())).replace(microsecond=0).isoformat()


def is_public_listing(row) -> bool:
    if not row:
        return False
    owner = get_db().execute("SELECT verified,suspended FROM users WHERE id=?", (row["owner_id"],)).fetchone()
    expiry = row["expires_at"] if "expires_at" in row.keys() else ""
    still_in_term = bool(expiry and expiry > now_iso())
    sample = bool("is_sample" in row.keys() and row["is_sample"])
    return bool(owner and not owner["suspended"] and row["payment_status"] == "paid" and row["approval_status"] == "approved" and row["status"] == "available" and still_in_term and (sample or (owner["verified"] and row["property_verified"])))


def log_event(event_type: str, path: str, details: str = "") -> None:
    try:
        user = get_current_user()
        visitor_key = current_visitor_key()
        get_db().execute(
            "INSERT INTO visitor_events(visitor_key,user_id,event_type,path,details,created_at) VALUES(?,?,?,?,?,?)",
            (visitor_key, user["id"] if user else None, event_type, path[:500], details[:1500], now_iso()),
        )
    except Exception as exc:
        print(f"Visitor event not recorded: {exc}")


def device_label(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "iphone" in ua:
        return "iPhone"
    if "ipad" in ua:
        return "iPad"
    if "android" in ua and "mobile" in ua:
        return "Android phone"
    if "android" in ua:
        return "Android tablet / device"
    if any(token in ua for token in ("mobile", "windows phone")):
        return "Mobile browser"
    if ua:
        return "Desktop browser"
    return "Unknown"


@app.after_request
def record_page_view(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
    if request.path.startswith(("/manage-admin", ADMIN_ROOT, "/partner/", "/login", "/join")):
        response.headers["Cache-Control"] = "no-store"
    if request.method == "GET" and response.status_code < 400 and request.endpoint not in {
        "static", "manifest", "service_worker", "icon_svg", "robots_txt", "sitemap_xml", "qr_platform", "listing_qr", "promo_media"
    }:
        try:
            user = get_current_user()
            visitor_key = current_visitor_key()
            now = datetime.now(timezone.utc)
            now_text = now.replace(microsecond=0).isoformat()
            existing = get_db().execute("SELECT * FROM visitor_sessions WHERE visitor_key=?", (visitor_key,)).fetchone()
            role = "administrator" if user and user["role"] == "admin" else (
                "partner" if user and user["role"] in {"owner", "agent", "host", "business"} else
                "house seeker" if user and user["role"] == "seeker" else "visitor"
            )
            referrer = ""
            if request.referrer:
                try:
                    referrer = urlparse(request.referrer).netloc[:200]
                except Exception:
                    referrer = ""
            account_phone = normalize_visitor_phone(user["phone"] or "") if user else ""
            account_name = (user["full_name"] or "") if user else ""
            if existing:
                try:
                    last_seen_dt = datetime.fromisoformat(existing["last_seen"])
                    new_visit = (now - last_seen_dt) > timedelta(minutes=30)
                except (TypeError, ValueError):
                    new_visit = True
                visit_count = int(existing["visit_count"] or 1) + (1 if new_visit else 0)
                last_visit_at = now_text if new_visit or not existing["last_visit_at"] else existing["last_visit_at"]
                known_phone = account_phone or existing["contact_phone"] or ""
                known_name = account_name or existing["contact_name"] or ""
                # Admin page visits are not counted as public visits. Existing admin browsers are
                # still updated so they remain labelled as administration traffic.
                get_db().execute(
                    "UPDATE visitor_sessions SET user_id=?,role=?,last_seen=?,last_path=?,referrer=?,device=?,page_views=page_views+1,visit_count=?,last_visit_at=?,contact_phone=?,contact_name=? WHERE visitor_key=?",
                    (user["id"] if user else existing["user_id"], role, now_text, request.path[:500], referrer, device_label(request.headers.get("User-Agent", "")), visit_count, last_visit_at, known_phone, known_name, visitor_key),
                )
            else:
                get_db().execute(
                    "INSERT INTO visitor_sessions(visitor_key,user_id,role,first_seen,last_seen,last_path,referrer,device,page_views,visit_count,last_visit_at,contact_phone,contact_name) VALUES(?,?,?,?,?,?,?,?,1,1,?,?,?)",
                    (visitor_key, user["id"] if user else None, role, now_text, now_text, request.path[:500], referrer, device_label(request.headers.get("User-Agent", "")), now_text, account_phone, account_name),
                )
            get_db().execute(
                "INSERT INTO visitor_events(visitor_key,user_id,event_type,path,details,created_at) VALUES(?,?,?,?,?,?)",
                (visitor_key, user["id"] if user else None, "page_view", request.path[:500], role, now_text),
            )
        except Exception as exc:
            print(f"Visitor analytics not recorded: {exc}")
    # Retain an anonymous first-party visitor key for 180 days so repeat visits
    # from this browser do not inflate unique-visitor counts. Cookie is HttpOnly.
    stable_key = current_visitor_key()
    if stable_key:
        response.set_cookie(
            "pm_visitor", stable_key, max_age=180 * 24 * 60 * 60,
            httponly=True, secure=request.is_secure, samesite="Lax", path="/"
        )
    return response


def safe_video_embed_url(value: str) -> str:
    """Allow only well-formed YouTube/Vimeo videos in the campaign placement."""
    raw = safe_external_url(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    video_id = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            from urllib.parse import parse_qs
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            video_id = path_parts[1]
        if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id or ""):
            return f"https://www.youtube-nocookie.com/embed/{video_id}"
    elif host == "youtu.be" and path_parts and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", path_parts[0]):
        return f"https://www.youtube-nocookie.com/embed/{path_parts[0]}"
    elif host in {"vimeo.com", "www.vimeo.com"} and path_parts and path_parts[0].isdigit():
        return f"https://player.vimeo.com/video/{path_parts[0]}"
    elif host == "player.vimeo.com" and len(path_parts) >= 2 and path_parts[0] == "video" and path_parts[1].isdigit():
        return f"https://player.vimeo.com/video/{path_parts[1]}"
    return ""


@app.context_processor
def inject_globals():
    user = get_current_user()
    settings = all_settings()
    enabled_categories = {
        key: meta for key, meta in CATEGORY_META.items()
        if settings.get(f"category_enabled_{key}", "1") == "1"
    }
    header_resource_links = []
    if settings.get("header_links_enabled", "0") == "1":
        for raw_line in settings.get("header_links", "").splitlines()[:8]:
            if "|" not in raw_line:
                continue
            label, target = raw_line.split("|", 1)
            label, target = label.strip(), safe_external_url(target.strip())
            if label and target and not is_competitor_property_portal_url(target):
                header_resource_links.append({"label": label[:55], "url": target})
    return {
        "site_settings": settings,
        "header_resource_links": header_resource_links,
        "promo_embed_url": safe_video_embed_url(settings.get("promo_video_url", "")),
        "is_competitor_property_portal_url": is_competitor_property_portal_url,
        "current_user": user,
        "csrf_field": csrf_field,
        "listing_images": listing_images,
        "category_meta": CATEGORY_META,
        "seo_category_pages": SEO_CATEGORY_PAGES,
        "public_base": public_base,
        "public_categories": enabled_categories,
        "money": money,
        "fee_for_category": fee_for_category,
        "expiry_days_remaining": expiry_days_remaining,
        "recovery_questions": RECOVERY_QUESTIONS,
        "admin_root": ADMIN_ROOT,
        "current_year": datetime.now().year,
        "current_date": datetime.now(timezone.utc).date().isoformat(),
        "storage_warning": bool(os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER")) and DATA_DIR.resolve() == (BASE_DIR / "instance").resolve(),
        "place_selector_data": selector_data(),
        "slugify": slugify,
    }


def safe_next_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    return None


def save_upload(file, target_dir: Path, allowed: set[str]) -> str:
    if not file or not file.filename:
        return ""
    original = secure_filename(file.filename)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in allowed:
        raise ValueError(f"Unsupported file type for {original}. Allowed: {', '.join(sorted(allowed))}.")
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_FILE_BYTES:
        raise ValueError(f"{original} is too large. Each image/document must be no more than {MAX_FILE_BYTES // (1024*1024)} MB.")
    target_dir.mkdir(parents=True, exist_ok=True)
    if ext == "pdf":
        header = file.stream.read(5)
        file.stream.seek(0)
        if header != b"%PDF-":
            raise ValueError(f"{original} does not look like a valid PDF document.")
        filename = f"{uuid.uuid4().hex}.pdf"
        file.save(target_dir / filename)
        return filename
    try:
        with Image.open(file.stream) as probe:
            probe.verify()
        file.stream.seek(0)
        with Image.open(file.stream) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((1800, 1600), Image.Resampling.LANCZOS)
            filename = f"{uuid.uuid4().hex}.webp"
            image.save(target_dir / filename, format="WEBP", quality=86, method=5)
            image.close()
        file.stream.seek(0)
        return filename
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"{original} is not a valid supported image. Upload a real JPG, PNG or WebP file.") from exc


def public_listings(where: str = "", params: tuple = (), limit: int = 100):
    sql = """
        SELECT l.*,u.full_name AS partner_name,u.business_name,u.role AS partner_role,u.verified AS partner_verified,
               (SELECT ROUND(AVG(r.stars),1) FROM ratings r WHERE r.listing_id=l.id) AS rating_average,
               (SELECT COUNT(*) FROM ratings r WHERE r.listing_id=l.id) AS rating_count
        FROM listings l JOIN users u ON u.id=l.owner_id
        WHERE l.status='available' AND l.approval_status='approved' AND l.payment_status='paid'
          AND u.suspended=0
          AND ((COALESCE(l.is_sample,0)=1) OR (l.property_verified=1 AND u.verified=1))
    """
    if where:
        sql += " AND " + where
    sql += " AND l.expires_at <> '' AND l.expires_at > ?"
    sql += """ ORDER BY CASE WHEN COALESCE(l.admin_rank,0)>0 THEN 0 ELSE 1 END,
                 CASE WHEN l.featured_until > ? AND lower(l.boost_tier)='vvip' THEN 0 WHEN l.featured_until > ? AND lower(l.boost_tier)='vip' THEN 1 WHEN l.featured_until > ? THEN 2 ELSE 3 END,
                 CASE WHEN COALESCE(l.is_sample,0)=1 THEN 1 ELSE 0 END, l.posted_at DESC LIMIT ?"""
    now = now_iso()
    return get_db().execute(sql, (*params, now, now, now, now, limit)).fetchall()


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dlat, dlon = math.radians(float(lat2) - float(lat1)), math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@app.route("/")
def index():
    focus_order = ["Nairobi", "Kiambu", "Mombasa", "Nakuru", "Kisumu", "Uasin Gishu", "Kajiado", "Machakos", "Kilifi", "Kwale", "Kakamega", "Bungoma"]
    featured_counties = [{"name": name, "slug": slugify(name), "constituency_count": len(COUNTY_CONSTITUENCIES[name])}
                         for name in focus_order if name in COUNTY_CONSTITUENCIES]
    return render_template("index.html", invite_url=public_base() + "/", featured_counties=featured_counties,
                           showcase_listings=public_listings("COALESCE(l.is_sample,0)=1", (), 6))


def build_listing_location(form, existing=None):
    """Validate the owner's Kenya location hierarchy and build its public label."""
    existing = existing or {}
    def get_existing(key):
        try:
            return existing[key] or ""
        except (KeyError, IndexError, TypeError):
            return ""
    raw_county = (form.get("county") or get_existing("county") or "").strip()
    county = next((name for name in COUNTY_CONSTITUENCIES if name.casefold() == raw_county.casefold() or slugify(name) == slugify(raw_county)), "")
    raw_constituency = (form.get("constituency") or get_existing("constituency") or "").strip()
    constituency = next((name for name in COUNTY_CONSTITUENCIES.get(county, []) if name.casefold() == raw_constituency.casefold() or slugify(name) == slugify(raw_constituency)), "")
    if not county or not constituency:
        return {"county": county, "constituency": constituency, "ward": "", "local_area": "", "location_name": ""}
    known_localities = selector_data().get(county, {}).get(constituency, [])
    raw_ward = (form.get("area_select") or form.get("ward") or get_existing("ward") or "").strip()
    ward = next((name for name in known_localities if name.casefold() == raw_ward.casefold() or slugify(name) == slugify(raw_ward)), "")
    raw_local = (form.get("local_area") or get_existing("local_area") or "").strip()[:180]
    # Existing listings with no separate structured fields can keep their address
    # while a landlord completes the hierarchy on the next edit.
    if not ward and not raw_local and not (form.get("county") or form.get("constituency")):
        old_label = (form.get("location_name") or get_existing("location_name") or "").strip()[:180]
        raw_local = old_label
    most_specific = raw_local or ward or constituency
    parts = []
    for part in (most_specific, constituency, county):
        if part and part.casefold() not in [p.casefold() for p in parts]:
            parts.append(part)
    label = ", ".join(parts)[:180]
    return {"county": county, "constituency": constituency, "ward": ward, "local_area": raw_local,
            "location_name": label}


def _search_tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", (value or "").casefold()) if len(token) > 1]


def _fuzzy_search_score(query: str, searchable_text: str) -> float:
    """Return a 0..1 score, tolerating typos without broadening every empty search."""
    query_tokens = _search_tokens(query)
    if not query_tokens:
        return 0.0
    words = set(_search_tokens(searchable_text))
    if not words:
        return 0.0
    scores = []
    for token in query_tokens:
        if token in words:
            scores.append(1.0)
            continue
        if len(token) >= 3 and any((token in word or word in token) and min(len(token), len(word)) >= 3 for word in words):
            scores.append(0.88)
            continue
        if len(token) < 4:
            scores.append(0.0)
            continue
        best = max((SequenceMatcher(None, token, word).ratio() for word in words), default=0.0)
        scores.append(best if best >= 0.72 else 0.0)
    matched = sum(1 for score in scores if score > 0)
    if matched == len(scores):
        return sum(scores) / len(scores)
    # Allow one missed token in longer queries, but not a single lucky match.
    if len(scores) >= 3 and matched >= len(scores) - 1:
        return (sum(scores) / len(scores)) * 0.94
    return 0.0


def _listing_search_text(row) -> str:
    category_label = CATEGORY_META.get(row["category"], {}).get("label", "")
    return " ".join(str(row[key] or "") for key in (
        "title", "description", "location_name", "landmarks", "property_type", "amenities", "water_quality", "county", "constituency", "ward", "local_area"
    )) + " " + category_label


@app.route("/homes")
def homes():
    q = request.args.get("q", "").strip()[:120]
    category = request.args.get("category", "residential").strip() or "residential"
    property_type = request.args.get("type", "").strip()
    location = request.args.get("location", "").strip()[:120]
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    min_beds = request.args.get("bedrooms", "").strip()
    category_meta = visible_categories()
    if category not in category_meta:
        category = "residential" if "residential" in category_meta else (next(iter(category_meta), ""))
        property_type = ""
    base_clauses, base_params = [], []
    if category in category_meta:
        base_clauses.append("l.category=?"); base_params.append(category)
    else:
        active_keys = list(category_meta)
        if active_keys:
            base_clauses.append("l.category IN (" + ",".join("?" for _ in active_keys) + ")")
            base_params.extend(active_keys)
        else:
            base_clauses.append("1=0")
    if property_type:
        base_clauses.append("l.property_type=?"); base_params.append(property_type)
    if min_price:
        try:
            value = max(0, float(min_price)); base_clauses.append("l.price_amount>=?"); base_params.append(value)
        except ValueError:
            min_price = ""
    if max_price:
        try:
            value = max(0, float(max_price)); base_clauses.append("l.price_amount<=?"); base_params.append(value)
        except ValueError:
            max_price = ""
    if min_price and max_price:
        try:
            if float(min_price) > float(max_price):
                min_price, max_price = max_price, min_price
                # Rebuild the price clauses in the correct order.
                base_clauses = [c for c in base_clauses if c not in {"l.price_amount>=?", "l.price_amount<=?"}]
                base_params = [v for v in base_params if not isinstance(v, (float, int)) or True]
                base_clauses.extend(["l.price_amount>=?", "l.price_amount<=?"])
                # Preserve all non-price values by reconstructing from filters above.
                base_params = []
                if category in category_meta:
                    base_params.append(category)
                else:
                    base_params.extend(list(category_meta))
                if property_type: base_params.append(property_type)
                base_params.extend([float(min_price), float(max_price)])
        except ValueError:
            pass
    if min_beds:
        try:
            base_clauses.append("COALESCE(l.bedrooms,0)>=?"); base_params.append(int(min_beds))
        except ValueError:
            min_beds = ""
    base_where = " AND ".join(base_clauses)
    clauses, params = list(base_clauses), list(base_params)
    if q:
        clauses.append("(l.title LIKE ? OR l.description LIKE ? OR l.location_name LIKE ? OR l.landmarks LIKE ? OR l.property_type LIKE ? OR l.amenities LIKE ? OR l.water_quality LIKE ? OR l.county LIKE ? OR l.constituency LIKE ? OR l.ward LIKE ? OR l.local_area LIKE ?)")
        params.extend([f"%{q}%"] * 11)
    if location:
        clauses.append("(l.location_name LIKE ? OR l.landmarks LIKE ? OR l.county LIKE ? OR l.constituency LIKE ? OR l.ward LIKE ? OR l.local_area LIKE ?)")
        params.extend([f"%{location}%"] * 6)
    where = " AND ".join(clauses)
    results = public_listings(where, tuple(params), 300)
    fuzzy_used = False
    user_lat, user_lon = request.args.get("lat", ""), request.args.get("lon", "")
    if not results and (q or location):
        # Search within other exact filters first. This handles common typos such as
        # "Ruyaka" for "Ruaka" and "apartmant" for "apartment".
        candidates = public_listings(base_where, tuple(base_params), 600)
        search_text = " ".join(x for x in (q, location) if x)
        scored = []
        for candidate in candidates:
            score = _fuzzy_search_score(search_text, _listing_search_text(candidate))
            if score >= 0.70:
                scored.append((score, candidate))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = [row for _, row in scored[:200]]
        fuzzy_used = bool(results)
    if user_lat and user_lon:
        try:
            latf, lonf = float(user_lat), float(user_lon)
            results = sorted(results, key=lambda r: haversine_km(latf, lonf, r["latitude"], r["longitude"]) if r["latitude"] is not None and r["longitude"] is not None else 1e9)
        except (ValueError, TypeError):
            user_lat, user_lon = "", ""
    details = {
        "q": q, "category": category, "type": property_type, "location": location,
        "min_price": min_price, "max_price": max_price, "bedrooms": min_beds,
        "count": len(results), "fuzzy_used": fuzzy_used,
        "no_match": not bool(results), "sort_nearby": bool(user_lat and user_lon),
    }
    log_event("property_search", request.path, json.dumps(details))
    return render_template(
        "homes.html", listings=results, q=q, category=category, property_type=property_type,
        location=location, min_price=min_price, max_price=max_price, bedrooms=min_beds,
        types=CATEGORY_META.get(category, {}).get("types", []),
        sorted_by_distance=bool(user_lat and user_lon), fuzzy_used=fuzzy_used,
        category_meta=category_meta,
        external_searches=external_property_searches(" ".join(x for x in (q, location) if x), category),
        featured_area_cards=[
            {"name":"Nairobi","slug":"nairobi"}, {"name":"Kiambu","slug":"kiambu"},
            {"name":"Mombasa","slug":"mombasa"}, {"name":"Nakuru","slug":"nakuru"},
            {"name":"Kisumu","slug":"kisumu"}, {"name":"Uasin Gishu","slug":"uasin-gishu"}
        ],
    )


def _place_category():
    requested = request.args.get("category", "residential").strip()
    return requested if requested in visible_categories() else ("residential" if "residential" in visible_categories() else next(iter(visible_categories()), "residential"))


def external_property_searches(area: str, category: str = "residential") -> list[dict]:
    """No third-party marketplace promotion: visitors stay within this platform."""
    return []


def _place_listing_results(terms: list[str], limit: int = 300, county: str | None = None,
                           constituency: str | None = None):
    """Search a place page without leaking results from neighbouring locations."""
    terms = list(dict.fromkeys(t.strip() for t in terms if t and t.strip()))[:150]
    if not terms:
        return []
    scope_clauses, scope_params = [], []
    if county:
        scope_clauses.append("l.county=?")
        scope_params.append(county)
    if constituency:
        scope_clauses.append("l.constituency=?")
        scope_params.append(constituency)
    match_clauses, match_params = [], []
    for term in terms:
        match_clauses.append("(lower(COALESCE(l.location_name,'')) LIKE ? OR lower(COALESCE(l.landmarks,'')) LIKE ? OR lower(COALESCE(l.ward,'')) LIKE ? OR lower(COALESCE(l.local_area,'')) LIKE ?)")
        pattern = f"%{term.casefold()}%"
        match_params.extend([pattern, pattern, pattern, pattern])
    match_sql = "(" + " OR ".join(match_clauses) + ")"
    where = " AND ".join([*scope_clauses, match_sql])
    params = tuple([*scope_params, *match_params])
    try:
        return public_listings(where, params, limit)
    except Exception:
        # Retain the county/constituency scope if an older SQLite build imposes
        # a tighter bind-parameter limit than expected.
        fallback = " AND ".join([*scope_clauses,
            "(lower(COALESCE(l.location_name,'')) LIKE ? OR lower(COALESCE(l.landmarks,'')) LIKE ? OR lower(COALESCE(l.ward,'')) LIKE ? OR lower(COALESCE(l.local_area,'')) LIKE ?)"])
        pattern = f"%{terms[0].casefold()}%"
        return public_listings(fallback, tuple([*scope_params, pattern, pattern, pattern, pattern]), limit)


def published_area_cards(county: str, constituency: str | None = None) -> list[dict]:
    """Return curated local-area links plus exact locality names on live listings.

    Owner-entered locations become discoverable without requiring a code update,
    but only after the listing is genuinely public and has passed platform checks.
    """
    cards = [row.copy() for row in county_fine_areas(county)
             if not constituency or row.get("constituency") == constituency]
    seen = {row["slug"] for row in cards}
    where = "l.county=?"
    params: tuple = (county,)
    if constituency:
        where += " AND l.constituency=?"
        params = (county, constituency)
    for row in public_listings(where, params, 10000):
        name = (row["local_area"] or row["ward"] or "").strip()
        if not name:
            continue
        slug = slugify(name)
        if not slug or slug in seen:
            continue
        row_constituency = (row["constituency"] or constituency or "").strip()
        cards.append({"name": name, "slug": slug, "constituency": row_constituency})
        seen.add(slug)
    return cards


def _place_context(county: str, area: str, category: str, listings: list, related: list | None = None):
    return {
        "county": county,
        "area": area,
        "category": category,
        "listings": listings,
        "other_sites": external_property_searches(f"{area}, {county}", category),
        "maps_url": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{area}, {county}, Kenya"),
        "related_places": related or [],
    }


@app.route("/places")
def places_index():
    counties = [{"name": name, "slug": slugify(name), "constituency_count": len(constituencies),
                 "summary": COUNTY_SUMMARIES.get(name, f"Browse homes, land and commercial property by constituency and local area across {name} County."),
                 "search_terms": " ".join([name, *constituencies, *all_known_localities(name)]),
                 "counties": None}
                for name, constituencies in sorted(COUNTY_CONSTITUENCIES.items())]
    focus_order = ["Nairobi", "Kiambu", "Kajiado", "Machakos", "Nakuru", "Mombasa", "Murang'a", "Kisumu", "Kilifi", "Nyeri", "Uasin Gishu", "Laikipia"]
    counties.sort(key=lambda row: (focus_order.index(row["name"]) if row["name"] in focus_order else 99, row["name"]))
    return render_template("places_index.html", counties=counties)


@app.route("/places/<county_slug>")
def county_page(county_slug: str):
    county = county_by_slug(county_slug)
    if not county:
        abort(404)
    category = _place_category()
    constituency_names = COUNTY_CONSTITUENCIES[county]
    wards = ward_map(county)
    areas = published_area_cards(county)
    terms = [county, *constituency_names, *[a["name"] for a in areas]]
    listings = _place_listing_results(terms, county=county)
    summary = COUNTY_SUMMARIES.get(county, f"Browse property opportunities throughout {county} County. Use the constituency directory and local-area links to narrow your search. Owners can publish an exact neighbourhood, ward, landmark and property photos.")
    constituency_cards = [{"name": con, "slug": slugify(con), "wards": wards.get(con, [])}
                          for con in constituency_names]
    return render_template("place_page.html", page_kind="county", county=county,
        area=county, summary=summary, category=category, listings=listings,
        constituency_cards=constituency_cards, area_cards=areas,
        other_sites=external_property_searches(county, category),
        maps_url="https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{county} County, Kenya"),
        canonical_url=public_base() + request.path)


@app.route("/places/<county_slug>/<constituency_slug>")
def constituency_page(county_slug: str, constituency_slug: str):
    county = county_by_slug(county_slug)
    constituency = constituency_by_slug(county, constituency_slug) if county else None
    if not county or not constituency:
        abort(404)
    category = _place_category()
    wards = ward_map(county).get(constituency, [])
    area_cards = published_area_cards(county, constituency)
    area_names = [item["name"] for item in area_cards]
    terms = [constituency, *wards, *area_names]
    listings = _place_listing_results(terms, county=county, constituency=constituency)
    summary = (f"Browse property in {constituency}, {county} County. Narrow the search by ward or neighbourhood and explore locally published listings."
               if county not in COUNTY_SUMMARIES else f"Explore {constituency} in {county} County with a more exact search by ward, estate, road or neighbourhood. The directory below helps owners and visitors move beyond a broad county search.")
    # Show other local constituencies nearby as easy navigation instead of a dead end.
    all_cons = COUNTY_CONSTITUENCIES[county]
    at = all_cons.index(constituency)
    nearby = [{"name": name, "slug": slugify(name)} for name in all_cons[max(0, at-2):at] + all_cons[at+1:at+3]]
    return render_template("place_page.html", page_kind="constituency", county=county,
        area=constituency, summary=summary, category=category, listings=listings,
        constituency=constituency, wards=wards, area_cards=area_cards,
        nearby_constituencies=nearby,
        other_sites=external_property_searches(f"{constituency}, {county}", category),
        maps_url="https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{constituency}, {county}, Kenya"),
        canonical_url=public_base() + request.path)


@app.route("/places/<county_slug>/<constituency_slug>/ward/<ward_slug>")
def ward_page(county_slug: str, constituency_slug: str, ward_slug: str):
    county = county_by_slug(county_slug)
    constituency = constituency_by_slug(county, constituency_slug) if county else None
    if not county or not constituency:
        abort(404)
    ward = next((name for name in ward_map(county).get(constituency, []) if slugify(name) == slugify(ward_slug)), None)
    if not ward:
        abort(404)
    category = _place_category()
    listings = _place_listing_results([ward], county=county, constituency=constituency)
    context = _place_context(county, ward, category, listings)
    return render_template("place_page.html", page_kind="locality", **context,
        summary=f"Find property listings associated with {ward}, within {constituency}, {county} County. Search by an exact estate, nearby road or landmark, or expand to the wider constituency.",
        constituency=constituency, parent_slug=slugify(constituency),
        area_cards=[], wards=[], nearby_constituencies=[], canonical_url=public_base() + request.path)


@app.route("/places/<county_slug>/area/<area_slug>")
def place_area_page(county_slug: str, area_slug: str):
    county = county_by_slug(county_slug)
    if not county:
        abort(404)
    row = next((area for area in published_area_cards(county) if area["slug"] == slugify(area_slug)), None)
    if not row:
        abort(404)
    category = _place_category()
    constituency = row["constituency"]
    related = [{"name": item["name"], "slug": item["slug"], "constituency": item["constituency"]}
               for item in published_area_cards(county, constituency) if item["slug"] != row["slug"]][:18]
    listings = _place_listing_results([row["name"]], county=county, constituency=constituency)
    context = _place_context(county, row["name"], category, listings, related)
    return render_template("place_page.html", page_kind="locality", **context,
        summary=f"Explore homes, stays, commercial spaces and property search links for {row['name']} in {constituency}, {county} County. Use the location name together with your budget and property type to narrow the result.",
        constituency=constituency, parent_slug=slugify(constituency), area_cards=[], wards=[],
        nearby_constituencies=[], canonical_url=public_base() + request.path)

@app.route("/property-search/<category_slug>")
@app.route("/property-search/<category_slug>/<county_slug>")
@app.route("/property-search/<category_slug>/<county_slug>/<constituency_slug>")
@app.route("/property-search/<category_slug>/<county_slug>/<constituency_slug>/<area_slug>")
def property_search_page(category_slug: str, county_slug: str | None = None, constituency_slug: str | None = None, area_slug: str | None = None):
    page = SEO_CATEGORY_PAGES.get(category_slug)
    if not page:
        abort(404)
    category = page["category"]
    if category not in visible_categories():
        abort(404)
    county = county_by_slug(county_slug) if county_slug else None
    if county_slug and not county:
        abort(404)
    constituency = constituency_by_slug(county, constituency_slug) if county and constituency_slug else None
    if constituency_slug and not constituency:
        abort(404)
    area_name = None
    if area_slug:
        if not county or not constituency:
            abort(404)
        area_card = next((item for item in published_area_cards(county, constituency) if item["slug"] == slugify(area_slug)), None)
        if area_card:
            area_name = area_card["name"]
        else:
            area_name = next((ward for ward in ward_map(county).get(constituency, []) if slugify(ward) == slugify(area_slug)), None)
        if not area_name:
            abort(404)
    clauses, params = ["l.category=?"], [category]
    if county:
        clauses.append("l.county=?"); params.append(county)
    if constituency:
        clauses.append("l.constituency=?"); params.append(constituency)
    if area_name:
        clauses.append("(lower(COALESCE(l.local_area,''))=lower(?) OR lower(COALESCE(l.ward,''))=lower(?) OR lower(COALESCE(l.location_name,'')) LIKE ? OR lower(COALESCE(l.landmarks,'')) LIKE ?)")
        area_pattern = f"%{area_name.casefold()}%"
        params.extend([area_name, area_name, area_pattern, area_pattern])
    listings = public_listings(" AND ".join(clauses), tuple(params), 300)
    place_name = area_name or constituency or county or "Kenya"
    if area_name:
        place_suffix = f" in {area_name}, {constituency}, {county} County, Kenya"
    elif constituency:
        place_suffix = f" in {constituency}, {county} County, Kenya"
    elif county:
        place_suffix = f" in {county} County, Kenya"
    else:
        place_suffix = " across Kenya"
    seo_title = f"{page['label']}{place_suffix} | PataMahali"
    if len(seo_title) > 68:
        seo_title = f"{page['short']} in {place_name} | PataMahali"
    description = f"{page['description']}"
    if area_name:
        description = f"{page['label']} in {area_name}, {constituency}, {county} County, Kenya. {page['description']} Browse active property adverts for this exact ward or neighbourhood and compare the details supplied by each advertiser."
    elif constituency:
        description = f"{page['label']} in {constituency}, {county} County, Kenya. {page['description']} Browse live listings where available, explore nearby wards, and list a property in this exact area."
    elif county:
        description = f"{page['label']} in {county} County, Kenya. {page['description']} Explore the county's constituencies and local areas, then open any live listings published here."
    nearby_areas = [item for item in published_area_cards(county, constituency) if not area_name or item["slug"] != slugify(area_name)][:60] if county else []
    wards = ward_map(county).get(constituency, []) if county and constituency else []
    constituency_cards = []
    if county and not constituency:
        constituency_cards = [{"name": name, "slug": slugify(name)} for name in COUNTY_CONSTITUENCIES.get(county, [])]
    enabled = visible_categories()
    category_links = [{"slug": slug, "label": item["label"], "count": item["category"]} for slug, item in SEO_CATEGORY_PAGES.items() if slug != category_slug and item["category"] in enabled]
    canonical_url = public_base() + request.path
    # Don't index empty, nearly-identical category/location combinations. The main
    # county and constituency directory pages remain indexable and discoverable.
    allow_index = (county is None) or bool(listings)
    return render_template("property_search_page.html", page=page, category=category, county=county,
        constituency=constituency, area_name=area_name, place_name=place_name, listings=listings, seo_title=seo_title,
        description=description, canonical_url=canonical_url, allow_index=allow_index,
        nearby_areas=nearby_areas, wards=wards, constituency_cards=constituency_cards,
        category_links=category_links, counties=sorted(COUNTY_CONSTITUENCIES.keys()))


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id: int):
    row = get_db().execute("SELECT l.*,u.full_name AS partner_name,u.business_name,u.role AS partner_role,u.phone AS partner_phone,u.email AS partner_email,u.contact_preference AS contact_preference,u.website_url AS website_url,u.social_url AS social_url,u.verified AS partner_verified FROM listings l JOIN users u ON l.owner_id=u.id WHERE l.id=?", (listing_id,)).fetchone()
    if not row or not is_public_listing(row):
        abort(404)
    get_db().execute("UPDATE listings SET views=views+1 WHERE id=?", (listing_id,))
    log_event("listing_view", request.path, json.dumps({"listing_id": listing_id, "category": row["category"]}))
    try:
        posted = datetime.fromisoformat(row["posted_at"])
        posted_display = posted.strftime("%d %b %Y")
    except (ValueError, TypeError):
        posted_display = row["posted_at"][:10]
    rating_summary = get_db().execute("SELECT ROUND(AVG(stars),1) AS average,COUNT(*) AS count FROM ratings WHERE listing_id=?", (listing_id,)).fetchone()
    my_rating = None
    viewer = get_current_user()
    if viewer and viewer["role"] == "seeker":
        my_rating = get_db().execute("SELECT stars,review FROM ratings WHERE listing_id=? AND reviewer_id=?", (listing_id, viewer["id"])).fetchone()
    return render_template("listing_detail.html", listing=row, images=listing_images(row), category=CATEGORY_META.get(row["category"], CATEGORY_META["residential"]), posted_display=posted_display, rating_summary=rating_summary, my_rating=my_rating)


@app.post("/listing/<int:listing_id>/rate")
@login_required
def rate_listing(listing_id: int):
    user = get_current_user()
    if not user or user["role"] != "seeker":
        flash("Property ratings are available to signed-in house seekers.", "warning")
        return redirect(url_for("listing_detail", listing_id=listing_id) + "#ratings")
    row = get_db().execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or not is_public_listing(row): abort(404)
    if row["owner_id"] == user["id"]:
        flash("You cannot rate your own property.", "warning")
        return redirect(url_for("listing_detail", listing_id=listing_id) + "#ratings")
    try:
        stars = int(request.form.get("stars", "5"))
        if stars < 1 or stars > 5: raise ValueError()
    except ValueError:
        flash("Choose a rating from 1 to 5 stars.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id) + "#ratings")
    review = request.form.get("review", "").strip()[:1200]
    get_db().execute("INSERT INTO ratings(listing_id,reviewer_id,stars,review,created_at) VALUES(?,?,?,?,?) ON CONFLICT(listing_id,reviewer_id) DO UPDATE SET stars=excluded.stars,review=excluded.review,created_at=excluded.created_at", (listing_id, user["id"], stars, review, now_iso()))
    audit("property_rating_saved", "listing", listing_id, f"Stars={stars}")
    flash("Your rating has been saved.", "success")
    return redirect(url_for("listing_detail", listing_id=listing_id) + "#ratings")


@app.post("/listing/<int:listing_id>/interest")
def express_interest(listing_id: int):
    row = get_db().execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or not is_public_listing(row):
        abort(404)
    name = request.form.get("full_name", "").strip()[:120]
    phone = request.form.get("phone", "").strip()[:40]
    email = request.form.get("email", "").strip()[:160]
    message = request.form.get("message", "").strip()[:2000]
    if not name or not phone:
        flash("Please add your name and phone number so the property partner can reply.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id) + "#interest")
    user = get_current_user()
    cur = get_db().execute("INSERT INTO interests(listing_id,seeker_id,full_name,phone,email,message,created_at) VALUES(?,?,?,?,?,?,?)", (listing_id, user["id"] if user and user["role"] == "seeker" else None, name, phone, email, message, now_iso()))
    # Link the voluntary enquiry contact to this browser, reducing repeat counts when
    # the same person returns on another visit/device using the same supplied number.
    visitor_key = current_visitor_key()
    normalized_phone = normalize_visitor_phone(phone)
    stamp = now_iso()
    tracked = get_db().execute("SELECT visitor_key FROM visitor_sessions WHERE visitor_key=?", (visitor_key,)).fetchone()
    if tracked:
        get_db().execute("UPDATE visitor_sessions SET user_id=COALESCE(?,user_id),role='house seeker',contact_name=?,contact_phone=?,last_seen=?,last_path=? WHERE visitor_key=?", (user["id"] if user and user["role"] == "seeker" else None, name, normalized_phone, stamp, request.path[:500], visitor_key))
    else:
        get_db().execute("INSERT INTO visitor_sessions(visitor_key,user_id,role,first_seen,last_seen,last_path,device,page_views,visit_count,last_visit_at,contact_name,contact_phone) VALUES(?,?,?,?,?,?,?,0,1,?,?,?)", (visitor_key, user["id"] if user and user["role"] == "seeker" else None, "house seeker", stamp, stamp, request.path[:500], device_label(request.headers.get("User-Agent", "")), stamp, name, normalized_phone))
    log_event("interest_submitted", request.path, json.dumps({"listing_id": listing_id, "interest_id": cur.lastrowid}))
    audit("interest_submitted", "listing", listing_id, f"Enquiry submitted by {name}")
    flash("Your interest has been sent. The property partner can now contact you to confirm availability and viewing details.", "success")
    return redirect(url_for("listing_detail", listing_id=listing_id) + "#interest")


@app.post("/listing/<int:listing_id>/report-taken")
def report_taken(listing_id: int):
    row = get_db().execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or not is_public_listing(row):
        abort(404)
    reason = request.form.get("reason", "").strip()[:800] or "Reported as no longer available"
    user = get_current_user()
    name = (user["full_name"] if user else request.form.get("reporter_name", "Visitor").strip()[:120])
    get_db().execute("INSERT INTO reports(listing_id,reporter_id,reporter_name,reason,created_at) VALUES(?,?,?,?,?)", (listing_id, user["id"] if user else None, name, reason, now_iso()))
    get_db().execute("UPDATE listings SET status='reported_taken',updated_at=? WHERE id=?", (now_iso(), listing_id))
    log_event("listing_reported_taken", request.path, json.dumps({"listing_id": listing_id}))
    audit("listing_reported_taken", "listing", listing_id, reason)
    flash("Thank you. The listing has been hidden while the report is reviewed by an administrator.", "success")
    return redirect(url_for("homes"))


@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")


@app.route("/terms")
def terms_of_use():
    return render_template("terms.html")


@app.route("/partners")
def partners_directory():
    rows = get_db().execute("SELECT u.id,u.full_name,u.business_name,u.role,u.created_at,COUNT(l.id) AS listing_count FROM users u LEFT JOIN listings l ON l.owner_id=u.id AND l.status='available' AND l.approval_status='approved' AND l.payment_status='paid' AND l.property_verified=1 WHERE u.role IN ('owner','agent','host','business') AND u.verified=1 AND u.suspended=0 GROUP BY u.id ORDER BY listing_count DESC,u.full_name").fetchall()
    return render_template("partners.html", partners=rows)


@app.route("/partner/register", methods=["GET", "POST"])
def partner_register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()[:120]
        business_name = request.form.get("business_name", "").strip()[:160]
        role = request.form.get("role", "owner").strip()
        email = request.form.get("email", "").strip().lower()[:160] or None
        phone = request.form.get("phone", "").strip()[:40]
        contact_preference = request.form.get("contact_preference", "whatsapp").strip()
        website_url = safe_external_url(request.form.get("website_url", "").strip())[:300]
        social_url = safe_external_url(request.form.get("social_url", "").strip())[:300]
        if is_competitor_property_portal_url(website_url) or is_competitor_property_portal_url(social_url):
            flash("Please use your own website or social profile, not a competing property marketplace.", "error")
            return render_template("partner_register.html", form=request.form)
        password = request.form.get("password", "")
        recovery_question = request.form.get("recovery_question", "").strip()
        recovery_answer = normalized_recovery_answer(request.form.get("recovery_answer", ""))
        # Identity-card uploads are optional and are not required to create a partner account.
        identity_type = "none"
        if contact_preference not in {"whatsapp", "call", "email", "website"}: contact_preference = "whatsapp"
        front = ""
        back = ""
        if role not in {"owner", "agent", "host", "business"}:
            role = "owner"
        if not full_name or not phone or not password or len(password) < 10:
            flash("Add your name and phone, and use a password of at least 10 characters.", "error")
            return render_template("partner_register.html", form=request.form)
        if recovery_question not in RECOVERY_QUESTIONS or len(recovery_answer) < 3:
            flash("Choose a private account-recovery question and enter an answer you can remember. The answer is stored as a password hash.", "error")
            return render_template("partner_register.html", form=request.form)
        # New accounts remain unverified until an administrator reviews contact and property evidence.
        try:
            cur = get_db().execute("INSERT INTO users(role,account_type,full_name,business_name,email,phone,contact_preference,website_url,social_url,password_hash,identity_type,identity_front,identity_back,created_at,recovery_question,recovery_answer_hash,recovery_updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (role, role, full_name, business_name, email, phone, contact_preference, website_url, social_url, generate_password_hash(password), identity_type, front, back, now_iso(), recovery_question, generate_password_hash(recovery_answer), now_iso()))
        except sqlite3.IntegrityError:
            flash("That email address is already registered. Please sign in instead or use another email.", "error")
            return render_template("partner_register.html", form=request.form)
        session.clear()
        session["user_id"] = cur.lastrowid
        session["csrf_token"] = secrets.token_urlsafe(24)
        session["visitor_key"] = secrets.token_urlsafe(20)
        refresh_current_user_cache()
        audit("partner_registered", "user", cur.lastrowid, f"Partner role={role}")
        flash("Partner application received. Your identity check is pending. You can submit listings and payment references, but nothing publishes until the required checks pass.", "success")
        return redirect(url_for("partner_dashboard"))
    return render_template("partner_register.html", form={})


@app.route("/partner/login", methods=["GET", "POST"])
def partner_login():
    if request.method == "POST":
        if auth_is_limited("partner"):
            flash("Too many unsuccessful sign-in attempts. Try again in 15 minutes.", "error")
            return render_template("partner_login.html"), 429
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE (lower(email)=? OR phone=?) AND role IN ('owner','agent','host','business')", (identity, identity)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            auth_failed("partner")
            flash("Those sign-in details did not match a partner account.", "error")
        elif user["suspended"]:
            flash("This partner account is temporarily suspended. Please contact support.", "error")
        else:
            auth_succeeded("partner")
            session.clear(); session["user_id"] = user["id"]; session["csrf_token"] = secrets.token_urlsafe(24); session["visitor_key"] = secrets.token_urlsafe(20)
            refresh_current_user_cache()
            get_db().execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), user["id"]))
            audit("partner_login", "user", user["id"])
            return redirect(safe_next_url(request.args.get("next")) or url_for("partner_dashboard"))
    return render_template("partner_login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if auth_is_limited("seeker"):
            flash("Too many unsuccessful sign-in attempts. Try again in 15 minutes.", "error")
            return render_template("login.html"), 429
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE (lower(email)=? OR phone=?) AND role='seeker'", (identity, identity)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            auth_failed("seeker")
            flash("Those sign-in details did not match a house-seeker account.", "error")
        elif user["suspended"]:
            flash("This account is temporarily suspended.", "error")
        else:
            auth_succeeded("seeker")
            session.clear(); session["user_id"] = user["id"]; session["csrf_token"] = secrets.token_urlsafe(24); session["visitor_key"] = secrets.token_urlsafe(20)
            refresh_current_user_cache()
            get_db().execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), user["id"]))
            audit("seeker_login", "user", user["id"])
            return redirect(safe_next_url(request.args.get("next")) or url_for("index"))
    return render_template("login.html")


@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()[:120]
        phone = request.form.get("phone", "").strip()[:40]
        email = request.form.get("email", "").strip().lower()[:160] or None
        password = request.form.get("password", "")
        if not name or not phone or len(password) < 10:
            flash("Add your name and phone number, and use a password of at least 10 characters.", "error")
        else:
            try:
                cur = get_db().execute("INSERT INTO users(role,account_type,full_name,email,phone,password_hash,created_at) VALUES('seeker','seeker',?,?,?,?,?)", (name, email, phone, generate_password_hash(password), now_iso()))
                session.clear(); session["user_id"] = cur.lastrowid; session["csrf_token"] = secrets.token_urlsafe(24); session["visitor_key"] = secrets.token_urlsafe(20)
                refresh_current_user_cache()
                audit("seeker_registered", "user", cur.lastrowid)
                flash("Your house-seeker account is ready.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("That email address is already registered. Please sign in.", "error")
    return render_template("join.html")


@app.post("/logout")
@login_required
def logout():
    user = get_current_user()
    audit("logout", "user", user["id"] if user else "")
    session.clear()
    return redirect(url_for("index"))


@app.post("/partner/profile")
@partner_required
def partner_profile_update():
    user = get_current_user()
    phone = request.form.get("phone", "").strip()[:40]
    email = request.form.get("email", "").strip().lower()[:160] or None
    preference = request.form.get("contact_preference", "whatsapp").strip()
    website = safe_external_url(request.form.get("website_url", "").strip())[:300]
    social = safe_external_url(request.form.get("social_url", "").strip())[:300]
    if is_competitor_property_portal_url(website) or is_competitor_property_portal_url(social):
        flash("Please use your own website or social profile, not a competing property marketplace.", "error")
        return redirect(url_for("partner_dashboard") + "#contact-profile")
    if preference not in {"whatsapp", "call", "email", "website"}: preference = "whatsapp"
    if not phone:
        flash("Add a phone number so people can contact you.", "error")
        return redirect(url_for("partner_dashboard") + "#contact-profile")
    if request.form.get("website_url", "").strip() and not website:
        flash("Website URL must be a valid HTTP or HTTPS link.", "error")
        return redirect(url_for("partner_dashboard") + "#contact-profile")
    if request.form.get("social_url", "").strip() and not social:
        flash("Social profile URL must be a valid HTTP or HTTPS link.", "error")
        return redirect(url_for("partner_dashboard") + "#contact-profile")
    try:
        get_db().execute("UPDATE users SET phone=?,email=?,contact_preference=?,website_url=?,social_url=? WHERE id=?", (phone,email,preference,website,social,user["id"]))
    except sqlite3.IntegrityError:
        flash("That email is already associated with another account.", "error")
        return redirect(url_for("partner_dashboard") + "#contact-profile")
    audit("partner_contact_profile_updated", "user", user["id"])
    flash("Your public contact options have been updated.", "success")
    return redirect(url_for("partner_dashboard") + "#contact-profile")


@app.route("/partner/dashboard")
@partner_required
def partner_dashboard():
    user = get_current_user()
    listing_rows = get_db().execute("SELECT * FROM listings WHERE owner_id=? ORDER BY posted_at DESC", (user["id"],)).fetchall()
    listings = [dict(row) for row in listing_rows]
    interests = get_db().execute("SELECT i.*,l.title AS listing_title,l.owner_id FROM interests i JOIN listings l ON l.id=i.listing_id WHERE l.owner_id=? ORDER BY i.created_at DESC LIMIT 30", (user["id"],)).fetchall()
    stats = {
        "listings": len(listings),
        "published": sum(1 for x in listings if x["status"] == "available" and x["approval_status"] == "approved" and x["payment_status"] == "paid" and x["property_verified"]),
        "enquiries": get_db().execute("SELECT COUNT(*) FROM interests i JOIN listings l ON i.listing_id=l.id WHERE l.owner_id=?", (user["id"],)).fetchone()[0],
    }
    return render_template("partner_dashboard.html", listings=listings, interests=interests, stats=stats)


@app.route("/partner/listings/<int:listing_id>/renew", methods=["GET", "POST"])
@partner_required
def partner_renew_listing(listing_id):
    user = get_current_user()
    listing = get_db().execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not listing:
        abort(404)
    if listing["status"] not in {"available", "expired", "archived"} or not (listing["approval_status"] == "approved" and listing["property_verified"] and listing["payment_status"] == "paid"):
        flash("Only a previously approved and paid listing that has not been marked taken, rejected or withdrawn can be renewed.", "warning")
        return redirect(url_for("partner_dashboard"))
    if request.method == "POST":
        reference = request.form.get("payment_reference", "").strip()[:120]
        if not reference:
            flash("Enter the new M-Pesa/payment reference after paying the same fee shown below.", "error")
        elif listing["renewal_payment_status"] == "submitted":
            flash("A renewal payment is already awaiting administrator review for this property.", "warning")
        else:
            get_db().execute("UPDATE listings SET renewal_payment_status='submitted',renewal_payment_reference=?,renewal_submitted_at=?,updated_at=? WHERE id=? AND owner_id=?", (reference, now_iso(), now_iso(), listing_id, user["id"]))
            audit("listing_renewal_payment_submitted", "listing", listing_id, f"Fee={float(listing['fee_amount'] or fee_for_category(listing['category']))}; reference supplied")
            flash("Renewal payment submitted. The listing stays hidden after its expiry until an administrator confirms the payment.", "success")
            return redirect(url_for("partner_dashboard"))
    return render_template("partner_renew_listing.html", listing=listing,
        renewal_fee=float(listing["fee_amount"] or fee_for_category(listing["category"])),
        payment_method=setting("payment_method", "M-Pesa"), payment_paybill=setting("payment_paybill", ""),
        payment_account=setting("payment_account", ""), payment_phone=setting("payment_phone", ""),
        payment_instructions=setting("payment_instructions", DEFAULT_SETTINGS["payment_instructions"]),
        expiry_days=listing_lifecycle_days())


@app.route("/partner/listings/<int:listing_id>/boost", methods=["GET", "POST"])
@partner_required
def partner_boost(listing_id):
    user = get_current_user()
    listing = get_db().execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not listing:
        abort(404)
    requests_for_listing = get_db().execute("SELECT * FROM boost_requests WHERE listing_id=? AND owner_id=? ORDER BY created_at DESC", (listing_id, user["id"])).fetchall()
    if request.method == "POST":
        tier = (request.form.get("tier") or "").strip().lower()
        if tier not in {"vip", "vvip"}:
            flash("Choose either VIP or VVIP visibility.", "error")
            return redirect(url_for("partner_boost", listing_id=listing_id))
        if not (listing["status"] == "available" and listing["approval_status"] == "approved" and listing["payment_status"] == "paid" and listing["property_verified"]):
            flash("Boost requests open once this property is live and approved. Finish the normal listing checks first.", "warning")
            return redirect(url_for("partner_boost", listing_id=listing_id))
        pending = get_db().execute("SELECT id FROM boost_requests WHERE listing_id=? AND status='pending' LIMIT 1", (listing_id,)).fetchone()
        if pending:
            flash("A boost payment is already waiting for admin review for this property.", "warning")
            return redirect(url_for("partner_boost", listing_id=listing_id))
        payment_reference = request.form.get("payment_reference", "").strip()[:120]
        if not payment_reference:
            flash("Enter the payment transaction/reference code. A real boost is applied only after an administrator reconciles it.", "error")
            return redirect(url_for("partner_boost", listing_id=listing_id))
        fee_key = "boost_fee_vvip" if tier == "vvip" else "boost_fee_vip"
        try:
            fee_amount = max(0, float(setting(fee_key, DEFAULT_SETTINGS[fee_key])))
        except (ValueError, TypeError):
            fee_amount = float(DEFAULT_SETTINGS[fee_key])
        timestamp = now_iso()
        get_db().execute("INSERT INTO boost_requests(listing_id,owner_id,tier,fee_amount,payment_reference,status,created_at,updated_at) VALUES(?,?,?,?,?,'pending',?,?)",
            (listing_id, user["id"], tier, fee_amount, payment_reference, timestamp, timestamp))
        audit("boost_payment_submitted", "listing", listing_id, f"Tier={tier}; fee={fee_amount}; reference supplied")
        flash("Boost request submitted. It will be applied after the admin confirms payment and reviews the request.", "success")
        return redirect(url_for("partner_boost", listing_id=listing_id))
    return render_template("partner_boost.html", listing=listing, boost_requests=requests_for_listing,
        vip_fee=setting("boost_fee_vip", DEFAULT_SETTINGS["boost_fee_vip"]),
        vvip_fee=setting("boost_fee_vvip", DEFAULT_SETTINGS["boost_fee_vvip"]),
        vip_days=setting("boost_duration_days_vip", DEFAULT_SETTINGS["boost_duration_days_vip"]),
        vvip_days=setting("boost_duration_days_vvip", DEFAULT_SETTINGS["boost_duration_days_vvip"]))


@app.route("/partner/recover", methods=["GET", "POST"])
def partner_recover():
    account = None
    stage = "lookup"
    identity = ""
    if request.method == "POST":
        if auth_is_limited("recovery"):
            flash("Too many recovery attempts. Please try again in 15 minutes.", "error")
            return render_template("partner_recover.html", stage="lookup", identity=""), 429
        stage = request.form.get("stage", "lookup")
        if stage == "lookup":
            identity = request.form.get("identity", "").strip().lower()[:160]
            account = get_db().execute("SELECT id,recovery_question,recovery_answer_hash FROM users WHERE (lower(email)=? OR phone=?) AND role IN ('owner','agent','host','business')", (identity, identity)).fetchone()
            if account and account["recovery_question"] and account["recovery_answer_hash"]:
                return render_template("partner_recover.html", stage="reset", identity=identity, account_id=account["id"], recovery_question=account["recovery_question"])
            auth_failed("recovery")
            flash("We could not verify an owner account with recovery details. Try the account's registered email or phone, or contact support.", "error")
            return render_template("partner_recover.html", stage="lookup", identity=identity)
        try:
            account_id = int(request.form.get("account_id", "0"))
        except ValueError:
            account_id = 0
        account = get_db().execute("SELECT * FROM users WHERE id=? AND role IN ('owner','agent','host','business')", (account_id,)).fetchone()
        answer = normalized_recovery_answer(request.form.get("recovery_answer", ""))
        new_password = request.form.get("new_password", "")
        if not account or not account["recovery_answer_hash"] or not check_password_hash(account["recovery_answer_hash"], answer):
            auth_failed("recovery")
            flash("The recovery answer did not match. Please try again.", "error")
            if account:
                return render_template("partner_recover.html", stage="reset", identity=account["email"] or account["phone"], account_id=account["id"], recovery_question=account["recovery_question"]), 401
            return render_template("partner_recover.html", stage="lookup", identity=""), 401
        if len(new_password) < 10:
            flash("Use a new password with at least 10 characters.", "error")
            return render_template("partner_recover.html", stage="reset", identity=account["email"] or account["phone"], account_id=account["id"], recovery_question=account["recovery_question"]), 400
        get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), account["id"]))
        auth_succeeded("recovery")
        audit("partner_password_recovered", "user", account["id"], "Password reset using configured recovery answer")
        flash("Password updated. You can now sign in to your existing PataMahali account.", "success")
        return redirect(url_for("partner_login"))
    return render_template("partner_recover.html", stage=stage, identity=identity)


@app.post("/partner/recovery-settings")
@partner_required
def partner_recovery_settings():
    user = get_current_user()
    question = request.form.get("recovery_question", "").strip()
    answer = normalized_recovery_answer(request.form.get("recovery_answer", ""))
    current_password = request.form.get("current_password", "")
    stored = get_db().execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if question not in RECOVERY_QUESTIONS or len(answer) < 3:
        flash("Choose a question and provide an answer of at least 3 characters.", "error")
    elif not stored or not check_password_hash(stored["password_hash"], current_password):
        flash("Enter your current password to protect recovery settings.", "error")
    else:
        get_db().execute("UPDATE users SET recovery_question=?,recovery_answer_hash=?,recovery_updated_at=? WHERE id=?", (question, generate_password_hash(answer), now_iso(), user["id"]))
        audit("partner_recovery_settings_updated", "user", user["id"])
        flash("Account recovery details saved. Your answer is stored as a password hash, not as readable text.", "success")
    return redirect(url_for("partner_dashboard") + "#account-recovery")


@app.route("/partner/management")
@partner_required
def partner_management():
    target = safe_external_url(setting("management_url", ""))
    if target:
        return redirect(target, code=302)
    return render_template("management_not_connected.html")


@app.route("/partner/listings/new", methods=["GET", "POST"])
@partner_required
def partner_new_listing():
    user = get_current_user()
    if request.method == "POST":
        category = request.form.get("category", "residential")
        if category not in CATEGORY_META:
            category = "residential"
        property_type = request.form.get("property_type", "").strip()[:120]
        title = request.form.get("title", "").strip()[:180]
        description = request.form.get("description", "").strip()[:5000]
        location = build_listing_location(request.form)
        location_name = location["location_name"]
        external_url = safe_external_url(request.form.get("external_url", ""))
        if is_competitor_property_portal_url(external_url):
            flash("Links to competing property marketplaces are not published here. Add your own website or booking page, or leave this optional field blank.", "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        landmarks = request.form.get("landmarks", "").strip()[:1200]
        price_period = request.form.get("price_period", "per month").strip()
        property_condition = request.form.get("property_condition", "").strip()[:120]
        if price_period not in PRICE_PERIODS:
            price_period = "per month"
        try:
            price_amount = float(request.form.get("price_amount", "0") or 0)
            deposit_amount = float(request.form.get("deposit_amount", "") or 0)
            bedrooms = int(request.form.get("bedrooms", "") or 0) or None
            bathrooms = int(request.form.get("bathrooms", "") or 0) or None
        except ValueError:
            flash("Check that rent, deposit and bedroom fields contain valid numbers.", "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        floor_area = request.form.get("floor_area", "").strip()[:80]
        amenities = request.form.get("amenities", "").strip()[:1200]
        water_quality = request.form.get("water_quality", "").strip()[:180]
        try:
            latitude = float(request.form.get("latitude", "").strip()) if request.form.get("latitude", "").strip() else None
            longitude = float(request.form.get("longitude", "").strip()) if request.form.get("longitude", "").strip() else None
            if latitude is not None and not -90 <= latitude <= 90: raise ValueError()
            if longitude is not None and not -180 <= longitude <= 180: raise ValueError()
        except ValueError:
            flash("Map coordinates are not valid. Use the map pin or leave coordinates blank for now.", "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        if not title or not property_type or not location_name or not location["county"] or not location["constituency"] or not (location["ward"] or location["local_area"]) or price_amount < 0:
            flash("Please complete property name, type, price, county, constituency and a ward/neighbourhood or exact local area.", "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        if latitude is None or longitude is None:
            flash("Add the property's map coordinates to help house seekers reach the real location. You can save this listing, but it cannot be approved until its location is checked.", "info")
        image_names = []
        try:
            for file in request.files.getlist("images")[:8]:
                if file and file.filename:
                    image_names.append(save_upload(file, LISTING_UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS))
        except ValueError as exc:
            for name in image_names: (LISTING_UPLOAD_DIR / name).unlink(missing_ok=True)
            flash(str(exc), "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        if not image_names:
            flash("Upload at least one genuine property photo so the review team can assess the listing.", "error")
            return render_template("listing_form.html", form=request.form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())
        fee = fee_for_category(category)
        payment_reference = request.form.get("payment_reference", "").strip()[:120]
        payment_status = "submitted" if payment_reference else "pending"
        cur = get_db().execute("""INSERT INTO listings(owner_id,category,property_type,title,description,price_amount,price_period,deposit_amount,bedrooms,bathrooms,floor_area,amenities,water_quality,location_name,county,constituency,ward,local_area,external_url,landmarks,latitude,longitude,property_condition,images,status,approval_status,payment_status,payment_reference,fee_amount,posted_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending','pending',?,?,?,?,?)""",
            (user["id"], category, property_type, title, description, price_amount, price_period, deposit_amount, bedrooms, bathrooms, floor_area, amenities, water_quality, location_name, location["county"], location["constituency"], location["ward"], location["local_area"], external_url, landmarks, latitude, longitude, property_condition, json.dumps(image_names), payment_status, payment_reference, fee, now_iso(), now_iso()))
        listing_id = cur.lastrowid
        log_event("property_submitted", request.path, json.dumps({"listing_id": listing_id, "category": category}))
        audit("property_submitted", "listing", listing_id, f"Fee {fee}; payment reference supplied={bool(payment_reference)}")
        flash("Listing saved privately. It will not appear in public searches until the payment is confirmed, your partner account is verified, and an administrator approves the property.", "success")
        return redirect(url_for("partner_dashboard"))
    return render_template("listing_form.html", form={}, categories=CATEGORY_META, price_periods=PRICE_PERIODS, location_catalog=selector_data())


@app.route("/partner/listings/<int:listing_id>/edit", methods=["GET", "POST"])
@partner_required
def partner_edit_listing(listing_id):
    user = get_current_user()
    row = get_db().execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not row:
        abort(404)
    if request.method == "POST":
        category = request.form.get("category", row["category"])
        if category not in CATEGORY_META:
            category = row["category"]
        property_type = request.form.get("property_type", "").strip()[:120]
        title = request.form.get("title", "").strip()[:180]
        description = request.form.get("description", "").strip()[:5000]
        location = build_listing_location(request.form, row)
        location_name = location["location_name"]
        external_url = safe_external_url(request.form.get("external_url", row["external_url"] or ""))
        if is_competitor_property_portal_url(external_url):
            flash("Links to competing property marketplaces are not published here. Remove that link and add your own website or booking page, or leave the field blank.", "error")
            return redirect(url_for("partner_edit_listing", listing_id=listing_id))
        landmarks = request.form.get("landmarks", "").strip()[:1200]
        price_period = request.form.get("price_period", "per month").strip()
        condition = request.form.get("property_condition", "").strip()[:120]
        water_quality = request.form.get("water_quality", row["water_quality"] or "").strip()[:180]
        if price_period not in PRICE_PERIODS: price_period = "per month"
        try:
            price_amount = float(request.form.get("price_amount", "0") or 0)
            deposit_amount = float(request.form.get("deposit_amount", "") or 0)
            bedrooms = int(request.form.get("bedrooms", "") or 0) or None
            bathrooms = int(request.form.get("bathrooms", "") or 0) or None
            latitude = float(request.form.get("latitude", "").strip()) if request.form.get("latitude", "").strip() else None
            longitude = float(request.form.get("longitude", "").strip()) if request.form.get("longitude", "").strip() else None
            if latitude is not None and not -90 <= latitude <= 90: raise ValueError()
            if longitude is not None and not -180 <= longitude <= 180: raise ValueError()
        except ValueError:
            flash("Check the price, room and coordinate fields.", "error")
            return redirect(url_for("partner_edit_listing", listing_id=listing_id))
        if not title or not property_type or not location_name or not location["county"] or not location["constituency"] or not (location["ward"] or location["local_area"]) or price_amount < 0:
            flash("Property name, type, price, county, constituency and a ward/neighbourhood or exact local area are required.", "error")
            return redirect(url_for("partner_edit_listing", listing_id=listing_id))
        original_names = listing_images(row)
        remove_names = set(request.form.getlist("remove_images"))
        names = [name for name in original_names if name not in remove_names]
        try:
            additions = []
            for file in request.files.getlist("images")[:8]:
                if file and file.filename:
                    additions.append(save_upload(file, LISTING_UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS))
            if additions:
                names = (names + additions)[-8:]
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("partner_edit_listing", listing_id=listing_id))
        if not names:
            flash("At least one genuine property photo is required.", "error")
            return redirect(url_for("partner_edit_listing", listing_id=listing_id))
        fee = fee_for_category(category)
        payment_status = row["payment_status"]
        payment_reference = row["payment_reference"]
        if category != row["category"]:
            payment_status = "pending"
            payment_reference = ""
        elif row["payment_status"] == "paid":
            fee = float(row["fee_amount"])
        # Any substantive edit puts the property back into the review queue.
        get_db().execute("""UPDATE listings SET category=?,property_type=?,title=?,description=?,price_amount=?,price_period=?,deposit_amount=?,bedrooms=?,bathrooms=?,floor_area=?,amenities=?,water_quality=?,location_name=?,county=?,constituency=?,ward=?,local_area=?,external_url=?,landmarks=?,latitude=?,longitude=?,property_condition=?,images=?,status='pending',approval_status='pending',payment_status=?,payment_reference=?,fee_amount=?,property_verified=0,last_confirmed_at='',updated_at=? WHERE id=? AND owner_id=?""",
            (category, property_type, title, description, price_amount, price_period, deposit_amount, bedrooms, bathrooms, request.form.get("floor_area", "").strip()[:80], request.form.get("amenities", "").strip()[:1200], water_quality, location_name, location["county"], location["constituency"], location["ward"], location["local_area"], external_url, landmarks, latitude, longitude, condition, json.dumps(names), payment_status, payment_reference, fee, now_iso(), listing_id, user["id"]))
        # Remove deleted photo files only if no other listing references them.
        if remove_names:
            other_rows = get_db().execute("SELECT images FROM listings WHERE id<>?", (listing_id,)).fetchall()
            referenced = set()
            for other in other_rows:
                try:
                    referenced.update(json.loads(other["images"] or "[]"))
                except (TypeError, json.JSONDecodeError):
                    pass
            for filename in remove_names - referenced:
                if filename in original_names and Path(filename).name == filename:
                    (LISTING_UPLOAD_DIR / filename).unlink(missing_ok=True)
        audit("partner_edited_property", "listing", listing_id, "Listing returned to verification queue after edit")
        flash("Listing updated and returned to review. It stays private until the property is checked again. If its category changed, the new fee must be paid.", "success")
        return redirect(url_for("partner_dashboard"))
    form = dict(row)
    return render_template("listing_form.html", form=form, categories=CATEGORY_META, price_periods=PRICE_PERIODS, edit_mode=True, existing_images=listing_images(row), existing_listing=row, location_catalog=selector_data())


@app.route("/partner/listings/<int:listing_id>/availability", methods=["POST"])
@partner_required
def partner_confirm_availability(listing_id):
    user = get_current_user()
    row = get_db().execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not row:
        abort(404)
    action = request.form.get("availability", "available")
    if action == "taken":
        get_db().execute("UPDATE listings SET status='occupied',updated_at=? WHERE id=?", (now_iso(), listing_id))
        audit("partner_marked_taken", "listing", listing_id)
        flash("The property is now marked as taken and is hidden from available searches.", "success")
    elif action == "available":
        # Partners can re-confirm but cannot unilaterally reverse an admin-reviewed taken/report status.
        if row["status"] in {"occupied", "reported_taken"}:
            flash("An administrator must review a taken/report status before the property can be listed again.", "warning")
        elif row["approval_status"] == "approved" and row["payment_status"] == "paid" and row["property_verified"]:
            get_db().execute("UPDATE listings SET status='available',last_confirmed_at=?,updated_at=? WHERE id=?", (now_iso(), now_iso(), listing_id))
            audit("availability_confirmed", "listing", listing_id)
            flash("Availability confirmation recorded.", "success")
        else:
            flash("This property is not yet approved for publication.", "warning")
    return redirect(url_for("partner_dashboard"))


@app.route("/partner/listings/<int:listing_id>/withdraw", methods=["POST"])
@partner_required
def partner_withdraw_listing(listing_id):
    user = get_current_user()
    row = get_db().execute("SELECT id,title,status FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not row:
        abort(404)
    get_db().execute("UPDATE listings SET status='removed',approval_status='removed',updated_at=? WHERE id=? AND owner_id=?", (now_iso(), listing_id, user["id"]))
    audit("partner_withdrew_property", "listing", listing_id, "Owner withdrew listing from public search; record retained")
    flash("This property has been withdrawn from public search. Its record and enquiry history have been kept.", "success")
    return redirect(url_for("partner_dashboard"))


@app.route("/manage-admin", methods=["GET"])
def admin_base_redirect():
    return redirect(ADMIN_ROOT)


def admin_entry():
    user = get_current_user()
    if user and user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        if auth_is_limited("admin"):
            flash("Too many unsuccessful sign-in attempts. Try again in 15 minutes.", "error")
            return render_template("admin_login.html", admin_path=ADMIN_ROOT), 429
        identity = request.form.get("identity", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM users WHERE role='admin' AND full_name=? LIMIT 1", (identity,)).fetchone()
        if not admin and identity:
            admin = get_db().execute("SELECT * FROM users WHERE role='admin' AND lower(COALESCE(email,''))=lower(?) LIMIT 1", (identity,)).fetchone()
        if not admin or not check_password_hash(admin["password_hash"], password):
            auth_failed("admin")
            flash("Administrator sign-in failed.", "error")
            return render_template("admin_login.html", admin_path=ADMIN_ROOT)
        auth_succeeded("admin")
        session.clear(); session["user_id"] = admin["id"]; session["csrf_token"] = secrets.token_urlsafe(24); session["visitor_key"] = secrets.token_urlsafe(20)
        refresh_current_user_cache()
        get_db().execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), admin["id"]))
        audit("admin_login", "user", admin["id"])
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html", admin_path=ADMIN_ROOT)


app.add_url_rule(ADMIN_ROOT, endpoint="admin_entry", view_func=admin_entry, methods=["GET", "POST"])


@app.route("/manage-admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    audit("admin_logout", "user", get_current_user()["id"])
    session.clear()
    return redirect(ADMIN_ROOT)


@app.route("/manage-admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    stats = {
        "listings": conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
        "published": conn.execute("SELECT COUNT(*) FROM listings WHERE status='available' AND approval_status='approved' AND payment_status='paid' AND property_verified=1").fetchone()[0],
        "pending_payment": conn.execute("SELECT COUNT(*) FROM listings WHERE payment_status IN ('pending','submitted')").fetchone()[0],
        "pending_review": conn.execute("SELECT COUNT(*) FROM listings WHERE payment_status='paid' AND approval_status='pending'").fetchone()[0],
        "partners": conn.execute("SELECT COUNT(*) FROM users WHERE role IN ('owner','agent','host','business')").fetchone()[0],
        "partners_pending": conn.execute("SELECT COUNT(*) FROM users WHERE role IN ('owner','agent','host','business') AND verified=0 AND suspended=0").fetchone()[0],
        "interests": conn.execute("SELECT COUNT(*) FROM interests").fetchone()[0],
        "reports": conn.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0],
        "visitors_today": conn.execute("SELECT COUNT(DISTINCT CASE WHEN v.contact_phone != '' THEN 'phone:' || v.contact_phone WHEN v.user_id IS NOT NULL THEN 'account:' || v.user_id ELSE 'browser:' || v.visitor_key END) FROM visitor_events e JOIN visitor_sessions v ON v.visitor_key=e.visitor_key WHERE e.event_type='page_view' AND e.details != 'administrator' AND e.path NOT LIKE ? AND e.path NOT LIKE '/manage-admin%' AND e.created_at>=?", (ADMIN_ROOT + '%', day_start)).fetchone()[0],
    }
    listings = conn.execute("SELECT l.*,u.full_name AS partner_name,u.business_name FROM listings l JOIN users u ON u.id=l.owner_id ORDER BY l.posted_at DESC LIMIT 8").fetchall()
    latest_events = conn.execute("SELECT * FROM visitor_events ORDER BY id DESC LIMIT 10").fetchall()
    return render_template("admin_dashboard.html", stats=stats, listings=listings, events=latest_events)


@app.route("/manage-admin/discoveries", methods=["GET", "POST"])
@admin_required
def admin_market_discoveries():
    flash("External property-feed cards are disabled. Public listings now come only from owner/agent submissions approved by the site administrator.", "info")
    return redirect(url_for("admin_listings"))


@app.post("/manage-admin/discoveries/<int:item_id>/delete")
@admin_required
def admin_market_discovery_delete(item_id):
    return redirect(url_for("admin_listings"))


@app.route("/manage-admin/listings")
@admin_required
def admin_listings():
    status = request.args.get("status", "").strip()
    category = request.args.get("category", "").strip()
    clauses, params = [], []
    if status:
        clauses.append("l.status=?"); params.append(status)
    if category in CATEGORY_META:
        clauses.append("l.category=?"); params.append(category)
    sql = "SELECT l.*,u.full_name AS partner_name,u.business_name,u.phone AS partner_phone,u.email AS partner_email,u.contact_preference AS contact_preference,u.website_url AS website_url,u.social_url AS social_url,u.verified AS partner_verified FROM listings l JOIN users u ON l.owner_id=u.id"
    if clauses: sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY l.posted_at DESC LIMIT 300"
    listings = get_db().execute(sql, params).fetchall()
    return render_template("admin_listings.html", listings=listings, status=status, category=category)


@app.route("/manage-admin/listings/<int:listing_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_listing(listing_id):
    row = get_db().execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row: abort(404)
    if request.method == "POST":
        category = request.form.get("category", row["category"])
        if category not in CATEGORY_META: category = row["category"]
        property_type = request.form.get("property_type", "").strip()[:120]
        title = request.form.get("title", "").strip()[:180]
        description = request.form.get("description", "").strip()[:5000]
        location_name = request.form.get("location_name", "").strip()[:180]
        landmarks = request.form.get("landmarks", "").strip()[:1200]
        condition = request.form.get("property_condition", "").strip()[:120]
        water_quality = request.form.get("water_quality", "").strip()[:180]
        price_period = request.form.get("price_period", "per month").strip()
        if price_period not in PRICE_PERIODS: price_period = "per month"
        try:
            price_amount = float(request.form.get("price_amount", "0") or 0)
            deposit_amount = float(request.form.get("deposit_amount", "") or 0)
            bedrooms = int(request.form.get("bedrooms", "") or 0) or None
            bathrooms = int(request.form.get("bathrooms", "") or 0) or None
            latitude = float(request.form.get("latitude", "").strip()) if request.form.get("latitude", "").strip() else None
            longitude = float(request.form.get("longitude", "").strip()) if request.form.get("longitude", "").strip() else None
            if latitude is not None and not -90 <= latitude <= 90: raise ValueError()
            if longitude is not None and not -180 <= longitude <= 180: raise ValueError()
            if price_amount < 0 or deposit_amount < 0: raise ValueError()
        except ValueError:
            flash("Check the price, deposit, room and coordinate fields.", "error")
            return redirect(url_for("admin_edit_listing", listing_id=listing_id))
        if not title or not property_type or not location_name:
            flash("Property title, type and location are required.", "error")
            return redirect(url_for("admin_edit_listing", listing_id=listing_id))
        images = listing_images(row)
        additions = []
        try:
            for file in request.files.getlist("images")[:8]:
                if file and file.filename:
                    additions.append(save_upload(file, LISTING_UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS))
        except ValueError as exc:
            for name in additions: (LISTING_UPLOAD_DIR / name).unlink(missing_ok=True)
            flash(str(exc), "error")
            return redirect(url_for("admin_edit_listing", listing_id=listing_id))
        images = (images + additions)[-8:]
        changed_category = category != row["category"]
        payment_status = "pending" if changed_category else row["payment_status"]
        payment_reference = "" if changed_category else row["payment_reference"]
        fee_amount = fee_for_category(category) if changed_category else float(row["fee_amount"])
        admin_rank = int(row["admin_rank"] or 0)
        get_db().execute("""UPDATE listings SET category=?,property_type=?,title=?,description=?,price_amount=?,price_period=?,deposit_amount=?,bedrooms=?,bathrooms=?,floor_area=?,amenities=?,water_quality=?,location_name=?,landmarks=?,latitude=?,longitude=?,property_condition=?,images=?,status='pending',approval_status='pending',payment_status=?,payment_reference=?,fee_amount=?,property_verified=0,admin_rank=?,last_confirmed_at='',updated_at=? WHERE id=?""",
            (category,property_type,title,description,price_amount,price_period,deposit_amount,bedrooms,bathrooms,request.form.get("floor_area", "").strip()[:80],request.form.get("amenities", "").strip()[:1200],water_quality,location_name,landmarks,latitude,longitude,condition,json.dumps(images),payment_status,payment_reference,fee_amount,admin_rank,now_iso(),listing_id))
        audit("admin_edited_listing", "listing", listing_id, "Listing returned to verification after admin edit")
        flash("Property updated. It is in the review queue and will be republished only after the required checks pass.", "success")
        return redirect(url_for("admin_listings"))
    return render_template("admin_listing_edit.html", listing=row, form=dict(row), categories=CATEGORY_META, price_periods=PRICE_PERIODS, existing_images=listing_images(row))


@app.post("/manage-admin/listings/<int:listing_id>/action")
@admin_required
def admin_listing_action(listing_id):
    row = get_db().execute("SELECT l.*,u.verified AS owner_verified FROM listings l JOIN users u ON u.id=l.owner_id WHERE l.id=?", (listing_id,)).fetchone()
    if not row: abort(404)
    action = request.form.get("action", "")
    if action == "mark_paid":
        reference = (request.form.get("payment_reference", "").strip() or row["payment_reference"] or "")[:120]
        if not reference:
            flash("Add and reconcile the actual payment reference before marking this listing paid.", "error")
        else:
            get_db().execute("UPDATE listings SET payment_status='paid',payment_reference=?,updated_at=? WHERE id=?", (reference, now_iso(), listing_id))
            audit("payment_confirmed_manually", "listing", listing_id, f"ref={reference}")
            flash("Payment marked as confirmed. Listing approval is still a separate step.", "success")
    elif action == "approve":
        if request.form.get("checks_confirmed") != "yes":
            flash("Confirm that you checked the property's existence and the partner's authority to advertise it.", "error")
        elif row["payment_status"] != "paid":
            flash("Cannot approve a listing until payment is confirmed.", "error")
        elif not row["owner_verified"]:
            flash("Verify the owner/agent account first.", "error")
        elif row["latitude"] is None or row["longitude"] is None:
            flash("Add and verify the property's actual map coordinates before approval.", "error")
        elif not listing_images(row):
            flash("A property photo is required before approval.", "error")
        else:
            published_at = now_iso()
            listing_expires = (datetime.now(timezone.utc) + timedelta(days=listing_lifecycle_days())).replace(microsecond=0).isoformat()
            get_db().execute("UPDATE listings SET approval_status='approved',property_verified=1,status='available',last_confirmed_at=?,expires_at=?,archived_at='',updated_at=? WHERE id=?", (published_at, listing_expires, published_at, listing_id))
            audit("listing_verified_and_approved", "listing", listing_id, f"Publication term ends {listing_expires}")
            flash("Property approved and published. It now passes the payment, partner and property verification gates.", "success")
    elif action == "confirm_renewal":
        reference = (request.form.get("payment_reference", "").strip() or row["renewal_payment_reference"] or "")[:120]
        if row["renewal_payment_status"] != "submitted" or not reference:
            flash("A submitted renewal reference is required before confirming renewal.", "error")
        elif not row["owner_verified"] or row["approval_status"] != "approved" or not row["property_verified"]:
            flash("This property does not pass the partner and listing checks required for renewal.", "error")
        else:
            renewal_time = datetime.now(timezone.utc).replace(microsecond=0)
            current_expiry = None
            try:
                current_expiry = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
                if current_expiry and current_expiry.tzinfo is None:
                    current_expiry = current_expiry.replace(tzinfo=timezone.utc)
            except ValueError:
                current_expiry = None
            renewal_start = current_expiry if current_expiry and current_expiry > renewal_time else renewal_time
            renewed_until = (renewal_start + timedelta(days=listing_lifecycle_days())).replace(microsecond=0).isoformat()
            get_db().execute("UPDATE listings SET renewal_payment_status='paid',payment_reference=CASE WHEN payment_reference='' THEN ? ELSE payment_reference END,renewal_payment_reference=?,renewal_count=renewal_count+1,renewal_submitted_at='',expires_at=?,status='available',last_confirmed_at=?,archived_at='',updated_at=? WHERE id=?", (reference, reference, renewed_until, renewal_time.isoformat(), renewal_time.isoformat(), listing_id))
            audit("listing_renewal_payment_confirmed", "listing", listing_id, f"Renewed until {renewed_until}; reference={reference}")
            flash(f"Renewal confirmed. The property term now runs through {renewed_until[:10]}.", "success")
    elif action == "reject":
        get_db().execute("UPDATE listings SET approval_status='rejected',status='rejected',updated_at=? WHERE id=?", (now_iso(), listing_id))
        audit("listing_rejected", "listing", listing_id, request.form.get("reason", "")[:500])
        flash("Listing rejected and kept out of public search.", "success")
    elif action in {"pin", "unpin"}:
        rank = 1 if action == "pin" else 0
        get_db().execute("UPDATE listings SET admin_rank=?,updated_at=? WHERE id=?", (rank, now_iso(), listing_id))
        audit("admin_priority_changed", "listing", listing_id, "Private priority enabled" if rank else "Private priority removed")
        flash("Private listing priority updated.", "success")
    elif action == "mark_taken":
        get_db().execute("UPDATE listings SET status='occupied',updated_at=? WHERE id=?", (now_iso(), listing_id))
        audit("admin_marked_taken", "listing", listing_id)
        flash("Listing marked as taken.", "success")
    elif action == "reinstate":
        if row["payment_status"] == "paid" and row["approval_status"] == "approved" and row["property_verified"] and row["owner_verified"]:
            reinstated_at = now_iso()
            reinstated_expiry = (datetime.now(timezone.utc) + timedelta(days=listing_lifecycle_days())).replace(microsecond=0).isoformat()
            get_db().execute("UPDATE listings SET status='available',last_confirmed_at=?,expires_at=?,archived_at='',updated_at=? WHERE id=?", (reinstated_at, reinstated_expiry, reinstated_at, listing_id))
            audit("admin_reinstated_listing", "listing", listing_id, f"New term ends {reinstated_expiry}")
            flash("Listing reinstated by administrator.", "success")
        else:
            flash("This listing does not meet all publication checks and cannot be reinstated.", "error")
    elif action == "remove":
        get_db().execute("UPDATE listings SET status='removed',approval_status='rejected',updated_at=? WHERE id=?", (now_iso(), listing_id))
        audit("listing_removed", "listing", listing_id, request.form.get("reason", "")[:500])
        flash("Listing removed from public results. Its history has been retained.", "success")
    elif action in {"delete_permanently", "archive_listing"}:
        # Safety-first soft deletion: remove from public search, but preserve owner data,
        # uploaded property photos, enquiries, ratings and audit history for recovery.
        archived_at = now_iso()
        get_db().execute("UPDATE listings SET status='archived',approval_status='removed',archived_at=?,updated_at=? WHERE id=?", (archived_at, archived_at, listing_id))
        audit("listing_archived_not_hard_deleted", "listing", listing_id, f"Title={row['title'][:160]}; data retained for recovery")
        flash("Property archived and removed from public search. The listing record, photos, enquiries and ratings were retained for data safety.", "success")
    else:
        flash("Unknown listing action.", "error")
    return redirect(url_for("admin_listings"))


@app.route("/manage-admin/partners")
@admin_required
def admin_partners():
    rows = get_db().execute("SELECT u.*, (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id) AS listing_count FROM users u WHERE u.role IN ('owner','agent','host','business') ORDER BY u.created_at DESC").fetchall()
    return render_template("admin_partners.html", partners=rows)


@app.post("/manage-admin/partners/<int:user_id>/action")
@admin_required
def admin_partner_action(user_id):
    user = get_db().execute("SELECT * FROM users WHERE id=? AND role IN ('owner','agent','host','business')", (user_id,)).fetchone()
    if not user: abort(404)
    action = request.form.get("action", "")
    if action == "verify":
        if not user["phone"]:
            flash("A working contact number is required before verification.", "error")
        else:
            get_db().execute("UPDATE users SET verified=1,suspended=0 WHERE id=?", (user_id,))
            audit("partner_contact_reviewed", "user", user_id, "Admin confirmed contact details and reviewed available account/listing evidence; no ID image required.")
            flash("Partner account verified after administrator review. Check each property separately before marking it as checked.", "success")
    elif action == "unverify":
        get_db().execute("UPDATE users SET verified=0 WHERE id=?", (user_id,))
        audit("partner_verification_revoked", "user", user_id)
        flash("Partner verification removed. Their listings no longer appear in public search.", "success")
    elif action == "suspend":
        get_db().execute("UPDATE users SET suspended=1 WHERE id=?", (user_id,))
        audit("partner_suspended", "user", user_id)
        flash("Partner suspended.", "success")
    elif action == "restore":
        get_db().execute("UPDATE users SET suspended=0 WHERE id=?", (user_id,))
        audit("partner_restored", "user", user_id)
        flash("Partner account restored.", "success")
    return redirect(url_for("admin_partners"))


@app.route("/manage-admin/documents/<path:filename>")
@admin_required
def admin_private_document(filename):
    allowed_names = set()
    for row in get_db().execute("SELECT identity_front,identity_back FROM users"):
        if row["identity_front"]: allowed_names.add(row["identity_front"])
        if row["identity_back"]: allowed_names.add(row["identity_back"])
    if filename not in allowed_names or Path(filename).name != filename:
        abort(404)
    response = send_from_directory(PRIVATE_DOC_DIR, filename, as_attachment=True, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.route("/manage-admin/interests")
@admin_required
def admin_interests():
    rows = get_db().execute("SELECT i.*,l.title AS listing_title,l.category,u.full_name AS partner_name FROM interests i JOIN listings l ON l.id=i.listing_id JOIN users u ON u.id=l.owner_id ORDER BY i.created_at DESC LIMIT 500").fetchall()
    return render_template("admin_interests.html", interests=rows)


@app.post("/manage-admin/interests/<int:interest_id>/action")
@admin_required
def admin_interest_action(interest_id):
    row = get_db().execute("SELECT * FROM interests WHERE id=?", (interest_id,)).fetchone()
    if not row: abort(404)
    status = request.form.get("status", "contacted")
    if status not in {"new", "contacted", "viewing", "closed", "spam"}: status = "contacted"
    get_db().execute("UPDATE interests SET status=? WHERE id=?", (status, interest_id))
    audit("interest_status_changed", "interest", interest_id, status)
    flash("Enquiry status updated.", "success")
    return redirect(url_for("admin_interests"))


@app.route("/manage-admin/reports")
@admin_required
def admin_reports():
    rows = get_db().execute("SELECT r.*,l.title AS listing_title,l.status AS listing_status,l.owner_id,l.location_name FROM reports r JOIN listings l ON l.id=r.listing_id ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END,r.created_at DESC LIMIT 500").fetchall()
    return render_template("admin_reports.html", reports=rows)


@app.post("/manage-admin/reports/<int:report_id>/action")
@admin_required
def admin_report_action(report_id):
    row = get_db().execute("SELECT r.*,l.status AS listing_status,l.payment_status,l.approval_status,l.property_verified,l.latitude,l.longitude,l.owner_id FROM reports r JOIN listings l ON l.id=r.listing_id WHERE r.id=?", (report_id,)).fetchone()
    if not row: abort(404)
    action = request.form.get("action", "")
    if action == "confirm_taken":
        get_db().execute("UPDATE listings SET status='occupied',updated_at=? WHERE id=(SELECT listing_id FROM reports WHERE id=?)", (now_iso(), report_id))
        get_db().execute("UPDATE reports SET status='confirmed_taken',resolved_at=? WHERE id=?", (now_iso(), report_id))
        audit("report_confirmed_taken", "report", report_id)
        flash("Report confirmed. Property remains hidden as taken.", "success")
    elif action == "reinstate":
        owner = get_db().execute("SELECT verified,suspended FROM users WHERE id=?", (row["owner_id"],)).fetchone()
        if row["payment_status"] == "paid" and row["approval_status"] == "approved" and row["property_verified"] and owner and owner["verified"] and not owner["suspended"] and row["latitude"] is not None and row["longitude"] is not None:
            get_db().execute("UPDATE listings SET status='available',last_confirmed_at=?,updated_at=? WHERE id=(SELECT listing_id FROM reports WHERE id=?)", (now_iso(), now_iso(), report_id))
            get_db().execute("UPDATE reports SET status='dismissed',resolved_at=? WHERE id=?", (now_iso(), report_id))
            audit("report_dismissed_and_listing_reinstated", "report", report_id)
            flash("Report dismissed and listing reinstated by administrator.", "success")
        else:
            flash("Cannot reinstate: the listing no longer passes all checks. Review payment, partner and property verification first.", "error")
    elif action == "dismiss":
        get_db().execute("UPDATE reports SET status='dismissed',resolved_at=? WHERE id=?", (now_iso(), report_id))
        audit("report_dismissed", "report", report_id)
        flash("Report dismissed. The listing status was not changed automatically; check it separately.", "success")
    return redirect(url_for("admin_reports"))


@app.route("/manage-admin/analytics")
@admin_required
def admin_analytics():
    conn = get_db()
    sessions = conn.execute("SELECT v.*,COALESCE(NULLIF(u.full_name,''),NULLIF(v.contact_name,'')) AS full_name,u.business_name,COALESCE(NULLIF(u.phone,''),NULLIF(v.contact_phone,'')) AS account_phone FROM visitor_sessions v LEFT JOIN users u ON v.user_id=u.id WHERE v.role != 'administrator' ORDER BY v.last_seen DESC LIMIT 250").fetchall()
    top_pages = conn.execute("SELECT e.path,COUNT(*) AS hits,COUNT(DISTINCT CASE WHEN v.contact_phone != '' THEN 'phone:' || v.contact_phone WHEN v.user_id IS NOT NULL THEN 'account:' || v.user_id ELSE 'browser:' || v.visitor_key END) AS visitors FROM visitor_events e JOIN visitor_sessions v ON v.visitor_key=e.visitor_key WHERE e.event_type='page_view' AND e.details != 'administrator' AND e.path NOT LIKE '/manage-admin%' AND e.path NOT LIKE ? GROUP BY e.path ORDER BY hits DESC LIMIT 15", (ADMIN_ROOT + '%',)).fetchall()
    search_events = conn.execute("SELECT details,created_at FROM visitor_events WHERE event_type='property_search' ORDER BY id DESC LIMIT 1500").fetchall()
    popular_counter, failed_counter = Counter(), Counter()
    popular_meta, failed_meta = {}, {}
    for event in search_events:
        try:
            data = json.loads(event["details"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        parts = [str(data.get(k, "")).strip() for k in ("q", "location", "category", "type") if str(data.get(k, "")).strip()]
        query_label = " · ".join(parts) or "Browse all places"
        normalized = re.sub(r"\s+", " ", query_label.casefold()).strip()
        popular_counter[normalized] += 1
        popular_meta[normalized] = {"label": query_label, "latest": event["created_at"], "count": data.get("count", 0)}
        if bool(data.get("no_match")) or int(data.get("count", 0) or 0) == 0:
            failed_counter[normalized] += 1
            failed_meta[normalized] = {"label": query_label, "latest": event["created_at"]}
    popular_searches = [{"label": popular_meta[key]["label"], "searches": count, "latest": popular_meta[key]["latest"], "last_count": popular_meta[key]["count"]} for key, count in popular_counter.most_common(12)]
    failed_searches = [{"label": failed_meta[key]["label"], "searches": count, "latest": failed_meta[key]["latest"]} for key, count in failed_counter.most_common(12)]
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    active_after = (now - timedelta(minutes=15)).isoformat()
    totals = {
        "sessions": conn.execute("SELECT COUNT(DISTINCT CASE WHEN contact_phone != '' THEN 'phone:' || contact_phone WHEN user_id IS NOT NULL THEN 'account:' || user_id ELSE 'browser:' || visitor_key END) FROM visitor_sessions WHERE role != 'administrator'").fetchone()[0],
        "returning": conn.execute("SELECT COUNT(DISTINCT CASE WHEN contact_phone != '' THEN 'phone:' || contact_phone WHEN user_id IS NOT NULL THEN 'account:' || user_id ELSE 'browser:' || visitor_key END) FROM visitor_sessions v WHERE role != 'administrator' AND (visit_count>1 OR (contact_phone != '' AND contact_phone IN (SELECT contact_phone FROM visitor_sessions WHERE contact_phone != '' GROUP BY contact_phone HAVING COUNT(*)>1)) OR (user_id IS NOT NULL AND user_id IN (SELECT user_id FROM visitor_sessions WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(*)>1)))").fetchone()[0],
        "shared": conn.execute("SELECT COUNT(DISTINCT CASE WHEN contact_phone != '' THEN 'phone:' || contact_phone WHEN user_id IS NOT NULL THEN 'account:' || user_id ELSE 'browser:' || visitor_key END) FROM visitor_sessions WHERE role != 'administrator' AND location_shared=1").fetchone()[0],
        "today": conn.execute("SELECT COUNT(DISTINCT CASE WHEN v.contact_phone != '' THEN 'phone:' || v.contact_phone WHEN v.user_id IS NOT NULL THEN 'account:' || v.user_id ELSE 'browser:' || v.visitor_key END) FROM visitor_events e JOIN visitor_sessions v ON v.visitor_key=e.visitor_key WHERE e.event_type='page_view' AND e.details != 'administrator' AND e.path NOT LIKE ? AND e.path NOT LIKE '/manage-admin%' AND e.created_at>=?", (ADMIN_ROOT + '%', day_start)).fetchone()[0],
        "active": conn.execute("SELECT COUNT(DISTINCT CASE WHEN contact_phone != '' THEN 'phone:' || contact_phone WHEN user_id IS NOT NULL THEN 'account:' || user_id ELSE 'browser:' || visitor_key END) FROM visitor_sessions WHERE role != 'administrator' AND last_seen>=?", (active_after,)).fetchone()[0],
        "mobile": conn.execute("SELECT COUNT(DISTINCT CASE WHEN contact_phone != '' THEN 'phone:' || contact_phone WHEN user_id IS NOT NULL THEN 'account:' || user_id ELSE 'browser:' || visitor_key END) FROM visitor_sessions WHERE role != 'administrator' AND (device LIKE '%phone%' OR device LIKE '%Mobile%' OR device LIKE '%iPhone%' OR device LIKE '%iPad%' OR device LIKE '%Android%')").fetchone()[0],
        "searches": conn.execute("SELECT COUNT(*) FROM visitor_events WHERE event_type='property_search'").fetchone()[0],
        "no_results": sum(failed_counter.values()),
    }
    return render_template("admin_analytics.html", sessions=sessions, top_pages=top_pages, popular_searches=popular_searches, failed_searches=failed_searches, totals=totals)

@app.post("/api/location")
def save_opt_in_location():
    payload = request.get_json(silent=True) or {}
    if payload.get("consent") is not True:
        return jsonify({"ok": False, "error": "Explicit location consent is required."}), 400
    try:
        lat, lon = float(payload.get("latitude")), float(payload.get("longitude"))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Coordinates were not valid."}), 400
    # Keep approximate neighborhood-level coordinates, not a precise movement history.
    lat = round(lat, 3); lon = round(lon, 3)
    key = current_visitor_key()
    user = get_current_user()
    conn = get_db()
    exists = conn.execute("SELECT visitor_key FROM visitor_sessions WHERE visitor_key=?", (key,)).fetchone()
    if exists:
        conn.execute("UPDATE visitor_sessions SET latitude_approx=?,longitude_approx=?,location_shared=1,user_id=?,last_seen=? WHERE visitor_key=?", (lat, lon, user["id"] if user else None, now_iso(), key))
    else:
        role = "partner" if user and user["role"] in {"owner", "agent", "host", "business"} else "house seeker" if user and user["role"] == "seeker" else "visitor"
        conn.execute("INSERT INTO visitor_sessions(visitor_key,user_id,role,first_seen,last_seen,last_path,device,page_views,latitude_approx,longitude_approx,location_shared) VALUES(?,?,?,?,?,?,?,?,?,?,1)", (key, user["id"] if user else None, role, now_iso(), now_iso(), request.referrer or "/", device_label(request.headers.get("User-Agent", "")), 0, lat, lon))
    conn.execute("INSERT INTO visitor_events(visitor_key,user_id,event_type,path,details,created_at) VALUES(?,?,?,?,?,?)", (key, user["id"] if user else None, "location_shared_with_consent", request.path, "Approximate coordinates rounded to 3 decimal places", now_iso()))
    return jsonify({"ok": True, "latitude": lat, "longitude": lon})


@app.route("/manage-admin/boost-requests")
@admin_required
def admin_boost_requests():
    rows = get_db().execute("""SELECT b.*,l.title AS listing_title,l.status AS listing_status,l.approval_status,l.payment_status AS listing_payment_status,l.property_verified,u.full_name AS owner_name,u.phone AS owner_phone
        FROM boost_requests b JOIN listings l ON l.id=b.listing_id JOIN users u ON u.id=b.owner_id
        ORDER BY CASE b.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, b.created_at DESC LIMIT 500""").fetchall()
    return render_template("admin_boost_requests.html", boost_requests=rows)


@app.post("/manage-admin/boost-requests/<int:request_id>/action")
@admin_required
def admin_boost_action(request_id):
    admin = get_current_user()
    boost = get_db().execute("SELECT b.*,l.status AS listing_status,l.approval_status,l.payment_status AS listing_payment_status,l.property_verified FROM boost_requests b JOIN listings l ON l.id=b.listing_id WHERE b.id=?", (request_id,)).fetchone()
    if not boost:
        abort(404)
    if boost["status"] != "pending":
        flash("This boost request was already reviewed.", "warning")
        return redirect(url_for("admin_boost_requests"))
    action = request.form.get("action", "").strip().lower()
    note = request.form.get("admin_note", "").strip()[:600]
    stamp = now_iso()
    if action == "approve":
        if not (boost["listing_status"] == "available" and boost["approval_status"] == "approved" and boost["listing_payment_status"] == "paid" and boost["property_verified"]):
            flash("Cannot activate a boost on a property that is not currently live, paid and approved.", "error")
            return redirect(url_for("admin_boost_requests"))
        tier = boost["tier"]
        duration_key = "boost_duration_days_vvip" if tier == "vvip" else "boost_duration_days_vip"
        try:
            days = max(1, min(365, int(setting(duration_key, DEFAULT_SETTINGS[duration_key]))))
        except (ValueError, TypeError):
            days = int(DEFAULT_SETTINGS[duration_key])
        active_until = (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()
        get_db().execute("UPDATE listings SET boost_tier=?,featured_until=?,updated_at=? WHERE id=?", (tier, active_until, stamp, boost["listing_id"]))
        get_db().execute("UPDATE boost_requests SET status='approved',admin_note=?,updated_at=? WHERE id=?", (note or f"Payment manually reviewed by administrator {admin['id']}", stamp, request_id))
        audit("boost_activated", "listing", boost["listing_id"], f"{tier.upper()} visibility for {days} days; boost request {request_id}")
        flash(f"{tier.upper()} placement is active for {days} days. It will appear ahead of standard listings in supported search results.", "success")
    elif action == "reject":
        if not note:
            note = "Payment or boost request could not be approved. Contact support if you believe this is an error."
        get_db().execute("UPDATE boost_requests SET status='rejected',admin_note=?,updated_at=? WHERE id=?", (note, stamp, request_id))
        audit("boost_rejected", "listing", boost["listing_id"], f"Boost request {request_id}: {note}")
        flash("Boost request rejected. It was not activated.", "success")
    else:
        flash("Choose approve or reject.", "error")
    return redirect(url_for("admin_boost_requests"))


@app.route("/manage-admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        logo_file = request.files.get("logo_file")
        if logo_file and logo_file.filename:
            try:
                logo_name = save_upload(logo_file, BRANDING_DIR, ALLOWED_IMAGE_EXTENSIONS)
                old_logo = setting("site_logo", "")
                set_setting("site_logo", logo_name)
                if old_logo and old_logo != logo_name and Path(old_logo).name == old_logo:
                    (BRANDING_DIR / old_logo).unlink(missing_ok=True)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin_settings"))
        promo_file = request.files.get("promo_image_file")
        if promo_file and promo_file.filename:
            try:
                promo_name = save_upload(promo_file, PROMO_DIR, ALLOWED_IMAGE_EXTENSIONS)
                old_promo = setting("promo_image", "")
                set_setting("promo_image", promo_name)
                if old_promo and old_promo != promo_name and Path(old_promo).name == old_promo:
                    (PROMO_DIR / old_promo).unlink(missing_ok=True)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin_settings"))
        if request.form.get("remove_promo_image"):
            old_promo = setting("promo_image", "")
            set_setting("promo_image", "")
            if old_promo and Path(old_promo).name == old_promo:
                (PROMO_DIR / old_promo).unlink(missing_ok=True)
        allowed_keys = set(DEFAULT_SETTINGS.keys())
        for key in allowed_keys:
            if key.endswith("_enabled"):
                value = "1" if request.form.get(key) else "0"
            elif key in request.form:
                value = request.form.get(key, "").strip()
            else:
                continue
            if key in {"brand_primary", "brand_accent"} and not (len(value) == 7 and value.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in value[1:])):
                flash(f"{key.replace('_',' ').title()} must be a valid hex color.", "error")
                return redirect(url_for("admin_settings"))
            if key == "public_theme" and value not in {"signature", "festive", "warm", "contrast"}:
                flash("Choose one of the available public themes.", "error")
                return redirect(url_for("admin_settings"))
            if key == "management_url" and value and not safe_external_url(value):
                flash("Management URL must begin with https:// or http:// and include a valid host.", "error")
                return redirect(url_for("admin_settings"))
            if key == "promo_link" and value and not safe_external_url(value):
                flash("Campaign destination must be a valid http:// or https:// URL.", "error")
                return redirect(url_for("admin_settings"))
            if key == "promo_link" and value and is_competitor_property_portal_url(value):
                flash("Use your own business destination for promotions, not a competing property marketplace.", "error")
                return redirect(url_for("admin_settings"))
            if key == "promo_video_url" and value and not safe_video_embed_url(value):
                flash("Video must be a public YouTube or Vimeo link.", "error")
                return redirect(url_for("admin_settings"))
            if key == "header_links" and value:
                for line_number, line in enumerate(value.splitlines(), 1):
                    if not line.strip():
                        continue
                    if "|" not in line:
                        flash(f"Header link line {line_number} must use Label | https://address format.", "error")
                        return redirect(url_for("admin_settings"))
                    label, target = line.split("|", 1)
                    if not label.strip() or len(label.strip()) > 55 or not safe_external_url(target.strip()):
                        flash(f"Header link line {line_number} needs a label (55 characters max) and a valid http:// or https:// URL.", "error")
                        return redirect(url_for("admin_settings"))
                    if is_competitor_property_portal_url(target.strip()):
                        flash(f"Header link line {line_number} cannot point to a competing property marketplace.", "error")
                        return redirect(url_for("admin_settings"))
            if key == "public_base_url" and value and not safe_external_url(value):
                flash("Public base URL must begin with https:// or http:// and include a valid host.", "error")
                return redirect(url_for("admin_settings"))
            if key.endswith("_url") and key.startswith("social_") and value and not safe_external_url(value):
                flash("Social profile links must be valid http:// or https:// URLs.", "error")
                return redirect(url_for("admin_settings"))
            if key.startswith("fee_"):
                try:
                    number = float(value)
                    if number < 0 or number > 100000000: raise ValueError()
                    value = str(round(number, 2))
                except ValueError:
                    flash(f"{key.replace('_',' ').title()} must be a non-negative number.", "error")
                    return redirect(url_for("admin_settings"))
            if key in {"listing_expiry_days", "boost_duration_days_vip", "boost_duration_days_vvip"}:
                try:
                    days = int(value)
                    if not 1 <= days <= 365: raise ValueError()
                    value = str(days)
                except ValueError:
                    flash(f"{key.replace('_',' ').title()} must be between 1 and 365 days.", "error")
                    return redirect(url_for("admin_settings"))
            if key in {"boost_fee_vip", "boost_fee_vvip"}:
                try:
                    amount = float(value)
                    if amount < 0 or amount > 100000000: raise ValueError()
                    value = str(round(amount, 2))
                except ValueError:
                    flash(f"{key.replace('_',' ').title()} must be a non-negative amount.", "error")
                    return redirect(url_for("admin_settings"))
            set_setting(key, value)
        new_password = request.form.get("new_admin_password", "")
        if new_password:
            if len(new_password) < 12:
                flash("New administrator password must be at least 12 characters.", "error")
                return redirect(url_for("admin_settings"))
            admin = get_current_user()
            get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), admin["id"]))
            audit("admin_password_changed", "user", admin["id"])
        audit("settings_updated", "settings", "all", "Site name, brand, fees and configuration updated")
        flash("Settings saved. New fees apply to newly submitted listings; existing invoice amounts stay recorded on their listings.", "success")
        return redirect(url_for("admin_settings"))
    settings = all_settings()
    # When an old configuration contains competitor destinations, present the admin
    # with a cleaned form so saving the settings removes those shortcuts permanently.
    settings["promo_link"] = "" if is_competitor_property_portal_url(settings.get("promo_link", "")) else settings.get("promo_link", "")
    allowed_header_lines = []
    for line in settings.get("header_links", "").splitlines():
        if "|" not in line:
            continue
        _label, _target = line.split("|", 1)
        if not is_competitor_property_portal_url(_target.strip()):
            allowed_header_lines.append(line)
    settings["header_links"] = "\n".join(allowed_header_lines)
    return render_template("admin_settings.html", settings=settings)


@app.route("/manage-admin/backups")
@admin_required
def admin_backups():
    files = sorted(BACKUP_DIR.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    backups = [{"name": p.name, "size": p.stat().st_size, "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d %b %Y %H:%M"), "url": url_for("admin_download_backup", filename=p.name)} for p in files[:50]]
    return render_template("admin_backups.html", backups=backups, db_size=DB_PATH.stat().st_size if DB_PATH.exists() else 0)


@app.post("/manage-admin/backups/create")
@admin_required
def admin_create_backup():
    filename = f"manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    path = create_db_snapshot(BACKUP_DIR / filename)
    audit("manual_database_backup_created", "backup", filename, f"{path.stat().st_size} bytes")
    flash(f"Database-only SQLite snapshot created: {filename}", "success")
    return redirect(url_for("admin_backups"))


@app.route("/manage-admin/backups/download-current")
@admin_required
def admin_download_current_backup():
    filename = f"patamahali-full-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    path = create_db_snapshot(BACKUP_DIR / filename)
    audit("database_backup_downloaded", "backup", filename)
    return send_file(path, as_attachment=True, download_name=filename, mimetype="application/vnd.sqlite3", max_age=0)


@app.route("/manage-admin/backups/download-full")
@admin_required
def admin_download_full_backup():
    """Download a portable snapshot containing SQLite records and uploaded media."""
    handle = tempfile.NamedTemporaryFile(prefix="patamahali-full-", suffix=".zip", delete=False)
    path = Path(handle.name)
    handle.close()
    try:
        create_full_backup_archive(path)
        audit("full_backup_archive_downloaded", "backup", path.name, "SQLite database plus listing, branding, promotion and private documents")
        response = send_file(path, as_attachment=True, download_name=f"patamahali-full-recovery-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip", mimetype="application/zip", max_age=0)
        response.call_on_close(lambda: path.unlink(missing_ok=True))
        return response
    except Exception:
        path.unlink(missing_ok=True)
        raise


@app.route("/manage-admin/backups/<path:filename>")
@admin_required
def admin_download_backup(filename):
    if Path(filename).name != filename or not filename.endswith(".sqlite3"):
        abort(404)
    path = BACKUP_DIR / filename
    if not path.is_file(): abort(404)
    audit("backup_downloaded", "backup", filename)
    return send_file(path, as_attachment=True, download_name=filename, mimetype="application/vnd.sqlite3", max_age=0)


@app.post("/manage-admin/backups/restore")
@admin_required
def admin_restore_backup():
    file = request.files.get("backup_file")
    if not file or not file.filename:
        flash("Choose a SQLite backup file first.", "error")
        return redirect(url_for("admin_backups"))
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in {".sqlite3", ".sqlite", ".db"}:
        flash("Choose a .sqlite3, .sqlite or .db file.", "error")
        return redirect(url_for("admin_backups"))
    temp_upload = BACKUP_DIR / f"restore-upload-{uuid.uuid4().hex}{ext}"
    try:
        file.save(temp_upload)
        if temp_upload.stat().st_size < 1024:
            raise ValueError("The file is too small to be a complete database.")
        test_conn = sqlite3.connect(f"file:{temp_upload}?mode=ro", uri=True)
        try:
            check = test_conn.execute("PRAGMA quick_check").fetchone()
            tables = {r[0] for r in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {"settings", "users", "listings", "interests", "visitor_sessions", "visitor_events", "reports", "audit_log", "auth_attempts"}
            if not check or check[0] != "ok" or not required.issubset(tables):
                raise ValueError("This file is not a valid backup for this site.")
        finally:
            test_conn.close()
        create_db_snapshot(BACKUP_DIR / f"before-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3")
        # Close this request's connection, then restore through SQLite's backup API.
        # This preserves SQLite journaling semantics better than replacing a live DB file.
        close_db()
        source_conn = sqlite3.connect(str(temp_upload), timeout=30)
        target_conn = connect_db(DB_PATH)
        try:
            source_conn.backup(target_conn)
            target_conn.commit()
            integrity = target_conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("Restored database failed the integrity check.")
        finally:
            source_conn.close()
            target_conn.close()
        refresh_current_user_cache()
        audit_conn = connect_db()
        try:
            admin_id = session.get("user_id")
            valid_admin = audit_conn.execute("SELECT id FROM users WHERE id=? AND role='admin'", (admin_id,)).fetchone() if admin_id else None
            actor_id = valid_admin["id"] if valid_admin else None
            audit_conn.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,details,created_at) VALUES(?,?,?,?,?,?)", (actor_id, "database_restored", "backup", secure_filename(file.filename), "Database replaced after SQLite integrity and schema validation", now_iso()))
            audit_conn.commit()
            if not valid_admin:
                session.clear()
                refresh_current_user_cache()
        finally:
            audit_conn.close()
        flash("Database restored from the selected backup. A safety backup of the previous database was created first.", "success")
    except Exception as exc:
        flash(f"Restore failed: {exc}", "error")
    finally:
        temp_upload.unlink(missing_ok=True)
    return redirect(url_for("admin_backups"))


@app.route("/media/<path:filename>")
def listing_media(filename):
    if Path(filename).name != filename or Path(filename).suffix.lower().lstrip(".") not in ALLOWED_IMAGE_EXTENSIONS:
        abort(404)
    row = get_db().execute("SELECT id,images,status,approval_status,payment_status,property_verified,is_sample FROM listings WHERE images LIKE ? LIMIT 1", (f"%{filename}%",)).fetchone()
    if not row:
        abort(404)
    owner = get_db().execute("SELECT verified,suspended FROM users WHERE id=(SELECT owner_id FROM listings WHERE id=?)", (row["id"],)).fetchone()
    # Photos for unapproved listings are visible only to the owning partner or admin.
    is_sample = bool("is_sample" in row.keys() and row["is_sample"])
    if not (row["status"] == "available" and row["approval_status"] == "approved" and row["payment_status"] == "paid" and not (owner and owner["suspended"]) and (is_sample or (row["property_verified"] and owner and owner["verified"]))):
        user = get_current_user()
        listing_owner = get_db().execute("SELECT owner_id FROM listings WHERE id=?", (row["id"],)).fetchone()
        if not user or (user["role"] != "admin" and user["id"] != listing_owner["owner_id"]):
            abort(404)
    response = send_from_directory(LISTING_UPLOAD_DIR, filename, max_age=86400)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/branding/<path:filename>")
def branding_media(filename):
    if Path(filename).name != filename or Path(filename).suffix.lower().lstrip(".") not in ALLOWED_IMAGE_EXTENSIONS:
        abort(404)
    if not (BRANDING_DIR / filename).is_file() or setting("site_logo", "") != filename:
        abort(404)
    response = send_from_directory(BRANDING_DIR, filename, max_age=86400)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/qr/platform.png")
def qr_platform():
    url = public_base() + "/"
    return qr_response(url, "platform")


@app.route("/qr/listing/<int:listing_id>.png")
def listing_qr(listing_id):
    row = get_db().execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or not is_public_listing(row): abort(404)
    return qr_response(public_base() + url_for("listing_detail", listing_id=listing_id), f"listing-{listing_id}")


def qr_response(url: str, filename: str):
    from io import BytesIO
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
    qr.add_data(url); qr.make(fit=True)
    image = qr.make_image(fill_color="#102641", back_color="#FFFFFF")
    out = BytesIO(); image.save(out, format="PNG"); out.seek(0)
    return send_file(out, mimetype="image/png", download_name=f"{filename}.png", max_age=3600)


@app.route("/promo-media/<path:filename>")
def promo_media(filename):
    if Path(filename).name != filename or setting("promo_image", "") != filename:
        abort(404)
    path = PROMO_DIR / filename
    if not path.is_file():
        abort(404)
    response = send_from_directory(PROMO_DIR, filename, max_age=86400)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/manifest.webmanifest")
def manifest():
    from flask import Response
    uploaded_logo = setting("site_logo", "")
    if uploaded_logo:
        logo_src = url_for("branding_media", filename=uploaded_logo)
        logo_type = "image/webp" if uploaded_logo.lower().endswith(".webp") else "image/png" if uploaded_logo.lower().endswith(".png") else "image/jpeg"
    else:
        logo_src, logo_type = url_for("static", filename="img/patamahali-avatar.png"), "image/png"
    body = {
        "name": setting("site_name", "PataMahali"),
        "short_name": setting("site_name", "PataMahali")[:12],
        "description": setting("site_description", "Verified property marketplace"),
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#F2F4F7", "theme_color": "#0C1B2D",
        "icons": [{"src": logo_src, "sizes": "512x512" if logo_type == "image/png" else "any", "type": logo_type, "purpose": "any maskable"}],
    }
    return app.response_class(json.dumps(body), mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(BASE_DIR / "static" / "js", "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/site-qr.png")
def site_qr():
    """Return a scannable QR code for the configured public website URL."""
    from io import BytesIO
    target = public_base().rstrip("/") + "/"
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(target)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#102641", back_color="#ffffff").convert("RGB")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    response = send_file(output, mimetype="image/png", max_age=3600, download_name="patamahali-website-qr.png")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/icon.svg")
def icon_svg():
    return send_from_directory(BASE_DIR / "static" / "img", "icon.svg", mimetype="image/svg+xml")


@app.route("/robots.txt")
def robots_txt():
    base = public_base()
    return app.response_class(f"User-agent: *\nDisallow: {ADMIN_ROOT}\nDisallow: /manage-admin/\nDisallow: /partner/\nDisallow: /login\nDisallow: /join\nSitemap: {base}/sitemap.xml\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    from xml.sax.saxutils import escape
    base = public_base()
    locs = [base + "/", base + "/homes", base + "/partners", base + "/places"]
    for county, constituencies in COUNTY_CONSTITUENCIES.items():
        county_path = url_for("county_page", county_slug=slugify(county))
        locs.append(base + county_path)
        for constituency in constituencies:
            constituency_path = url_for("constituency_page", county_slug=slugify(county), constituency_slug=slugify(constituency))
            locs.append(base + constituency_path)
    # Search-intent hubs for rentals, land, sale property, hospitality, commerce and warehouses.
    for category_slug, category_info in SEO_CATEGORY_PAGES.items():
        if category_info["category"] in visible_categories():
            locs.append(base + url_for("property_search_page", category_slug=category_slug))
    # Submit category/location combinations only when real active inventory supports them.
    # Broad county and constituency directories remain available regardless of inventory.
    rows = public_listings(limit=10000)
    backed_county_categories = set()
    backed_constituency_categories = set()
    backed_area_categories = set()
    for row in rows:
        if row["category"] in {info["category"] for info in SEO_CATEGORY_PAGES.values()}:
            cat_slug = next((slug for slug, info in SEO_CATEGORY_PAGES.items() if info["category"] == row["category"]), None)
            county_name = (row["county"] or "").strip()
            con_name = (row["constituency"] or "").strip()
            if cat_slug and county_name in COUNTY_CONSTITUENCIES:
                backed_county_categories.add((cat_slug, county_name))
                if con_name in COUNTY_CONSTITUENCIES[county_name]:
                    backed_constituency_categories.add((cat_slug, county_name, con_name))
                    exact_area = (row["local_area"] or row["ward"] or "").strip()
                    if exact_area:
                        backed_area_categories.add((cat_slug, county_name, con_name, exact_area))
    for cat_slug, county_name in sorted(backed_county_categories):
        locs.append(base + url_for("property_search_page", category_slug=cat_slug, county_slug=slugify(county_name)))
    for cat_slug, county_name, con_name in sorted(backed_constituency_categories):
        locs.append(base + url_for("property_search_page", category_slug=cat_slug, county_slug=slugify(county_name), constituency_slug=slugify(con_name)))
    for cat_slug, county_name, con_name, exact_area in sorted(backed_area_categories):
        locs.append(base + url_for("property_search_page", category_slug=cat_slug, county_slug=slugify(county_name), constituency_slug=slugify(con_name), area_slug=slugify(exact_area)))
    for row in rows:
        locs.append(base + url_for("listing_detail", listing_id=row["id"]))
        county = (row["county"] or "").strip()
        if county and county in COUNTY_CONSTITUENCIES:
            exact_area = (row["local_area"] or row["ward"] or "").strip()
            if exact_area:
                locs.append(base + url_for("place_area_page", county_slug=slugify(county), area_slug=slugify(exact_area)))
            ward = (row["ward"] or "").strip()
            constituency = (row["constituency"] or "").strip()
            if ward and constituency and ward in ward_map(county).get(constituency, []):
                locs.append(base + url_for("ward_page", county_slug=slugify(county), constituency_slug=slugify(constituency), ward_slug=slugify(ward)))
    locs = list(dict.fromkeys(locs))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{escape(loc)}</loc></url>" for loc in locs) + "</urlset>"
    return app.response_class(xml, mimetype="application/xml")



@app.route("/llms.txt")
def llms_txt():
    base = public_base()
    body = [
        f"# {setting('site_name', 'PataMahali')}",
        "", setting("site_description", "Kenya property marketplace for houses, rentals, land and commercial space."), "",
        "## Core pages", f"- Home: {base}/", f"- Search properties: {base}/homes",
        f"- All counties and place directory: {base}/places", f"- Property partners: {base}/partners",
        *[f"- {info['label']}: {base}/property-search/{slug}" for slug, info in SEO_CATEGORY_PAGES.items()],
        "", "## Location coverage", "The directory includes all 47 Kenyan counties and their 290 constituencies, plus curated ward, estate, town, road and locality links where available. Exact localities can also be entered by property owners.",
        "", "## Listing trust", "A property photo on the home page may be illustrative. A property is advertised as a live listing only after it is submitted by a property partner and passes the platform's payment, identity, location and approval checks.",
        "", "## Contact", f"- Site: {base}/", f"- Privacy: {base}/privacy", f"- Terms: {base}/terms", ""
    ]
    return app.response_class("\n".join(body), mimetype="text/plain")

@app.errorhandler(413)
def too_large(_error):
    return render_template("error.html", code=413, message="That upload is too large. Please reduce the file size and try again."), 413


@app.errorhandler(403)
def forbidden(error):
    return render_template("error.html", code=403, message=getattr(error, "description", "You do not have access to this page.")), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="We could not find that page or the listing is not publicly available."), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Please refresh and try again.")), 400


@app.errorhandler(500)
def server_error(error):
    # Log detail for owner/developer, keep internal exception data out of visitor pages.
    print(f"Internal server error: {error}")
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
