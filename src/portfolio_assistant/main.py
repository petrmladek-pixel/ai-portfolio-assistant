from fastapi import FastAPI

from .config import get_settings
from .routers.web import router as web_router

settings = get_settings()

app = FastAPI(title=settings.app_name)

# Include web routes
app.include_router(web_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
