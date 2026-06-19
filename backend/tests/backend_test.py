"""Backend API tests for AI Ads Studio.
Covers: health, websites CRUD, scrape, ad generate (image only), ads CRUD,
filters, stats, meta-settings, media serving.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://smart-content-pub.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Health ----------------
class TestHealth:
    def test_root(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        body = r.json()
        assert "message" in body
        assert "AI Ads Studio" in body["message"]


# ---------------- Stats ----------------
class TestStats:
    def test_stats_shape(self, session):
        r = session.get(f"{API}/stats")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_ads", "drafts", "approved", "downloaded", "websites", "pending_videos"]:
            assert k in d, f"missing key {k}"
            assert isinstance(d[k], int)


# ---------------- Websites CRUD ----------------
class TestWebsites:
    created_id = None

    def test_create(self, session):
        payload = {"name": "TEST_collegeop", "url": "https://collegeop.com", "description": "TEST desc"}
        r = session.post(f"{API}/websites", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == payload["name"]
        assert d["url"] == payload["url"]
        assert "id" in d
        TestWebsites.created_id = d["id"]

    def test_list_contains(self, session):
        r = session.get(f"{API}/websites")
        assert r.status_code == 200
        ids = [w["id"] for w in r.json()]
        assert TestWebsites.created_id in ids

    def test_update(self, session):
        r = session.patch(f"{API}/websites/{TestWebsites.created_id}",
                          json={"description": "TEST updated"})
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "TEST updated"

    def test_update_not_found(self, session):
        r = session.patch(f"{API}/websites/nonexistent", json={"name": "x"})
        assert r.status_code == 404

    def test_delete(self, session):
        r = session.delete(f"{API}/websites/{TestWebsites.created_id}")
        assert r.status_code == 200
        # verify gone
        r2 = session.get(f"{API}/websites")
        ids = [w["id"] for w in r2.json()]
        assert TestWebsites.created_id not in ids

    def test_delete_not_found(self, session):
        r = session.delete(f"{API}/websites/does-not-exist")
        assert r.status_code == 404


# ---------------- Scrape ----------------
class TestScrape:
    def test_scrape_example(self, session):
        r = session.post(f"{API}/scrape", json={"url": "https://example.com"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "title" in d and "description" in d and "body" in d
        assert "Example" in d["title"]

    def test_scrape_bad_url(self, session):
        r = session.post(f"{API}/scrape", json={"url": "http://this-host-does-not-exist-xyz-12345.invalid"})
        assert r.status_code == 400


# ---------------- Meta Settings ----------------
class TestMetaSettings:
    def test_get_initial(self, session):
        r = session.get(f"{API}/meta-settings")
        assert r.status_code == 200
        d = r.json()
        for k in ["fb_access_token", "fb_page_id", "ig_account_id"]:
            assert k in d

    def test_put_and_persist(self, session):
        payload = {
            "fb_access_token": "TEST_fb_token_123",
            "fb_page_id": "TEST_page_456",
            "ig_account_id": "TEST_ig_789",
        }
        r = session.put(f"{API}/meta-settings", json=payload)
        assert r.status_code == 200, r.text
        # GET back
        r2 = session.get(f"{API}/meta-settings")
        d = r2.json()
        assert d["fb_access_token"] == payload["fb_access_token"]
        assert d["fb_page_id"] == payload["fb_page_id"]
        assert d["ig_account_id"] == payload["ig_account_id"]


# ---------------- Ad Generation (CRITICAL) ----------------
class TestAdGeneration:
    ad_id = None
    website_id = None

    def test_create_website_for_ad(self, session):
        r = session.post(f"{API}/websites", json={
            "name": "TEST_AdSite",
            "url": "https://example.com",
            "description": "site for ad gen tests",
        })
        assert r.status_code == 200
        TestAdGeneration.website_id = r.json()["id"]

    def test_generate_image_only(self, session):
        payload = {
            "website_id": TestAdGeneration.website_id,
            "topic": "Online coding bootcamp for college students",
            "include_image": True,
            "include_video": False,
        }
        r = session.post(f"{API}/ads/generate", json=payload, timeout=180)
        assert r.status_code == 200, f"Generate failed: {r.status_code} {r.text[:500]}"
        d = r.json()
        assert "id" in d
        assert d["caption"] and isinstance(d["caption"], str) and len(d["caption"]) > 5
        assert isinstance(d["hashtags"], list) and 5 <= len(d["hashtags"]) <= 20
        assert d["image_prompt"]
        assert d["image_path"], "image_path should be set"
        assert d["image_path"].startswith("images/")
        assert d["video_status"] == "none"
        assert d["status"] == "draft"
        TestAdGeneration.ad_id = d["id"]

    def test_image_served_via_api_media(self, session):
        assert TestAdGeneration.ad_id is not None
        url = f"{API}/media/images/{TestAdGeneration.ad_id}.png"
        r = session.get(url)
        assert r.status_code == 200, f"Media not served: {url}"
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 1000


# ---------------- Ads CRUD & Filters ----------------
class TestAdsCRUD:
    def test_get_by_id(self, session):
        ad_id = TestAdGeneration.ad_id
        assert ad_id
        r = session.get(f"{API}/ads/{ad_id}")
        assert r.status_code == 200
        assert r.json()["id"] == ad_id

    def test_list_all(self, session):
        r = session.get(f"{API}/ads")
        assert r.status_code == 200
        assert any(a["id"] == TestAdGeneration.ad_id for a in r.json())

    def test_filter_by_website(self, session):
        r = session.get(f"{API}/ads", params={"website_id": TestAdGeneration.website_id})
        assert r.status_code == 200
        ads = r.json()
        assert len(ads) >= 1
        for a in ads:
            assert a["website_id"] == TestAdGeneration.website_id

    def test_update_status_approved(self, session):
        ad_id = TestAdGeneration.ad_id
        r = session.patch(f"{API}/ads/{ad_id}/status", json={"status": "approved"})
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_filter_by_status_approved(self, session):
        r = session.get(f"{API}/ads", params={"status": "approved"})
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert TestAdGeneration.ad_id in ids
        for a in r.json():
            assert a["status"] == "approved"

    def test_download_image_marks_downloaded(self, session):
        ad_id = TestAdGeneration.ad_id
        r = session.get(f"{API}/ads/{ad_id}/download/image")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 1000
        # verify status auto-updated
        r2 = session.get(f"{API}/ads/{ad_id}")
        assert r2.json()["status"] == "downloaded"

    def test_delete_ad_and_files(self, session):
        ad_id = TestAdGeneration.ad_id
        r = session.delete(f"{API}/ads/{ad_id}")
        assert r.status_code == 200
        # verify gone
        r2 = session.get(f"{API}/ads/{ad_id}")
        assert r2.status_code == 404
        # image url should now 404
        r3 = session.get(f"{API}/media/images/{ad_id}.png")
        assert r3.status_code == 404

    def test_cleanup_website(self, session):
        r = session.delete(f"{API}/websites/{TestAdGeneration.website_id}")
        assert r.status_code == 200
