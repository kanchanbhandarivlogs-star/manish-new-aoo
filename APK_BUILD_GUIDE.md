# 📱 Ads Studio APK — Android Build Guide (Hindi/Hinglish)

Aapke laptop par APK file build karne ke liye yeh steps follow karein.

---

## ✅ Already Done (Maine kar diya hai)

- ✅ Capacitor v7 installed
- ✅ Android project generated at `frontend/android/`
- ✅ App ID: `com.collegeop.adsstudio`
- ✅ App Name: **Ads Studio**
- ✅ Custom yellow "A" icon at all densities (mdpi–xxxhdpi)
- ✅ Production React build copied into Android assets
- ✅ Backend URL hardcoded into APK: `https://smart-content-pub.preview.emergentagent.com`

---

## 🛠️ Aapko Kya Karna Hai (One-Time Setup)

### Step 1 — GitHub se code download karein

1. Emergent chat input ke neeche **"Save to GitHub"** click karein
2. Apne GitHub repo mein push karein
3. Apne laptop par clone karein:
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

### Step 2 — Android Studio install karein (one-time, ~10 GB)

- 🔗 Download: https://developer.android.com/studio
- Install karte waqt yeh check karein:
  - ✅ Android SDK
  - ✅ Android SDK Platform-Tools
  - ✅ Android Virtual Device (optional, emulator ke liye)

### Step 3 — Dependencies install karein

```bash
cd frontend
yarn install
yarn build
npx cap sync android
```

### Step 4 — Android Studio mein kholiye

```bash
npx cap open android
```

Ya manually: Android Studio → "Open" → `frontend/android` folder select karein.

### Step 5 — APK Build karein

Android Studio mein:

**Method A: Debug APK (testing ke liye, instant install)**
1. Top menu: **Build → Build Bundle(s) / APK(s) → Build APK(s)**
2. 2–5 min wait karein
3. Bottom-right notification mein **"locate"** click karein
4. `app-debug.apk` file milegi at: `frontend/android/app/build/outputs/apk/debug/`

**Method B: Signed Release APK (sharing ke liye)**
1. Top menu: **Build → Generate Signed Bundle / APK**
2. **APK** select karein → Next
3. **"Create new"** keystore (pehli baar):
   - Path: koi safe location (e.g. `~/keystores/ads-studio.jks`)
   - Password: koi strong password (yaad rakhein!)
   - Alias: `ads-studio`
   - Validity: 25 years
   - First/Last name: aapka naam
4. Build Type: **release** → Finish
5. ~3 min wait karein → APK ready

---

## 📤 APK Share / Install Karne Ka Tarika

### Apne phone par install karna:
1. APK file phone mein bhejein (WhatsApp / USB cable / Google Drive)
2. Phone settings: **"Install from unknown sources"** allow karein
3. APK file tap karein → Install

### Clients ko share karna:
- WhatsApp se direct APK bhej sakte hain
- Email attachment ke through
- Google Drive shared link
- Ya Play Store par publish (separate flow, AAB chahiye)

---

## 🔄 Code Update Karne Ke Baad (Re-build)

Jab bhi code mein change ho:

```bash
cd frontend
yarn build              # React app re-build
npx cap sync android    # Android wrapper update
```

Phir Android Studio mein **Build → Build APK(s)** se new APK ban jayegi.

---

## 🎨 App Icon Customize Karna (Optional)

Abhi ek yellow "A" placeholder icon hai. Apna logo lagana ho:

1. 1024x1024 px ka PNG banao
2. https://icon.kitchen mein upload karo (free tool)
3. Generated icons download karo → `android/app/src/main/res/mipmap-*` folders mein paste karo
4. `npx cap sync android` chala kar Android Studio mein dobara build karo

---

## ⚠️ Important Notes

1. **APK iPhone par NAHI chalega** — woh iOS hai, alag build chahiye
2. **Internet zaroori hai** — APK aapke deployed backend se baat karta hai
3. **Backend URL change** karna ho to:
   - `frontend/.env` mein `REACT_APP_BACKEND_URL` update karein
   - `yarn build && npx cap sync android` chalakar APK dobara build karein
4. **Play Store** ke liye AAB file chahiye:
   - `Build → Generate Signed Bundle / APK → Android App Bundle`

---

## 🆘 Common Errors

| Error | Solution |
|---|---|
| `SDK location not found` | Android Studio → File → Project Structure → SDK Location set karein |
| `Gradle sync failed` | File → Invalidate Caches / Restart |
| `Java version mismatch` | Project Structure → Java 17 select karein |
| APK install nahi ho raha | Phone settings → Security → Unknown sources ON karein |

---

## 📞 Help

Koi step atak jaye to mujhe (E1 agent) chat mein puch lena — guide kar dunga.

Happy building! 🚀
