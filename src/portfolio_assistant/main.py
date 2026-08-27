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
    with Session(engine) as session:
        # Check if user exists
        user = session.exec(
            select(User).where(User.email == "petr.mladek@gmail.com")
        ).first()
        if user:
            return

        # Seed data
        new_user = User(
            email="petr.mladek@gmail.com",
            full_name="Petr Mladek",
            hashed_password=hash_password("password123"),
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        # Default portfolio
        default_portfolio = Portfolio(
            name="Default Portfolio", broker="Unknown", user_id=new_user.id
        )
        session.add(default_portfolio)

        # Buffett portfolio
        buffett_portfolio = Portfolio(
            name="Ukazkove portfolio (Warren Buffett)",
            broker="Berkshire Hathaway",
            description="Top positions of Berkshire Hathaway",
            user_id=new_user.id,
        )
        session.add(buffett_portfolio)
        session.commit()
        session.refresh(buffett_portfolio)

        # Positions - Total value: 10M CZK
        # Simplified quantities for 10M CZK total
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
