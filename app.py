"""
VidGrab Pro — Application Server
"""

import os
import re
import shutil
import uuid
import threading
from datetime import timedelta

import yt_dlp
from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for, session, abort
)
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)

import database as db

# ──────────────────────────── Config ────────────────────────────

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-please-change-in-production"),
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    MAX_CONTENT_LENGTH=64 * 1024 * 1024,
)

login_manager = LoginManager(app)
login_manager.login_view = "login"

JOBS = {}  # in-memory job registry

db.init_db()  # ensure SQLite schema exists (runs at import so Gunicorn works too)


# ──────────────────────────── Auth ────────────────────────────

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = str(id)
        self.username = username
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    u = db.get_user(user_id)
    return User(**u) if u else None


def current_identity():
    """Returns (username, is_guest)"""
    if current_user.is_authenticated:
        return current_user.username, False
    if session.get("guest"):
        return "Guest", True
    return None, False


# ──────────────────────────── Helpers ────────────────────────────

def human_size(num):
    if not num:
        return "-"
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def human_speed(bps):
    return f"{human_size(bps)}/s" if bps else "—"


def human_eta(sec):
    if not sec:
        return "—"
    m, s = divmod(int(sec), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def safe_name(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:120]


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def clean_error(msg):
    """Strip ANSI color codes and truncate to first line for JSON display."""
    return _ANSI_RE.sub("", msg).split("\n")[0].strip()[:200]


def get_ffmpeg_location():
    """Return an explicit ffmpeg/ffprobe directory if one is bundled, else None.

    Priority:
      1. FFMPEG_LOCATION env (Render/admin override)
      2. imageio_ffmpeg bundled static binary (works on Render without apt)
      3. FFmpeg found on PATH (local dev)
    """
    override = os.environ.get("FFMPEG_LOCATION")
    if override and os.path.isdir(override):
        return override
    try:
        import imageio_ffmpeg
        binary = imageio_ffmpeg.get_ffmpeg_exe()
        if binary:
            return os.path.dirname(binary)
    except Exception:
        pass  # imageio-ffmpeg not installed — fall through to PATH
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    return None


def base_ydl_opts(**extra):
    """Shared yt-dlp options. Keeps extraction robust against YouTube bot
    detection and soft-blocks."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "js_runtimes": {},
        "ffmpeg_location": get_ffmpeg_location(),
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    }
    opts.update(extra)
    return opts


# ──────────────────────────── Pages ────────────────────────────

@app.route("/")
def home():
    username, is_guest = current_identity()
    if not username:
        return redirect(url_for("login"))
    return render_template("index.html", username=username, is_guest=is_guest)


@app.route("/history")
@login_required
def history_page():
    return render_template(
        "history.html",
        username=current_user.username,
        history=db.get_history(current_user.id),
        stats=db.get_stats(current_user.id),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json(silent=True) or {}
    user = db.verify_user(data.get("username", "").strip(), data.get("password", ""))
    if not user:
        return jsonify(ok=False, error="Incorrect username or password"), 401

    login_user(User(**user), remember=True)
    session.permanent = True
    session.pop("guest", None)
    return jsonify(ok=True, redirect="/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if len(username) < 3:
        return jsonify(ok=False, error="Username must be at least 3 characters"), 400
    if "@" not in email:
        return jsonify(ok=False, error="Please enter a valid email address"), 400
    if len(password) < 6:
        return jsonify(ok=False, error="Password must be at least 6 characters"), 400

    res = db.create_user(username, email, password)
    if not res["ok"]:
        return jsonify(ok=False, error=res["error"]), 409

    login_user(User(res["id"], username, email), remember=True)
    session.permanent = True
    return jsonify(ok=True, redirect="/")


@app.route("/guest")
def guest():
    session["guest"] = True
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login"))


# ──────────────────────────── API ────────────────────────────

@app.post("/api/inspect")
def api_inspect():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="Please enter a valid link (must start with http)"), 400

    opts = base_ydl_opts(skip_download=True)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify(error=f"Could not read this link. {clean_error(str(e))}"), 400

    if info.get("_type") == "playlist":
        info = (info.get("entries") or [{}])[0]

    # Collect unique video qualities
    buckets = {}
    for f in info.get("formats", []):
        h = f.get("height")
        if not h or f.get("vcodec") == "none":
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        prev = buckets.get(h)
        if not prev or size > prev["_raw"]:
            buckets[h] = {
                "id": f["format_id"],
                "label": f"{h}p",
                "ext": f.get("ext", "mp4"),
                "fps": f.get("fps"),
                "size": human_size(size),
                "hd": h >= 720,
                "_raw": size,
            }

    formats = sorted(buckets.values(), key=lambda x: -int(x["label"][:-1]))
    for f in formats:
        f.pop("_raw", None)

    if not formats:
        formats = [{"id": "best", "label": "Best", "ext": "mp4", "fps": None, "size": "-", "hd": True}]

    return jsonify(
        title=info.get("title") or "Untitled",
        thumbnail=info.get("thumbnail") or "",
        duration=info.get("duration") or 0,
        uploader=info.get("uploader") or info.get("channel") or "Unknown",
        views=info.get("view_count") or 0,
        platform=(info.get("extractor_key") or "Web"),
        formats=formats,
    )


@app.post("/api/download")
def api_download():
    d = request.get_json(silent=True) or {}
    url = d.get("url", "").strip()
    if not url:
        return jsonify(error="Missing URL"), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"state": "queued", "percent": 0, "speed": "—", "eta": "—"}
    user_id = current_user.id if current_user.is_authenticated else None

    media_type = d.get("type", "video")
    fmt_id = d.get("format_id", "best")
    meta = {
        "title": d.get("title", "Unknown"),
        "thumbnail": d.get("thumbnail", ""),
        "platform": d.get("platform", "Web"),
        "quality": d.get("quality", "Best"),
        "url": url,
    }

    def hook(p):
        if p["status"] == "downloading":
            total = p.get("total_bytes") or p.get("total_bytes_estimate") or 0
            done = p.get("downloaded_bytes") or 0
            JOBS[job_id] = {
                "state": "downloading",
                "percent": round(done / total * 100, 1) if total else 0,
                "speed": human_speed(p.get("speed")),
                "eta": human_eta(p.get("eta")),
            }
        elif p["status"] == "finished":
            JOBS[job_id] = {"state": "processing", "percent": 100, "speed": "—", "eta": "—"}

    out_tpl = os.path.join(DOWNLOAD_DIR, f"{job_id}__%(title).80s.%(ext)s")

    if media_type == "audio":
        opts = base_ydl_opts(
            format="bestaudio/best",
            outtmpl=out_tpl,
            progress_hooks=[hook],
            postprocessors=[{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        )
    else:
        selector = f"{fmt_id}+bestaudio/{fmt_id}/best" if fmt_id != "best" else "bestvideo+bestaudio/best"
        opts = base_ydl_opts(
            format=selector,
            outtmpl=out_tpl,
            progress_hooks=[hook],
            merge_output_format="mp4",
        )

    def worker():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

            # locate produced file
            target = None
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(job_id + "__"):
                    target = os.path.join(DOWNLOAD_DIR, f)
                    if media_type == "audio" and f.endswith(".mp3"):
                        break
                    if media_type == "video" and f.endswith((".mp4", ".mkv", ".webm")):
                        break

            if not target or not os.path.exists(target):
                raise FileNotFoundError("Output file missing")

            size = human_size(os.path.getsize(target))
            ext = os.path.splitext(target)[1]
            nice = safe_name(info.get("title", "download")) + ext

            JOBS[job_id] = {
                "state": "done",
                "percent": 100,
                "speed": "—",
                "eta": "—",
                "path": target,
                "filename": nice,
                "size": size,
            }

            if user_id:
                db.add_history(user_id, media_type=media_type, file_size=size, **meta)

        except Exception as e:
            JOBS[job_id] = {"state": "error", "error": clean_error(str(e))}

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(job=job_id)


@app.get("/api/status/<job>")
def api_status(job):
    return jsonify(JOBS.get(job, {"state": "unknown"}))


@app.get("/api/file/<job>")
def api_file(job):
    j = JOBS.get(job)
    if not j or j.get("state") != "done":
        abort(404)
    return send_file(j["path"], as_attachment=True, download_name=j["filename"])


@app.delete("/api/history/<int:item_id>")
@login_required
def api_del_history(item_id):
    db.delete_history(item_id, current_user.id)
    return jsonify(ok=True)


@app.delete("/api/history")
@login_required
def api_clear_history():
    db.clear_history(current_user.id)
    return jsonify(ok=True)


# ──────────────────────────── Error handlers ────────────────────────────

def _api_error(status, message):
    """Return a JSON error when the request targets an API route, HTML otherwise."""
    if request.path.startswith("/api/"):
        return jsonify(error=message), status
    return message, status


@app.errorhandler(404)
def not_found(e):
    return _api_error(404, "Not found")


@app.errorhandler(405)
def method_not_allowed(e):
    return _api_error(405, "Method not allowed")


@app.errorhandler(413)
def too_large(e):
    return _api_error(413, "Request too large")


@app.errorhandler(500)
def server_error(e):
    return _api_error(500, "Internal server error. Please try again.")


# ──────────────────────────── Run ────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"\n  > VidGrab Pro running at  http://127.0.0.1:{port}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)