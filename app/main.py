import uuid
import json
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from google_auth_oauthlib.flow import Flow

from app.config import settings
from app.services.pipeline import JobStatus, jobs, run_pipeline
from app.services.youtube_pub import TOKEN_FILE

app = FastAPI(title="Dhamma Audio → Video", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# --- Models ---

class JobRequest(BaseModel):
    audio_url: str
    title: str
    description: str = ""
    publish_telegram: bool = True
    publish_youtube: bool = False
    stock_clip_count: int = 5
    generate_thumbnail: bool = True
    thumbnail_prompt: str = ""


class JobResponse(BaseModel):
    job_id: str
    status: str


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- API ---

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = JobStatus(id=job_id)
    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        audio_url=req.audio_url,
        title=req.title,
        description=req.description,
        publish_telegram=req.publish_telegram,
        publish_youtube=req.publish_youtube,
        stock_clip_count=req.stock_clip_count,
        generate_thumb=req.generate_thumbnail,
        thumbnail_prompt=req.thumbnail_prompt,
    )
    return JobResponse(job_id=job_id, status="pending")


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return {
        "id": job.id,
        "status": job.status,
        "step": job.step,
        "progress": job.progress,
        "error": job.error,
        "output_path": job.output_path,
        "thumbnail_path": job.thumbnail_path,
        "telegram_result": job.telegram_result,
        "youtube_url": job.youtube_url,
    }


@app.get("/api/jobs")
async def list_jobs():
    return [
        {
            "id": j.id,
            "status": j.status,
            "step": j.step,
            "progress": j.progress,
            "created_at": j.created_at,
        }
        for j in sorted(jobs.values(), key=lambda x: x.created_at, reverse=True)
    ]


@app.get("/api/download/{job_id}")
async def download_output(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.output_path:
        return {"error": "No output available"}
    path = Path(job.output_path)
    if not path.exists():
        return {"error": "Output file not found"}
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.get("/api/thumbnail/{job_id}")
async def get_thumbnail(job_id: str):
    """Download or preview the generated thumbnail."""
    job = jobs.get(job_id)
    if not job or not job.thumbnail_path or job.thumbnail_path.startswith("Error"):
        return {"error": "No thumbnail available"}
    path = Path(job.thumbnail_path)
    if not path.exists():
        return {"error": "Thumbnail file not found"}
    return FileResponse(path, media_type="image/png", filename=path.name)


# --- YouTube OAuth ---

@app.get("/api/youtube/auth")
async def youtube_auth(request: Request):
    """Start YouTube OAuth2 flow."""
    if not settings.youtube_client_id or not settings.youtube_client_secret:
        return {"error": "YouTube client ID/secret not configured"}

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.youtube_client_id,
                "client_secret": settings.youtube_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
        redirect_uri=str(request.url_for("youtube_callback")),
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"auth_url": auth_url}


@app.get("/api/youtube/callback")
async def youtube_callback(request: Request, code: str = ""):
    """Handle YouTube OAuth2 callback."""
    if not code:
        return {"error": "No authorization code"}

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.youtube_client_id,
                "client_secret": settings.youtube_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
        redirect_uri=str(request.url_for("youtube_callback")),
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
    }))

    return HTMLResponse("<h2>YouTube authorized successfully! You can close this tab.</h2>")


@app.get("/api/config/status")
async def config_status():
    """Check which services are configured."""
    return {
        "pexels": bool(settings.pexels_api_key),
        "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "youtube": bool(settings.youtube_client_id) and TOKEN_FILE.exists(),
        "youtube_oauth_needed": bool(settings.youtube_client_id) and not TOKEN_FILE.exists(),
        "openai": bool(settings.openai_api_key),
    }
