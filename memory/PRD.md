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

## Implemented (Feb 20, 2026 — iter-5: code-quality)
- ✅ **Token storage hardened**: JWT moved from `localStorage` → `sessionStorage` + in-memory mirror (`/app/frontend/src/lib/tokenStore.js`). Token now wipes on tab close, drastically shrinking XSS exfiltration window.
- ✅ **Admin wallet = unlimited**: `_charge_user` and auto-gen scheduler skip deduction for `role == "admin"`. `GET /api/wallet` returns `unlimited: true` for admins; frontend badge shows "∞ UNLIMITED".
- ✅ **Watermark logic extracted** into `/app/backend/services/watermark.py` — small focused helpers (`fetch_website_logo_bytes`, `apply_logo_watermark`). `server.py` shrunk from 1342 → 1230 lines.
- ✅ **LLM error UX**: text + image generation wrap upstream `LlmChat` calls; budget/rate-limit errors now return HTTP 503 with friendly messages instead of generic 500.
- ✅ **Code-quality fixes**: hardcoded test creds → env vars; magic numbers (180000, 60000) → named constants; `console.warn` wrapped in dev-only conditional; ambiguous `l` variable renamed in test file.
- ✅ **Iter-5 backend tests**: 15/15 pytest cases passed (`/app/test_reports/iteration_5.json`).

## Implemented (Feb 20, 2026 — iter-4: watermark + security)
- ✅ **Automatic logo watermarking** on every generated/variant/auto-gen ad image. Picks the website's `<link rel=icon>` / `apple-touch-icon` / `og:image` → `/favicon.ico` → Google Favicon API. If no logo found, falls back to a text-only brand-name badge. Composited bottom-right with a semi-translucent white badge for legibility on any background. (`_fetch_website_logo_bytes` + `_apply_logo_watermark` in server.py)
- ✅ **Auth + tenant isolation** on `/ads/{id}/download/image`, `/ads/{id}/download/video`, `/ads/{id}/publish` — all now require `Depends(get_current_user)` and filter by `owner_id` for non-admins.
- ✅ **`owner_id` field added to `Ad` pydantic model** (previously dropped by `extra="ignore"`).
- ✅ **Per-website Meta credentials preferred** in `publish_ad` over legacy global `meta_settings` collection.
- ✅ Backend testing iter-4: 14/14 pytest cases passed — auth, tenant isolation, watermark, publish-gate, variant flow, public lead capture.

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
