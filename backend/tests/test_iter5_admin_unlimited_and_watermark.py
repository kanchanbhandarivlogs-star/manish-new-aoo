"""Iteration 5 backend tests.

Covers the iter-5 changes:
  (1) Admin wallet is unlimited:
        - GET /api/wallet returns unlimited:true for admin
        - admin balance does NOT decrease after ad generation
        - admin balance does NOT decrease after variant creation
  (2) Non-admin user IS charged on /api/ads/generate
  (3) services.watermark module exists & is importable;
        - fetch_website_logo_bytes('https://www.google.com') returns bytes > 300
        - apply_logo_watermark mutates the source PNG (size changes)
  (4) Watermark is still applied through the new module on real ad-gen output
  (5) Auth gates remain enforced on download/publish
"""
from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from PIL import Image, ImageDraw

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MEDIA_DIR = Path("/app/backend/generated_media")

ADMIN_EMAIL = os.environ.get("ADMIN_TEST_EMAIL", "manish99346626@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_TEST_PASSWORD", "Manish@1234")


# ---------- helpers ----------
def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _register(email: str, password: str, name: str) -> str:
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def admin_website(admin_token):
    payload = {
        "name": "TEST_Iter5Site",
        "url": "https://www.python.org",
        "description": "TEST iter5 site",
    }
    r = requests.post(f"{API}/websites", json=payload, headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, f"site create failed: {r.status_code} {r.text}"
    site = r.json()
    yield site
    requests.delete(f"{API}/websites/{site['id']}", headers=_h(admin_token), timeout=10)


@pytest.fixture(scope="module")
def other_user(admin_token):
    uniq = uuid.uuid4().hex[:8]
    email = f"test_iter5_{uniq}@example.com"
    pw = "TestPass@123"
    token = _register(email, pw, f"TEST_iter5_{uniq}")
    me = requests.get(f"{API}/auth/me", headers=_h(token), timeout=10).json()
    yield {"token": token, "id": me["id"], "email": email}
    # admin deletes
    requests.delete(
        f"{API}/admin/users/{me['id']}", headers=_h(admin_token), timeout=10
    )


@pytest.fixture(scope="module")
def other_user_website(other_user):
    payload = {
        "name": "TEST_Iter5OtherSite",
        "url": "https://www.python.org",
        "description": "TEST iter5 site",
    }
    r = requests.post(f"{API}/websites", json=payload, headers=_h(other_user["token"]), timeout=20)
    assert r.status_code == 200, f"site create failed: {r.status_code} {r.text}"
    site = r.json()
    yield site
    requests.delete(f"{API}/websites/{site['id']}", headers=_h(other_user["token"]), timeout=10)


# =========================================================================
# (3) services.watermark module – pure unit-level tests (no HTTP)
# =========================================================================
class TestWatermarkServiceModule:
    """Validate the new /app/backend/services/watermark.py module is correct
    and replaces the inline logic faithfully."""

    def test_module_path_exists(self):
        p = Path("/app/backend/services/watermark.py")
        assert p.exists(), "/app/backend/services/watermark.py is missing"
        # init
        assert Path("/app/backend/services/__init__.py").exists(), "services/__init__.py missing"

    def test_module_importable_and_has_public_api(self):
        # ensure /app/backend is on path
        sys.path.insert(0, "/app/backend")
        mod = importlib.import_module("services.watermark")
        importlib.reload(mod)
        assert hasattr(mod, "fetch_website_logo_bytes"), "fetch_website_logo_bytes missing"
        assert hasattr(mod, "apply_logo_watermark"), "apply_logo_watermark missing"

    def test_fetch_website_logo_bytes_google(self):
        sys.path.insert(0, "/app/backend")
        from services.watermark import fetch_website_logo_bytes  # type: ignore

        data = fetch_website_logo_bytes("https://www.google.com")
        assert data is not None, "fetch_website_logo_bytes returned None for google.com"
        assert isinstance(data, (bytes, bytearray))
        assert len(data) > 300, f"logo bytes too small: {len(data)}"

    def test_apply_logo_watermark_modifies_file(self, tmp_path):
        sys.path.insert(0, "/app/backend")
        from services.watermark import apply_logo_watermark  # type: ignore

        # Make a plain solid-color PNG so we can verify the badge area changes.
        sample = tmp_path / "sample.png"
        img = Image.new("RGB", (800, 800), (40, 60, 90))  # dark navy
        ImageDraw.Draw(img).rectangle([0, 0, 800, 800], fill=(40, 60, 90))
        img.save(sample, format="PNG")
        before_size = sample.stat().st_size
        before_img = Image.open(sample).convert("RGB")
        # Sample a region within the badge area (badge sits in bottom-right with
        # ~20 px margin and is ~160-200 px wide).
        sample_box = (600, 700, 770, 770)
        before_avg = sum(sum(p) / 3 for p in before_img.crop(sample_box).getdata()) / (
            (sample_box[2] - sample_box[0]) * (sample_box[3] - sample_box[1])
        )

        apply_logo_watermark(sample, "https://www.google.com", brand_text="TestBrand")

        after_size = sample.stat().st_size
        after_img = Image.open(sample).convert("RGB")
        after_avg = sum(sum(p) / 3 for p in after_img.crop(sample_box).getdata()) / (
            (sample_box[2] - sample_box[0]) * (sample_box[3] - sample_box[1])
        )
        print(
            f"watermark: size {before_size}->{after_size} | "
            f"br-region avg {before_avg:.1f}->{after_avg:.1f}"
        )
        assert after_size > before_size + 2000, (
            f"file size barely changed – watermark likely didn't write "
            f"(before={before_size}, after={after_size})"
        )
        assert after_avg > before_avg + 30, (
            f"badge region not brightened: before={before_avg:.1f} after={after_avg:.1f}"
        )


# =========================================================================
# (1) Admin wallet unlimited
# =========================================================================
class TestAdminUnlimitedWallet:
    def test_admin_wallet_endpoint_returns_unlimited_true(self, admin_token):
        r = requests.get(f"{API}/wallet", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, f"wallet failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("unlimited") is True, f"admin should have unlimited:true, got {body}"
        assert "balance" in body
        assert isinstance(body["balance"], (int, float))
        assert "pricing" in body and isinstance(body["pricing"], dict)

    def test_admin_balance_unchanged_after_ad_generation(self, admin_token, admin_website):
        before = requests.get(f"{API}/wallet", headers=_h(admin_token), timeout=10).json()
        b_before = before["balance"]
        payload = {
            "website_id": admin_website["id"],
            "topic": "TEST_iter5_admin_unlimited",
            "include_image": True,
            "include_video": False,
        }
        r = requests.post(f"{API}/ads/generate", json=payload, headers=_h(admin_token), timeout=180)
        assert r.status_code == 200, f"ad gen failed: {r.status_code} {r.text[:200]}"
        ad = r.json()
        after = requests.get(f"{API}/wallet", headers=_h(admin_token), timeout=10).json()
        b_after = after["balance"]
        print(f"admin wallet before={b_before} after={b_after}")
        assert b_after == b_before, (
            f"admin balance changed despite unlimited rule: {b_before} -> {b_after}"
        )
        # Audit: confirm txn was logged with amount=0 and 'admin — free' tag
        txns = after.get("transactions", [])
        free_admin_txns = [
            t for t in txns
            if t.get("amount") == 0 and "admin" in (t.get("reason") or "").lower()
        ]
        assert free_admin_txns, "expected admin free-charge txn with amount=0 in wallet history"
        # cleanup
        requests.delete(f"{API}/ads/{ad['id']}", headers=_h(admin_token), timeout=10)

    def test_admin_balance_unchanged_after_variant(self, admin_token, admin_website):
        # create parent ad
        payload = {
            "website_id": admin_website["id"],
            "topic": "TEST_iter5_admin_variant_parent",
            "include_image": True,
            "include_video": False,
        }
        r = requests.post(f"{API}/ads/generate", json=payload, headers=_h(admin_token), timeout=180)
        assert r.status_code == 200, f"parent gen failed: {r.text[:200]}"
        parent = r.json()
        b_before = requests.get(f"{API}/wallet", headers=_h(admin_token), timeout=10).json()["balance"]
        r2 = requests.post(
            f"{API}/ads/{parent['id']}/variants", headers=_h(admin_token), timeout=180
        )
        assert r2.status_code == 200, f"variant failed: {r2.status_code} {r2.text[:200]}"
        v = r2.json()
        b_after = requests.get(f"{API}/wallet", headers=_h(admin_token), timeout=10).json()["balance"]
        print(f"admin variant wallet before={b_before} after={b_after}")
        assert b_after == b_before, (
            f"admin balance changed on variant: {b_before} -> {b_after}"
        )
        # cleanup
        requests.delete(f"{API}/ads/{v['id']}", headers=_h(admin_token), timeout=10)
        requests.delete(f"{API}/ads/{parent['id']}", headers=_h(admin_token), timeout=10)


# =========================================================================
# (2) Non-admin user IS charged
# =========================================================================
class TestNonAdminCharged:
    def test_non_admin_wallet_returns_unlimited_false(self, other_user):
        r = requests.get(f"{API}/wallet", headers=_h(other_user["token"]), timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("unlimited") is False, f"non-admin should not be unlimited: {body}"

    def test_topup_then_ad_gen_decreases_balance(self, admin_token, other_user, other_user_website):
        # Top-up via the actual admin endpoint: POST /api/admin/wallet/topup
        topup_amount = 50
        r = requests.post(
            f"{API}/admin/wallet/topup",
            json={"user_id": other_user["id"], "amount": topup_amount, "note": "TEST_iter5"},
            headers=_h(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, f"topup failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("wallet_balance", 0) >= topup_amount, (
            f"topup didn't credit: {body}"
        )

        # Now generate an ad as this user — image cost is 5 credits
        before = requests.get(f"{API}/wallet", headers=_h(other_user["token"]), timeout=10).json()
        b_before = before["balance"]
        pricing = before["pricing"]
        image_cost = int(pricing.get("image", 5))

        payload = {
            "website_id": other_user_website["id"],
            "topic": "TEST_iter5_charge_check",
            "include_image": True,
            "include_video": False,
        }
        r = requests.post(
            f"{API}/ads/generate", json=payload, headers=_h(other_user["token"]), timeout=180
        )
        assert r.status_code == 200, f"non-admin ad gen failed: {r.status_code} {r.text[:200]}"
        ad = r.json()

        after = requests.get(f"{API}/wallet", headers=_h(other_user["token"]), timeout=10).json()
        b_after = after["balance"]
        print(f"non-admin wallet before={b_before} after={b_after} cost={image_cost}")
        assert b_after == b_before - image_cost, (
            f"non-admin expected {b_before - image_cost}, got {b_after}"
        )
        # txn history shows a negative txn
        neg = [t for t in after.get("transactions", []) if t.get("amount") == -image_cost]
        assert neg, "no negative wallet txn recorded for non-admin"
        requests.delete(
            f"{API}/ads/{ad['id']}", headers=_h(other_user["token"]), timeout=10
        )


# =========================================================================
# (4) Real ad-gen output still receives watermark via the new module
# =========================================================================
class TestAdGenStillWatermarked:
    def test_generated_ad_image_has_bright_badge_bottom_right(self, admin_token, admin_website):
        payload = {
            "website_id": admin_website["id"],
            "topic": "TEST_iter5_watermark_visual",
            "include_image": True,
            "include_video": False,
        }
        r = requests.post(f"{API}/ads/generate", json=payload, headers=_h(admin_token), timeout=180)
        assert r.status_code == 200, f"ad gen failed: {r.status_code} {r.text[:200]}"
        ad = r.json()
        try:
            path = MEDIA_DIR / ad["image_path"]
            assert path.exists(), f"image file missing: {path}"
            assert path.stat().st_size > 5000, "image file suspiciously small"
            img = Image.open(path).convert("RGB")
            w, h = img.size
            assert w > 200 and h > 200
            # Sample badge area in bottom-right corner
            margin = max(16, int(min(w, h) * 0.025))
            box = (
                max(0, w - margin - 90),
                max(0, h - margin - 90),
                max(0, w - margin - 20),
                max(0, h - margin - 20),
            )
            crop = img.crop(box)
            px = list(crop.getdata())
            avg = sum(sum(p) / 3 for p in px) / len(px)
            print(f"iter5 badge region avg brightness = {avg:.1f}")
            assert avg > 120, (
                f"watermark badge appears missing on ad image (avg={avg:.1f})"
            )
        finally:
            requests.delete(f"{API}/ads/{ad['id']}", headers=_h(admin_token), timeout=10)


# =========================================================================
# (5) Auth/tenant gates still enforced
# =========================================================================
class TestAuthGatesStillEnforced:
    @pytest.fixture(scope="class")
    def shared_admin_ad(self, admin_token, admin_website):
        payload = {
            "website_id": admin_website["id"],
            "topic": "TEST_iter5_gate_ad",
            "include_image": True,
            "include_video": False,
        }
        r = requests.post(f"{API}/ads/generate", json=payload, headers=_h(admin_token), timeout=180)
        assert r.status_code == 200, f"setup ad gen failed: {r.status_code} {r.text[:200]}"
        ad = r.json()
        yield ad
        requests.delete(f"{API}/ads/{ad['id']}", headers=_h(admin_token), timeout=10)

    def test_download_image_no_auth_returns_401_or_403(self, shared_admin_ad):
        r = requests.get(
            f"{API}/ads/{shared_admin_ad['id']}/download/image",
            timeout=15,
            allow_redirects=False,
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_download_image_cross_tenant_returns_404(self, shared_admin_ad, other_user):
        r = requests.get(
            f"{API}/ads/{shared_admin_ad['id']}/download/image",
            headers=_h(other_user["token"]),
            timeout=15,
            allow_redirects=False,
        )
        assert r.status_code == 404, f"cross-tenant expected 404, got {r.status_code}"

    def test_download_image_owner_returns_file(self, shared_admin_ad, admin_token):
        r = requests.get(
            f"{API}/ads/{shared_admin_ad['id']}/download/image",
            headers=_h(admin_token),
            timeout=20,
        )
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 1000

    def test_publish_no_auth_returns_401_or_403(self, shared_admin_ad):
        r = requests.post(
            f"{API}/ads/{shared_admin_ad['id']}/publish",
            json={"platforms": ["facebook"]},
            timeout=15,
            allow_redirects=False,
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_publish_owner_without_fb_token_returns_400(self, shared_admin_ad, admin_token):
        r = requests.post(
            f"{API}/ads/{shared_admin_ad['id']}/publish",
            json={"platforms": ["facebook"]},
            headers=_h(admin_token),
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"
        body = r.json()
        detail = body.get("detail") or body.get("message") or ""
        assert "FB Access Token" in detail or "fb_access_token" in detail.lower(), detail
