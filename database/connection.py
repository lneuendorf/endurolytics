import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def normalize_database_url(url: str) -> str:
    """Normalize provider-supplied URLs to a SQLAlchemy-compatible form.

    Neon and Render commonly hand out ``postgres://`` URLs, but SQLAlchemy needs
    the explicit ``postgresql+psycopg2://`` driver prefix.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def create_engine_from_url(database_url: str | None = None):
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///enduralytics.db")
    url = normalize_database_url(url)
    if url.startswith("postgresql"):
        return create_engine(url, pool_pre_ping=True)
    return create_engine(url)


def get_session_factory(database_url: str | None = None):
    engine = create_engine_from_url(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    factory = get_session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(database_url: str | None = None):
    engine = create_engine_from_url(database_url)
    Base.metadata.create_all(engine)
    return engine
