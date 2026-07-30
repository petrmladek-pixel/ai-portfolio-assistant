from fastapi import FastAPI

from .config import get_settings
from .routers.web import router as web_router  # <-- Import the web router

settings = get_settings()

app = FastAPI(title=settings.app_name)

# Register the web dashboard router
app.include_router(web_router)  # <-- Register the web router


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
