# All comments and docstrings are strictly in English.
# Lines are wrapped to stay within the 88-character limit.

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .config import get_settings
from .core.database import engine
from .core.migrations import run_db_migrations
from .core.security import hash_password
from .models.db_models import Portfolio, Position
from .models.user import User
from .routers import auth, portfolio, web_dashboard, web_upload
from .routers.web import router

settings = get_settings()


def seed_database() -> None:
    """Seed the database with default user and portfolios if missing."""
    # Guard: Never run the development seeder in production environments
    if settings.environment == "production":
        return

    # Use a generic demo email to avoid hardcoding personal data in git
    demo_email = getattr(settings, "demo_user_email", "demo@portfolio-assistant.ai")

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == demo_email)).first()
        if user:
            return

        new_user = User(
            email=demo_email,
            full_name="Demo User",
            hashed_password=hash_password("password123"),
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        default_portfolio = Portfolio(
            name="Default Portfolio", broker="Unknown", user_id=new_user.id
        )
        session.add(default_portfolio)

        buffett_portfolio = Portfolio(
            name="Warren Buffett Portfolio",
            broker="Berkshire Hathaway",
            description="Top positions of Berkshire Hathaway",
            user_id=new_user.id,
        )
        session.add(buffett_portfolio)
        session.commit()
        session.refresh(buffett_portfolio)

        positions = [
            (
                "Apple Inc.",
                "AAPL",
                "US0378331005",
                "CZK",
                Decimal("1000"),
                Decimal("4000.00"),
            ),
            (
                "American Express",
                "AXP",
                "US0258161092",
                "CZK",
                Decimal("1000"),
                Decimal("1200.00"),
            ),
            (
                "Bank of America",
                "BAC",
                "US0605051046",
                "CZK",
                Decimal("1000"),
                Decimal("1000.00"),
            ),
            (
                "Coca-Cola",
                "KO",
                "US1912161007",
                "CZK",
                Decimal("1000"),
                Decimal("800.00"),
            ),
            (
                "Occidental Petroleum",
                "OXY",
                "US6745991058",
                "CZK",
                Decimal("1000"),
                Decimal("600.00"),
            ),
            ("Cash", "CASH", "CASH", "CZK", Decimal("2400000"), Decimal("1.00")),
        ]

        for name, ticker, isin, currency, qty, cost in positions:
            pos = Position(
                asset_name=name,
                ticker=ticker,
                isin=isin,
                currency=currency,
                quantity=qty,
                unit_cost=cost,
                acquisition_date=date.today(),
                portfolio_id=buffett_portfolio.id,
            )
            session.add(pos)
        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Prepare local storage before serving requests."""
    os.makedirs(settings.data_dir, exist_ok=True)
    await asyncio.to_thread(run_db_migrations)
    await asyncio.to_thread(seed_database)
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


@app.get("/favicon.ico", include_in_schema=False, response_model=None)
async def favicon() -> Response | FileResponse:
    """Serves the favicon from public directory or silences browser with 204."""
    favicon_path = os.path.join("public", "icon-light-32x32.png")

    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/png")

    return Response(status_code=204)
