# ☁️ APK Cloud Build Guide — No Android Studio Needed

GitHub Actions par APK automatically build hoga. Total time: ~15 minutes setup, phir har APK ~3-5 min mein.

---

## ✅ What You Get

- 📱 **Real APK file** (not PWA)
- 🚫 **No "emergent" name** visible in app anywhere (Capacitor native WebView)
- 🎨 **Yellow "A" icon** on phone home screen
- 💯 **No Android Studio** installation needed
- ☁️ **Cloud build** — APK ready in GitHub Actions
- 🆓 **Free** (GitHub Actions free tier)

---

## 📋 Setup (One-Time, ~15 min)

### Step 1 — GitHub Account (Free)
- Agar account nahi hai: https://github.com/signup
- Email verify karein

### Step 2 — Code GitHub par push karein
- Emergent chat input ke neeche **"Save to GitHub"** button click karein
- Apne GitHub account ko connect karein
- New repo banaiye: `ads-studio` (ya kuch bhi naam)
- Push hone do — ~30 seconds

### Step 3 — APK Build Workflow chalao

1. GitHub par apna repo open karein
2. Top mein **"Actions"** tab click karein
3. Left sidebar mein **"Build Android APK"** workflow dikhega
4. Right side mein **"Run workflow"** dropdown click karein
5. **"Run workflow"** green button click karein
6. ⏳ Wait 5-7 min (cloud par sab build ho raha hai)

### Step 4 — APK Download karein

1. Workflow complete hone par green checkmark dikhega
2. Workflow run click karein
3. Bottom mein **"Artifacts"** section mein **`ads-studio-debug-apk`** milega
4. Click karke download karein — ZIP milegi
5. ZIP extract karein → **`app-debug.apk`** mil jayegi

### Step 5 — Phone par install karein

1. APK file phone par bhejein:
   - WhatsApp se share kar do (xaapne aap ko)
   - Ya Google Drive par upload → phone par download
   - Ya USB cable
2. Phone par tap APK
3. Settings → **"Install from unknown sources"** allow karein (agar maange)
4. **Install** click karein
5. Done! ✅ App icon home screen par dikhega → tap → app open

---

## 🔄 Code Update Karne Ke Baad

Whenever you change something in the app:

1. Emergent mein code update karein
2. **"Save to GitHub"** button click karein (push to same repo)
3. GitHub Actions automatic chalega (har push par)
4. ~5 min mein naya APK ready
5. Download karke install (purani APK uninstall ya replace ho jayegi)

---

## 🌐 URL "emergent" Word Se Hata Ne Ke Liye

Abhi APK internally `smart-content-pub.preview.emergentagent.com` se baat karta hai. Aap user-facing UI mein yeh URL kahin nahi dikhega (Capacitor native WebView use karta hai, koi address bar nahi).

**But agar aap chahein ki backend ka URL bhi "emergent" naam se na ho:**

### Option A: Custom Domain (₹600/year)
1. Domain kharidein: Namecheap / GoDaddy / Hostinger
   - Example: `adsstudio.in` ya `collegeop.app`
2. Backend ko Render/Railway par deploy karein
3. Domain ko backend se point karein (DNS CNAME)
4. GitHub Actions Secret update karein:
   - Repo → Settings → Secrets and variables → Actions
   - **"New repository secret"**:
     - Name: `REACT_APP_BACKEND_URL`
     - Value: `https://api.adsstudio.in` (apne domain ka URL)
5. Workflow re-run → naya APK ab aapke custom URL se baat karega

### Option B: Free Subdomain
- `*.onrender.com` (Render free hosting) — "onrender" word dikhega
- `*.up.railway.app` (Railway) — "railway" dikhega
- `*.vercel.app` (Vercel) — "vercel" dikhega

These are FREE but have provider's name. Custom domain (Option A) sabse clean hai.

---

## ⚠️ Troubleshooting

### Workflow fail ho raha hai?
- Repo → Actions → failed run open karein
- "Show logs" click karke exact error dekho
- Mujhe error screenshot share karein, fix bata dunga

### APK install nahi ho raha?
- Phone Settings → Apps → "Install unknown apps" → Chrome/your-file-manager → Allow

### Icon nahi dikh raha install ke baad?
- Phone restart karke dekhein
- Settings → Apps → "Ads Studio" search karein — agar dikha to fix successful

### App khulne par crash?
- Phone ka **Chrome browser version 80+** hona chahiye (modern WebView)
- Internet on hona chahiye

---

## 💡 Pro Tips

1. **Signed Release APK** (Play Store ke liye): Workflow YAML mein signing setup add kar sakte hain — bataiye karwana hai to.
2. **Auto-deploy on push**: Already setup hai — `main` branch par push karte hi APK build ho jayega
3. **Multiple versions**: GitHub Actions har run ko alag artifact save karta hai, 30 din tak available

---

Done! GitHub Actions workflow ready hai. Bas **Save to GitHub** click karein aur workflow trigger karein. 🚀
