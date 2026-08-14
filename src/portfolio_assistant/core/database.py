from collections.abc import Generator

from sqlmodel import Session, create_engine

SQLMODEL_DATABASE_URL = "sqlite:///./data/portfolio_assistant.db"


engine = create_engine(SQLMODEL_DATABASE_URL, echo=True)


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
