"""
Rhythm OS — Backend Server
Downloads Spotify tracks as MP3 using yt-dlp (searches YouTube by track name).
"""

import os, json, subprocess, tempfile, threading, time, uuid, shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests as req

app = Flask(__name__)
CORS(app, origins="*")

SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

jobs = {}  # job_id -> dict

# ── Spotify helpers ──────────────────────────────────────────────────────────
def get_spotify_token():
    """Get a client-credentials token for metadata lookup."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    r = req.post("https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET))
    return r.json().get("access_token") if r.ok else None

def get_track_info(spotify_url):
    """Return (title, artist) from a Spotify track URL."""
    track_id = spotify_url.rstrip("/").split("/")[-1].split("?")[0]
    token = get_spotify_token()
    if not token:
        return None, None
    r = req.get(f"https://api.spotify.com/v1/tracks/{track_id}",
                headers={"Authorization": f"Bearer {token}"})
    if not r.ok:
        return None, None
    d = r.json()
    title  = d.get("name", "")
    artist = ", ".join(a["name"] for a in d.get("artists", []))
    return title, artist

# ── Download worker ──────────────────────────────────────────────────────────
def run_download(job_id: str, spotify_url: str):
    job = jobs[job_id]
    try:
        # 1. Get track info from Spotify
        job["message"] = "Looking up track…"; job["progress"] = 10
        title, artist = get_track_info(spotify_url)

        if not title:
            job["status"] = "error"
            job["error"]  = "Could not look up track — check SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in Render environment variables"
            return

        search_query = f"{artist} - {title} audio"
        job["message"]  = f"Searching: {artist} – {title}"
        job["progress"] = 25
        print(f"[dl] {search_query}")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_tmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

            cmd = [
                "yt-dlp",
                f"ytsearch1:{search_query}",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "5",
                "--output", out_tmpl,
                "--no-playlist",
                "--max-downloads", "1",
                "--socket-timeout", "30",
                "--retries", "3",
                "--no-warnings",
            ]

            job["message"] = "Downloading audio…"; job["progress"] = 45

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180, cwd=tmpdir
            )

            print(f"[yt-dlp rc={result.returncode}]")
            print(f"[stdout] {result.stdout[-800:]}")
            print(f"[stderr] {result.stderr[-800:]}")

            if result.returncode != 0:
                err = (result.stderr or result.stdout or "yt-dlp failed").strip()[-400:]
                job["status"] = "error"; job["error"] = err
                return

            job["message"] = "Finishing up…"; job["progress"] = 85

            audio = (list(Path(tmpdir).rglob("*.mp3")) +
                     list(Path(tmpdir).rglob("*.m4a")) +
                     list(Path(tmpdir).rglob("*.opus")))

            if not audio:
                job["status"] = "error"
                job["error"]  = "No audio file produced. " + result.stderr[-200:]
                return

            out_dir = Path(tempfile.gettempdir()) / "rhythmos_dl"
            out_dir.mkdir(exist_ok=True)
            safe = f"{artist} - {title}"[:80].replace("/","-")
            dest = out_dir / f"{job_id}.mp3"
            shutil.copy2(audio[0], dest)

            job.update({"status":"done","progress":100,"message":"Ready",
                        "file_path":str(dest),"filename":f"{safe}.mp3"})

            def cleanup():
                time.sleep(600); dest.unlink(missing_ok=True); jobs.pop(job_id,None)
            threading.Thread(target=cleanup, daemon=True).start()

    except subprocess.TimeoutExpired:
        job["status"]="error"; job["error"]="Timed out after 3 minutes"
    except Exception as e:
        import traceback
        job["status"]="error"; job["error"]=f"{type(e).__name__}: {e}"
        print(traceback.format_exc())

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return jsonify({
        "ok": True,
        "ffmpeg": shutil.which("ffmpeg") or "not found",
        "ytdlp":  shutil.which("yt-dlp")  or "not found",
    })

@app.route("/download/start", methods=["POST"])
def download_start():
    data = request.json or {}
    url  = data.get("spotify_url","").strip()
    if not url: return jsonify({"error":"Missing spotify_url"}), 400
    jid = str(uuid.uuid4())[:8]
    jobs[jid] = {"status":"queued","progress":0,"message":"Queued…",
                 "file_path":None,"filename":None,"error":None}
    threading.Thread(target=run_download, args=(jid, url), daemon=True).start()
    return jsonify({"job_id": jid})

@app.route("/download/status/<jid>")
def download_status(jid):
    j = jobs.get(jid)
    if not j: return jsonify({"error":"Not found"}), 404
    return jsonify({"status":j["status"],"progress":j["progress"],
                    "message":j["message"],"error":j.get("error")})

@app.route("/download/file/<jid>")
def download_file(jid):
    j = jobs.get(jid)
    if not j or j["status"]!="done": return jsonify({"error":"Not ready"}), 404
    return send_file(j["file_path"], as_attachment=True,
                     download_name=j["filename"], mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
