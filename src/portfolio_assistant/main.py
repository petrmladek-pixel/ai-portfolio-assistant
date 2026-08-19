import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from .config import get_settings
from .core.database import engine
from .models.db_models import Portfolio, Position  # noqa: F401

# Import models to ensure SQLModel knows about them for create_all
from .models.user import User  # noqa: F401
from .routers import auth, portfolio
from .routers.web import router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    # Initialize SQLite database
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Include routes
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
