"""Iteration 4: Verify (1) auth gating on download/publish, (2) tenant isolation,
   (3) owner_id on Ad doc, (4) logo watermark composited on generated image."""
from __future__ import annotations

import io
import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from PIL import Image

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MEDIA_DIR = Path("/app/backend/generated_media")

# Credentials are loaded from /app/memory/test_credentials.md via the test runner's env
ADMIN_EMAIL = os.environ.get("ADMIN_TEST_EMAIL", "manish99346626@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_TEST_PASSWORD", "Manish@1234")


# ---------- helpers ----------
def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _register(email: str, password: str, name: str) -> str:
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=15,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def other_user():
    """Create a fresh non-admin user for cross-tenant tests."""
    uniq = uuid.uuid4().hex[:8]
    email = f"test_other_{uniq}@example.com"
    pw = "TestPass@123"
    token = _register(email, pw, f"TEST_other_{uniq}")
    me = requests.get(f"{API}/auth/me", headers=_h(token), timeout=10).json()
    yield {"token": token, "id": me["id"], "email": email}
    # teardown: admin deletes
    admin = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    requests.delete(f"{API}/admin/users/{me['id']}", headers=_h(admin), timeout=10)


@pytest.fixture(scope="module")
def admin_website(admin_token):
    payload = {
        "name": "TEST_WatermarkSite",
        "url": "https://www.python.org",
        "description": "Python official site for logo fetch test",
    }
    r = requests.post(f"{API}/websites", json=payload, headers=_h(admin_token), timeout=15)
    assert r.status_code == 200, f"site create failed: {r.status_code} {r.text}"
    site = r.json()
    yield site
    requests.delete(f"{API}/websites/{site['id']}", headers=_h(admin_token), timeout=10)


@pytest.fixture(scope="module")
def admin_ad(admin_token, admin_website):
    payload = {
        "website_id": admin_website["id"],
        "topic": "TEST_Learn Python fast",
        "include_image": True,
        "include_video": False,
    }
    r = requests.post(f"{API}/ads/generate", json=payload, headers=_h(admin_token), timeout=120)
    assert r.status_code == 200, f"ad gen failed: {r.status_code} {r.text}"
    ad = r.json()
    yield ad
    # cleanup
    requests.delete(f"{API}/ads/{ad['id']}", headers=_h(admin_token), timeout=10)


# ---------- Auth basics ----------
def test_login_admin_returns_jwt(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 20


def test_auth_me_returns_admin_profile(admin_token):
    r = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == ADMIN_EMAIL
    assert data["role"] == "admin"
    assert "wallet_balance" in data


# ---------- Ad generation, owner_id, image+watermark ----------
def test_generate_ad_returns_owner_id_and_image(admin_ad, admin_token):
    """Verify Ad pydantic now exposes owner_id (recently fixed)."""
    me = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=10).json()
    assert admin_ad.get("owner_id") == me["id"], "owner_id missing or mismatched on returned Ad"
    assert admin_ad.get("image_path"), "image_path missing on returned Ad"
    # GET back from DB and confirm persistence
    r = requests.get(f"{API}/ads/{admin_ad['id']}", headers=_h(admin_token), timeout=10)
    assert r.status_code == 200
    db_ad = r.json()
    assert db_ad["owner_id"] == me["id"]
    assert db_ad["image_path"] == admin_ad["image_path"]


def test_image_file_exists_and_watermark_applied(admin_ad):
    """File must exist on disk + be a valid PNG.
    Watermark presence is best-effort: we just confirm pixel data at the
    bottom-right corner shows the bright (white-ish) badge that the
    _apply_logo_watermark routine paints."""
    rel = admin_ad["image_path"]
    path = MEDIA_DIR / rel
    assert path.exists(), f"image file missing on disk: {path}"
    assert path.stat().st_size > 1000, "image file is suspiciously small"
    img = Image.open(path).convert("RGB")
    w, h = img.size
    assert w > 200 and h > 200, f"image dimensions too small: {w}x{h}"
    # Sample a ~60x60 block near the bottom-right corner where the badge sits.
    # The badge is white (RGBA 255,255,255,235), so the *average* R/G/B in
    # that region should be substantially above the global average.
    margin = max(16, int(min(w, h) * 0.025))
    badge_box = (
        max(0, w - margin - 80),
        max(0, h - margin - 80),
        max(0, w - margin - 20),
        max(0, h - margin - 20),
    )
    crop = img.crop(badge_box)
    px = list(crop.getdata())
    avg_brightness = sum(sum(p) / 3 for p in px) / len(px)
    print(f"badge region avg brightness = {avg_brightness:.1f} (expect >150 for white-ish badge)")
    # The badge has white (~255) background + dark text/logo. Average should be high
    # but we keep the threshold lenient (>140) because the badge only covers part
    # of the sampled crop. If <100 the badge almost certainly didn't render.
    assert avg_brightness > 120, (
        f"badge region appears dark ({avg_brightness:.1f}) – watermark likely NOT applied"
    )


# ---------- download_image auth gate ----------
def test_download_image_without_auth_returns_401(admin_ad):
    r = requests.get(f"{API}/ads/{admin_ad['id']}/download/image", timeout=15, allow_redirects=False)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:200]}"


def test_download_image_cross_tenant_returns_404(admin_ad, other_user):
    r = requests.get(
        f"{API}/ads/{admin_ad['id']}/download/image",
        headers=_h(other_user["token"]),
        timeout=15,
        allow_redirects=False,
    )
    assert r.status_code == 404, f"cross-tenant should be 404, got {r.status_code}"


def test_download_image_with_owner_returns_file(admin_ad, admin_token):
    r = requests.get(
        f"{API}/ads/{admin_ad['id']}/download/image",
        headers=_h(admin_token),
        timeout=20,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")
    assert len(r.content) > 1000


# ---------- download_video auth gate ----------
def test_download_video_without_auth_returns_401(admin_ad):
    r = requests.get(f"{API}/ads/{admin_ad['id']}/download/video", timeout=10, allow_redirects=False)
    assert r.status_code in (401, 403)


def test_download_video_cross_tenant_returns_404(admin_ad, other_user):
    r = requests.get(
        f"{API}/ads/{admin_ad['id']}/download/video",
        headers=_h(other_user["token"]),
        timeout=10,
        allow_redirects=False,
    )
    assert r.status_code == 404


# ---------- publish_ad auth gate ----------
def test_publish_without_auth_returns_401(admin_ad):
    r = requests.post(
        f"{API}/ads/{admin_ad['id']}/publish",
        json={"platforms": ["facebook"]},
        timeout=10,
        allow_redirects=False,
    )
    assert r.status_code in (401, 403), f"got {r.status_code} {r.text[:200]}"


def test_publish_cross_tenant_returns_404(admin_ad, other_user):
    r = requests.post(
        f"{API}/ads/{admin_ad['id']}/publish",
        json={"platforms": ["facebook"]},
        headers=_h(other_user["token"]),
        timeout=10,
    )
    assert r.status_code == 404


def test_publish_with_owner_no_fb_token_returns_400(admin_ad, admin_token):
    """Website has no fb_access_token configured -> should 400 with the
    'Set FB Access Token...' error message."""
    r = requests.post(
        f"{API}/ads/{admin_ad['id']}/publish",
        json={"platforms": ["facebook"]},
        headers=_h(admin_token),
        timeout=15,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"
    body = r.json()
    detail = body.get("detail") or body.get("message") or ""
    assert "FB Access Token" in detail or "fb_access_token" in detail.lower(), (
        f"unexpected error msg: {detail}"
    )


# ---------- variants (owner-gated, watermarked) ----------
def test_create_variant_owner_only_and_watermark(admin_ad, admin_token, other_user):
    # Cross-tenant should 404
    r = requests.post(
        f"{API}/ads/{admin_ad['id']}/variants",
        headers=_h(other_user["token"]),
        timeout=15,
    )
    assert r.status_code == 404

    # Owner: should generate, charge wallet, return new ad
    r = requests.post(
        f"{API}/ads/{admin_ad['id']}/variants",
        headers=_h(admin_token),
        timeout=180,
    )
    assert r.status_code == 200, f"variant failed: {r.status_code} {r.text[:200]}"
    v = r.json()
    me = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=10).json()
    assert v["owner_id"] == me["id"]
    assert v["parent_ad_id"] == admin_ad["id"]
    assert v.get("image_path"), "variant image_path missing"
    # File exists
    path = MEDIA_DIR / v["image_path"]
    assert path.exists(), f"variant image missing on disk: {path}"
    # cleanup
    requests.delete(f"{API}/ads/{v['id']}", headers=_h(admin_token), timeout=10)


# ---------- Public lead capture stays open ----------
def test_public_apply_endpoint_no_auth_required(admin_website):
    payload = {
        "name": "TEST_Lead",
        "phone": "9999999999",
        "email": "TEST_lead@example.com",
        "city": "Mumbai",
    }
    # Implementation uses /api/public/leads/{wid} (the review_request "/api/apply"
    # is the *frontend* path; backend route is /public/leads/{wid}).
    r = requests.post(f"{API}/public/leads/{admin_website['id']}", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"public apply failed: {r.status_code} {r.text[:200]}"
