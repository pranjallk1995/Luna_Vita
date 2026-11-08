"""The UI gateway: serves the React app, enforces sign-in, and fronts the backend.

Every data route checks the shared Luna session and this app's allowlist first,
and only the routes the UI uses are forwarded.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import httpx
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from config import SSOConfig, UIConfig
from photos import FoodPhotos
from sso import CURRENT_USER, LunaSingleSignOn, send_user

ID = r"\d+"
DAY = r"\d{4}-\d{2}-\d{2}"
# The backend routes the browser app may reach, as (method, path pattern).
PROXIED_ROUTES = tuple(
    (method, re.compile(pattern))
    for method, pattern in (
        ("GET", rf"/api/summary/{DAY}"),
        ("GET", r"/api/recommendations"),
        ("GET", r"/api/food"),
        ("POST", r"/api/food"),
        ("PUT", rf"/api/food/{ID}"),
        ("DELETE", rf"/api/food/{ID}"),
        ("GET", r"/api/analysis/displayed"),
        ("PUT", r"/api/analysis/range"),
        ("DELETE", r"/api/analysis/range"),
        ("GET", r"/api/measurements"),
        ("POST", r"/api/measurements/batch"),
        ("DELETE", rf"/api/measurements/{ID}"),
        ("GET", r"/api/body-composition"),
        ("GET", r"/api/workouts"),
        ("PUT", rf"/api/workouts/{DAY}"),
        ("DELETE", rf"/api/workouts/{DAY}"),
        ("GET", r"/api/workouts/exercises"),
        ("POST", r"/api/workouts/exercises"),
        ("PUT", rf"/api/workouts/exercises/{ID}"),
        ("DELETE", rf"/api/workouts/exercises/{ID}"),
        ("GET", rf"/api/reports/daily/{DAY}"),
    )
)
UNAVAILABLE = "Luna Vita's backend is unavailable. Please try again."


class StaticApp(StaticFiles):
    """Serve the built app: hashed bundles are cached forever, the page itself never."""

    async def get_response(self, path: str, scope: Any) -> Response:
        response = await super().get_response(path, scope)
        immutable = path.startswith("assets/")
        response.headers["Cache-Control"] = UIConfig.IMMUTABLE_CACHE_CONTROL if immutable else "no-cache"
        return response


class UIGateway:
    """Translate browser requests into session checks and backend calls."""

    def __init__(
        self,
        config: UIConfig,
        backend_transport: httpx.AsyncBaseTransport | None = None,
        sso_transport: httpx.AsyncBaseTransport | None = None,
        visia_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.sso = LunaSingleSignOn(config.allowed_emails, config.sso, sso_transport, app="vita")
        self.backend = httpx.AsyncClient(
            event_hooks={"request": [send_user]},
            base_url=config.api_url,
            headers={"Authorization": f"Bearer {config.api_token}"},
            timeout=UIConfig.API_TIMEOUT_SECONDS,
            transport=backend_transport,
        )
        self.visia = httpx.AsyncClient(
            base_url=config.visia_api_url, timeout=UIConfig.FOOD_PHOTO_TIMEOUT_SECONDS, transport=visia_transport
        )
        self.photos = FoodPhotos()

    # Sign-in

    @staticmethod
    def here(request: Request) -> str:
        """This app's public address. Behind a TLS-terminating proxy such as a Cloudflare
        tunnel, the proxy's X-Forwarded-Proto and X-Forwarded-Host give the real one."""
        headers = request.headers
        scheme = headers.get("x-forwarded-proto", "").split(",")[0].strip() or request.url.scheme
        host = headers.get("x-forwarded-host", "").split(",")[0].strip() or request.url.netloc
        return f"{scheme}://{host}/"

    async def person(self, request: Request) -> dict[str, Any] | None:
        return await self.sso.user(request.cookies.get(SSOConfig.COOKIE_NAME))

    def protected(self, handler: Callable[[Request], Awaitable[Response]]):
        """Run ``handler`` only for a signed-in person on this app's allowlist."""

        async def endpoint(request: Request) -> Response:
            user = await self.person(request)
            if user is None:
                return JSONResponse({"error": "Sign in to continue."}, status_code=401)
            if not self.sso.is_allowed(user):
                return JSONResponse({"error": "This account is not authorized."}, status_code=403)
            token = CURRENT_USER.set(user.get("user_id"))
            try:
                return await handler(request)
            finally:
                CURRENT_USER.reset(token)

        return endpoint

    async def session(self, request: Request) -> Response:
        """Tell the browser app who is signed in, with its settings once they are allowed."""
        here = self.here(request)
        user = await self.person(request)
        if user is None:
            return JSONResponse({"status": "signed_out", "login_url": self.sso.login_url(here)})
        logout_url = self.sso.logout_url(here)
        if not self.sso.is_allowed(user):
            return JSONResponse({"status": "forbidden", "email": user.get("email"), "logout_url": logout_url})
        return JSONResponse({"status": "signed_in", "email": user.get("email"), "logout_url": logout_url, "settings": self.settings()})

    @staticmethod
    def settings() -> dict[str, Any]:
        return {
            "version": UIConfig.VERSION,
            "time_zone": UIConfig.TIME_ZONE,
            "utc_offset": UIConfig.UTC_OFFSET,
            "food_photo_size": UIConfig.FOOD_PHOTO_SIZE,
            "food_photo_quality": UIConfig.FOOD_PHOTO_QUALITY / 100,
            "photo_upload_types": UIConfig.PHOTO_UPLOAD_TYPES,
            "max_food_rows": UIConfig.MAX_FOOD_ROWS,
            "max_measurement_rows": UIConfig.MAX_MEASUREMENT_ROWS,
        }

    # Food photos

    async def food_photo(self, request: Request) -> Response:
        """A stored Luna Visia photo for ``?url=<its public link>``, fitted to the table's 3:2 format, or whole with ``&size=large``."""
        url = request.query_params.get("url", "")
        path = FoodPhotos.visia_image_path(url)
        if path is None:
            return JSONResponse({"error": "Not a Luna Visia image."}, status_code=404)
        large = request.query_params.get("size") == "large"
        data = self.photos.cached(path, large)
        if data is None:
            try:
                response = await self.visia.get(path)
                response.raise_for_status()
                data = await anyio.to_thread.run_sync(self.photos.fit, path, response.content, large)
            except (httpx.HTTPError, OSError):
                return JSONResponse({"error": "That photo is unavailable."}, status_code=404)
        return Response(data, media_type="image/webp", headers={"Cache-Control": UIConfig.IMMUTABLE_CACHE_CONTROL})

    # Backend

    async def proxy(self, request: Request) -> Response:
        path = request.url.path
        if not any(method == request.method and pattern.fullmatch(path) for method, pattern in PROXIED_ROUTES):
            return JSONResponse({"error": "Not found."}, status_code=404)
        body = await request.body()
        if len(body) > UIConfig.MAX_REQUEST_BYTES:
            return JSONResponse({"error": "This request is too large."}, status_code=413)
        try:
            response = await self.backend.request(
                request.method,
                path,
                params=request.query_params,
                content=body,
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
            )
        except httpx.HTTPError:
            return JSONResponse({"error": UNAVAILABLE}, status_code=502)
        return Response(
            response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers={"Cache-Control": "no-store"},
        )

    # Application

    @staticmethod
    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok", "version": UIConfig.VERSION})

    def application(self) -> Starlette:
        app = Starlette(
            routes=[
                Route("/health", self.health),
                # Luna Unia's status page checks every app's UI at Streamlit's health path.
                Route("/_stcore/health", self.health),
                Route("/auth/session", self.session),
                Route("/app/food-photos", self.protected(self.food_photo)),
                Route("/api/{path:path}", self.protected(self.proxy), methods=["GET", "POST", "PUT", "DELETE"]),
                Mount("/", StaticApp(directory=UIConfig.STATIC_DIR, html=True, check_dir=False)),
            ]
        )

        async def secure_headers(request: Request, call_next) -> Response:
            response = await call_next(request)
            response.headers["Content-Security-Policy"] = UIConfig.CONTENT_SECURITY_POLICY
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        app.add_middleware(BaseHTTPMiddleware, dispatch=secure_headers)
        return app


def create_app() -> Starlette:
    return UIGateway(UIConfig.from_env()).application()
