"""
Rhythm OS — Backend Server
Handles Spotify OAuth token exchange and MP3 downloads via spotDL/yt-dlp.

Deploy this on Render (free tier) — see README.md for instructions.
"""

import os, json, tempfile, threading, time, uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app, origins="*")

# ─── Config ────────────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
FRONTEND_URL          = os.environ.get("FRONTEND_URL", "http://localhost:8080")

# In-memory job store (resets on server restart, fine for free tier)
jobs = {}   # job_id -> { status, progress, message, file_path, filename, error }

# ─── Health check ──────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return jsonify({"ok": True, "service": "Rhythm OS Backend"})

# ─── Spotify token exchange ─────────────────────────────────────────────────
@app.route("/token", methods=["POST"])
def token():
    """Exchange authorization code for access token (keeps client_secret off the frontend)."""
    data = request.json or {}
    code          = data.get("code")
    redirect_uri  = data.get("redirect_uri")
    code_verifier = data.get("code_verifier")

    if not all([code, redirect_uri, code_verifier]):
        return jsonify({"error": "Missing code, redirect_uri, or code_verifier"}), 400

    resp = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  redirect_uri,
        "client_id":     SPOTIFY_CLIENT_ID,
        "code_verifier": code_verifier,
    })

    if not resp.ok:
        return jsonify({"error": resp.text}), resp.status_code
    return jsonify(resp.json())

@app.route("/refresh", methods=["POST"])
def refresh():
    """Refresh an expired access token."""
    data = request.json or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Missing refresh_token"}), 400

    resp = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     SPOTIFY_CLIENT_ID,
    })
    if not resp.ok:
        return jsonify({"error": resp.text}), resp.status_code
    return jsonify(resp.json())

# ─── Download job management ────────────────────────────────────────────────
def run_download(job_id: str, spotify_url: str):
    """Run spotDL in a thread, update job status as it progresses."""
    job = jobs[job_id]
    try:
        import subprocess, shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            job["status"]   = "downloading"
            job["message"]  = "Finding audio source…"
            job["progress"] = 10

            cmd = [
                "spotdl", "download", spotify_url,
                "--output", tmpdir,
                "--format", "mp3",
                "--bitrate", "128k",
                "--no-cache",
            ]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in proc.stdout:
                line = line.strip()
                print(f"[spotdl] {line}")
                if "Downloading" in line:
                    job["message"]  = "Downloading…"
                    job["progress"] = 40
                elif "Converting" in line or "FFmpeg" in line:
                    job["message"]  = "Converting to MP3…"
                    job["progress"] = 75
                elif "Downloaded" in line or "Saved" in line:
                    job["message"]  = "Finishing up…"
                    job["progress"] = 90

            proc.wait()

            if proc.returncode != 0:
                job["status"] = "error"
                job["error"]  = "spotDL failed — track may not be available"
                return

            # Find the MP3
            mp3s = list(Path(tmpdir).rglob("*.mp3"))
            if not mp3s:
                job["status"] = "error"
                job["error"]  = "No MP3 produced"
                return

            # Move to a stable temp location (tmpdir will be deleted)
            out_dir  = Path(tempfile.gettempdir()) / "rhythmos_downloads"
            out_dir.mkdir(exist_ok=True)
            dest = out_dir / (job_id + ".mp3")
            shutil.copy2(mp3s[0], dest)

            job["status"]    = "done"
            job["progress"]  = 100
            job["message"]   = "Ready"
            job["file_path"] = str(dest)
            job["filename"]  = mp3s[0].name

            # Auto-delete file after 10 minutes
            def cleanup():
                time.sleep(600)
                dest.unlink(missing_ok=True)
                jobs.pop(job_id, None)
            threading.Thread(target=cleanup, daemon=True).start()

    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)

@app.route("/download/start", methods=["POST"])
def download_start():
    """Kick off a download job. Returns job_id immediately."""
    data        = request.json or {}
    spotify_url = data.get("spotify_url")
    if not spotify_url:
        return jsonify({"error": "Missing spotify_url"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status":    "queued",
        "progress":  0,
        "message":   "Queued…",
        "file_path": None,
        "filename":  None,
        "error":     None,
    }

    thread = threading.Thread(target=run_download, args=(job_id, spotify_url), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/download/status/<job_id>")
def download_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "message":  job["message"],
        "error":    job.get("error"),
    })

@app.route("/download/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Not ready"}), 404
    return send_file(
        job["file_path"],
        as_attachment=True,
        download_name=job["filename"],
        mimetype="audio/mpeg",
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
