"""FastAPI web application for GarminClaudeSync configuration."""

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config_store import load_config, save_config

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="GarminClaudeSync Config")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "credentials"}
    )


@app.get("/credentials", response_class=HTMLResponse)
async def credentials_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "credentials"}
    )


@app.post("/credentials")
async def save_credentials(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
):
    config = load_config()
    config["garmin"]["email"] = email
    if password:
        config["garmin"]["password"] = password
    save_config(config)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "page": "credentials",
            "flash": "Credentials saved.",
        },
    )


@app.get("/hr-zones", response_class=HTMLResponse)
async def hr_zones_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "hr_zones"}
    )


@app.post("/hr-zones")
async def save_hr_zones(request: Request):
    form = await request.form()
    config = load_config()
    zones = []
    for i in range(5):
        zones.append(
            {
                "name": form.get(f"zone_{i}_name", f"Z{i + 1}"),
                "min_bpm": int(form.get(f"zone_{i}_min", 0)),
                "max_bpm": int(form.get(f"zone_{i}_max", 0)),
            }
        )
    config["hr_zones"] = zones
    save_config(config)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "page": "hr_zones",
            "flash": "HR zones saved.",
        },
    )


@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "sync"}
    )


@app.post("/sync")
async def save_sync(
    request: Request,
    interval_minutes: int = Form(60),
):
    config = load_config()
    config["sync_schedule"]["interval_minutes"] = interval_minutes
    save_config(config)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "page": "sync",
            "flash": "Sync schedule saved.",
        },
    )


@app.get("/export", response_class=HTMLResponse)
async def export_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "export"}
    )


@app.post("/export")
async def save_export(request: Request):
    form = await request.form()
    config = load_config()
    data_types = ["activities", "hrv", "sleep", "body_battery", "training_status"]
    for dtype in data_types:
        config["data_export"][dtype] = dtype in form
    save_config(config)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "page": "export",
            "flash": "Export settings saved.",
        },
    )


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "index.html", {"request": request, "config": config, "page": "status"}
    )


def start():
    """Start the web config UI server.

    Binds to 127.0.0.1 for local-only access. For Docker deployments,
    change to 0.0.0.0 and place behind a reverse proxy.
    """
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8585)
