"""AI Ads Studio – backend API."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from auth import (
    LoginPayload,
    RegisterPayload,
    User,
    UserPublic,
    WalletTopUpPayload,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    seed_admin,
    verify_password,
)

# ---------------------- ENV ----------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MEDIA_DIR = ROOT_DIR / "generated_media"
IMAGES_DIR = MEDIA_DIR / "images"
VIDEOS_DIR = MEDIA_DIR / "videos"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------------------- FASTAPI ----------------------
app = FastAPI(title="AI Ads Studio")
app.state.db = db  # expose for auth dependency
api_router = APIRouter(prefix="/api")
app.mount("/api/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# ---------------------- CREDIT PRICING ----------------------
PRICING = {
    "image": 5,
    "video_4s": 30,
    "video_8s": 60,
    "video_12s": 90,
    "variant": 5,
    "auto_gen": 5,
}


def _video_cost(duration: int) -> int:
    return PRICING.get(f"video_{duration}s", 30)


async def _charge_user(user_id: str, amount: int, reason: str) -> None:
    """Atomic deduct from wallet; raise 402 if insufficient. Also logs txn.
    Admin accounts have unlimited credits — charge is skipped but logged.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "role": 1})
    if user and user.get("role") == "admin":
        await db.wallet_txns.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "amount": 0,
            "reason": f"{reason} (admin — free)",
            "created_at": now_iso(),
        })
        return
    res = await db.users.find_one_and_update(
        {"id": user_id, "wallet_balance": {"$gte": amount}},
        {"$inc": {"wallet_balance": -amount}},
        projection={"_id": 0, "wallet_balance": 1},
    )
    if not res:
        raise HTTPException(
            402,
            f"Insufficient wallet balance. Need {amount} credits for {reason}. Ask admin to top-up.",
        )
    await db.wallet_txns.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": -amount,
        "reason": reason,
        "created_at": now_iso(),
    })


async def _credit_user(user_id: str, amount: int, note: str) -> Dict[str, Any]:
    res = await db.users.find_one_and_update(
        {"id": user_id},
        {"$inc": {"wallet_balance": amount}},
        return_document=True,
        projection={"_id": 0, "password_hash": 0},
    )
    if not res:
        raise HTTPException(404, "User not found")
    await db.wallet_txns.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": amount,
        "reason": f"admin topup: {note}" if note else "admin topup",
        "created_at": now_iso(),
    })
    return res


# ---------------------- MODELS ----------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Website(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str = ""
    name: str
    url: str
    description: Optional[str] = ""
    cta_url: Optional[str] = ""
    lead_form_url: Optional[str] = ""
    lead_webhook_url: Optional[str] = ""
    whatsapp_number: Optional[str] = ""
    # Per-website Meta credentials
    fb_access_token: Optional[str] = ""
    fb_page_id: Optional[str] = ""
    ig_account_id: Optional[str] = ""
    telegram_bot_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    auto_generate: bool = False
    last_auto_run_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class WebsiteCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""
    cta_url: Optional[str] = ""
    lead_form_url: Optional[str] = ""
    lead_webhook_url: Optional[str] = ""
    whatsapp_number: Optional[str] = ""
    fb_access_token: Optional[str] = ""
    fb_page_id: Optional[str] = ""
    ig_account_id: Optional[str] = ""
    telegram_bot_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    auto_generate: bool = False


class WebsiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    cta_url: Optional[str] = None
    lead_form_url: Optional[str] = None
    lead_webhook_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    fb_access_token: Optional[str] = None
    fb_page_id: Optional[str] = None
    ig_account_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    auto_generate: Optional[bool] = None


class GenerateRequest(BaseModel):
    website_id: Optional[str] = None
    topic: str
    audience: Optional[str] = "Indian college students aged 17-24"
    tone: Optional[str] = "energetic, fun, Gen Z friendly"
    include_image: bool = True
    include_video: bool = False
    video_duration: Literal[4, 8, 12] = 4
    video_size: Literal["1280x720", "1024x1024", "1024x1792", "1792x1024"] = "1024x1792"


class ScrapeRequest(BaseModel):
    url: str


class Ad(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str = ""
    website_id: Optional[str] = None
    website_name: Optional[str] = None
    topic: str
    caption: str
    hashtags: List[str] = []
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    video_status: Literal["none", "pending", "ready", "failed"] = "none"
    status: Literal["draft", "approved", "downloaded"] = "draft"
    published_to: List[str] = []
    parent_ad_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class StatusUpdate(BaseModel):
    status: Literal["draft", "approved", "downloaded"]


class PublishRequest(BaseModel):
    platforms: List[Literal["facebook", "instagram"]] = ["facebook"]


class VariantRequest(BaseModel):
    tweak: Optional[str] = "Make it noticeably different in angle and visual style."


class MetaSettings(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fb_access_token: Optional[str] = ""
    fb_page_id: Optional[str] = ""
    ig_account_id: Optional[str] = ""
    telegram_bot_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    updated_at: str = Field(default_factory=now_iso)


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str = ""
    website_id: str
    website_name: Optional[str] = ""
    name: str
    phone: str
    email: Optional[str] = ""
    course: Optional[str] = ""
    city: Optional[str] = ""
    message: Optional[str] = ""
    source_ad_id: Optional[str] = None
    forwarded: bool = False
    created_at: str = Field(default_factory=now_iso)


class LeadCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    course: Optional[str] = ""
    city: Optional[str] = ""
    message: Optional[str] = ""
    source_ad_id: Optional[str] = None


# ---------------------- LLM HELPERS ----------------------
async def _llm_text(system: str, user_text: str) -> str:
    """Call GPT-5.2 via emergentintegrations and return raw text."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ["EMERGENT_LLM_KEY"]
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    return await chat.send_message(UserMessage(text=user_text))


def _fetch_website_logo_bytes(website_url: str) -> Optional[bytes]:
    """Backward-compatible thin wrapper kept for legacy callers/tests."""
    from services.watermark import fetch_website_logo_bytes
    return fetch_website_logo_bytes(website_url)


def _apply_logo_watermark(
    image_path: Path, website_url: Optional[str], brand_text: Optional[str] = None
) -> None:
    """Backward-compatible thin wrapper kept for legacy callers/tests."""
    from services.watermark import apply_logo_watermark
    apply_logo_watermark(image_path, website_url, brand_text)


async def _generate_image_to_file(
    prompt: str,
    ad_id: str,
    website_url: Optional[str] = None,
    brand_text: Optional[str] = None,
) -> str:
    """Generate image with Nano Banana, save to disk, watermark, return relative path."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ["EMERGENT_LLM_KEY"]
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message="You are a professional advertising creative director.",
    ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"]
    )
    _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if not images:
        raise RuntimeError("No image returned")
    image_bytes = base64.b64decode(images[0]["data"])
    out_path = IMAGES_DIR / f"{ad_id}.png"
    out_path.write_bytes(image_bytes)
    # Overlay the website's logo + brand name as a watermark (bottom-right)
    _apply_logo_watermark(out_path, website_url, brand_text)
    return f"images/{ad_id}.png"


def _generate_video_to_file(
    prompt: str, ad_id: str, duration: int = 4, size: str = "1024x1792"
) -> str:
    """Generate video via Sora 2 (sync) and save to disk."""
    from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

    api_key = os.environ["EMERGENT_LLM_KEY"]
    video_gen = OpenAIVideoGeneration(api_key=api_key)
    video_bytes = video_gen.text_to_video(
        prompt=prompt,
        model="sora-2",
        size=size,
        duration=duration,
        max_wait_time=600,
    )
    if not video_bytes:
        raise RuntimeError("No video bytes returned")
    out_path = VIDEOS_DIR / f"{ad_id}.mp4"
    video_gen.save_video(video_bytes, str(out_path))
    return f"videos/{ad_id}.mp4"


# ---------------------- SCRAPER HELPERS ----------------------
def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _extract_meta_description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _extract_body_paragraphs(soup: BeautifulSoup, max_count: int = 5) -> str:
    paragraphs: List[str] = []
    for p in soup.find_all("p")[:8]:
        text = p.get_text(strip=True)
        if text and len(text) > 30:
            paragraphs.append(text)
        if len(paragraphs) >= max_count:
            break
    return "\n".join(paragraphs)[:2000]


async def _scrape_url(url: str) -> Dict[str, str]:
    """Fetch URL and extract title, meta description and a body excerpt."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Ads-Studio/1.0)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    return {
        "title": _extract_title(soup),
        "description": _extract_meta_description(soup),
        "body": _extract_body_paragraphs(soup),
        "url": url,
    }


# ---------------------- AD GENERATION HELPERS ----------------------
_CREATIVE_SYSTEM = (
    "You are a senior performance-marketing copywriter for Indian social media. "
    "You craft scroll-stopping Instagram & Facebook ad creatives for college and "
    "student audiences."
)


def _build_creative_prompt(payload: GenerateRequest, website_name: Optional[str]) -> str:
    return f"""Create a complete ad creative pack for this brief.

Brand / Website: {website_name or 'N/A'}
Topic / Product: {payload.topic}
Target audience: {payload.audience}
Tone: {payload.tone}

Return STRICT JSON with these keys and nothing else:
{{
  "caption": "<2-4 line Instagram caption in Hinglish, with 3-5 fitting emojis, persuasive, ends with a soft CTA>",
  "hashtags": ["#tag1", "#tag2", "..."],
  "image_prompt": "<Detailed visual prompt for an AI image model. Square/portrait ad banner. Mention subject, lighting, mood, composition, color palette, typography hints.>",
  "video_prompt": "<Short 4-8 second cinematic shot description for a video ad model.>"
}}"""


def _parse_creative_json(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise HTTPException(500, f"LLM returned non-JSON: {raw[:200]}")
        return json.loads(match.group(0))


async def _resolve_website(website_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not website_id:
        return None
    site = await db.websites.find_one({"id": website_id}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found")
    return site


async def _resolve_website_name(website_id: Optional[str]) -> Optional[str]:
    site = await _resolve_website(website_id)
    return site["name"] if site else None


def _public_frontend_url() -> str:
    """Best-effort base URL to host the lead-form page (frontend)."""
    base = os.environ.get("PUBLIC_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
    return base.rstrip("/")


def _build_cta_lines(site: Optional[Dict[str, Any]]) -> str:
    """Build the CTA block appended to ad captions."""
    if not site:
        return ""
    lines: List[str] = []
    cta = (site.get("cta_url") or site.get("url") or "").strip()
    if cta:
        lines.append(f"🌐 Visit: {cta}")
    lead_url = (site.get("lead_form_url") or "").strip()
    if not lead_url:
        base = _public_frontend_url()
        if base:
            lead_url = f"{base}/apply/{site['id']}"
    if lead_url:
        lines.append(f"📝 Apply Now: {lead_url}")
    wa = (site.get("whatsapp_number") or "").strip().replace("+", "").replace(" ", "")
    if wa:
        msg = f"Hi%20{site['name'].replace(' ', '%20')}%20team%2C%20I%20saw%20your%20ad"
        lines.append(f"💬 WhatsApp: https://wa.me/{wa}?text={msg}")
    return "\n".join(lines)


def _send_telegram_notification(token: str, chat_id: str, text: str) -> bool:
    """Post a Markdown message to Telegram using provided credentials."""
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        logger.exception("Telegram send failed")
        return False


# ---------------------- ROUTES: HEALTH ----------------------
@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "AI Ads Studio backend running", "ts": now_iso()}


# ---------------------- ROUTES: WEBSITES ----------------------
@api_router.post("/websites", response_model=Website)
async def create_website(payload: WebsiteCreate, user=Depends(get_current_user)) -> Website:
    site = Website(owner_id=user["id"], **payload.model_dump())
    await db.websites.insert_one(site.model_dump())
    return site


@api_router.get("/websites", response_model=List[Website])
async def list_websites(user=Depends(get_current_user)) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {} if user["role"] == "admin" else {"owner_id": user["id"]}
    return await db.websites.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.patch("/websites/{wid}", response_model=Website)
async def update_website(wid: str, payload: WebsiteUpdate, user=Depends(get_current_user)) -> Dict[str, Any]:
    q: Dict[str, Any] = {"id": wid}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    update_doc = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_doc:
        raise HTTPException(400, "No fields to update")
    result = await db.websites.find_one_and_update(
        q, {"$set": update_doc}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(404, "Website not found")
    return result


@api_router.delete("/websites/{wid}")
async def delete_website(wid: str, user=Depends(get_current_user)) -> Dict[str, bool]:
    q: Dict[str, Any] = {"id": wid}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    result = await db.websites.delete_one(q)
    if result.deleted_count == 0:
        raise HTTPException(404, "Website not found")
    return {"ok": True}


# ---------------------- ROUTES: SCRAPE ----------------------
@api_router.post("/scrape")
async def scrape(payload: ScrapeRequest, user=Depends(get_current_user)) -> Dict[str, str]:
    try:
        return await _scrape_url(payload.url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Scrape failed: {e}")


# ---------------------- ROUTES: GENERATE ----------------------
@api_router.post("/ads/generate", response_model=Ad)
async def generate_ad(
    payload: GenerateRequest, background_tasks: BackgroundTasks, user=Depends(get_current_user)
) -> Ad:
    """Generate caption + image inline; video is queued in background."""
    site = await _resolve_website(payload.website_id)
    if site and user["role"] != "admin" and site.get("owner_id") != user["id"]:
        raise HTTPException(403, "Not your website")
    website_name = site["name"] if site else None

    # ---- charge wallet first ----
    cost = 0
    if payload.include_image:
        cost += PRICING["image"]
    if payload.include_video:
        cost += _video_cost(payload.video_duration)
    if cost == 0:
        cost = 1  # caption-only baseline
    await _charge_user(user["id"], cost, "ad generation")

    raw = await _llm_text(_CREATIVE_SYSTEM, _build_creative_prompt(payload, website_name))
    parsed = _parse_creative_json(raw)

    ad_id = str(uuid.uuid4())
    caption_text = parsed.get("caption", "")
    cta = _build_cta_lines(site)
    if cta:
        caption_text = f"{caption_text}\n\n{cta}"
    ad = Ad(
        id=ad_id,
        owner_id=user["id"],
        website_id=payload.website_id,
        website_name=website_name,
        topic=payload.topic,
        caption=caption_text,
        hashtags=parsed.get("hashtags", []),
        image_prompt=parsed.get("image_prompt", ""),
        video_prompt=parsed.get("video_prompt", ""),
        video_status="pending" if payload.include_video else "none",
    )

    if payload.include_image and ad.image_prompt:
        try:
            ad.image_path = await _generate_image_to_file(
                ad.image_prompt,
                ad_id,
                site.get("url") if site else None,
                website_name,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Image gen failed")
            raise HTTPException(500, f"Image generation failed: {e}")

    await db.ads.insert_one(ad.model_dump())

    if payload.include_video and ad.video_prompt:
        background_tasks.add_task(
            _video_task,
            ad_id,
            ad.video_prompt,
            payload.video_duration,
            payload.video_size,
        )
    return ad


async def _video_task(ad_id: str, prompt: str, duration: int, size: str) -> None:
    """Background task: generate video, update ad doc."""
    try:
        loop = asyncio.get_event_loop()
        rel_path = await loop.run_in_executor(
            None, _generate_video_to_file, prompt, ad_id, duration, size
        )
        await db.ads.update_one(
            {"id": ad_id},
            {"$set": {"video_path": rel_path, "video_status": "ready"}},
        )
        logger.info(f"Video ready for ad {ad_id}")
    except Exception:  # noqa: BLE001
        logger.exception(f"Video gen failed for {ad_id}")
        await db.ads.update_one({"id": ad_id}, {"$set": {"video_status": "failed"}})


# ---------------------- ROUTES: ADS ----------------------
@api_router.get("/ads", response_model=List[Ad])
async def list_ads(
    website_id: Optional[str] = None, status: Optional[str] = None, user=Depends(get_current_user)
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {} if user["role"] == "admin" else {"owner_id": user["id"]}
    if website_id:
        q["website_id"] = website_id
    if status:
        q["status"] = status
    return await db.ads.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    doc = await db.ads.find_one(q, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Ad not found")
    return doc


@api_router.patch("/ads/{ad_id}/status", response_model=Ad)
async def update_ad_status(ad_id: str, payload: StatusUpdate, user=Depends(get_current_user)) -> Dict[str, Any]:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    result = await db.ads.find_one_and_update(
        q, {"$set": {"status": payload.status}},
        return_document=True, projection={"_id": 0},
    )
    if not result:
        raise HTTPException(404, "Ad not found")
    return result


@api_router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: str, user=Depends(get_current_user)) -> Dict[str, bool]:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    doc = await db.ads.find_one(q)
    if not doc:
        raise HTTPException(404, "Ad not found")
    for key in ("image_path", "video_path"):
        rel = doc.get(key)
        if rel:
            try:
                (MEDIA_DIR / rel).unlink(missing_ok=True)
            except OSError:
                pass
    await db.ads.delete_one(q)
    return {"ok": True}


@api_router.get("/ads/{ad_id}/download/image")
async def download_image(ad_id: str, user=Depends(get_current_user)) -> FileResponse:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    doc = await db.ads.find_one(q, {"_id": 0})
    if not doc or not doc.get("image_path"):
        raise HTTPException(404, "Image not found")
    path = MEDIA_DIR / doc["image_path"]
    if not path.exists():
        raise HTTPException(404, "Image file missing")
    await db.ads.update_one({"id": ad_id}, {"$set": {"status": "downloaded"}})
    return FileResponse(path, media_type="image/png", filename=f"ad-{ad_id}.png")


@api_router.get("/ads/{ad_id}/download/video")
async def download_video(ad_id: str, user=Depends(get_current_user)) -> FileResponse:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    doc = await db.ads.find_one(q, {"_id": 0})
    if not doc or not doc.get("video_path"):
        raise HTTPException(404, "Video not found")
    path = MEDIA_DIR / doc["video_path"]
    if not path.exists():
        raise HTTPException(404, "Video file missing")
    await db.ads.update_one({"id": ad_id}, {"$set": {"status": "downloaded"}})
    return FileResponse(path, media_type="video/mp4", filename=f"ad-{ad_id}.mp4")


# ---------------------- ROUTES: STATS ----------------------
@api_router.get("/stats")
async def stats(user=Depends(get_current_user)) -> Dict[str, int]:
    base: Dict[str, Any] = {} if user["role"] == "admin" else {"owner_id": user["id"]}
    return {
        "total_ads": await db.ads.count_documents(base),
        "drafts": await db.ads.count_documents({**base, "status": "draft"}),
        "approved": await db.ads.count_documents({**base, "status": "approved"}),
        "downloaded": await db.ads.count_documents({**base, "status": "downloaded"}),
        "websites": await db.websites.count_documents(base),
        "pending_videos": await db.ads.count_documents({**base, "video_status": "pending"}),
        "leads": await db.leads.count_documents(base),
    }


# ---------------------- ROUTES: AUTH ----------------------
@api_router.post("/auth/register")
async def register(payload: RegisterPayload) -> Dict[str, Any]:
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user = User(email=email, name=payload.name or "", role="owner", wallet_balance=0)
    doc = user.model_dump()
    doc["password_hash"] = hash_password(payload.password)
    await db.users.insert_one(doc)
    token = create_access_token(user.id, user.email, user.role)
    return {"token": token, "user": UserPublic(**user.model_dump()).model_dump()}


@api_router.post("/auth/login")
async def login(payload: LoginPayload) -> Dict[str, Any]:
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user["id"], user["email"], user.get("role", "owner"))
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"token": token, "user": user}


@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)) -> Dict[str, Any]:
    return user


# ---------------------- ROUTES: WALLET ----------------------
@api_router.get("/wallet")
async def wallet(user=Depends(get_current_user)) -> Dict[str, Any]:
    txns = await db.wallet_txns.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    is_admin = user.get("role") == "admin"
    return {
        "balance": user.get("wallet_balance", 0),
        "unlimited": is_admin,
        "transactions": txns,
        "pricing": PRICING,
    }


# ---------------------- ROUTES: ADMIN ----------------------
@api_router.get("/admin/users", response_model=List[UserPublic])
async def admin_list_users(_admin=Depends(require_admin)) -> List[Dict[str, Any]]:
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    return docs


@api_router.post("/admin/users", response_model=UserPublic)
async def admin_create_user(payload: RegisterPayload, _admin=Depends(require_admin)) -> Dict[str, Any]:
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already exists")
    user = User(email=email, name=payload.name or "", role="owner", wallet_balance=0)
    doc = user.model_dump()
    doc["password_hash"] = hash_password(payload.password)
    await db.users.insert_one(doc)
    return UserPublic(**user.model_dump()).model_dump()


@api_router.delete("/admin/users/{uid}")
async def admin_delete_user(uid: str, _admin=Depends(require_admin)) -> Dict[str, bool]:
    res = await db.users.delete_one({"id": uid, "role": {"$ne": "admin"}})
    if res.deleted_count == 0:
        raise HTTPException(404, "User not found or cannot delete admin")
    return {"ok": True}


@api_router.post("/admin/wallet/topup", response_model=UserPublic)
async def admin_topup(payload: WalletTopUpPayload, _admin=Depends(require_admin)) -> Dict[str, Any]:
    if payload.amount == 0:
        raise HTTPException(400, "Amount cannot be zero")
    updated = await _credit_user(payload.user_id, payload.amount, payload.note or "")
    return UserPublic(**updated).model_dump()


@api_router.get("/admin/users/{uid}/wallet")
async def admin_user_wallet(uid: str, _admin=Depends(require_admin)) -> Dict[str, Any]:
    user = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "User not found")
    txns = await db.wallet_txns.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"user": user, "transactions": txns}


# ---------------------- BRANDING ----------------------
@api_router.get("/branding")
async def branding() -> Dict[str, str]:
    return {
        "creator": os.environ.get("ADMIN_NAME", "Admin"),
        "company": os.environ.get("COMPANY_NAME", "Company"),
    }


# ---------------------- ROUTES: PUBLISH ----------------------
META_GRAPH = "https://graph.facebook.com/v19.0"


def _public_media_url(rel_path: str) -> str:
    """Build a publicly-fetchable URL for Meta to download our generated media."""
    base = os.environ.get("PUBLIC_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
    base = base.rstrip("/")
    return f"{base}/api/media/{rel_path}"


def _post_to_facebook_page(token: str, page_id: str, image_url: str, caption: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{META_GRAPH}/{page_id}/photos",
        data={"url": image_url, "caption": caption, "access_token": token},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Facebook publish failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()


def _post_to_instagram(token: str, ig_id: str, image_url: str, caption: str) -> Dict[str, Any]:
    container = requests.post(
        f"{META_GRAPH}/{ig_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
        timeout=30,
    )
    if container.status_code != 200:
        raise RuntimeError(f"Instagram container failed: {container.status_code} {container.text[:300]}")
    creation_id = container.json().get("id")
    publish = requests.post(
        f"{META_GRAPH}/{ig_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if publish.status_code != 200:
        raise RuntimeError(f"Instagram publish failed: {publish.status_code} {publish.text[:300]}")
    return publish.json()


def _format_caption(ad: Dict[str, Any]) -> str:
    tags = " ".join(ad.get("hashtags") or [])
    return f"{ad.get('caption', '')}\n\n{tags}".strip()


@api_router.post("/ads/{ad_id}/publish")
async def publish_ad(
    ad_id: str, payload: PublishRequest, user=Depends(get_current_user)
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    ad = await db.ads.find_one(q, {"_id": 0})
    if not ad:
        raise HTTPException(404, "Ad not found")
    if not ad.get("image_path"):
        raise HTTPException(400, "Ad has no image to publish")

    # Prefer per-website credentials; fall back to global settings for legacy support
    site = await _resolve_website(ad.get("website_id")) if ad.get("website_id") else None
    settings = await db.meta_settings.find_one({}, {"_id": 0}) or {}
    token = (site or {}).get("fb_access_token") or settings.get("fb_access_token") or ""
    page_id = (site or {}).get("fb_page_id") or settings.get("fb_page_id") or ""
    ig_id = (site or {}).get("ig_account_id") or settings.get("ig_account_id") or ""

    if not token:
        raise HTTPException(400, "Set FB Access Token in Settings first")

    image_url = _public_media_url(ad["image_path"])
    caption = _format_caption(ad)
    results: Dict[str, Any] = {}
    published = list(ad.get("published_to") or [])

    if "facebook" in payload.platforms:
        if not page_id:
            raise HTTPException(400, "Set Facebook Page ID in Settings first")
        try:
            results["facebook"] = _post_to_facebook_page(token, page_id, image_url, caption)
            if "facebook" not in published:
                published.append("facebook")
        except Exception as e:  # noqa: BLE001
            logger.exception("FB publish failed")
            raise HTTPException(400, f"Facebook publish error: {e}")

    if "instagram" in payload.platforms:
        if not ig_id:
            raise HTTPException(400, "Set Instagram Business Account ID in Settings first")
        try:
            results["instagram"] = _post_to_instagram(token, ig_id, image_url, caption)
            if "instagram" not in published:
                published.append("instagram")
        except Exception as e:  # noqa: BLE001
            logger.exception("IG publish failed")
            raise HTTPException(400, f"Instagram publish error: {e}")

    await db.ads.update_one(
        {"id": ad_id},
        {"$set": {"published_to": published, "status": "downloaded"}},
    )
    return {"ok": True, "published_to": published, "results": results}


# ---------------------- ROUTES: A/B VARIANTS ----------------------
@api_router.post("/ads/{ad_id}/variants", response_model=Ad)
async def create_variant(ad_id: str, user=Depends(get_current_user)) -> Ad:
    """Regenerate a fresh image + caption variant from the same brief."""
    q: Dict[str, Any] = {"id": ad_id}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    parent = await db.ads.find_one(q, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Ad not found")

    await _charge_user(user["id"], PRICING["variant"], "ad variant")

    site = await _resolve_website(parent.get("website_id"))
    payload = GenerateRequest(
        website_id=parent.get("website_id"),
        topic=parent["topic"],
        include_image=True,
        include_video=False,
    )
    raw = await _llm_text(
        _CREATIVE_SYSTEM + " Produce a noticeably different angle from previous attempts.",
        _build_creative_prompt(payload, parent.get("website_name")),
    )
    parsed = _parse_creative_json(raw)
    new_id = str(uuid.uuid4())
    caption_text = parsed.get("caption", "")
    cta = _build_cta_lines(site)
    if cta:
        caption_text = f"{caption_text}\n\n{cta}"
    variant = Ad(
        id=new_id,
        owner_id=user["id"],
        website_id=parent.get("website_id"),
        website_name=parent.get("website_name"),
        topic=parent["topic"],
        caption=caption_text,
        hashtags=parsed.get("hashtags", []),
        image_prompt=parsed.get("image_prompt", ""),
        video_prompt=parsed.get("video_prompt", ""),
        parent_ad_id=ad_id,
    )
    if variant.image_prompt:
        try:
            variant.image_path = await _generate_image_to_file(
                variant.image_prompt,
                new_id,
                site.get("url") if site else None,
                parent.get("website_name"),
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Variant image gen failed")
            raise HTTPException(500, f"Variant image generation failed: {e}")
    await db.ads.insert_one(variant.model_dump())
    return variant


# ---------------------- SCHEDULER: PEAK-HOUR AUTO-GEN ----------------------
PEAK_HOURS = {9, 13, 18}  # 9 AM / 1 PM / 6 PM (server timezone)
SCHEDULER_TICK_SEC = 60


async def _auto_generate_for_website(site: Dict[str, Any]) -> None:
    """Scrape the website + create one approved-ready ad. Skips if owner is out of credits."""
    owner_id = site.get("owner_id", "")
    if not owner_id:
        return
    # check & charge owner credits before LLM calls (admins get unlimited credits)
    owner = await db.users.find_one({"id": owner_id}, {"_id": 0, "wallet_balance": 1, "role": 1})
    if not owner:
        logger.info(f"Skip auto-gen for {site.get('name')} — owner missing")
        return
    if owner.get("role") != "admin" and (owner.get("wallet_balance", 0) or 0) < PRICING["auto_gen"]:
        logger.info(f"Skip auto-gen for {site.get('name')} — insufficient credits")
        return
    try:
        await _charge_user(owner_id, PRICING["auto_gen"], f"auto-gen [{site.get('name')}]")
        scraped = await _scrape_url(site["url"])
        topic_seed = scraped.get("title") or scraped.get("description") or site["name"]
        body_hint = scraped.get("body", "")
        topic = f"{topic_seed}{' — ' + body_hint[:300] if body_hint else ''}".strip()
        payload = GenerateRequest(
            website_id=site["id"],
            topic=topic,
            include_image=True,
            include_video=False,
        )
        raw = await _llm_text(_CREATIVE_SYSTEM, _build_creative_prompt(payload, site["name"]))
        parsed = _parse_creative_json(raw)
        new_id = str(uuid.uuid4())
        caption_text = parsed.get("caption", "")
        cta = _build_cta_lines(site)
        if cta:
            caption_text = f"{caption_text}\n\n{cta}"
        ad = Ad(
            id=new_id,
            owner_id=owner_id,
            website_id=site["id"],
            website_name=site["name"],
            topic=topic,
            caption=caption_text,
            hashtags=parsed.get("hashtags", []),
            image_prompt=parsed.get("image_prompt", ""),
            video_prompt=parsed.get("video_prompt", ""),
        )
        if ad.image_prompt:
            ad.image_path = await _generate_image_to_file(
                ad.image_prompt, new_id, site.get("url"), site.get("name")
            )
        await db.ads.insert_one(ad.model_dump())
        await db.websites.update_one(
            {"id": site["id"]}, {"$set": {"last_auto_run_at": now_iso()}}
        )
        logger.info(f"Auto-generated ad {new_id} for {site['name']}")
    except Exception:  # noqa: BLE001
        logger.exception(f"Auto-gen failed for website {site.get('id')}")


async def _scheduler_loop() -> None:
    """Wake up every minute; on peak hours, run auto-gen for opted-in websites."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            hour_str = now.strftime("%Y-%m-%dT%H")
            if now.hour in PEAK_HOURS:
                async for site in db.websites.find({"auto_generate": True}, {"_id": 0}):
                    last = site.get("last_auto_run_at") or ""
                    # only run if last run was in a different hour-bucket
                    if not last.startswith(hour_str):
                        await _auto_generate_for_website(site)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler tick failed")
        await asyncio.sleep(SCHEDULER_TICK_SEC)


@api_router.get("/scheduler/status")
async def scheduler_status(user=Depends(get_current_user)) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    q: Dict[str, Any] = {"auto_generate": True}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    opted = await db.websites.count_documents(q)
    return {
        "peak_hours_utc": sorted(PEAK_HOURS),
        "current_hour_utc": now.hour,
        "is_peak_now": now.hour in PEAK_HOURS,
        "websites_opted_in": opted,
    }


@app.on_event("startup")
async def _start_scheduler() -> None:
    await db.users.create_index("email", unique=True)
    await db.websites.create_index("owner_id")
    await db.ads.create_index("owner_id")
    await db.leads.create_index("owner_id")
    await seed_admin(db)
    asyncio.create_task(_scheduler_loop())


# ---------------------- ROUTES: LEADS ----------------------
def _forward_lead_to_webhook(webhook_url: str, lead: Dict[str, Any]) -> bool:
    try:
        resp = requests.post(webhook_url, json=lead, timeout=10)
        return 200 <= resp.status_code < 300
    except Exception:  # noqa: BLE001
        logger.exception("Lead webhook delivery failed")
        return False


@api_router.get("/public/websites/{wid}")
async def public_website(wid: str) -> Dict[str, Any]:
    """Public, no-auth endpoint used by the apply form page."""
    site = await db.websites.find_one({"id": wid}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found")
    return {
        "id": site["id"],
        "name": site["name"],
        "description": site.get("description", ""),
        "cta_url": site.get("cta_url", "") or site.get("url", ""),
    }


@api_router.post("/public/leads/{wid}", response_model=Lead)
async def create_public_lead(wid: str, payload: LeadCreate) -> Lead:
    """Public, no-auth endpoint where the lead form posts."""
    site = await db.websites.find_one({"id": wid}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found")
    lead = Lead(
        owner_id=site.get("owner_id", ""),
        website_id=wid,
        website_name=site.get("name", ""),
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip(),
        course=(payload.course or "").strip(),
        city=(payload.city or "").strip(),
        message=(payload.message or "").strip(),
        source_ad_id=payload.source_ad_id,
    )
    if not lead.name or not lead.phone:
        raise HTTPException(400, "Name and phone are required")

    webhook_url = (site.get("lead_webhook_url") or "").strip()
    if webhook_url:
        ok = _forward_lead_to_webhook(webhook_url, lead.model_dump())
        lead.forwarded = ok

    await db.leads.insert_one(lead.model_dump())

    # Fire-and-forget Telegram alert
    alert = (
        f"🔥 *NEW LEAD* — {lead.website_name}\n"
        f"👤 {lead.name}\n"
        f"📱 `{lead.phone}`\n"
        f"{'📧 ' + lead.email + chr(10) if lead.email else ''}"
        f"{'📚 ' + lead.course + chr(10) if lead.course else ''}"
        f"{'📍 ' + lead.city + chr(10) if lead.city else ''}"
        f"{'💬 ' + lead.message + chr(10) if lead.message else ''}"
    )
    asyncio.create_task(asyncio.to_thread(
        _send_telegram_notification,
        (site.get("telegram_bot_token") or "").strip(),
        (site.get("telegram_chat_id") or "").strip(),
        alert,
    ))
    return lead


@api_router.get("/leads", response_model=List[Lead])
async def list_leads(website_id: Optional[str] = None, user=Depends(get_current_user)) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {} if user["role"] == "admin" else {"owner_id": user["id"]}
    if website_id:
        q["website_id"] = website_id
    return await db.leads.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)


@api_router.delete("/leads/{lid}")
async def delete_lead(lid: str, user=Depends(get_current_user)) -> Dict[str, bool]:
    q: Dict[str, Any] = {"id": lid}
    if user["role"] != "admin":
        q["owner_id"] = user["id"]
    res = await db.leads.delete_one(q)
    if res.deleted_count == 0:
        raise HTTPException(404, "Lead not found")
    return {"ok": True}


@api_router.get("/leads/export.csv")
async def export_leads_csv(website_id: Optional[str] = None, user=Depends(get_current_user)):
    import csv
    from io import StringIO
    from fastapi.responses import Response

    q: Dict[str, Any] = {} if user["role"] == "admin" else {"owner_id": user["id"]}
    if website_id:
        q["website_id"] = website_id
    docs = await db.leads.find(q, {"_id": 0}).sort("created_at", -1).to_list(5000)
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["created_at", "website_name", "name", "phone", "email", "course", "city", "message", "forwarded"]
    )
    for d in docs:
        writer.writerow([
            d.get("created_at", ""),
            d.get("website_name", ""),
            d.get("name", ""),
            d.get("phone", ""),
            d.get("email", ""),
            d.get("course", ""),
            d.get("city", ""),
            d.get("message", ""),
            "yes" if d.get("forwarded") else "no",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ---------------------- APP WIRING ----------------------
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
