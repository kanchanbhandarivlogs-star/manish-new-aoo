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
    created_at: str = Field(default_factory=now_iso)


class WebsiteCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""


class WebsiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


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
    created_at: str = Field(default_factory=now_iso)


class StatusUpdate(BaseModel):
    status: Literal["draft", "approved", "downloaded"]


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
