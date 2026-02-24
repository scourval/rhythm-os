# Rhythm OS — Setup Guide

This app has two parts:
- **Frontend** (`index.html`) — the app your instructors open in their browser
- **Backend** (`backend/server.py`) — a Python server that downloads MP3s, deployed free on Render

Follow these steps in order. Takes about 20 minutes total.

---

## STEP 1 — Create a Spotify App (5 min)

You need this so instructors can log in with their Spotify accounts.

1. Go to **https://developer.spotify.com/dashboard**
2. Log in with your Spotify account
3. Click **Create app** and fill in:
   - **App name:** `Rhythm OS`
   - **App description:** `DJ tool for instructors`
   - **Redirect URI:** type `https://placeholder.com` for now (you'll update this later)
   - Check ✅ **Web API** and ✅ **Web Playback SDK**
4. Click **Save**
5. On your new app page click **Settings** in the top right
6. Copy your **Client ID** → paste it in a Notepad/Notes file, save it
7. Click **View client secret** → copy and save that too

---

## STEP 2 — Put the code on GitHub (5 min)

Render (the free hosting service) needs your code on GitHub.

1. Go to **https://github.com** → sign up free if needed
2. Click **+** (top right) → **New repository**
3. Name it `rhythm-os` → set to **Public** → click **Create repository**
4. Open **Terminal** on Mac, or **Command Prompt** on Windows
5. Type these commands one at a time, pressing Enter after each:

```
cd Desktop
mkdir rhythm-os
cd rhythm-os
```

6. Create a folder called `backend` inside `rhythm-os`
7. Copy `backend/server.py`, `backend/requirements.txt`, and `backend/render.yaml` into that folder
8. Then run:

```
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/rhythm-os.git
git push -u origin main
```

Replace `YOUR-GITHUB-USERNAME` with your actual GitHub username.
It will ask for your GitHub username and password — use a [Personal Access Token](https://github.com/settings/tokens) as the password.

---

## STEP 3 — Deploy the Backend on Render (5 min)

Render gives you free Python hosting.

1. Go to **https://render.com** → Sign up using your GitHub account (easiest)
2. Click **New +** → **Web Service**
3. Choose **"Connect a repository"** → select `rhythm-os`
4. Fill in:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt && spotdl --download-ffmpeg`
   - **Start Command:** `gunicorn server:app`
   - **Instance Type:** Free
5. Scroll to **Environment Variables** → click **Add Environment Variable** for each:
   | Key | Value |
   |-----|-------|
   | `SPOTIFY_CLIENT_ID` | your Client ID from Step 1 |
   | `SPOTIFY_CLIENT_SECRET` | your Client Secret from Step 1 |
6. Click **Create Web Service**
7. Watch the logs — build takes 3–5 minutes
8. When you see **"Your service is live"**, copy the URL
   It looks like: `https://rhythm-os-backend.onrender.com`
   **Save this URL.**

---

## STEP 4 — Deploy the Frontend on Netlify (2 min)

1. Go to **https://netlify.com** → sign up free
2. On the dashboard, you'll see a box that says **"Drag and drop your site folder here"**
3. Drag your `index.html` file directly onto that box
4. Wait about 30 seconds
5. Netlify gives you a URL like `https://luminous-fox-abc123.netlify.app`
   **Save this URL.**

---

## STEP 5 — Wire It All Together (3 min)

You now have all three pieces. Time to connect them.

### Update index.html:

Open `index.html` in any text editor (Notepad on Windows, TextEdit on Mac, or VS Code).

Find these lines near the top of the `<script>` section:

```javascript
const HARDCODED_CLIENT_ID = ''; // Set your Spotify Client ID here
const BACKEND_URL = ''; // Set your Render backend URL here
```

Replace with your actual values — keep the quotes:

```javascript
const HARDCODED_CLIENT_ID = 'paste_your_client_id_here';
const BACKEND_URL = 'https://rhythm-os-backend.onrender.com';
```

Find this line:

```javascript
const HARDCODED_REDIRECT_URI = ''; // Set to your deployed frontend URL
```

Replace with your Netlify URL:

```javascript
const HARDCODED_REDIRECT_URI = 'https://luminous-fox-abc123.netlify.app';
```

Save the file, then **drag and drop it onto Netlify again** to update it (same process as Step 4).

### Update Spotify Redirect URI:

1. Go back to **https://developer.spotify.com/dashboard**
2. Open your Rhythm OS app → **Settings** → **Edit**
3. Under **Redirect URIs**, remove `https://placeholder.com`
4. Add your Netlify URL: `https://luminous-fox-abc123.netlify.app`
5. Click **Save**

---

## STEP 6 — Test It! 🎉

1. Open your Netlify URL in a browser
2. Go through the setup wizard (choose modality, BPM buckets, etc.)
3. Click **Connect Spotify** and log in
4. Your liked songs should start loading
5. Click **⬇ Download Songs** in the topbar
6. Paste your Render URL in the Backend URL box and click **Save**
7. Click **⬇ Download All Liked Songs**

Songs will download 2 at a time. Each takes ~30–60 seconds (the backend finds it on YouTube, converts to MP3, sends it to you).

---

## Sharing with Your Instructors

Just send them your Netlify URL. They go to the site, log in with **their own Spotify**, and the app loads their library. Downloads go straight to their own computer. Nothing is stored permanently — files are deleted from the server after 10 minutes.

---

## Troubleshooting

**"Cannot reach backend" in the download modal**
The Render free tier goes to sleep after 15 min of inactivity. The first request wakes it up (takes ~30 sec). Just wait and click **Save** again.

**Spotify shows "INVALID_CLIENT: Invalid redirect URI"**
The Redirect URI in your Spotify dashboard must exactly match your Netlify URL — same capitalization, no trailing slash, must start with `https://`.

**"spotDL failed — track may not be available"**
A small % of tracks can't be matched on YouTube. This is normal. The rest of your songs will still download fine.

**Songs aren't loading / stuck at 0**
Double-check the `HARDCODED_CLIENT_ID` value in `index.html` — it must exactly match the Client ID shown in your Spotify dashboard.
# rhythm.os
# rhythm-os
