"""Multi-tenant AI Ads Studio backend tests (iteration 3)."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://smart-content-pub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("ADMIN_TEST_EMAIL", "manish99346626@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_TEST_PASSWORD", "Manish@1234")

# Track created users for cleanup
_created_user_ids: list[str] = []


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------- FIXTURES ----------------
@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["user"]["role"] == "admin"
    return data["token"]


def _make_user(admin_token: str, suffix: str, password: str = "Test@1234") -> dict:
    email = f"TEST_{suffix}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(
        f"{API}/admin/users",
        json={"email": email, "password": password, "name": f"Test {suffix}"},
        headers=_auth_headers(admin_token),
        timeout=15,
    )
    assert r.status_code == 200, f"Create user failed: {r.text}"
    u = r.json()
    _created_user_ids.append(u["id"])
    # Now login as user
    lr = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert lr.status_code == 200, lr.text
    return {"id": u["id"], "email": email, "password": password, "token": lr.json()["token"]}


@pytest.fixture(scope="module")
def user_a(admin_token):
    return _make_user(admin_token, "userA")


@pytest.fixture(scope="module")
def user_b(admin_token):
    return _make_user(admin_token, "userB")


# ---------------- TESTS ----------------
class TestBranding:
    def test_branding(self):
        r = requests.get(f"{API}/branding", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("creator") == "Manish Kumar"
        assert d.get("company") == "CollegeOp.com"


class TestAuth:
    def test_admin_login(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_auth_headers(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "admin"
        assert d["email"] == ADMIN_EMAIL
        assert d["wallet_balance"] == 10000

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_root_public(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200


class TestAuthGating:
    """All listed endpoints must return 401 without bearer token."""
    @pytest.mark.parametrize("method,path", [
        ("GET", "/websites"),
        ("POST", "/websites"),
        ("GET", "/ads"),
        ("POST", "/ads/generate"),
        ("GET", "/leads"),
        ("GET", "/wallet"),
        ("GET", "/stats"),
        ("GET", "/scheduler/status"),
        ("GET", "/admin/users"),
        ("POST", "/admin/users"),
        ("POST", "/admin/wallet/topup"),
    ])
    def test_requires_auth(self, method, path):
        r = requests.request(method, f"{API}{path}", json={}, timeout=10)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code} (expected 401)"


class TestAdminGate:
    def test_non_admin_cannot_list_users(self, user_a):
        r = requests.get(f"{API}/admin/users", headers=_auth_headers(user_a["token"]), timeout=10)
        assert r.status_code == 403

    def test_non_admin_cannot_topup(self, user_a, user_b):
        r = requests.post(
            f"{API}/admin/wallet/topup",
            json={"user_id": user_b["id"], "amount": 100},
            headers=_auth_headers(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 403


class TestAdminUserCRUD:
    def test_list_users(self, admin_token):
        r = requests.get(f"{API}/admin/users", headers=_auth_headers(admin_token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert any(u["role"] == "admin" for u in r.json())

    def test_create_user_zero_balance(self, admin_token):
        email = f"TEST_zerobalance_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(
            f"{API}/admin/users",
            json={"email": email, "password": "Test@1234", "name": "Zero Bal"},
            headers=_auth_headers(admin_token),
            timeout=15,
        )
        assert r.status_code == 200
        u = r.json()
        assert u["wallet_balance"] == 0
        assert u["role"] == "owner"
        _created_user_ids.append(u["id"])

    def test_admin_cannot_delete_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=_auth_headers(admin_token), timeout=10).json()
        r = requests.delete(f"{API}/admin/users/{me['id']}", headers=_auth_headers(admin_token), timeout=10)
        assert r.status_code == 404


class TestWalletTopup:
    def test_topup_and_balance(self, admin_token, user_a):
        # top up 100
        r = requests.post(
            f"{API}/admin/wallet/topup",
            json={"user_id": user_a["id"], "amount": 100, "note": "test"},
            headers=_auth_headers(admin_token),
            timeout=10,
        )
        assert r.status_code == 200, r.text
        # Verify user's wallet
        w = requests.get(f"{API}/wallet", headers=_auth_headers(user_a["token"]), timeout=10).json()
        assert w["balance"] >= 100  # may already have from earlier topup; check minimum
        # Confirm topup transaction present
        topups = [t for t in w["transactions"] if t["amount"] == 100]
        assert len(topups) >= 1


class TestCreditDeduction:
    def test_image_ad_deducts_5(self, admin_token):
        # Create dedicated user with exact 100 balance
        user = _make_user(admin_token, "credit")
        requests.post(
            f"{API}/admin/wallet/topup",
            json={"user_id": user["id"], "amount": 100},
            headers=_auth_headers(admin_token),
            timeout=10,
        )
        # Generate image-only ad
        r = requests.post(
            f"{API}/ads/generate",
            json={"topic": "Test ad credit deduction", "include_image": True, "include_video": False},
            headers=_auth_headers(user["token"]),
            timeout=120,
        )
        assert r.status_code == 200, f"Ad gen failed: {r.status_code} {r.text[:300]}"
        ad = r.json()
        assert ad.get("image_path"), "Image not generated"
        # wallet should be 95
        w = requests.get(f"{API}/wallet", headers=_auth_headers(user["token"]), timeout=10).json()
        assert w["balance"] == 95, f"Expected 95, got {w['balance']}"
        # 2 txns
        assert len(w["transactions"]) >= 2
        amts = sorted(t["amount"] for t in w["transactions"])
        assert -5 in amts and 100 in amts

    def test_insufficient_balance_402(self, admin_token):
        user = _make_user(admin_token, "broke")
        requests.post(
            f"{API}/admin/wallet/topup",
            json={"user_id": user["id"], "amount": 3},
            headers=_auth_headers(admin_token),
            timeout=10,
        )
        r = requests.post(
            f"{API}/ads/generate",
            json={"topic": "Too poor", "include_image": True, "include_video": False},
            headers=_auth_headers(user["token"]),
            timeout=30,
        )
        assert r.status_code == 402
        assert "Insufficient" in r.text


class TestTenantIsolation:
    def test_isolation(self, admin_token, user_a, user_b):
        # A creates a website
        r = requests.post(
            f"{API}/websites",
            json={"name": "TEST_A_site", "url": "https://a.example.com"},
            headers=_auth_headers(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        wid = r.json()["id"]
        # B lists websites — must not include W1
        bl = requests.get(f"{API}/websites", headers=_auth_headers(user_b["token"]), timeout=10).json()
        assert all(w["id"] != wid for w in bl)
        # B GET/PATCH/DELETE -> 404
        # No direct GET single endpoint; PATCH and DELETE both should 404 for B
        pr = requests.patch(
            f"{API}/websites/{wid}",
            json={"name": "hacked"},
            headers=_auth_headers(user_b["token"]),
            timeout=10,
        )
        assert pr.status_code == 404
        dr = requests.delete(f"{API}/websites/{wid}", headers=_auth_headers(user_b["token"]), timeout=10)
        assert dr.status_code == 404
        # Admin sees all
        ar = requests.get(f"{API}/websites", headers=_auth_headers(admin_token), timeout=10).json()
        assert any(w["id"] == wid for w in ar)


class TestPerWebsiteMeta:
    def test_website_meta_fields(self, user_a):
        r = requests.post(
            f"{API}/websites",
            json={
                "name": "TEST_meta_site",
                "url": "https://meta.example.com",
                "fb_access_token": "fbtok",
                "fb_page_id": "pg",
                "ig_account_id": "ig",
                "telegram_bot_token": "tb",
                "telegram_chat_id": "tc",
            },
            headers=_auth_headers(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        w = r.json()
        assert w["fb_access_token"] == "fbtok"
        assert w["fb_page_id"] == "pg"
        assert w["ig_account_id"] == "ig"
        assert w["telegram_bot_token"] == "tb"
        assert w["telegram_chat_id"] == "tc"


class TestPublicEndpoints:
    def test_public_website_and_lead(self, user_a, admin_token):
        # Create website
        r = requests.post(
            f"{API}/websites",
            json={"name": "TEST_public_site", "url": "https://pub.example.com"},
            headers=_auth_headers(user_a["token"]),
            timeout=10,
        )
        wid = r.json()["id"]
        # Public website fetch (no auth)
        pr = requests.get(f"{API}/public/websites/{wid}", timeout=10)
        assert pr.status_code == 200
        assert pr.json()["name"] == "TEST_public_site"
        # Public lead submit (no auth)
        lr = requests.post(
            f"{API}/public/leads/{wid}",
            json={"name": "Test Lead", "phone": "+919999999999", "email": "lead@ex.com"},
            timeout=10,
        )
        assert lr.status_code == 200
        lead = lr.json()
        assert lead["owner_id"] == user_a["id"]
        # User A sees this lead
        my_leads = requests.get(f"{API}/leads", headers=_auth_headers(user_a["token"]), timeout=10).json()
        assert any(item["id"] == lead["id"] for item in my_leads)


class TestSchedulerAndStats:
    def test_stats_auth(self, user_a):
        r = requests.get(f"{API}/stats", headers=_auth_headers(user_a["token"]), timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_ads", "drafts", "websites", "leads"):
            assert k in d

    def test_scheduler_status(self, user_a):
        r = requests.get(f"{API}/scheduler/status", headers=_auth_headers(user_a["token"]), timeout=10)
        assert r.status_code == 200
        assert "peak_hours_utc" in r.json()


# ---------------- TEARDOWN ----------------
def teardown_module(module):
    """Cleanup test users via admin."""
    try:
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        if r.status_code != 200:
            return
        tok = r.json()["token"]
        for uid in _created_user_ids:
            try:
                requests.delete(f"{API}/admin/users/{uid}", headers=_auth_headers(tok), timeout=10)
            except Exception:
                pass
    except Exception:
        pass
