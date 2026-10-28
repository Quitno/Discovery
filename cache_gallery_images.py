#!/usr/bin/env python3
"""Download and compress PataMahali's discovery-gallery images during the Render build.

Creates 640x420 WebP files under static/img/gallery/ (usually only a few MB total)
for sources that permit reuse: Unsplash/Pexels catalogue images and images with a
clear Creative Commons/public-domain licence. Third-party estate-agent/editorial
listing images are not re-hosted unless their card says it has an open licence; the
page can still try the original image URL and uses an on-page local fallback if it
fails. Source URLs, credits and the licence/source note remain in the manifest.

The build does not fail if an image host is temporarily unavailable. A failed
licensed slot may reuse a successfully cached image from the same section.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from photo_rails import PHOTO_SECTIONS, gallery_cache_filename  # noqa: E402

# Identify the licence of an image URL from the card that actually owns it.
_URL_LICENSES = {}
for _section in PHOTO_SECTIONS:
    for _card in _section.get("cards", []):
        for _url in (_card.get("_original_src"), _card.get("src")):
            if isinstance(_url, str) and _url.startswith(("http://", "https://")):
                _URL_LICENSES[_url] = str(_card.get("license", "")).lower()

GALLERY_DIR = ROOT / "static" / "img" / "gallery"
GALLERY_DIR.mkdir(parents=True, exist_ok=True)
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 250 * 1024
TIMEOUT_SECONDS = float(os.environ.get("PATAMAHALI_IMAGE_TIMEOUT", "9"))


def _url_is_cacheable(url: str) -> bool:
    """Only re-host photos with a reusable provider licence or clear open licence."""
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host in {"images.unsplash.com", "images.pexels.com", "plus.unsplash.com"}:
        return True
    licence = _URL_LICENSES.get(url, "")
    if any(mark in licence for mark in ("cc by", "cc0", "public domain", "creative commons zero")):
        return host.endswith("wikimedia.org") or host.endswith("wikipedia.org") or host in {"commons.wikimedia.org", "upload.wikimedia.org"}
    return False


def _headers(url: str, card: dict) -> dict:
    headers = {
        "User-Agent": "PataMahaliGalleryCache/1.0 (+https://trorinovationstech.co.ke; image thumbnails)",
        "Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5",
    }
    source_page = card.get("source_page")
    if source_page and str(source_page).startswith(("https://", "http://")):
        headers["Referer"] = source_page
    else:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme and parsed.netloc:
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
    return headers


def _download_and_compress(url: str, card: dict, target: Path) -> tuple[bool, str]:
    if not url.startswith(("https://", "http://")):
        return False, "not a remote URL"
    try:
        req = urllib.request.Request(url, headers=_headers(url, card))
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                return False, f"HTTP {status}"
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and not (content_type.startswith("image/") or "octet-stream" in content_type):
                return False, f"not an image response ({content_type})"
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
        if not data or len(data) > MAX_DOWNLOAD_BYTES:
            return False, "empty/oversized image"
        from io import BytesIO
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image = ImageOps.fit(image, (640, 420), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
            target.parent.mkdir(parents=True, exist_ok=True)
            # Try smaller quality levels so the local image pack remains lightweight.
            for quality in (70, 64, 58):
                image.save(target, "WEBP", quality=quality, method=6, optimize=True)
                if target.stat().st_size <= MAX_OUTPUT_BYTES:
                    break
        if target.stat().st_size < 500:
            target.unlink(missing_ok=True)
            return False, "output unexpectedly small"
        return True, url
    except (urllib.error.URLError, TimeoutError, OSError, UnidentifiedImageError, ValueError) as exc:
        target.unlink(missing_ok=True)
        return False, type(exc).__name__ + ": " + str(exc)[:140]


def _slot_list():
    slots = []
    for section_index, section in enumerate(PHOTO_SECTIONS):
        for card_index, card in enumerate(section.get("cards", [])):
            filename = card.get("_cache_filename") or gallery_cache_filename(section_index, card_index, card)
            target = GALLERY_DIR / filename
            slots.append({
                "section_index": section_index,
                "card_index": card_index,
                "section": section,
                "card": card,
                "target": target,
                "filename": filename,
                "candidates": [
                    candidate for candidate in (card.get("_remote_candidates") or [card.get("src", ""), card.get("fallback", ""), card.get("fallback2", "")])
                    if _url_is_cacheable(str(candidate))
                ],
                "cacheable": _url_is_cacheable(str(card.get("_original_src") or card.get("src", ""))),
            })
    return slots


def run(only_missing=True, dry_run=False):
    slots = _slot_list()
    if dry_run:
        print("PataMahali gallery build plan")
        for section in PHOTO_SECTIONS:
            print(f"  {section.get('title')}: {len(section.get('cards', []))} cards")
        print(f"Total cards: {len(slots)}")
        print(f"Cache folder: {GALLERY_DIR}")
        print(f"Existing local cached images: {sum(s['target'].is_file() and s['target'].stat().st_size > 500 for s in slots)}")
        return 0

    results = {}
    pending = []
    for slot in slots:
        if only_missing and slot["target"].is_file() and slot["target"].stat().st_size > 500:
            results[slot["filename"]] = {"status": "cached", "url": "existing cache"}
        elif slot["cacheable"]:
            pending.append(slot)
        else:
            results[slot["filename"]] = {"status": "external_only", "url": slot["card"].get("_original_src") or slot["card"].get("src", "")}

    def work(slot):
        errors = []
        for url in slot["candidates"]:
            ok, result = _download_and_compress(str(url), slot["card"], slot["target"])
            if ok:
                return slot["filename"], {"status": "downloaded", "url": result}
            errors.append(f"{url}: {result}")
        return slot["filename"], {"status": "failed", "errors": errors[-3:]}

    # Parallel downloads keep the deployment build quick without overloading hosts.
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for filename, result in pool.map(work, pending):
            results[filename] = result
            if result["status"] == "downloaded":
                print(f"[image-cache] saved {filename} from {result['url']}")

    # Keep gallery cards visible when one or more source hosts reject hotlinking.
    # Prefer a different successfully cached photograph from the same category.
    category_successes = {}
    for slot in slots:
        item = results.get(slot["filename"], {})
        if item.get("status") in {"downloaded", "cached"} and slot["target"].is_file():
            category_successes.setdefault(slot["section_index"], []).append(slot["target"])
    for slot in slots:
        if slot["target"].is_file() and slot["target"].stat().st_size > 500:
            continue
        if not slot["cacheable"]:
            continue
        successful = category_successes.get(slot["section_index"], [])
        if successful:
            # Cycle through different successful photos to avoid one repeated image.
            donor = successful[slot["card_index"] % len(successful)]
            shutil.copyfile(donor, slot["target"])
            results[slot["filename"]] = {"status": "copied_category_fallback", "url": str(donor)}
            print(f"[image-cache] fallback copy for {slot['filename']} from {donor.name}")
        else:
            category = slot["section"].get("category", "residential")
            backup_names = {
                "residential": "apartment-building.webp", "short_stay": "modern-interior.webp",
                "commercial": "modern-interior.webp", "industrial": "apartment-building.webp",
                "land_sale": "residential-land.webp", "property_sale": "apartment-building.webp",
            }
            backup = ROOT / "static" / "img" / "property-scenes" / backup_names.get(category, "apartment-building.webp")
            if backup.is_file():
                with Image.open(backup) as source:
                    image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (640, 420), method=Image.Resampling.LANCZOS)
                    image.save(slot["target"], "WEBP", quality=64, method=6, optimize=True)
                results[slot["filename"]] = {"status": "local_scene_fallback", "url": str(backup)}

    manifest = []
    for slot in slots:
        entry = {
            "section": slot["section"].get("title"),
            "label": slot["card"].get("label"),
            "file": slot["filename"],
            "original_source": slot["card"].get("_original_src") or slot["card"].get("src"),
            "source_page": slot["card"].get("source_page"),
            "credit": slot["card"].get("credit"),
            "license": slot["card"].get("license"),
            "cached_locally_permitted": slot["cacheable"],
            **results.get(slot["filename"], {"status": "failed"}),
        }
        manifest.append(entry)
    manifest_path = GALLERY_DIR / "manifest.json"
    manifest_path.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cards": manifest}, indent=2, ensure_ascii=False), encoding="utf-8")

    success = sum(1 for slot in slots if slot["target"].is_file() and slot["target"].stat().st_size > 500)
    total_bytes = sum(slot["target"].stat().st_size for slot in slots if slot["target"].is_file())
    print(f"[image-cache] Ready: {success}/{len(slots)} images; {total_bytes / 1024 / 1024:.2f} MiB compressed WebP")
    print(f"[image-cache] Manifest: {manifest_path}")
    # A source-host outage must not break the whole site deployment.
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="redownload images even when a local copy exists")
    args = parser.parse_args()
    raise SystemExit(run(only_missing=not args.refresh, dry_run=args.dry_run))
