"""FastAPI application factory (``uvicorn nsapp.api.app:app``)."""
from __future__ import annotations

import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from nsapp import VERSION
from nsapp.api.routes import protected, router
from nsapp.db import assert_schema, engine
from nsapp.errors import AppError
from nsapp.logging import correlation_id, event
from nsapp.repositories import jobs
from nsapp.services import auth
from nsapp.settings import ensure_dirs

WEB_DIR = Path(os.getenv("NS_WEB_DIR") or Path(__file__).resolve().parents[2] / "web")
_REQUEST_ID = re.compile(r"[a-zA-Z0-9-]{1,64}")
_QUIET_ROUTES = {"/healthz", "/readyz"}
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    assert_schema()
    auth.init()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="NodeSeek Entertainment Center", version=VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.include_router(router)
    app.include_router(protected)

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"detail": exc.code}, status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": "INTERNAL_ERROR"}, status_code=500)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]) for err in exc.errors()]
        return JSONResponse({"detail": "VALIDATION_FAILED", "fields": fields}, status_code=422)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        cid = supplied if _REQUEST_ID.fullmatch(supplied) else secrets.token_hex(12)
        token = correlation_id.set(cid)
        started = time.monotonic()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = cid
            for name, value in _SECURITY_HEADERS.items():
                response.headers[name] = value
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            route = request.scope.get("route")
            template = getattr(route, "path", "unmatched")
            if template not in _QUIET_ROUTES:
                event(
                    "request_finished", method=request.method, route=template,
                    status_code=response.status_code, elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            return response
        finally:
            correlation_id.reset(token)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        try:
            assert_schema()
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1").scalar_one()
            ready = jobs.state()["ready"]
        except Exception:
            ready = False
        return JSONResponse({"status": "ok" if ready else "unavailable", "ready": ready}, status_code=200 if ready else 503)

    _mount_frontend(app)
    return app


class ImmutableAssets(StaticFiles):
    """Build output is content-hashed, so browsers may cache it for a year."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


_RELOAD_ONCE = "if(!sessionStorage.getItem('ns_reloaded')){sessionStorage.setItem('ns_reloaded','1');location.reload()}"


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built single-page app: hashed assets cache forever, the shell never."""

    # A browser that cached the 2.0 shell still asks for these two files. Answer them so the stale
    # page reloads itself once and fetches the current shell, instead of rendering blank.
    @app.get("/assets/main.js", include_in_schema=False)
    def legacy_script() -> Response:
        return Response(_RELOAD_ONCE, media_type="text/javascript", headers={"Cache-Control": "no-store"})

    @app.get("/assets/styles.css", include_in_schema=False)
    def legacy_styles() -> Response:
        return Response("", media_type="text/css", headers={"Cache-Control": "no-store"})

    if (WEB_DIR / "assets").is_dir():
        app.mount("/assets", ImmutableAssets(directory=WEB_DIR / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        shell = WEB_DIR / "index.html"
        if not shell.is_file():
            raise HTTPException(status_code=503, detail="FRONTEND_NOT_BUILT")
        target = (WEB_DIR / path).resolve()
        if path and target.is_relative_to(WEB_DIR.resolve()) and target.is_file():
            return FileResponse(target)
        return FileResponse(shell, headers={"Cache-Control": "no-cache"})


app = create_app()
