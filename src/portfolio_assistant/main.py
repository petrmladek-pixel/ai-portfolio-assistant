import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .routers import auth, portfolio, web_dashboard, web_upload
from .routers.web import router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Include routes
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(router)
app.include_router(web_dashboard.router)
app.include_router(web_upload.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
