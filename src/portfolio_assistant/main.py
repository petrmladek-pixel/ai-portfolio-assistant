# All comments and docstrings are strictly in English.
# Lines are wrapped to stay within the 88-character limit.

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from .config import get_settings
from .core.database import engine
from .core.migrations import run_db_migrations
from .routers import ai, allocations, auth, portfolio, web_dashboard, web_upload
from .routers.web import router
from .services.demo_service import get_or_create_demo_buffett_portfolio

settings = get_settings()


def seed_database() -> None:
    """Seed the isolated system-owned demo portfolio when explicitly enabled."""
    if not settings.enable_demo_data:
        return
    # Guard: Never run the development seeder in production environments
    if settings.environment == "production":
        return

    with Session(engine) as session:
        get_or_create_demo_buffett_portfolio(session)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Prepare local storage before serving requests."""
    os.makedirs(settings.data_dir, exist_ok=True)
    await asyncio.to_thread(run_db_migrations)
    await asyncio.to_thread(seed_database)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory="src/portfolio_assistant/static"),
    name="static",
)

# Include routes
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(portfolio.demo_router)
app.include_router(allocations.router)
app.include_router(ai.router)
app.include_router(router)
app.include_router(web_dashboard.router)
app.include_router(web_upload.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/favicon.ico", include_in_schema=False, response_model=None)
async def favicon() -> Response | FileResponse:
    """Serves the favicon from public directory or silences browser with 204."""
    favicon_path = os.path.join("public", "icon-light-32x32.png")

    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/png")

    return Response(status_code=204)
