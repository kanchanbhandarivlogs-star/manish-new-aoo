"""Watermark service: fetches a website's logo and composites it onto an ad image.

Public API:
    fetch_website_logo_bytes(url) -> Optional[bytes]
    apply_logo_watermark(image_path, website_url, brand_text=None) -> None
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; AI-Ads-Studio/1.0)"
HTTP_TIMEOUT_SEC = 6
FONT_CANDIDATES: Tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
LOGO_RELATIVE_SIZE = 0.14  # ~14% of shorter side
TEXT_RELATIVE_SIZE = 0.028
MIN_LOGO_PX = 96
MIN_FONT_PX = 20
BADGE_ALPHA = 235
TEXT_COLOR = (20, 20, 20, 255)
GOOGLE_FAVICON_URL = "https://www.google.com/s2/favicons?domain={host}&sz=128"


# ---------- HTTP helpers ----------
def _http_get(url: str) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_SEC)
        return r
    except requests.RequestException:
        return None


def _is_valid_image_response(resp: Optional[requests.Response], min_bytes: int = 200) -> bool:
    if resp is None or not resp.ok or not resp.content or len(resp.content) <= min_bytes:
        return False
    ct = (resp.headers.get("content-type") or "").lower()
    return "image" in ct


# ---------- Logo sources ----------
def _icon_candidates_from_html(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    candidates: List[str] = []
    for tag in soup.find_all("link"):
        rel = tag.get("rel") or []
        if isinstance(rel, str):
            rel = [rel]
        rel_str = " ".join(rel).lower()
        if any(k in rel_str for k in ("apple-touch-icon", "icon")):
            href = tag.get("href")
            if href:
                candidates.append(urljoin(base_url, href))
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        candidates.append(urljoin(base_url, og["content"]))
    return candidates


def _fetch_from_html(website_url: str) -> Optional[bytes]:
    page = _http_get(website_url)
    if page is None or not page.ok:
        return None
    for candidate in _icon_candidates_from_html(page.text, website_url):
        r = _http_get(candidate)
        if _is_valid_image_response(r):
            return r.content
    return None


def _fetch_favicon_ico(website_url: str) -> Optional[bytes]:
    parsed = urlparse(website_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    r = _http_get(f"{parsed.scheme}://{parsed.netloc}/favicon.ico")
    return r.content if _is_valid_image_response(r) else None


def _fetch_google_favicon(website_url: str) -> Optional[bytes]:
    host = urlparse(website_url).netloc or website_url
    r = _http_get(GOOGLE_FAVICON_URL.format(host=host))
    if r is not None and r.ok and r.content and len(r.content) > 300:
        return r.content
    return None


def fetch_website_logo_bytes(website_url: str) -> Optional[bytes]:
    """Best-effort logo fetch: HTML icons → /favicon.ico → Google Favicon API."""
    for source in (_fetch_from_html, _fetch_favicon_ico, _fetch_google_favicon):
        try:
            data = source(website_url)
            if data:
                return data
        except Exception:  # noqa: BLE001
            logger.debug("logo source %s failed for %s", source.__name__, website_url, exc_info=True)
    return None


# ---------- Pillow rendering helpers ----------
def _load_logo_image(logo_bytes: Optional[bytes]):
    if not logo_bytes:
        return None
    try:
        from PIL import Image
        return Image.open(BytesIO(logo_bytes)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _resize_logo(logo_img, base_size: Tuple[int, int]):
    from PIL import Image
    target = max(MIN_LOGO_PX, int(min(base_size) * LOGO_RELATIVE_SIZE))
    ratio = target / max(logo_img.size)
    new_size = (max(1, int(logo_img.size[0] * ratio)), max(1, int(logo_img.size[1] * ratio)))
    return logo_img.resize(new_size, Image.LANCZOS)


def _load_brand_font(base_size: Tuple[int, int]):
    from PIL import ImageFont
    font_size = max(MIN_FONT_PX, int(min(base_size) * TEXT_RELATIVE_SIZE))
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, font_size)
    return ImageFont.load_default()


def _measure_text(text: str, font) -> Tuple[int, int]:
    from PIL import Image, ImageDraw
    tmp = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _compose_badge(logo_img, text: str, font, base_size: Tuple[int, int]):
    from PIL import Image, ImageDraw

    pad = max(10, int(min(base_size) * 0.012))
    gap = pad
    logo_w, logo_h = (logo_img.size if logo_img is not None else (0, 0))
    text_size = _measure_text(text, font) if text else (0, 0)

    content_w = logo_w + (gap if (logo_w and text_size[0]) else 0) + text_size[0]
    content_h = max(logo_h, text_size[1])
    if content_w == 0 or content_h == 0:
        return None

    badge_w = content_w + pad * 2
    badge_h = content_h + pad * 2
    badge = Image.new("RGBA", (badge_w, badge_h), (255, 255, 255, BADGE_ALPHA))

    cursor_x = pad
    if logo_img is not None:
        ly = pad + (content_h - logo_h) // 2
        badge.alpha_composite(logo_img, dest=(cursor_x, ly))
        cursor_x += logo_w + gap

    if text:
        ty = pad + (content_h - text_size[1]) // 2
        ImageDraw.Draw(badge).text((cursor_x, ty), text, fill=TEXT_COLOR, font=font)

    return badge


def apply_logo_watermark(
    image_path: Path,
    website_url: Optional[str],
    brand_text: Optional[str] = None,
    logo_file_path: Optional[Path] = None,
) -> None:
    """Composite the website's logo (and optional brand text) onto the bottom-right of the ad.
    Priority for the logo source:
        1) `logo_file_path` (user-uploaded HD logo) — highest quality
        2) Auto-fetched favicon/icon from `website_url`
        3) Text-only brand badge using `brand_text`
    """
    if not (website_url or brand_text or logo_file_path):
        return
    try:
        from PIL import Image

        base = Image.open(image_path).convert("RGBA")
        logo_img = None

        # 1) User-uploaded logo (preferred)
        if logo_file_path and Path(logo_file_path).exists():
            try:
                logo_img = Image.open(logo_file_path).convert("RGBA")
            except Exception:  # noqa: BLE001
                logo_img = None

        # 2) Fallback to auto-fetched favicon
        if logo_img is None and website_url:
            logo_img = _load_logo_image(fetch_website_logo_bytes(website_url))

        if logo_img is not None:
            logo_img = _resize_logo(logo_img, base.size)

        text = (brand_text or "").strip()
        font = _load_brand_font(base.size) if text else None

        badge = _compose_badge(logo_img, text, font, base.size)
        if badge is None:
            return

        margin = max(16, int(min(base.size) * 0.025))
        # Bottom-right placement (safest — Sora/Nano-Banana rarely render copy in this corner)
        pos = (base.size[0] - badge.size[0] - margin, base.size[1] - badge.size[1] - margin)
        base.alpha_composite(badge, dest=pos)
        base.convert("RGB").save(image_path, format="PNG")
    except Exception:  # noqa: BLE001
        logger.exception("Watermark failed for %s", website_url)


def build_video_watermark_overlay(
    website_url: Optional[str],
    brand_text: Optional[str],
    logo_file_path: Optional[Path],
    out_png_path: Path,
) -> Optional[Tuple[int, int]]:
    """Render a single watermark badge PNG (logo + optional brand text) and save it.

    Returns the (width, height) of the rendered badge so the caller can compute the
    correct ffmpeg overlay position. Returns None if no logo/text could be sourced.
    """
    from PIL import Image

    logo_img = None
    if logo_file_path and Path(logo_file_path).exists():
        try:
            logo_img = Image.open(logo_file_path).convert("RGBA")
        except Exception:  # noqa: BLE001
            logo_img = None
    if logo_img is None and website_url:
        logo_img = _load_logo_image(fetch_website_logo_bytes(website_url))

    # Size the logo using a fixed reference (720x1280 portrait — Sora 2 default)
    # so the badge looks consistent regardless of the real video dimensions; ffmpeg
    # will scale it via the overlay filter if needed.
    base_size = (720, 1280)
    if logo_img is not None:
        logo_img = _resize_logo(logo_img, base_size)

    text = (brand_text or "").strip()
    font = _load_brand_font(base_size) if text else None
    badge = _compose_badge(logo_img, text, font, base_size)
    if badge is None:
        return None
    badge.save(out_png_path, format="PNG")
    return badge.size
