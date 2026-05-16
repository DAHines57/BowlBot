from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.config import sqlalchemy_url_for_alembic

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(sqlalchemy_url_for_alembic(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    get_engine()
    return _SessionLocal()
