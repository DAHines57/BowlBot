"""HTTP routes for the league site."""
from __future__ import annotations

import os
from flask import Blueprint, Response, current_app, redirect, render_template, request, url_for

bp = Blueprint("site", __name__)


def _svc():
    s = current_app.config.get("LEAGUE_SERVICE")
    if not s:
        return None
    return s


@bp.route("/health")
def health():
    from db.availability import db_status
    from db.config import get_database_url

    svc = _svc()
    source = getattr(svc.data, "read_source", "sheets") if svc else None
    try:
        get_database_url()
        database_url_set = True
    except RuntimeError:
        database_url_set = False
    db = db_status()
    return {
        "ok": True,
        "service": bool(svc),
        "read_source": source,
        "database_url_set": database_url_set,
        "db": db,
    }, 200


@bp.route("/")
def home():
    """Unified stats page. Data arrives via /api/*; this only serves the shell."""
    svc = _svc()
    if not svc:
        return render_template(
            "error.html",
            message="Database not ready. Set DATABASE_URL, run docker compose up -d, then python sync_db.py.",
        ), 503
    return render_template("app.html")


@bp.route("/app")
def unified_app():
    """Where the unified page used to live, before it became the root."""
    return redirect(url_for("site.home"), code=301)


def _refresh_cache_response():
    secret = os.environ.get("RELOAD_SECRET", "").strip()
    if secret and request.args.get("key") != secret:
        return Response("Forbidden", status=403)
    svc = _svc()
    if not svc:
        return _no_svc()
    ok, msg = svc.refresh_data()
    return Response(msg, status=200 if ok else 500)


@bp.route("/refresh", methods=["POST"])
def refresh_cache():
    """Clear in-process caches and re-read facts from Postgres."""
    return _refresh_cache_response()


@bp.route("/reload", methods=["POST"])
def reload_compat():
    """Alias for /refresh (no longer reads Excel)."""
    return _refresh_cache_response()


def _no_svc():
    return render_template(
        "error.html",
        message="Database not ready. Set DATABASE_URL and run python sync_db.py.",
    ), 503
