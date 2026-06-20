"""Tests for the NEW features:
- /api/scheduler/status
- Website auto_generate flag (CRUD)
- /api/ads/{id}/variants (A/B variant)
- /api/ads/{id}/publish (validation + structured error path)
"""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Scheduler ----------------
class TestSchedulerStatus:
    def test_scheduler_status_shape(self, session):
        r = session.get(f"{API}/scheduler/status")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["peak_hours_utc"] == [9, 13, 18]
        assert isinstance(d["current_hour_utc"], int)
        assert 0 <= d["current_hour_utc"] <= 23
        assert isinstance(d["is_peak_now"], bool)
        assert isinstance(d["websites_opted_in"], int)
        assert d["is_peak_now"] == (d["current_hour_utc"] in (9, 13, 18))


# ---------------- Website auto_generate flag ----------------
class TestWebsiteAutoGenerate:
    wid = None

    def test_create_with_auto_generate(self, session):
        r = session.post(f"{API}/websites", json={
            "name": "TEST_AutoGenSite",
            "url": "https://example.com",
            "description": "test",
            "auto_generate": True,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["auto_generate"] is True
        assert "last_auto_run_at" in d
        TestWebsiteAutoGenerate.wid = d["id"]

    def test_get_includes_auto_generate(self, session):
        r = session.get(f"{API}/websites")
        assert r.status_code == 200
        match = next((w for w in r.json() if w["id"] == TestWebsiteAutoGenerate.wid), None)
        assert match is not None
        assert match["auto_generate"] is True

    def test_scheduler_count_increments(self, session):
        r = session.get(f"{API}/scheduler/status")
        assert r.json()["websites_opted_in"] >= 1

    def test_patch_toggle_off(self, session):
        r = session.patch(
            f"{API}/websites/{TestWebsiteAutoGenerate.wid}",
            json={"auto_generate": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["auto_generate"] is False

    def test_patch_toggle_on_again(self, session):
        r = session.patch(
            f"{API}/websites/{TestWebsiteAutoGenerate.wid}",
            json={"auto_generate": True},
        )
        assert r.status_code == 200
        assert r.json()["auto_generate"] is True

    def test_cleanup(self, session):
        r = session.delete(f"{API}/websites/{TestWebsiteAutoGenerate.wid}")
        assert r.status_code == 200


# ---------------- Variants + Publish (CRITICAL) ----------------
class TestVariantAndPublish:
    parent_id = None
    variant_id = None

    def test_create_parent_ad(self, session):
        r = session.post(f"{API}/ads/generate", json={
            "topic": "TEST_parent_variant_topic Online coding bootcamp",
            "include_image": True,
            "include_video": False,
        }, timeout=180)
        assert r.status_code == 200, f"parent generate failed: {r.text[:500]}"
        d = r.json()
        assert d["image_path"], "parent must have image_path"
        assert d["parent_ad_id"] is None
        assert d["published_to"] == []
        TestVariantAndPublish.parent_id = d["id"]
        TestVariantAndPublish.parent_caption = d["caption"]
        TestVariantAndPublish.parent_image = d["image_path"]

    def test_variant_generation(self, session):
        assert TestVariantAndPublish.parent_id
        r = session.post(
            f"{API}/ads/{TestVariantAndPublish.parent_id}/variants",
            timeout=180,
        )
        assert r.status_code == 200, f"variant failed: {r.text[:500]}"
        v = r.json()
        # Different ID
        assert v["id"] != TestVariantAndPublish.parent_id
        # parent_ad_id linked
        assert v["parent_ad_id"] == TestVariantAndPublish.parent_id
        # status draft
        assert v["status"] == "draft"
        # caption different
        assert v["caption"] and v["caption"] != TestVariantAndPublish.parent_caption
        # image fresh
        assert v["image_path"]
        assert v["image_path"] != TestVariantAndPublish.parent_image
        TestVariantAndPublish.variant_id = v["id"]

    def test_variant_image_served(self, session):
        url = f"{API}/media/images/{TestVariantAndPublish.variant_id}.png"
        r = session.get(url)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 1000

    # ----- publish path (uses parent ad) -----
    def test_publish_without_token_returns_400(self, session):
        # First clear settings token
        session.put(f"{API}/meta-settings", json={
            "fb_access_token": "",
            "fb_page_id": "",
            "ig_account_id": "",
        })
        r = session.post(
            f"{API}/ads/{TestVariantAndPublish.parent_id}/publish",
            json={"platforms": ["facebook"]},
        )
        assert r.status_code == 400, r.text
        assert "FB Access Token" in r.json().get("detail", "")

    def test_publish_with_fake_token_returns_502_not_500(self, session):
        # Set fake token + page id
        session.put(f"{API}/meta-settings", json={
            "fb_access_token": "FAKE_TOKEN_xyz",
            "fb_page_id": "FAKE_PAGE_123",
            "ig_account_id": "FAKE_IG_456",
        })
        r = session.post(
            f"{API}/ads/{TestVariantAndPublish.parent_id}/publish",
            json={"platforms": ["facebook"]},
            timeout=60,
        )
        # NOTE: Backend raises HTTPException(502, "Facebook publish failed: ...")
        # but Cloudflare strips upstream 502 bodies & replaces with HTML Bad-Gateway
        # page. We accept either: a JSON 400/502 with detail, OR a CF-intercepted
        # 502 HTML page. Either way it MUST NOT be a 500 crash.
        assert r.status_code != 500, f"got 500 crash: {r.text[:300]}"
        assert r.status_code in (400, 502), f"got {r.status_code}: {r.text[:300]}"

    def test_ad_published_to_still_empty(self, session):
        r = session.get(f"{API}/ads/{TestVariantAndPublish.parent_id}")
        assert r.status_code == 200
        assert r.json().get("published_to", []) == []

    # ----- cleanup -----
    def test_cleanup_parent(self, session):
        r = session.delete(f"{API}/ads/{TestVariantAndPublish.parent_id}")
        assert r.status_code == 200

    def test_cleanup_variant(self, session):
        if TestVariantAndPublish.variant_id:
            r = session.delete(f"{API}/ads/{TestVariantAndPublish.variant_id}")
            assert r.status_code == 200

    def test_cleanup_meta_settings(self, session):
        # reset to empty so future runs are clean
        r = session.put(f"{API}/meta-settings", json={
            "fb_access_token": "",
            "fb_page_id": "",
            "ig_account_id": "",
        })
        assert r.status_code == 200
