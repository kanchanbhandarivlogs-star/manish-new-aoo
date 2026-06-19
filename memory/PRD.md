# PRD — AI Ads Studio (ADS.STUDIO)

## Original Problem Statement
User runs collegeop.com and wants a free AI tool that generates social media ads (image + video + captions) for any website they configure. They will manually post the downloaded assets. Key requirements:
- Multiple websites must be add/edit/deletable dynamically (no code changes)
- Free AI (using Emergent Universal Key)
- Image ads, video ads, and captions
- Approval workflow (Draft → Approved → Downloaded)

## Tech Stack
- Backend: FastAPI + Motor (MongoDB)
- Frontend: React 19 + TailwindCSS (neo-brutalist theme)
- AI: GPT-5.2 (captions), Nano Banana (images), Sora 2 (videos) via emergentintegrations + EMERGENT_LLM_KEY
- Scraping: BeautifulSoup + lxml

## Implemented (June 19, 2026)
- ✅ Websites Manager (add/edit/delete, multiple websites, no code needed)
- ✅ URL Scraper (title + meta-description + body excerpt)
- ✅ AI Ad Generation pipeline (caption + hashtags + image-prompt + video-prompt in one LLM call → image inline → video in background)
- ✅ Image ads with Nano Banana (saved to disk, served at /api/media/images/{id}.png)
- ✅ Video ads with Sora 2 (background generation, status tracked: pending/ready/failed)
- ✅ Approval Dashboard (Draft → Approved → Downloaded with status badges)
- ✅ Ad Gallery (filters by status + website, focus modal with full caption, hashtags, image, video player)
- ✅ Download endpoints (image PNG, video MP4) that auto-mark as downloaded
- ✅ Copy caption + hashtags to clipboard
- ✅ Meta Settings page (editable Facebook token, page ID, IG account ID — stored in DB, no code change required)
- ✅ Dashboard stats + peak student-traffic hour suggestions
- ✅ Neo-brutalist pastel UI with Outfit/Figtree fonts and marquee ticker

## Personas
- Primary: collegeop.com owner / small marketing team. Needs daily fresh ads, posts manually to IG/FB.
- Secondary: Any small Indian SaaS / D2C brand wanting AI ad generation.

## P0 (next iteration if requested)
- Direct Meta posting (FB Page + IG Business publish) using stored token
- Scheduled auto-generation at peak hours (cron job)
- Image editing (regenerate variations from existing ad)

## P1
- Multi-language captions
- A/B caption variants in one click
- Analytics: track which downloaded ads performed best
