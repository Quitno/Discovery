from __future__ import annotations

import hmac
import hashlib
import os
import csv
import io
import re
import secrets
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, date
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from zoneinfo import ZoneInfo

import qrcode
from flask import (
    Flask, abort, flash, g, redirect, render_template, request, send_file,
    url_for, session, make_response
)
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
# Render persistent disks are commonly mounted at /var/data. If that mount exists,
# keep the SQLite database there; otherwise use the bundled instance directory.
PERSISTENT_MOUNT = Path("/var/data")
if PERSISTENT_MOUNT.is_dir() and os.access(PERSISTENT_MOUNT, os.W_OK):
    DB_PATH = PERSISTENT_MOUNT / "discovery_hub.sqlite3"
    BACKUP_DIR = PERSISTENT_MOUNT / "hub_backups"
else:
    DB_PATH = INSTANCE_DIR / "discovery_hub.sqlite3"
    BACKUP_DIR = INSTANCE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
# Respect Render's forwarded HTTPS/host headers for absolute URLs, QR codes, and sitemap.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

THEMES = {
    "evergreen": {
        "label": "Evergreen Signature", "bg": "#f7f7f2", "surface": "#ffffff",
        "ink": "#172e2c", "muted": "#687976", "primary": "#14594f",
        "primary_ink": "#ffffff", "accent": "#d8fa8c", "accent_ink": "#20352b",
        "line": "#e4e9e2", "soft": "#edf4e9", "hero": "#e7f0e5", "warm": "#ff815f"
    },
    "christmas": {
        "label": "Christmas", "bg": "#f8f7f1", "surface": "#ffffff",
        "ink": "#19372b", "muted": "#68786c", "primary": "#15563b",
        "primary_ink": "#ffffff", "accent": "#e5c56b", "accent_ink": "#282d20",
        "line": "#e4e8dc", "soft": "#f7ebdf", "hero": "#e6f0e5", "warm": "#c9454d"
    },
    "valentines": {
        "label": "Valentine's", "bg": "#fbf6f7", "surface": "#ffffff",
        "ink": "#39212d", "muted": "#806874", "primary": "#813b5a",
        "primary_ink": "#ffffff", "accent": "#f7a6c1", "accent_ink": "#432134",
        "line": "#efdee5", "soft": "#f9e9ef", "hero": "#f6e6ec", "warm": "#ea765e"
    },
    "easter": {
        "label": "Easter", "bg": "#faf8f5", "surface": "#ffffff",
        "ink": "#302b3b", "muted": "#777184", "primary": "#66508a",
        "primary_ink": "#ffffff", "accent": "#f3c6a4", "accent_ink": "#3e2b28",
        "line": "#e9e2ed", "soft": "#f1edf9", "hero": "#f0ebf8", "warm": "#df8b6d"
    },
    "summer": {
        "label": "Bright Season", "bg": "#f8f8f3", "surface": "#ffffff",
        "ink": "#193633", "muted": "#647874", "primary": "#08786d",
        "primary_ink": "#ffffff", "accent": "#ffd17f", "accent_ink": "#363021",
        "line": "#e0e9e4", "soft": "#e7f5ef", "hero": "#e3f3ec", "warm": "#ff8a5d"
    },
    "blackfriday": {
        "label": "Black Friday", "bg": "#f5f5f2", "surface": "#ffffff",
        "ink": "#202220", "muted": "#686d68", "primary": "#242824",
        "primary_ink": "#ffffff", "accent": "#ffb56b", "accent_ink": "#2b251e",
        "line": "#e3e5df", "soft": "#eeeeea", "hero": "#e9eae4", "warm": "#f06d43"
    },
    "newyear": {
        "label": "New Year", "bg": "#f7f8f4", "surface": "#ffffff",
        "ink": "#1c3034", "muted": "#68777b", "primary": "#225968",
        "primary_ink": "#ffffff", "accent": "#e6c66f", "accent_ink": "#302c21",
        "line": "#e2e8e8", "soft": "#edf3f4", "hero": "#e5eef0", "warm": "#ed876c"
    },
}

CATEGORIES = [
    "Property & Land", "Hotels & Stays", "Travel", "Events & Tickets",
    "Furniture & Interiors", "Building & Construction", "More Services"
]
ICONS = ["home", "bed", "plane", "ticket", "chair", "bricks", "compass", "shopping", "building", "map", "sparkles"]

DEFAULT_SETTINGS = {
    "brand_name": "The Discovery Hub",
    "tagline": "Good things are closer than you think.",
    "hero_title": "A gateway to more.",
    "hero_description": "Discover connected websites for property, travel, furniture, business services and website or app projects.",
    "theme_mode": "auto",
    "selected_theme": "evergreen",
    "show_search_suggestions": "1",
    "show_featured_strip": "1",
    "footer_note": "A connected gateway to specialist websites and digital services.",
    "whatsapp_number": "",
}


def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


@contextmanager
def db_session():
    """Open and reliably close a short-lived SQLite connection."""
    conn = db_connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def utc_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "category"


app.jinja_env.filters["slugify"] = slugify


@app.template_filter("wa_digits")
def wa_digits(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    elif len(digits) == 10 and digits.startswith(("07", "01")):
        digits = "254" + digits[1:]
    return digits if len(digits) >= 10 else ""


def site_categories(site):
    primary = str(site.get("category", "More Services") or "More Services").strip()
    values = [primary]
    for extra in re.split(r"[,\n;]", str(site.get("extra_categories", "") or "")):
        extra = extra.strip()[:80]
        if extra and extra.casefold() not in {x.casefold() for x in values}:
            values.append(extra)
    return values


@app.template_filter("site_categories")
def jinja_site_categories(site):
    return site_categories(site)


def initialise_database():
    with db_session() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                url TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'More Services',
                extra_categories TEXT NOT NULL DEFAULT '',
                icon TEXT NOT NULL DEFAULT 'compass',
                keywords TEXT NOT NULL DEFAULT '',
                search_url_template TEXT NOT NULL DEFAULT '',
                cta TEXT NOT NULL DEFAULT 'Explore now',
                visible INTEGER NOT NULL DEFAULT 1,
                featured INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL CHECK(event_type IN ('click','search')),
                site_id INTEGER NULL,
                query TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_type_date ON events(event_type, created_at);
            CREATE INDEX IF NOT EXISTS idx_events_site_date ON events(site_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_sites_visible_order ON sites(visible, sort_order);
            CREATE TABLE IF NOT EXISTS customer_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                admin_feedback TEXT NOT NULL DEFAULT '', 
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                business_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                project_type TEXT NOT NULL,
                project_name TEXT NOT NULL DEFAULT '',
                project_summary TEXT NOT NULL,
                target_audience TEXT NOT NULL DEFAULT '',
                pages_count TEXT NOT NULL DEFAULT '1-5',
                feature_level TEXT NOT NULL DEFAULT 'standard',
                key_features TEXT NOT NULL DEFAULT '',
                brand_assets TEXT NOT NULL DEFAULT '',
                content_status TEXT NOT NULL DEFAULT 'need-help',
                domain_hosting TEXT NOT NULL DEFAULT 'not-sure',
                integrations TEXT NOT NULL DEFAULT '',
                target_launch TEXT NOT NULL DEFAULT '',
                timeline TEXT NOT NULL DEFAULT 'flexible',
                budget TEXT NOT NULL DEFAULT 'not-sure',
                maintenance TEXT NOT NULL DEFAULT 'not-sure',
                additional_notes TEXT NOT NULL DEFAULT '',
                estimate_min INTEGER NOT NULL DEFAULT 0,
                estimate_max INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_project_requests_created ON project_requests(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_project_requests_status ON project_requests(status, created_at DESC);
        """)
        request_columns = {row["name"] for row in conn.execute("PRAGMA table_info(project_requests)").fetchall()}
        if "user_id" not in request_columns:
            conn.execute("ALTER TABLE project_requests ADD COLUMN user_id INTEGER NULL")
        if "admin_feedback" not in request_columns:
            conn.execute("ALTER TABLE project_requests ADD COLUMN admin_feedback TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_project_requests_user ON project_requests(user_id, created_at DESC)")
        site_columns = {row["name"] for row in conn.execute("PRAGMA table_info(sites)").fetchall()}
        if "extra_categories" not in site_columns:
            conn.execute("ALTER TABLE sites ADD COLUMN extra_categories TEXT NOT NULL DEFAULT ''")
        # Seed defaults without overwriting settings an administrator has already changed.
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('app_secret',?)", (secrets.token_urlsafe(48),))
        count = conn.execute("SELECT COUNT(*) AS n FROM sites").fetchone()["n"]
        if count == 0:
            now = utc_now()
            seed = [
                ("House Hunter", "house-hunter-ba7e.onrender.com", "https://house-hunter-ba7e.onrender.com", "Explore houses, apartments, land and property opportunities.", "Property & Land", "home", "house, houses, home, homes, apartments, apartment, rent, rental, bedsitter, land, property, real estate, Nairobi, Kenya", "", "Find a home", 1, 1, 10),
                ("OTravel", "otravel-bleg.onrender.com", "https://otravel-bleg.onrender.com", "Explore travel services, stays and booking opportunities.", "Hotels & Stays", "bed", "travel, trips, hotels, hotel, accommodation, stays, airbnb, holiday, holidays, tour, tours, booking, reservations, flights, Kenya", "", "Explore travel", 1, 1, 20),
                ("TRT", "trt-isfa.onrender.com", "https://trt-isfa.onrender.com", "Discover furniture, interior styling and home products.", "Furniture & Interiors", "chair", "furniture, table, coffee table, chairs, wardrobe, mirrors, lighting, decor, interior, home, products, Kenya", "", "Shop furniture", 1, 1, 30),
                ("Oedge", "oedge.onrender.com", "https://oedge.onrender.com", "Explore the services and opportunities available through Oedge.", "More Services", "compass", "oedge, services, discover, online services, Kenya", "", "Explore Oedge", 1, 0, 40),
            ]
            for name, slug, url, desc, category, icon, keywords, search_t, cta, visible, featured, order in seed:
                conn.execute("""INSERT INTO sites(name,slug,url,description,category,icon,keywords,search_url_template,cta,visible,featured,sort_order,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, slug, url, desc, category, icon, keywords, search_t, cta, visible, featured, order, now, now))
            # OTravel legitimately covers both stays and travel; it is shown in both departments.
            conn.execute("UPDATE sites SET extra_categories='Travel' WHERE name='OTravel'")

        # Curated destinations the owner has previously identified as live. Add them
        # to existing installations too, but never overwrite or unhide admin-edited rows.
        # This intentionally only adds missing entries; all current site settings remain intact.
        now = utc_now()
        supplemental_sites = [
            ("Denmart", "denmart", "https://denmart.co.ke",
             "Online shopping and services from Denmart.", "Shopping & Services", "shopping",
             "denmart, shopping, supermarket, groceries, products, online shopping, online ordering, Kenya",
             "", "Shop online", 1, 0, 50),
            ("Prime School Portal", "prime-school-portal", "https://prime-1-rd0g.onrender.com",
             "School portal and school administration services.", "School Management", "building",
             "school, school portal, students, parents, fees, school management, Kenya",
             "", "Open school portal", 1, 0, 60),
        ]
        for name, slug, url, desc, category, icon, keywords, search_t, cta, visible, featured, order in supplemental_sites:
            exists = conn.execute(
                "SELECT 1 FROM sites WHERE lower(url)=lower(?) OR lower(name)=lower(?) LIMIT 1",
                (url, name),
            ).fetchone()
            if not exists:
                conn.execute("""INSERT INTO sites(name,slug,url,description,category,icon,keywords,search_url_template,cta,visible,featured,sort_order,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, slug, url, desc, category, icon, keywords, search_t, cta, visible, featured, order, now, now))
        conn.commit()


initialise_database()
with db_session() as _conn:
    app.secret_key = _conn.execute("SELECT value FROM settings WHERE key='app_secret'").fetchone()["value"]


def get_setting(key, default=""):
    with db_session() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db_session() as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        conn.commit()


def settings_dict():
    with db_session() as conn:
        rows = conn.execute("SELECT key,value FROM settings").fetchall()
    result = {row["key"]: row["value"] for row in rows}
    return {**DEFAULT_SETTINGS, **result}


def easter_sunday(year: int) -> date:
    # Gregorian computus (Meeus/Jones/Butcher), good for seasonal styling only.
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def current_theme_key():
    settings = settings_dict()
    mode = settings.get("theme_mode", "auto")
    selected = settings.get("selected_theme", "evergreen")
    if mode != "auto":
        return selected if selected in THEMES else "evergreen"
    try:
        today = datetime.now(ZoneInfo("Africa/Nairobi")).date()
    except Exception:
        today = date.today()
    if (today.month == 12 and today.day >= 1) or (today.month == 1 and today.day <= 7):
        return "christmas" if today.month == 12 else "newyear"
    if today.month == 2 and 1 <= today.day <= 14:
        return "valentines"
    easter = easter_sunday(today.year)
    if easter - timedelta(days=3) <= today <= easter + timedelta(days=1):
        return "easter"
    # Black Friday: the final Friday of November, with a 7-day promotional window.
    if today.month == 11:
        fridays = [date(today.year, 11, day) for day in range(1, 31) if date(today.year, 11, day).weekday() == 4]
        if fridays and fridays[-1] - timedelta(days=6) <= today <= fridays[-1]:
            return "blackfriday"
    if today.month in (6, 7, 8):
        return "summer"
    return selected if selected in THEMES else "evergreen"


def get_theme():
    key = current_theme_key()
    return key, THEMES.get(key, THEMES["evergreen"])


@app.context_processor
def inject_globals():
    brand = get_setting("brand_name", DEFAULT_SETTINGS["brand_name"])
    _, theme = get_theme()
    sidebar_categories = []
    seen_categories = set()
    visible_sites = get_sites(visible_only=True)
    for site in visible_sites:
        for category in site_categories(site):
            key = category.casefold()
            if key not in seen_categories:
                seen_categories.add(key)
                sidebar_categories.append({"name": category, "slug": slugify(category), "icon": site.get("icon", "compass")})
    settings = settings_dict()
    whatsapp_digits = re.sub(r"\D", "", settings.get("whatsapp_number", ""))
    if whatsapp_digits.startswith("00"):
        whatsapp_digits = whatsapp_digits[2:]
    elif len(whatsapp_digits) == 10 and whatsapp_digits.startswith(("07", "01")):
        whatsapp_digits = "254" + whatsapp_digits[1:]
    whatsapp_url = ("https://wa.me/" + whatsapp_digits + "?text=" + quote_plus(
        f"Hello, I found {brand} and would like to discuss a website or app project."
    )) if len(whatsapp_digits) >= 10 else ""
    return {
        "brand_name": brand,
        "site_settings": settings,
        "active_theme": theme,
        "active_theme_key": get_theme()[0],
        "csrf_field": csrf_field,
        "icon_svg": icon_svg,
        "categories": [item["name"] for item in sidebar_categories],
        "sidebar_categories": sidebar_categories,
        "whatsapp_url": whatsapp_url,
        "whatsapp_digits": whatsapp_digits,
        "current_year": datetime.utcnow().year,
        "customer_logged_in": bool(session.get("customer_id")),
        "customer_name": session.get("customer_name", ""),
    }


def csrf_field():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


@app.before_request
def enforce_csrf():
    # Every POST route is either an administrator action or a searchless site utility.
    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not supplied or not expected or not hmac.compare_digest(supplied, expected):
            abort(400, description="Your form expired. Refresh the page and try again.")


def credential_fingerprint():
    material = os.environ.get("USER_NAME", "") + "\0" + os.environ.get("USER_PASSWORD", "")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        valid_session = session.get("admin_logged_in") and hmac.compare_digest(
            str(session.get("credential_fingerprint", "")), credential_fingerprint()
        ) and bool(os.environ.get("USER_NAME")) and bool(os.environ.get("USER_PASSWORD"))
        if not valid_session:
            session.clear()
            if request.path.startswith("/admin") and request.endpoint != "admin_login":
                return redirect(url_for("admin_login", next=request.path))
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def get_sites(visible_only=False, order=True):
    query = "SELECT * FROM sites"
    if visible_only:
        query += " WHERE visible=1"
    query += " ORDER BY " + ("featured DESC, sort_order ASC, name COLLATE NOCASE ASC" if order else "id DESC")
    with db_session() as conn:
        return [dict(row) for row in conn.execute(query).fetchall()]


def get_site(site_id):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
    return dict(row) if row else None


def normalise_http_url(value):
    value = (value or "").strip()
    if not value:
        raise ValueError("Enter a destination URL.")
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise ValueError("Enter a valid http:// or https:// destination URL.")
    if any(ch.isspace() for ch in value):
        raise ValueError("URLs cannot contain spaces.")
    return value


def clean_analytics_query(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email hidden]", value)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{6,}\d)(?!\w)", "[number hidden]", value)
    return value.strip()[:120]


def log_event(event_type, site_id=None, query=""):
    try:
        with db_session() as conn:
            conn.execute("INSERT INTO events(event_type,site_id,query,created_at) VALUES(?,?,?,?)",
                         (event_type, site_id, clean_analytics_query(query) if event_type == "search" else "", utc_now()))
            conn.commit()
    except sqlite3.Error:
        app.logger.exception("Analytics event could not be recorded")


def site_matches(site, query):
    query_l = query.casefold().strip()
    if not query_l:
        return 0
    title = str(site.get("name", "")).casefold()
    categories = " ".join(site_categories(site)).casefold()
    description = str(site.get("description", "")).casefold()
    keywords = [x.strip().casefold() for x in re.split(r"[,\n;]", str(site.get("keywords", ""))) if x.strip()]
    score = 0
    if query_l == title:
        score += 12
    elif query_l in title:
        score += 8
    if query_l in categories:
        score += 7 if query_l in [c.casefold() for c in site_categories(site)] else 5
    if query_l in description:
        score += 3
    if any(query_l == keyword for keyword in keywords):
        score += 8
    elif any(query_l in keyword or keyword in query_l for keyword in keywords):
        score += 5
    terms = [t for t in re.findall(r"[a-z0-9]+", query_l) if len(t) > 2]
    haystack = " ".join([title, categories, description, " ".join(keywords)])
    for term in terms:
        if term in haystack:
            score += 1
    return score


def get_categories(sites=None):
    sites = sites if sites is not None else get_sites(visible_only=True)
    seen, result = set(), []
    for site in sites:
        for cat in site_categories(site):
            cat = cat.strip()
            if cat and cat.casefold() not in seen:
                result.append(cat)
                seen.add(cat.casefold())
    return result


def icon_svg(key, size=28):
    paths = {
        "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
        "bed": '<path d="M3 18V5m0 10h18v5M3 9h7a3 3 0 0 1 3 3v3M13 12h5a3 3 0 0 1 3 3"/>',
        "plane": '<path d="m2 16 20-7-6-5-3 1 3 5-6 2-4-4-2 1 2 5-4 2z"/>',
        "ticket": '<path d="M4 5h16v4a3 3 0 0 0 0 6v4H4v-4a3 3 0 0 0 0-6z"/><path d="M13 7v2m0 3v2m0 3v1"/>',
        "chair": '<path d="M6 11V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6M5 11h14v4H5zM7 15v6m10-6v6"/>',
        "bricks": '<path d="M3 4h8v5H3zM13 4h8v5h-8zM7 10h10v5H7zM3 16h8v4H3zM13 16h8v4h-8z"/>',
        "compass": '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z"/>',
        "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
        "message": '<path d="M21 11.5a8.5 8.5 0 0 1-12.8 7.3L3 20l1.3-4.2A8.5 8.5 0 1 1 21 11.5z"/>',
        "shopping": '<path d="M4 8h16l-1.5 12h-13zM8 8a4 4 0 0 1 8 0"/>',
        "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
        "building": '<path d="M4 21V4h11v17M15 9h5v12M7 7h2m-2 4h2m-2 4h2m4-8h1m-1 4h1m-1 4h1m5-3h1m-1 4h1M2 21h20"/>',
        "map": '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15m6-12v15"/>',
        "sparkles": '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 14l1 2.5 2.5 1-2.5 1L19 21l-1-2.5-2.5-1 2.5-1z"/>',
    }
    path = paths.get(key, paths["compass"])
    return Markup(f'<svg class="line-icon" width="{int(size)}" height="{int(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


@app.route("/")
def home():
    sites = get_sites(visible_only=True)
    group_map = {}
    for site in sites:
        for category in site_categories(site):
            group_map.setdefault(category, []).append(site)
    brand = get_setting("brand_name", DEFAULT_SETTINGS["brand_name"])
    description = "Discover connected websites for property, travel, furniture and more. Start here to find specialist services, or request a website or app for your own business."
    return render_template("home.html", sites=sites, group_map=group_map,
                           category_names=list(group_map.keys()), title="Explore websites, services and digital projects",
                           meta_description=description, robots="index,follow",
                           current_year=datetime.utcnow().year)


@app.route("/account/register", methods=["GET", "POST"])
def customer_register():
    if session.get("customer_id"):
        return redirect(url_for("customer_projects"))
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()[:100]
        email = request.form.get("email", "").strip().lower()[:160]
        password = request.form.get("password", "")
        if not name or not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email) or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "error")
            return render_template("account_auth.html", title="Create project account", mode="register", robots="noindex,nofollow"), 400
        try:
            with db_session() as conn:
                cur = conn.execute("INSERT INTO customer_accounts(full_name,email,password_hash,created_at) VALUES(?,?,?,?)",
                                   (name, email, generate_password_hash(password), utc_now()))
                account_id = cur.lastrowid
        except sqlite3.IntegrityError:
            flash("An account already uses that email. Please sign in instead.", "error")
            return render_template("account_auth.html", title="Create project account", mode="register", robots="noindex,nofollow"), 409
        session.clear()
        session["customer_id"] = account_id
        session["customer_name"] = name
        session["csrf_token"] = secrets.token_urlsafe(32)
        session.permanent = True
        flash("Your project account is ready. You can now track requests and read updates here.", "success")
        return redirect(url_for("customer_projects"))
    return render_template("account_auth.html", title="Create project account", mode="register", robots="noindex,nofollow")


@app.route("/account/login", methods=["GET", "POST"])
def customer_login():
    if session.get("customer_id"):
        return redirect(url_for("customer_projects"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:160]
        password = request.form.get("password", "")
        with db_session() as conn:
            account = conn.execute("SELECT * FROM customer_accounts WHERE email=?", (email,)).fetchone()
        if not account or not check_password_hash(account["password_hash"], password):
            flash("Email or password was not recognised.", "error")
            return render_template("account_auth.html", title="Sign in to your project account", mode="login", robots="noindex,nofollow"), 401
        session.clear()
        session["customer_id"] = account["id"]
        session["customer_name"] = account["full_name"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        session.permanent = True
        return redirect(url_for("customer_projects"))
    return render_template("account_auth.html", title="Sign in to your project account", mode="login", robots="noindex,nofollow")


@app.route("/account/logout", methods=["POST"])
def customer_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/my-projects")
def customer_projects():
    customer_id = session.get("customer_id")
    if not customer_id:
        flash("Sign in to a project account to track submitted requests and read updates.", "info")
        return redirect(url_for("customer_login", next="/my-projects"))
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM project_requests WHERE user_id=? ORDER BY created_at DESC", (customer_id,)).fetchall()
    return render_template("customer_projects.html", title="My project requests", requests=[dict(row) for row in rows], project_types=PROJECT_TYPES, robots="noindex,nofollow")


PROJECT_TYPES = {
    "business-website": "Business website",
    "online-store": "E-commerce / online store",
    "web-app": "Web application or portal",
    "mobile-app": "Mobile app",
    "redesign": "Website or app redesign",
    "automation": "Integration or business automation",
    "seo": "Search visibility / SEO",
    "other": "Other digital project",
}

# Planning ranges in KES are deliberately indicative and are recalculated on the server.
PROJECT_BASE_RANGES = {
    "business-website": (10000, 20000),
    "online-store": (25000, 60000),
    "web-app": (50000, 120000),
    "mobile-app": (60000, 150000),
    "redesign": (8000, 22000),
    "automation": (15000, 45000),
    "seo": (5000, 20000),
    "other": (12000, 45000),
}
PAGE_RANGES = {"1-5": (0, 0), "6-10": (5000, 9000), "11-20": (12000, 22000), "21+": (25000, 50000)}
FEATURE_RANGES = {"simple": (0, 0), "standard": (5000, 15000), "advanced": (15000, 40000)}
CONTENT_RANGES = {"ready": (0, 0), "need-help": (3000, 10000), "full-service": (6000, 18000)}
TIMELINE_MULTIPLIERS = {"flexible": (1.0, 1.0), "month": (1.0, 1.08), "two-weeks": (1.08, 1.15), "one-week": (1.18, 1.30)}


def estimate_project(form):
    project_type = form.get("project_type", "business-website")
    if project_type not in PROJECT_BASE_RANGES:
        project_type = "other"
    low, high = PROJECT_BASE_RANGES[project_type]
    pages = form.get("pages_count", "1-5")
    if pages not in PAGE_RANGES:
        pages = "1-5"
    add_low, add_high = PAGE_RANGES[pages]
    low += add_low
    high += add_high
    features = form.get("feature_level", "standard")
    if features not in FEATURE_RANGES:
        features = "standard"
    add_low, add_high = FEATURE_RANGES[features]
    low += add_low
    high += add_high
    content = form.get("content_status", "need-help")
    if content not in CONTENT_RANGES:
        content = "need-help"
    add_low, add_high = CONTENT_RANGES[content]
    low += add_low
    high += add_high
    timeline = form.get("timeline", "flexible")
    if timeline not in TIMELINE_MULTIPLIERS:
        timeline = "flexible"
    min_factor, max_factor = TIMELINE_MULTIPLIERS[timeline]
    return int(round(low * min_factor / 500) * 500), int(round(high * max_factor / 500) * 500)


@app.route("/build-a-website-or-app", methods=["GET", "POST"])
def project_request():
    default_estimate = estimate_project({"project_type": "business-website", "pages_count": "1-5", "feature_level": "simple", "content_status": "ready", "timeline": "flexible"})
    if request.method == "POST":
        # Hidden honeypot catches basic form bots without disrupting real visitors.
        if request.form.get("company_website", "").strip():
            return redirect(url_for("project_request", submitted="1"))
        name = request.form.get("name", "").strip()[:100]
        phone = request.form.get("phone", "").strip()[:50]
        email = request.form.get("email", "").strip()[:120]
        project_type = request.form.get("project_type", "other").strip()
        summary = request.form.get("project_summary", "").strip()[:5000]
        if not name or not phone or not summary or project_type not in PROJECT_TYPES:
            flash("Please complete your name, phone number, project type and project brief.", "error")
            return render_template("project_request.html", title="Website and app development in Kenya", project_types=PROJECT_TYPES,
                                   estimate_min=default_estimate[0], estimate_max=default_estimate[1]), 400
        if email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            flash("Please enter a valid email address, or leave that field blank.", "error")
            return render_template("project_request.html", title="Website and app development in Kenya", project_types=PROJECT_TYPES,
                                   estimate_min=default_estimate[0], estimate_max=default_estimate[1]), 400
        estimate_min, estimate_max = estimate_project(request.form)
        allowed = {
            "name": name, "phone": phone, "email": email,
            "business_name": request.form.get("business_name", "").strip()[:150],
            "location": request.form.get("location", "").strip()[:120],
            "project_type": project_type,
            "project_name": request.form.get("project_name", "").strip()[:150],
            "project_summary": summary,
            "target_audience": request.form.get("target_audience", "").strip()[:1000],
            "pages_count": request.form.get("pages_count", "1-5") if request.form.get("pages_count") in PAGE_RANGES else "1-5",
            "feature_level": request.form.get("feature_level", "standard") if request.form.get("feature_level") in FEATURE_RANGES else "standard",
            "key_features": request.form.get("key_features", "").strip()[:3000],
            "brand_assets": request.form.get("brand_assets", "").strip()[:1000],
            "content_status": request.form.get("content_status", "need-help") if request.form.get("content_status") in CONTENT_RANGES else "need-help",
            "domain_hosting": request.form.get("domain_hosting", "not-sure") if request.form.get("domain_hosting") in ("have-both", "domain-only", "hosting-only", "need-both", "not-sure") else "not-sure",
            "integrations": request.form.get("integrations", "").strip()[:1500],
            "target_launch": request.form.get("target_launch", "").strip()[:40],
            "timeline": request.form.get("timeline", "flexible") if request.form.get("timeline") in TIMELINE_MULTIPLIERS else "flexible",
            "budget": request.form.get("budget", "not-sure") if request.form.get("budget") in ("under-10000", "10000-25000", "25000-50000", "50000-100000", "100000-plus", "not-sure") else "not-sure",
            "maintenance": request.form.get("maintenance", "not-sure") if request.form.get("maintenance") in ("yes", "no", "not-sure") else "not-sure",
            "additional_notes": request.form.get("additional_notes", "").strip()[:2500],
            "estimate_min": estimate_min, "estimate_max": estimate_max,
            "user_id": session.get("customer_id"),
            "created_at": utc_now(), "updated_at": utc_now(),
        }
        with db_session() as conn:
            conn.execute("""INSERT INTO project_requests
                (user_id,name,phone,email,business_name,location,project_type,project_name,project_summary,target_audience,
                 pages_count,feature_level,key_features,brand_assets,content_status,domain_hosting,integrations,
                 target_launch,timeline,budget,maintenance,additional_notes,estimate_min,estimate_max,status,admin_feedback,created_at,updated_at)
                VALUES(:user_id,:name,:phone,:email,:business_name,:location,:project_type,:project_name,:project_summary,:target_audience,
                 :pages_count,:feature_level,:key_features,:brand_assets,:content_status,:domain_hosting,:integrations,
                 :target_launch,:timeline,:budget,:maintenance,:additional_notes,:estimate_min,:estimate_max,'New','',:created_at,:updated_at)""", allowed)
        flash("Your project brief has been received. The estimate is a planning guide; the final price and delivery plan will be confirmed after scope review.", "success")
        return redirect(url_for("project_request", submitted="1"))
    return render_template("project_request.html", title="Website and app development in Kenya", project_types=PROJECT_TYPES,
                           submitted=request.args.get("submitted") == "1", estimate_min=default_estimate[0], estimate_max=default_estimate[1],
                           meta_description="Request affordable website, e-commerce, web app or mobile app development in Kenya. Share your project brief and get an initial price range based on scope, features and timing.", robots="index,follow")


@app.route("/admin/requests")
@admin_required
def admin_project_requests():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM project_requests ORDER BY created_at DESC LIMIT 500").fetchall()
    return render_template("admin_requests.html", title="Project requests", section="requests", requests=[dict(r) for r in rows], project_types=PROJECT_TYPES)


@app.route("/admin/requests/<int:request_id>/status", methods=["POST"])
@admin_required
def admin_project_request_status(request_id):
    status = request.form.get("status", "New")
    if status not in ("New", "Reviewing", "Contacted", "Quoted", "Won", "Closed"):
        status = "New"
    feedback = request.form.get("admin_feedback", "").strip()[:4000]
    with db_session() as conn:
        changed = conn.execute("UPDATE project_requests SET status=?,admin_feedback=?,updated_at=? WHERE id=?", (status, feedback, utc_now(), request_id)).rowcount
    if not changed:
        abort(404)
    flash("Project request status updated.", "success")
    return redirect(url_for("admin_project_requests") + f"#request-{request_id}")


@app.route("/admin/requests/export.csv")
@admin_required
def admin_project_requests_export():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM project_requests ORDER BY created_at DESC").fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(rows[0].keys() if rows else ["id", "name", "phone", "email", "project_type", "project_summary", "status", "created_at"])
    for row in rows:
        writer.writerow([row[k] for k in row.keys()])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="project-requests.csv"'
    return response


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()[:120]
    results = []
    service_listing = False
    if query:
        log_event("search", query=query)
        sites = get_sites(visible_only=True)
        scored = [(site_matches(site, query), site) for site in sites]
        results = [site for score, site in sorted(scored, key=lambda x: (x[0], x[1]["featured"], -x[1]["sort_order"]), reverse=True) if score > 0]
        query_normalised = re.sub(r"[^a-z0-9]+", " ", query.casefold()).strip()
        development_terms = ("web developer", "web development", "website", "websites", "build a site", "build website",
                             "make a website", "app developer", "app development", "mobile app", "web app", "software",
                             "ecommerce", "e commerce", "online store", "website design", "app design", "developer", "coding")
        service_listing = any(term in query_normalised for term in development_terms)
    return render_template("search.html", query=query, results=results, service_listing=service_listing,
                           title=(f"Search: {query}" if query else "Search our network"),
                           meta_description="Search connected websites and find website or app development support for your business.", robots="noindex,follow")


@app.route("/explore/<path:category_slug>")
def explore_category(category_slug):
    sites = get_sites(visible_only=True)
    matching = [s for s in sites if any(slugify(cat) == category_slug for cat in site_categories(s))]
    if not matching:
        abort(404)
    category_name = next((cat for site in matching for cat in site_categories(site) if slugify(cat) == category_slug), matching[0]["category"])
    return render_template("category.html", category_name=category_name, sites=matching,
                           title=f"Explore {category_name}", meta_description=f"Discover websites and services for {category_name.lower()}.", robots="index,follow")


@app.route("/go/<int:site_id>")
def go_site(site_id):
    site = get_site(site_id)
    if not site or not site["visible"]:
        abort(404)
    query = request.args.get("q", "").strip()[:120]
    log_event("click", site_id=site_id)
    target = site["url"]
    pattern = site.get("search_url_template", "").strip()
    if query and pattern and "{query}" in pattern:
        try:
            target = pattern.replace("{query}", quote_plus(query))
            parsed = urlparse(target)
            allowed = urlparse(site["url"])
            if parsed.scheme not in ("http", "https") or parsed.netloc != allowed.netloc:
                target = site["url"]
        except Exception:
            target = site["url"]
    return redirect(target, code=302)


@app.route("/robots.txt")
def robots_txt():
    lines = ["User-agent: *", "Allow: /", "Disallow: /admin", "Disallow: /go/", "Disallow: /account/", "Disallow: /my-projects", f"Sitemap: {url_for('sitemap_xml', _external=True)}"]
    return app.response_class("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    host = request.url_root.rstrip("/")
    urls = [host + "/", host + url_for("project_request")]
    for category in get_categories():
        urls.append(host + url_for("explore_category", category_slug=slugify(category)))
    lastmod = datetime.utcnow().date().isoformat()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for location in urls:
        xml += f"  <url><loc>{location}</loc><lastmod>{lastmod}</lastmod></url>\n"
    xml += "</urlset>\n"
    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response


@app.route("/manifest.webmanifest")
def manifest():
    response = make_response(render_template("manifest.webmanifest", brand=brand_safe(get_setting("brand_name")), theme=get_theme()[1]))
    response.headers["Content-Type"] = "application/manifest+json"
    return response


def brand_safe(value):
    return (value or "The Discovery Hub").strip()[:60]


@app.route("/service-worker.js")
def service_worker():
    response = send_file(BASE_DIR / "static" / "js" / "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/offline")
def offline():
    return render_template("offline.html", title="You're offline")


@app.route("/health")
def health():
    try:
        with db_session() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "reachable"}, 200
    except sqlite3.Error:
        return {"status": "error", "database": "unavailable"}, 503


# ---------------------------- Administration ----------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        expected_name = os.environ.get("USER_NAME", "")
        expected_password = os.environ.get("USER_PASSWORD", "")
        supplied_name = request.form.get("username", "")
        supplied_password = request.form.get("password", "")
        if not expected_name or not expected_password:
            flash("Admin login is not configured yet. Set USER_NAME and USER_PASSWORD in Render environment variables.", "error")
        elif hmac.compare_digest(supplied_name, expected_name) and hmac.compare_digest(supplied_password, expected_password):
            session.clear()
            session["admin_logged_in"] = True
            session["credential_fingerprint"] = credential_fingerprint()
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            next_url = request.args.get("next", "")
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("admin_dashboard")
            return redirect(next_url)
        else:
            flash("Those login details were not recognised.", "error")
    return render_template("admin_login.html", title="Administrator sign in")


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("admin_login"))


def admin_analytics():
    since7 = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    since30 = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        total_clicks = conn.execute("SELECT COUNT(*) n FROM events WHERE event_type='click'").fetchone()["n"]
        clicks7 = conn.execute("SELECT COUNT(*) n FROM events WHERE event_type='click' AND created_at>=?", (since7,)).fetchone()["n"]
        searches = conn.execute("SELECT COUNT(*) n FROM events WHERE event_type='search'").fetchone()["n"]
        searches7 = conn.execute("SELECT COUNT(*) n FROM events WHERE event_type='search' AND created_at>=?", (since7,)).fetchone()["n"]
        clicks30 = conn.execute("SELECT COUNT(*) n FROM events WHERE event_type='click' AND created_at>=?", (since30,)).fetchone()["n"]
        top_sites = conn.execute("""SELECT s.id,s.name,s.category,COUNT(e.id) visits FROM events e JOIN sites s ON s.id=e.site_id
                                  WHERE e.event_type='click' GROUP BY s.id ORDER BY visits DESC,s.name LIMIT 6""").fetchall()
        top_searches = conn.execute("""SELECT query,COUNT(*) searches FROM events WHERE event_type='search' AND query!=''
                                      GROUP BY query ORDER BY searches DESC,query LIMIT 10""").fetchall()
        daily = []
        for days_ago in range(13, -1, -1):
            day = (datetime.utcnow().date() - timedelta(days=days_ago))
            start = day.strftime("%Y-%m-%d") + " 00:00:00"
            end = (day + timedelta(days=1)).strftime("%Y-%m-%d") + " 00:00:00"
            n = conn.execute("SELECT COUNT(*) n FROM events WHERE created_at>=? AND created_at<?", (start, end)).fetchone()["n"]
            daily.append({"day": day.strftime("%d %b"), "count": n})
    all_sites = get_sites(order=False)
    return {"total_clicks": total_clicks, "clicks7": clicks7, "clicks30": clicks30,
            "searches": searches, "searches7": searches7, "top_sites": [dict(x) for x in top_sites],
            "top_searches": [dict(x) for x in top_searches], "daily": daily, "site_count": len(all_sites),
            "visible_count": sum(1 for s in all_sites if s["visible"])}


@app.route("/admin")
@app.route("/admin/")
@admin_required
def admin_dashboard():
    stats = admin_analytics()
    max_daily = max([x["count"] for x in stats["daily"]] + [1])
    return render_template("admin_dashboard.html", title="Overview", stats=stats, max_daily=max_daily, section="dashboard")


def site_form_data(form):
    name = form.get("name", "").strip()[:100]
    if not name:
        raise ValueError("Enter a site name.")
    url = normalise_http_url(form.get("url", ""))
    category = form.get("category", "More Services").strip()[:80] or "More Services"
    extra_categories = form.get("extra_categories", "").strip()[:300]
    icon = form.get("icon", "compass").strip()
    if icon not in ICONS:
        icon = "compass"
    description = form.get("description", "").strip()[:400]
    keywords = form.get("keywords", "").strip()[:1500]
    cta = form.get("cta", "Explore now").strip()[:60] or "Explore now"
    search_template = form.get("search_url_template", "").strip()[:500]
    if search_template:
        if "{query}" not in search_template:
            raise ValueError("The search URL template must include {query}, for example https://example.com/search?q={query}.")
        sample = search_template.replace("{query}", "test")
        parsed = urlparse(sample)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Enter a valid search URL template.")
        if parsed.netloc != urlparse(url).netloc:
            raise ValueError("The search URL must use the same hostname as the destination URL.")
    visible = 1 if form.get("visible") == "1" else 0
    featured = 1 if form.get("featured") == "1" else 0
    try:
        sort_order = max(-10000, min(10000, int(form.get("sort_order", "100"))))
    except ValueError:
        sort_order = 100
    return {"name": name, "slug": slugify(name), "url": url, "description": description,
            "category": category, "extra_categories": extra_categories, "icon": icon, "keywords": keywords, "search_url_template": search_template,
            "cta": cta, "visible": visible, "featured": featured, "sort_order": sort_order}


@app.route("/admin/sites")
@admin_required
def admin_sites():
    return render_template("admin_sites.html", title="Manage destinations", sites=get_sites(order=False), section="sites", icons=ICONS, categories=CATEGORIES)


@app.route("/admin/sites/new", methods=["GET", "POST"])
@admin_required
def admin_site_new():
    if request.method == "POST":
        try:
            data = site_form_data(request.form)
            now = utc_now()
            with db_session() as conn:
                conn.execute("""INSERT INTO sites(name,slug,url,description,category,extra_categories,icon,keywords,search_url_template,cta,visible,featured,sort_order,created_at,updated_at)
                    VALUES(:name,:slug,:url,:description,:category,:extra_categories,:icon,:keywords,:search_url_template,:cta,:visible,:featured,:sort_order,:created_at,:updated_at)""", {**data, "created_at": now, "updated_at": now})
                conn.commit()
            flash("Destination added to your network.", "success")
            return redirect(url_for("admin_sites"))
        except (ValueError, sqlite3.Error) as exc:
            flash(str(exc), "error")
    return render_template("admin_site_form.html", title="Add destination", site=None, section="sites", icons=ICONS, categories=CATEGORIES)


@app.route("/admin/sites/<int:site_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_site_edit(site_id):
    site = get_site(site_id)
    if not site:
        abort(404)
    if request.method == "POST":
        try:
            data = site_form_data(request.form)
            data["updated_at"] = utc_now()
            data["id"] = site_id
            with db_session() as conn:
                conn.execute("""UPDATE sites SET name=:name,slug=:slug,url=:url,description=:description,category=:category,extra_categories=:extra_categories,
                    icon=:icon,keywords=:keywords,search_url_template=:search_url_template,cta=:cta,visible=:visible,
                    featured=:featured,sort_order=:sort_order,updated_at=:updated_at WHERE id=:id""", data)
                conn.commit()
            flash("Destination updated.", "success")
            return redirect(url_for("admin_sites"))
        except (ValueError, sqlite3.Error) as exc:
            flash(str(exc), "error")
    return render_template("admin_site_form.html", title="Edit destination", site=site, section="sites", icons=ICONS, categories=CATEGORIES)


@app.route("/admin/sites/<int:site_id>/visibility", methods=["POST"])
@admin_required
def admin_site_visibility(site_id):
    site = get_site(site_id)
    if not site:
        abort(404)
    with db_session() as conn:
        conn.execute("UPDATE sites SET visible=?,updated_at=? WHERE id=?", (0 if site["visible"] else 1, utc_now(), site_id))
        conn.commit()
    flash(f"{site['name']} is now {'visible' if not site['visible'] else 'hidden'} on the public hub.", "success")
    return redirect(url_for("admin_sites"))


@app.route("/admin/sites/<int:site_id>/delete", methods=["POST"])
@admin_required
def admin_site_delete(site_id):
    site = get_site(site_id)
    if not site:
        abort(404)
    with db_session() as conn:
        conn.execute("DELETE FROM sites WHERE id=?", (site_id,))
        conn.commit()
    flash(f"{site['name']} was removed from the hub directory. Its actual website was not deleted.", "success")
    return redirect(url_for("admin_sites"))


@app.route("/admin/appearance", methods=["GET", "POST"])
@admin_required
def admin_appearance():
    if request.method == "POST":
        brand = request.form.get("brand_name", "").strip()[:60]
        if not brand:
            flash("The brand name cannot be empty.", "error")
        else:
            mode = request.form.get("theme_mode", "auto")
            selected = request.form.get("selected_theme", "evergreen")
            if mode not in ("auto", "manual"):
                mode = "auto"
            if selected not in THEMES:
                selected = "evergreen"
            values = {
                "brand_name": brand,
                "tagline": request.form.get("tagline", "").strip()[:120],
                "theme_mode": mode,
                "selected_theme": selected,
                "footer_note": request.form.get("footer_note", "").strip()[:160],
                "whatsapp_number": request.form.get("whatsapp_number", "").strip()[:40],
            }
            for key, val in values.items():
                set_setting(key, val)
            flash("Branding and appearance settings saved.", "success")
            return redirect(url_for("admin_appearance"))
    return render_template("admin_appearance.html", title="Appearance & branding", section="appearance", themes=THEMES)


@app.route("/admin/qr")
@admin_required
def admin_qr():
    return render_template("admin_qr.html", title="QR codes", section="qr", sites=get_sites(visible_only=True))


def make_qr_bytes(data):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#17342f", back_color="#ffffff")
    import io
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


@app.route("/share-qr.png")
def public_hub_qr():
    """Public QR code for visitors to share or scan the main landing page."""
    output = make_qr_bytes(url_for("home", _external=True))
    return send_file(output, mimetype="image/png", as_attachment=request.args.get("download") == "1", download_name="website-landing-page-qr.png", max_age=300)


@app.route("/admin/qr/hub.png")
@admin_required
def admin_qr_hub_png():
    output = make_qr_bytes(url_for("home", _external=True))
    return send_file(output, mimetype="image/png", as_attachment=request.args.get("download") == "1", download_name="discovery-hub-qr.png")


@app.route("/admin/qr/<int:site_id>.png")
@admin_required
def admin_qr_site_png(site_id):
    site = get_site(site_id)
    if not site:
        abort(404)
    output = make_qr_bytes(url_for("go_site", site_id=site_id, _external=True))
    filename = f"{slugify(site['name'])}-qr.png"
    return send_file(output, mimetype="image/png", as_attachment=request.args.get("download") == "1", download_name=filename)


@app.route("/admin/backup", methods=["GET", "POST"])
@admin_required
def admin_backup():
    if request.method == "POST":
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        destination = BACKUP_DIR / f"discovery-hub-{stamp}.sqlite3"
        try:
            with db_session() as source:
                target = sqlite3.connect(str(destination))
                source.backup(target)
                target.close()
            flash(f"Backup created: {destination.name}", "success")
        except Exception:
            app.logger.exception("Database backup failed")
            flash("The backup could not be created. Check the server logs and storage permissions.", "error")
        return redirect(url_for("admin_backup"))
    backups = []
    if BACKUP_DIR.exists():
        for file in sorted(BACKUP_DIR.glob("discovery-hub-*.sqlite3"), reverse=True):
            try:
                backups.append({"name": file.name, "size": file.stat().st_size, "modified": datetime.fromtimestamp(file.stat().st_mtime).strftime("%d %b %Y, %H:%M")})
            except OSError:
                pass
    return render_template("admin_backup.html", title="Database backups", section="backup", backups=backups, db_path=str(DB_PATH))


@app.route("/admin/backup/download-current")
@admin_required
def admin_backup_download_current():
    temp = tempfile.NamedTemporaryFile(prefix="discovery-hub-backup-", suffix=".sqlite3", delete=False)
    temp_path = Path(temp.name)
    temp.close()
    try:
        with db_session() as source:
            target = sqlite3.connect(str(temp_path))
            source.backup(target)
            target.close()
        response = send_file(temp_path, mimetype="application/vnd.sqlite3", as_attachment=True,
                             download_name=f"discovery-hub-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.sqlite3",
                             max_age=0)
        response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
        return response
    except Exception:
        temp_path.unlink(missing_ok=True)
        app.logger.exception("Database download failed")
        abort(500)


@app.route("/admin/backup/download/<path:filename>")
@admin_required
def admin_backup_download(filename):
    safe_name = Path(filename).name
    path = BACKUP_DIR / safe_name
    if not safe_name.startswith("discovery-hub-") or not safe_name.endswith(".sqlite3") or not path.is_file():
        abort(404)
    return send_file(path, mimetype="application/vnd.sqlite3", as_attachment=True, download_name=safe_name)


@app.after_request
def secure_response_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    if request.path.startswith("/admin") or request.path.startswith("/go/"):
        response.headers["Cache-Control"] = "no-store"
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Please refresh", error_message=getattr(error, "description", "Your request could not be processed."), code=400), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", title="Page not found", error_message="That page may have moved, or it may not be available yet.", code=404), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Unhandled internal error")
    return render_template("error.html", title="Something went wrong", error_message="We could not complete that request. Please try again.", code=500), 500


if __name__ == "__main__":
    # Local development only. Production should run through Gunicorn via Procfile.
    app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
