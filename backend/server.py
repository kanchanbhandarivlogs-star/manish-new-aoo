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
from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

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
api_router = APIRouter(prefix="/api")
app.mount("/api/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


# ---------------------- MODELS ----------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Website(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    description: Optional[str] = ""
    auto_generate: bool = False
    last_auto_run_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class WebsiteCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""
    auto_generate: bool = False


class WebsiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
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
    updated_at: str = Field(default_factory=now_iso)


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


async def _generate_image_to_file(prompt: str, ad_id: str) -> str:
    """Generate image with Nano Banana, save to disk, return relative path."""
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


async def _resolve_website_name(website_id: Optional[str]) -> Optional[str]:
    if not website_id:
        return None
    site = await db.websites.find_one({"id": website_id}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found")
    return site["name"]


# ---------------------- ROUTES: HEALTH ----------------------
@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "AI Ads Studio backend running", "ts": now_iso()}


# ---------------------- ROUTES: WEBSITES ----------------------
@api_router.post("/websites", response_model=Website)
async def create_website(payload: WebsiteCreate) -> Website:
    site = Website(**payload.model_dump())
    await db.websites.insert_one(site.model_dump())
    return site


@api_router.get("/websites", response_model=List[Website])
async def list_websites() -> List[Dict[str, Any]]:
    return await db.websites.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.patch("/websites/{wid}", response_model=Website)
async def update_website(wid: str, payload: WebsiteUpdate) -> Dict[str, Any]:
    update_doc = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_doc:
        raise HTTPException(400, "No fields to update")
    result = await db.websites.find_one_and_update(
        {"id": wid}, {"$set": update_doc}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(404, "Website not found")
    return result


@api_router.delete("/websites/{wid}")
async def delete_website(wid: str) -> Dict[str, bool]:
    result = await db.websites.delete_one({"id": wid})
    if result.deleted_count == 0:
        raise HTTPException(404, "Website not found")
    return {"ok": True}


# ---------------------- ROUTES: SCRAPE ----------------------
@api_router.post("/scrape")
async def scrape(payload: ScrapeRequest) -> Dict[str, str]:
    try:
        return await _scrape_url(payload.url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Scrape failed: {e}")


# ---------------------- ROUTES: GENERATE ----------------------
@api_router.post("/ads/generate", response_model=Ad)
async def generate_ad(
    payload: GenerateRequest, background_tasks: BackgroundTasks
) -> Ad:
    """Generate caption + image inline; video is queued in background."""
    website_name = await _resolve_website_name(payload.website_id)

    raw = await _llm_text(_CREATIVE_SYSTEM, _build_creative_prompt(payload, website_name))
    parsed = _parse_creative_json(raw)

    ad_id = str(uuid.uuid4())
    ad = Ad(
        id=ad_id,
        website_id=payload.website_id,
        website_name=website_name,
        topic=payload.topic,
        caption=parsed.get("caption", ""),
        hashtags=parsed.get("hashtags", []),
        image_prompt=parsed.get("image_prompt", ""),
        video_prompt=parsed.get("video_prompt", ""),
        video_status="pending" if payload.include_video else "none",
    )

    if payload.include_image and ad.image_prompt:
        try:
            ad.image_path = await _generate_image_to_file(ad.image_prompt, ad_id)
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
    website_id: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if website_id:
        q["website_id"] = website_id
    if status:
        q["status"] = status
    return await db.ads.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str) -> Dict[str, Any]:
    doc = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Ad not found")
    return doc


@api_router.patch("/ads/{ad_id}/status", response_model=Ad)
async def update_ad_status(ad_id: str, payload: StatusUpdate) -> Dict[str, Any]:
    result = await db.ads.find_one_and_update(
        {"id": ad_id},
        {"$set": {"status": payload.status}},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(404, "Ad not found")
    return result


@api_router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: str) -> Dict[str, bool]:
    doc = await db.ads.find_one({"id": ad_id})
    if not doc:
        raise HTTPException(404, "Ad not found")
    for key in ("image_path", "video_path"):
        rel = doc.get(key)
        if rel:
            try:
                (MEDIA_DIR / rel).unlink(missing_ok=True)
            except OSError:
                pass
    await db.ads.delete_one({"id": ad_id})
    return {"ok": True}


@api_router.get("/ads/{ad_id}/download/image")
async def download_image(ad_id: str) -> FileResponse:
    doc = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not doc or not doc.get("image_path"):
        raise HTTPException(404, "Image not found")
    path = MEDIA_DIR / doc["image_path"]
    if not path.exists():
        raise HTTPException(404, "Image file missing")
    await db.ads.update_one({"id": ad_id}, {"$set": {"status": "downloaded"}})
    return FileResponse(path, media_type="image/png", filename=f"ad-{ad_id}.png")


@api_router.get("/ads/{ad_id}/download/video")
async def download_video(ad_id: str) -> FileResponse:
    doc = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not doc or not doc.get("video_path"):
        raise HTTPException(404, "Video not found")
    path = MEDIA_DIR / doc["video_path"]
    if not path.exists():
        raise HTTPException(404, "Video file missing")
    await db.ads.update_one({"id": ad_id}, {"$set": {"status": "downloaded"}})
    return FileResponse(path, media_type="video/mp4", filename=f"ad-{ad_id}.mp4")


# ---------------------- ROUTES: STATS ----------------------
@api_router.get("/stats")
async def stats() -> Dict[str, int]:
    return {
        "total_ads": await db.ads.count_documents({}),
        "drafts": await db.ads.count_documents({"status": "draft"}),
        "approved": await db.ads.count_documents({"status": "approved"}),
        "downloaded": await db.ads.count_documents({"status": "downloaded"}),
        "websites": await db.websites.count_documents({}),
        "pending_videos": await db.ads.count_documents({"video_status": "pending"}),
    }


# ---------------------- ROUTES: META SETTINGS ----------------------
@api_router.get("/meta-settings")
async def get_meta_settings() -> Dict[str, Any]:
    doc = await db.meta_settings.find_one({}, {"_id": 0})
    if not doc:
        return {"fb_access_token": "", "fb_page_id": "", "ig_account_id": ""}
    return doc


@api_router.put("/meta-settings")
async def upsert_meta_settings(payload: MetaSettings) -> MetaSettings:
    payload.updated_at = now_iso()
    await db.meta_settings.update_one({}, {"$set": payload.model_dump()}, upsert=True)
    return payload


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
async def publish_ad(ad_id: str, payload: PublishRequest) -> Dict[str, Any]:
    ad = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(404, "Ad not found")
    if not ad.get("image_path"):
        raise HTTPException(400, "Ad has no image to publish")

    settings = await db.meta_settings.find_one({}, {"_id": 0}) or {}
    token = settings.get("fb_access_token") or ""
    page_id = settings.get("fb_page_id") or ""
    ig_id = settings.get("ig_account_id") or ""

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
            raise HTTPException(502, str(e))

    if "instagram" in payload.platforms:
        if not ig_id:
            raise HTTPException(400, "Set Instagram Business Account ID in Settings first")
        try:
            results["instagram"] = _post_to_instagram(token, ig_id, image_url, caption)
            if "instagram" not in published:
                published.append("instagram")
        except Exception as e:  # noqa: BLE001
            logger.exception("IG publish failed")
            raise HTTPException(502, str(e))

    await db.ads.update_one(
        {"id": ad_id},
        {"$set": {"published_to": published, "status": "downloaded"}},
    )
    return {"ok": True, "published_to": published, "results": results}


# ---------------------- ROUTES: A/B VARIANTS ----------------------
@api_router.post("/ads/{ad_id}/variants", response_model=Ad)
async def create_variant(ad_id: str) -> Ad:
    """Regenerate a fresh image + caption variant from the same brief."""
    parent = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Ad not found")

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
    variant = Ad(
        id=new_id,
        website_id=parent.get("website_id"),
        website_name=parent.get("website_name"),
        topic=parent["topic"],
        caption=parsed.get("caption", ""),
        hashtags=parsed.get("hashtags", []),
        image_prompt=parsed.get("image_prompt", ""),
        video_prompt=parsed.get("video_prompt", ""),
        parent_ad_id=ad_id,
    )
    if variant.image_prompt:
        try:
            variant.image_path = await _generate_image_to_file(variant.image_prompt, new_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("Variant image gen failed")
            raise HTTPException(500, f"Variant image generation failed: {e}")
    await db.ads.insert_one(variant.model_dump())
    return variant


# ---------------------- SCHEDULER: PEAK-HOUR AUTO-GEN ----------------------
PEAK_HOURS = {9, 13, 18}  # 9 AM / 1 PM / 6 PM (server timezone)
SCHEDULER_TICK_SEC = 60


async def _auto_generate_for_website(site: Dict[str, Any]) -> None:
    """Scrape the website + create one approved-ready ad."""
    try:
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
        ad = Ad(
            id=new_id,
            website_id=site["id"],
            website_name=site["name"],
            topic=topic,
            caption=parsed.get("caption", ""),
            hashtags=parsed.get("hashtags", []),
            image_prompt=parsed.get("image_prompt", ""),
            video_prompt=parsed.get("video_prompt", ""),
        )
        if ad.image_prompt:
            ad.image_path = await _generate_image_to_file(ad.image_prompt, new_id)
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
async def scheduler_status() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    opted = await db.websites.count_documents({"auto_generate": True})
    return {
        "peak_hours_utc": sorted(PEAK_HOURS),
        "current_hour_utc": now.hour,
        "is_peak_now": now.hour in PEAK_HOURS,
        "websites_opted_in": opted,
    }


@app.on_event("startup")
async def _start_scheduler() -> None:
    asyncio.create_task(_scheduler_loop())


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
