from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=False)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
