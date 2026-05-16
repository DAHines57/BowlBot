import os
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see README — Local PostgreSQL)")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def sqlalchemy_url_for_alembic() -> str:
    """Alembic config wants a driver name; psycopg3 uses postgresql+psycopg://."""
    url = get_database_url()
    parsed = urlparse(url)
    if parsed.scheme in ("postgresql", "postgres"):
        scheme = "postgresql+psycopg"
    else:
        scheme = parsed.scheme
    return urlunparse(parsed._replace(scheme=scheme))
