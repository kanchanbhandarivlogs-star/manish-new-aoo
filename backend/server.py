from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import asyncio
import uuid
from pathlib import Path
from typing import List, Optional, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict, HttpUrl
import requests
from bs4 import BeautifulSoup

# ---------------------- ENV ----------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MEDIA_DIR = ROOT_DIR / 'generated_media'
IMAGES_DIR = MEDIA_DIR / 'images'
VIDEOS_DIR = MEDIA_DIR / 'videos'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ---------------------- FASTAPI ----------------------
app = FastAPI(title="AI Ads Studio")
api_router = APIRouter(prefix="/api")

# Mount generated media so frontend can fetch directly via /api/media/...
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
    image_path: Optional[str] = None   # relative path like images/{id}.png
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


# ---------------------- HELPERS ----------------------
async def _llm_text(system: str, user_text: str) -> str:
    """Call GPT-5.2 via emergentintegrations and return text."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = os.environ['EMERGENT_LLM_KEY']
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    msg = UserMessage(text=user_text)
    return await chat.send_message(msg)


async def _generate_image_to_file(prompt: str, ad_id: str) -> str:
    """Generate image with Nano Banana, save to images/{ad_id}.png, return relative path."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = os.environ['EMERGENT_LLM_KEY']
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message="You are a professional advertising creative director."
    ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=prompt)
    _, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise RuntimeError("No image returned")
    img = images[0]
    image_bytes = base64.b64decode(img['data'])
    out_path = IMAGES_DIR / f"{ad_id}.png"
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    return f"images/{ad_id}.png"


def _generate_video_to_file(prompt: str, ad_id: str, duration: int = 4, size: str = "1024x1792") -> str:
    """Sync video gen with Sora 2."""
    from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
    api_key = os.environ['EMERGENT_LLM_KEY']
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


async def _scrape_url(url: str) -> dict:
    """Fetch URL and extract title + main text snippet."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Ads-Studio/1.0)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
    meta_desc = ""
    m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if m and m.get("content"):
        meta_desc = m["content"].strip()
    # collect first 5 paragraphs
    paragraphs = []
    for p in soup.find_all("p")[:8]:
        text = p.get_text(strip=True)
        if text and len(text) > 30:
            paragraphs.append(text)
        if len(paragraphs) >= 5:
            break
    body = "\n".join(paragraphs)[:2000]
    return {"title": title, "description": meta_desc, "body": body, "url": url}


# ---------------------- ROUTES: HEALTH ----------------------
@api_router.get("/")
async def root():
    return {"message": "AI Ads Studio backend running", "ts": now_iso()}


# ---------------------- ROUTES: WEBSITES ----------------------
@api_router.post("/websites", response_model=Website)
async def create_website(payload: WebsiteCreate):
    site = Website(**payload.model_dump())
    await db.websites.insert_one(site.model_dump())
    return site


@api_router.get("/websites", response_model=List[Website])
async def list_websites():
    docs = await db.websites.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api_router.patch("/websites/{wid}", response_model=Website)
async def update_website(wid: str, payload: WebsiteUpdate):
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
async def delete_website(wid: str):
    result = await db.websites.delete_one({"id": wid})
    if result.deleted_count == 0:
        raise HTTPException(404, "Website not found")
    return {"ok": True}


# ---------------------- ROUTES: SCRAPE ----------------------
@api_router.post("/scrape")
async def scrape(payload: ScrapeRequest):
    try:
        data = await _scrape_url(payload.url)
        return data
    except Exception as e:
        raise HTTPException(400, f"Scrape failed: {e}")


# ---------------------- ROUTES: GENERATE ----------------------
@api_router.post("/ads/generate", response_model=Ad)
async def generate_ad(payload: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate caption + image immediately. Video is queued in background if requested."""
    # Find website context
    website_name = None
    if payload.website_id:
        site = await db.websites.find_one({"id": payload.website_id}, {"_id": 0})
        if not site:
            raise HTTPException(404, "Website not found")
        website_name = site["name"]

    # 1) Generate caption + hashtags + image prompt + video prompt via GPT
    system = (
        "You are a senior performance-marketing copywriter for Indian social media. "
        "You craft scroll-stopping Instagram & Facebook ad creatives for college and student audiences."
    )
    user_text = f"""Create a complete ad creative pack for this brief.

Brand / Website: {website_name or 'N/A'}
Topic / Product: {payload.topic}
Target audience: {payload.audience}
Tone: {payload.tone}

Return STRICT JSON with these keys and nothing else:
{{
  "caption": "<2-4 line Instagram caption in Hinglish, with 3-5 fitting emojis, persuasive, ends with a soft CTA>",
  "hashtags": ["#tag1", "#tag2", "..."],   // 8-12 relevant hashtags (mix broad + niche, Indian student culture)
  "image_prompt": "<Detailed visual prompt for an AI image model. Square/portrait ad banner. Mention subject, lighting, mood, composition, color palette, typography hints. No text overlay specifics-- focus on visual.>",
  "video_prompt": "<Short 4-8 second cinematic shot description for a video ad model. Specify camera move, subject, action, mood, lighting>"
}}"""
    raw = await _llm_text(system, user_text)
    # Try to parse JSON
    import json, re
    cleaned = raw.strip()
    # strip markdown fences if any
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        # fallback: try to find first {...}
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            raise HTTPException(500, f"LLM returned non-JSON: {raw[:200]}")
        parsed = json.loads(m.group(0))

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

    # 2) Generate image inline
    if payload.include_image and ad.image_prompt:
        try:
            ad.image_path = await _generate_image_to_file(ad.image_prompt, ad_id)
        except Exception as e:
            logger.exception("Image gen failed")
            raise HTTPException(500, f"Image generation failed: {e}")

    # 3) Save ad to DB (without video yet)
    await db.ads.insert_one(ad.model_dump())

    # 4) Kick off video generation in background (if requested)
    if payload.include_video and ad.video_prompt:
        background_tasks.add_task(
            _video_task,
            ad_id,
            ad.video_prompt,
            payload.video_duration,
            payload.video_size,
        )

    return ad


async def _video_task(ad_id: str, prompt: str, duration: int, size: str):
    """Background task: generate video, update ad doc."""
    try:
        # Run sync in threadpool
        loop = asyncio.get_event_loop()
        rel_path = await loop.run_in_executor(
            None, _generate_video_to_file, prompt, ad_id, duration, size
        )
        await db.ads.update_one(
            {"id": ad_id},
            {"$set": {"video_path": rel_path, "video_status": "ready"}},
        )
        logger.info(f"Video ready for ad {ad_id}")
    except Exception as e:
        logger.exception(f"Video gen failed for {ad_id}")
        await db.ads.update_one(
            {"id": ad_id}, {"$set": {"video_status": "failed"}}
        )


# ---------------------- ROUTES: ADS ----------------------
@api_router.get("/ads", response_model=List[Ad])
async def list_ads(website_id: Optional[str] = None, status: Optional[str] = None):
    q = {}
    if website_id:
        q["website_id"] = website_id
    if status:
        q["status"] = status
    docs = await db.ads.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api_router.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str):
    doc = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Ad not found")
    return doc


@api_router.patch("/ads/{ad_id}/status", response_model=Ad)
async def update_ad_status(ad_id: str, payload: StatusUpdate):
    result = await db.ads.find_one_and_update(
        {"id": ad_id}, {"$set": {"status": payload.status}},
        return_document=True, projection={"_id": 0},
    )
    if not result:
        raise HTTPException(404, "Ad not found")
    return result


@api_router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: str):
    doc = await db.ads.find_one({"id": ad_id})
    if not doc:
        raise HTTPException(404, "Ad not found")
    # remove files
    for key, base in [("image_path", MEDIA_DIR), ("video_path", MEDIA_DIR)]:
        rel = doc.get(key)
        if rel:
            try:
                (base / rel).unlink(missing_ok=True)
            except Exception:
                pass
    await db.ads.delete_one({"id": ad_id})
    return {"ok": True}


@api_router.get("/ads/{ad_id}/download/image")
async def download_image(ad_id: str):
    doc = await db.ads.find_one({"id": ad_id}, {"_id": 0})
    if not doc or not doc.get("image_path"):
        raise HTTPException(404, "Image not found")
    path = MEDIA_DIR / doc["image_path"]
    if not path.exists():
        raise HTTPException(404, "Image file missing")
    # mark downloaded
    await db.ads.update_one({"id": ad_id}, {"$set": {"status": "downloaded"}})
    return FileResponse(path, media_type="image/png", filename=f"ad-{ad_id}.png")


@api_router.get("/ads/{ad_id}/download/video")
async def download_video(ad_id: str):
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
async def stats():
    total = await db.ads.count_documents({})
    drafts = await db.ads.count_documents({"status": "draft"})
    approved = await db.ads.count_documents({"status": "approved"})
    downloaded = await db.ads.count_documents({"status": "downloaded"})
    websites = await db.websites.count_documents({})
    pending_videos = await db.ads.count_documents({"video_status": "pending"})
    return {
        "total_ads": total,
        "drafts": drafts,
        "approved": approved,
        "downloaded": downloaded,
        "websites": websites,
        "pending_videos": pending_videos,
    }


# ---------------------- ROUTES: META SETTINGS ----------------------
@api_router.get("/meta-settings")
async def get_meta_settings():
    doc = await db.meta_settings.find_one({}, {"_id": 0})
    if not doc:
        return {"fb_access_token": "", "fb_page_id": "", "ig_account_id": ""}
    return doc


@api_router.put("/meta-settings")
async def upsert_meta_settings(payload: MetaSettings):
    payload.updated_at = now_iso()
    await db.meta_settings.update_one(
        {}, {"$set": payload.model_dump()}, upsert=True
    )
    return payload


# ---------------------- APP WIRING ----------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
