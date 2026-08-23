import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.security import create_access_token, hash_password
from portfolio_assistant.main import app
from portfolio_assistant.models.db_models import Portfolio
from portfolio_assistant.models.user import User

# Setup in-memory SQLite for testing
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_db_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_register_user(client: TestClient, session: Session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "password" not in data
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.user_id == data["id"])
    ).one()
    assert portfolio.name == "Default Portfolio"
    assert portfolio.broker == "Default"


def test_login_provisions_default_portfolio_for_legacy_user(
    client: TestClient, session: Session
):
    user = User(
        email="legacy@example.com",
        hashed_password=hash_password("password"),
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "legacy@example.com", "password": "password"},
    )

    assert response.status_code == 200
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.user_id == user.id)
    ).one()
    assert portfolio.name == "Default Portfolio"


def test_register_duplicate_user(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User with this email already exists"


def test_login_success(client: TestClient):
    # Register first
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged in"
    assert "session_token" in client.cookies


def test_login_wrong_password(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_logout(client: TestClient):
    # Login first
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert "session_token" in client.cookies

    # Logout
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert "session_token" not in client.cookies


def test_get_current_user_dependency(client: TestClient):
    # Register and login
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )

    # Add a protected route for testing
    from typing import Annotated

    from fastapi import Depends

    from portfolio_assistant.core.security import get_current_user
    from portfolio_assistant.models.user import User

    @app.get("/api/test-protected")
    def protected_route(
        current_user: Annotated[User, Depends(get_current_user)],
    ):
        return {"email": current_user.email}

    response = client.get("/api/test-protected")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_dashboard_allows_a_stale_session_cookie(client: TestClient):
    token = create_access_token(data={"sub": "missing@example.com"})
    client.cookies.set("session_token", token)

    response = client.get("/")

    assert response.status_code == 200
    assert "User not found" not in response.text
