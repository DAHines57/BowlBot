"""HTTP routes for the league site."""
from __future__ import annotations

import os
from flask import Blueprint, Response, current_app, render_template, request

from league_admin import (
    list_public_seasons,
    list_public_weeks_for_season,
    playoff_weeks_by_season,
    public_latest_week,
)

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
    svc = _svc()
    if not svc:
        return render_template(
            "error.html",
            message="Database not ready. Set DATABASE_URL, run docker compose up -d, then python sync_db.py.",
        ), 503
    seasons = list_public_seasons(svc.data)
    cur = seasons[0] if seasons else svc.data.get_current_season()
    latest_wk = public_latest_week(svc.data, cur) if cur else 1
    weeks_by_season = {s: list_public_weeks_for_season(svc.data, s) for s in seasons}
    playoff_weeks = playoff_weeks_by_season(svc.data, seasons)
    catalog = svc.lookup_catalog()
    public_set = set(seasons)
    catalog = {
        **catalog,
        "players_by_season": {
            k: v for k, v in (catalog.get("players_by_season") or {}).items() if k in public_set
        },
        "teams_by_season": {
            k: v for k, v in (catalog.get("teams_by_season") or {}).items() if k in public_set
        },
    }
    return render_template(
        "home.html",
        seasons=seasons,
        current_season=cur,
        latest_week=latest_wk,
        weeks_by_season=weeks_by_season,
        playoff_weeks_by_season=playoff_weeks,
        lookup_catalog=catalog,
    )


def _season_arg() -> str:
    svc = _svc()
    if not svc:
        return ""
    return svc.resolve_season(request.args.get("season"))


def _embed_flag() -> bool:
    v = (request.args.get("embed") or "").strip().lower()
    return v in ("1", "true", "yes")


def _week_arg():
    raw = request.args.get("week")
    if raw is None or (isinstance(raw, str) and str(raw).strip() == ""):
        return None
    s = str(raw).strip().lower()
    if s in ("all", "*"):
        return "all"
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@bp.route("/week/summary")
def week_summary():
    svc = _svc()
    if not svc:
        return _no_svc()
    season = _season_arg()
    if season == "all":
        season = svc.data.get_current_season()
    week = _week_arg()
    html, err = svc.weekly_summary_page(season, week, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/week/results")
def week_results():
    svc = _svc()
    if not svc:
        return _no_svc()
    season = _season_arg()
    if season == "all":
        season = svc.data.get_current_season()
    week = _week_arg()
    html, err = svc.weekly_results_page(season, week, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/playoffs")
def playoffs():
    svc = _svc()
    if not svc:
        return _no_svc()
    season = _season_arg()
    html, err = svc.playoff_results_page(season, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/bracket")
def playoff_bracket():
    svc = _svc()
    if not svc:
        return _no_svc()
    raw = request.args.get("season")
    if raw is None or str(raw).strip().lower() in ("", "all", "all-time", "alltime"):
        html, err = svc.playoff_bracket_index_page(embed=_embed_flag())
    else:
        html, err = svc.playoff_bracket_page(_season_arg(), embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/players")
def players():
    svc = _svc()
    if not svc:
        return _no_svc()
    html, err = svc.players_page(_season_arg(), embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/teams")
def teams():
    svc = _svc()
    if not svc:
        return _no_svc()
    html, err = svc.teams_page(_season_arg(), embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/leaders")
def leaders():
    svc = _svc()
    if not svc:
        return _no_svc()
    html, err = svc.leaders_page(_season_arg(), embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/team/<path:team_name>/weekly")
def team_weekly(team_name: str):
    svc = _svc()
    if not svc:
        return _no_svc()
    html, err = svc.team_weekly_page(team_name, _season_arg(), embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/top/players")
def top_players():
    svc = _svc()
    if not svc:
        return _no_svc()
    n = request.args.get("n", default=5, type=int)
    worst = request.args.get("worst", default=0, type=int) == 1
    week = request.args.get("week", type=int)
    html, err = svc.top_players_page(_season_arg(), n, worst, week, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/top/games")
def top_games():
    svc = _svc()
    if not svc:
        return _no_svc()
    n = request.args.get("n", default=50, type=int)
    worst = request.args.get("worst", default=0, type=int) == 1
    html, err = svc.top_games_page(_season_arg(), n, worst, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/player")
def player_query():
    svc = _svc()
    if not svc:
        return _no_svc()
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("error.html", message="Missing q= player name."), 400
    season = _season_arg()
    if season != "all":
        matches = svc.find_player_names(q, season)
        if len(matches) > 1:
            return render_template(
                "pick_player.html",
                query=q,
                season=request.args.get("season") or "",
                matches=matches,
                embed=_embed_flag(),
            )
    html, err = svc.player_detail_page(q, season, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


@bp.route("/player/<path:name>")
def player_named(name: str):
    svc = _svc()
    if not svc:
        return _no_svc()
    season = _season_arg()
    html, err = svc.player_detail_page(name, season, embed=_embed_flag())
    if err:
        return render_template("error.html", message=err), 400
    return Response(html, mimetype="text/html; charset=utf-8")


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
