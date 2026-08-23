from collections.abc import Generator

from sqlmodel import Session, create_engine

from portfolio_assistant.config import get_settings

SQLMODEL_DATABASE_URL = get_settings().database_url

engine = create_engine(SQLMODEL_DATABASE_URL)


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
