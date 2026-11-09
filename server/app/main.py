from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .config import settings
from .db import Base, engine
from .routers import auth, billing, device_api, inventory, org

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="MCPLedger", version=__version__,
              docs_url=None if settings.is_prod else "/api/docs", redoc_url=None,
              openapi_url=None if settings.is_prod else "/api/openapi.json")

for r in (auth.router, org.router, inventory.router, device_api.router, billing.router):
    app.include_router(r)

# Enterprise features (server/ee, MCPLedger Enterprise License). Each endpoint checks the
# org's plan or license itself; the open-source build works the same without this folder.
if importlib.util.find_spec("ee") is not None:
    from ee import router as ee_router
    app.include_router(ee_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.secure_cookies:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if not request.url.path.startswith("/api"):
        h.setdefault("Content-Security-Policy",
                     "default-src 'self'; script-src 'self' https://cdn.paddle.com; "
                     "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
                     "img-src 'self' data:; connect-src 'self' https://*.paddle.com; "
                     "frame-src https://*.paddle.com; frame-ancestors 'none'")
    return response


@app.get("/healthz")
def healthz():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True, "version": __version__}


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)[:300]}, status_code=422)


def _mount_spa(static_dir: str) -> None:
    root = Path(static_dir)
    index = root / "index.html"
    if not index.is_file():
        return

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


if settings.static_dir:
    _mount_spa(settings.static_dir)


if os.environ.get("AUTO_CREATE_TABLES", "1" if not settings.is_prod else "0") == "1":
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
