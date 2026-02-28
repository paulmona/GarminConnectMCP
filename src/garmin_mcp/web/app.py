"""FastAPI web application for GarminClaudeSync configuration.

SECURITY:
- CSRF protection via per-session tokens on all POST forms.
- Binds to 127.0.0.1 only (localhost).
- OpenAPI/Swagger docs disabled to reduce attack surface.
- Credentials are stored in .env (gitignored), never in config.json.
"""

import secrets
from pathlib import Path

from dotenv import get_key, set_key
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config_store import load_config, save_config

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
ENV_PATH = Path(".env")

app = FastAPI(title="GarminClaudeSync Config", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# CSRF token store keyed by session ID
_csrf_tokens: dict[str, str] = {}


def _get_csrf_token(session_id: str) -> str:
    """Get or create a CSRF token for a session."""
    if session_id not in _csrf_tokens:
        _csrf_tokens[session_id] = secrets.token_hex(32)
    return _csrf_tokens[session_id]


def _ensure_session(request: Request) -> str:
    """Return existing session ID from cookie, or generate a new one."""
    return request.cookies.get("gcs_session", secrets.token_hex(16))


async def _validate_csrf(request: Request) -> None:
    """Validate CSRF token from form against session token. Raises 403 on failure."""
    session_id = request.cookies.get("gcs_session", "")
    if not session_id or session_id not in _csrf_tokens:
        raise HTTPException(status_code=403, detail="Invalid session")
    form = await request.form()
    form_token = str(form.get("csrf_token", ""))
    if not secrets.compare_digest(form_token, _csrf_tokens[session_id]):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def _read_credentials() -> dict[str, str]:
    """Read Garmin credentials from .env file."""
    if not ENV_PATH.exists():
        return {"email": "", "password": ""}
    return {
        "email": get_key(str(ENV_PATH), "GARMIN_EMAIL") or "",
        "password": get_key(str(ENV_PATH), "GARMIN_PASSWORD") or "",
    }


def _make_response(request: Request, page: str, extra_ctx: dict | None = None):
    """Build a TemplateResponse with CSRF token and session cookie."""
    session_id = _ensure_session(request)
    csrf_token = _get_csrf_token(session_id)
    config = load_config()
    ctx = {
        "request": request,
        "config": config,
        "page": page,
        "csrf_token": csrf_token,
    }
    if extra_ctx:
        ctx.update(extra_ctx)
    response = templates.TemplateResponse("index.html", ctx)
    response.set_cookie(
        "gcs_session", session_id, httponly=True, samesite="strict",
    )
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    creds = _read_credentials()
    return _make_response(request, "credentials", {
        "garmin_email": creds["email"],
        "has_password": bool(creds["password"]),
    })


@app.get("/credentials", response_class=HTMLResponse)
async def credentials_page(request: Request):
    creds = _read_credentials()
    return _make_response(request, "credentials", {
        "garmin_email": creds["email"],
        "has_password": bool(creds["password"]),
    })


@app.post("/credentials")
async def save_credentials(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
):
    await _validate_csrf(request)
    if not ENV_PATH.exists():
        ENV_PATH.touch(mode=0o600)
    set_key(str(ENV_PATH), "GARMIN_EMAIL", email)
    if password:
        set_key(str(ENV_PATH), "GARMIN_PASSWORD", password)
    creds = _read_credentials()
    return _make_response(request, "credentials", {
        "garmin_email": creds["email"],
        "has_password": bool(creds["password"]),
        "flash": "Credentials saved to .env.",
    })


@app.get("/hr-zones", response_class=HTMLResponse)
async def hr_zones_page(request: Request):
    return _make_response(request, "hr_zones")


@app.post("/hr-zones")
async def save_hr_zones(request: Request):
    await _validate_csrf(request)
    form = await request.form()
    config = load_config()
    zones = []
    for i in range(5):
        name = str(form.get(f"zone_{i}_name", f"Z{i + 1}"))[:10]
        min_bpm = max(0, min(250, int(form.get(f"zone_{i}_min", 0))))
        max_bpm = max(0, min(250, int(form.get(f"zone_{i}_max", 0))))
        zones.append({"name": name, "min_bpm": min_bpm, "max_bpm": max_bpm})
    config["hr_zones"] = zones
    save_config(config)
    return _make_response(request, "hr_zones", {"flash": "HR zones saved."})


@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    return _make_response(request, "sync")


@app.post("/sync")
async def save_sync(request: Request, interval_minutes: int = Form(60)):
    await _validate_csrf(request)
    allowed = {15, 30, 60, 120, 360, 720, 1440}
    if interval_minutes not in allowed:
        interval_minutes = 60
    config = load_config()
    config["sync_schedule"]["interval_minutes"] = interval_minutes
    save_config(config)
    return _make_response(request, "sync", {"flash": "Sync schedule saved."})


@app.get("/export", response_class=HTMLResponse)
async def export_page(request: Request):
    return _make_response(request, "export")


@app.post("/export")
async def save_export(request: Request):
    await _validate_csrf(request)
    form = await request.form()
    config = load_config()
    data_types = ["activities", "hrv", "sleep", "body_battery", "training_status"]
    for dtype in data_types:
        config["data_export"][dtype] = dtype in form
    save_config(config)
    return _make_response(request, "export", {"flash": "Export settings saved."})


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    return _make_response(request, "status")


def start():
    """Start the web config UI server.

    Binds to 127.0.0.1 for local-only access. For Docker deployments,
    change to 0.0.0.0 and place behind a reverse proxy.
    """
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8585)
