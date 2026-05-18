"""Admin score entry, season setup, deletes."""
from __future__ import annotations

import json
from urllib.parse import quote

import os

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, url_for

from app.admin_auth import admin_pin_configured, check_admin_authorized, unlock_admin
from db.season_admin import (
    create_season,
    delete_season,
    delete_week,
    get_season_roster,
    list_all_player_names,
    list_db_seasons,
    save_season_roster,
    suggest_new_season_numbers,
)
from db.session import get_session
from league_admin import (
    default_entry_target,
    default_entry_week,
    get_week_entry,
    list_season_teams_from_db,
    parse_week_rows_payload,
    save_week_entry,
)
from stats.compute import parse_season_number

admin_bp = Blueprint("admin", __name__)


def _svc():
    return current_app.config.get("LEAGUE_SERVICE")


def _forbidden_admin():
    return redirect(url_for("admin.admin_home", next=request.path))


def _no_svc():
    return (
        render_template(
            "error.html",
            message="Database not ready. Set DATABASE_URL and run python sync_db.py.",
        ),
        503,
    )


def _require_admin():
    if not check_admin_authorized():
        return _forbidden_admin()
    return None


def _parse_week_arg(required: bool = False) -> tuple[int | None, str | None]:
    raw = request.args.get("week") or request.form.get("week")
    if raw is None or str(raw).strip() == "":
        if required:
            return None, "Missing week."
        return None, None
    try:
        week = int(raw)
    except (TypeError, ValueError):
        return None, "Invalid week."
    if week < 1:
        return None, "Week must be at least 1."
    return week, None


def _season_label(svc) -> str:
    raw = request.args.get("season") or request.form.get("season")
    if raw is None or str(raw).strip() == "":
        season, _ = default_entry_target(svc.data)
        return season
    return svc.resolve_season(str(raw).strip())


def _season_number_from_request() -> tuple[int | None, str | None]:
    raw = request.args.get("season") or request.form.get("season") or request.args.get("season_number")
    if raw is None or str(raw).strip() == "":
        return None, "Missing season."
    num = parse_season_number(str(raw).strip())
    if num is None and str(raw).strip().isdigit():
        num = int(str(raw).strip())
    if num is None:
        return None, "Invalid season."
    return num, None


def _season_choices(svc, db_seasons: list[dict]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for row in db_seasons:
        label = row["label"]
        if label not in seen:
            labels.append(label)
            seen.add(label)
    for label in svc.seasons_sorted():
        if label not in seen:
            labels.append(label)
            seen.add(label)

    def sort_key(name: str) -> int:
        num = parse_season_number(name)
        return num if num is not None else 0

    return sorted(labels, key=sort_key, reverse=True)


def _render_admin_home():
    svc = _svc()
    if not svc:
        return _no_svc()
    session = get_session()
    try:
        db_seasons = list_db_seasons(session)
    finally:
        session.close()
    return render_template(
        "admin_hub.html",
        db_seasons=db_seasons,
    )


@admin_bp.route("/admin")
def admin_home():
    """PIN gate and menu — use /admin?pin=… or /admin?key=… then pick a task."""
    if not check_admin_authorized():
        return render_template(
            "admin_gate.html",
            pin_required=admin_pin_configured(),
            error=request.args.get("error"),
            next_path=request.args.get("next") or "/admin",
        )
    nxt = (request.args.get("next") or "").strip()
    if nxt and nxt.startswith("/admin") and nxt != "/admin":
        return redirect(nxt)
    return _render_admin_home()


@admin_bp.route("/admin/unlock", methods=["POST"])
def admin_unlock():
    if unlock_admin():
        nxt = request.form.get("next") or "/admin"
        if nxt.startswith("/admin"):
            return redirect(nxt)
        return redirect("/admin")
    return redirect(
        url_for("admin.admin_home", error="wrong_pin", next=request.form.get("next"))
    )


@admin_bp.route("/admin/hub")
def admin_hub_redirect():
    """Legacy URL → /admin."""
    return redirect(url_for("admin.admin_home", **request.args))


@admin_bp.route("/admin/enter")
def admin_enter_form():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return _no_svc()

    week, err = _parse_week_arg()
    if err:
        return render_template("error.html", message=err), 400
    season = _season_label(svc)

    session = get_session()
    try:
        db_seasons = list_db_seasons(session)
    finally:
        session.close()

    if week is None:
        season_num = parse_season_number(season)
        db_teams = (
            list_season_teams_from_db(season_num) if season_num is not None else []
        )
        week = default_entry_week(svc.data, season, season_teams=db_teams or None)

    team = (request.args.get("team") or "").strip() or None
    payload, err = get_week_entry(svc.data, season, week, team=team)
    if err:
        return render_template("error.html", message=err), 400
    season_choices = _season_choices(svc, db_seasons)
    if payload["season"] not in season_choices:
        season_choices = [payload["season"], *season_choices]

    db_teams = list_season_teams_from_db(payload["season_number"])
    all_teams = sorted(set(payload["teams"]) | set(db_teams))
    if not payload["teams"] and db_teams:
        payload["teams"] = db_teams

    from league_admin import list_season_week_completion

    week_statuses = list_season_week_completion(
        svc.data,
        payload["season"],
        season_teams=all_teams,
        through_week=payload["week"],
    )
    # Admin is PIN-gated; hide fill helper only when explicitly disabled (e.g. production).
    hide_debug = os.environ.get("ADMIN_DEBUG_TOOLS", "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    )
    show_debug_tools = not hide_debug
    return render_template(
        "admin_enter.html",
        entry=payload,
        season_choices=season_choices,
        all_teams=all_teams,
        week_statuses=week_statuses,
        selected_team=team or "",
        show_debug_tools=show_debug_tools,
    )


@admin_bp.route("/admin/week", methods=["GET"])
def admin_week_get():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return jsonify({"error": "database not ready"}), 503

    week, err = _parse_week_arg(required=True)
    if err:
        return jsonify({"error": err}), 400
    season = _season_label(svc)
    team = (request.args.get("team") or "").strip() or None
    payload, err = get_week_entry(svc.data, season, week, team=team)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(payload)


@admin_bp.route("/admin/week", methods=["POST"])
def admin_week_post():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return jsonify({"error": "database not ready"}), 503

    if request.is_json:
        body = request.get_json(silent=True) or {}
    else:
        raw = request.form.get("payload")
        if not raw:
            return jsonify({"error": "Missing JSON body or form field payload."}), 400
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON in payload."}), 400

    season_raw = body.get("season")
    if not season_raw:
        return jsonify({"error": "Missing season."}), 400
    season = svc.resolve_season(str(season_raw))

    try:
        week = int(body.get("week"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing or invalid week."}), 400
    if week < 1:
        return jsonify({"error": "Week must be at least 1."}), 400

    rows, err = parse_week_rows_payload(body)
    if err:
        return jsonify({"error": err}), 400

    ok, msg = save_week_entry(
        svc.data,
        season,
        week,
        rows,
        refresh=svc.refresh_data,
    )
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"ok": ok, "message": msg}), 200 if ok else 500

    if ok:
        team = (body.get("team") or request.form.get("team") or "").strip()
        q = f"?season={quote(season)}&week={week}"
        if team:
            q += f"&team={quote(team)}"
        return Response("", status=303, headers={"Location": f"/admin/enter{q}"})
    return render_template("error.html", message=msg), 500


@admin_bp.route("/admin/week/delete", methods=["POST"])
def admin_week_delete_post():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return _no_svc()
    season_num, err = _season_number_from_request()
    if err:
        return render_template("error.html", message=err), 400
    week, err = _parse_week_arg(required=True)
    if err:
        return render_template("error.html", message=err), 400
    session = get_session()
    try:
        count = delete_week(session, season_num, week)
        session.commit()
        svc.refresh_data()
    except Exception as exc:
        session.rollback()
        return render_template("error.html", message=str(exc)), 400
    finally:
        session.close()
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/admin/week", methods=["DELETE"])
def admin_week_delete():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return jsonify({"error": "database not ready"}), 503

    season_num, err = _season_number_from_request()
    if err:
        return jsonify({"error": err}), 400
    week, err = _parse_week_arg(required=True)
    if err:
        return jsonify({"error": err}), 400

    session = get_session()
    try:
        count = delete_week(session, season_num, week)
        session.commit()
        svc.refresh_data()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    finally:
        session.close()

    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True, "deleted_rows": count})
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/admin/season", methods=["GET"])
def admin_season_form():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return _no_svc()

    season_num, _ = _season_number_from_request()
    roster = None
    session = get_session()
    try:
        db_seasons = list_db_seasons(session)
        all_players = list_all_player_names(session)
        if season_num is not None:
            roster = get_season_roster(session, season_num)
    finally:
        session.close()

    existing_numbers = {s["number"] for s in db_seasons}
    return render_template(
        "admin_season.html",
        db_seasons=db_seasons,
        roster=roster,
        season_number=season_num,
        season_choices=_season_choices(svc, db_seasons),
        new_season_options=suggest_new_season_numbers(db_seasons),
        existing_season_numbers=existing_numbers,
        all_players=all_players,
    )


@admin_bp.route("/admin/season", methods=["POST"])
def admin_season_post():
    denied = _require_admin()
    if denied:
        return denied
    svc = _svc()
    if not svc:
        return _no_svc()

    action = (request.form.get("action") or "save_roster").strip()
    session = get_session()
    try:
        if action == "create":
            num_raw = request.form.get("new_season_number", "").strip()
            if not num_raw.isdigit():
                raise ValueError("Season number must be an integer.")
            season_num = int(num_raw)
            allowed = suggest_new_season_numbers(list_db_seasons(session))
            if season_num not in allowed:
                raise ValueError(
                    f"Season {season_num} cannot be created. "
                    f"Choose one of: {', '.join(f'Season {n}' for n in allowed)}."
                )
            clone_raw = request.form.get("clone_from", "").strip()
            clone_from = int(clone_raw) if clone_raw.isdigit() else None
            create_season(session, season_num, clone_from=clone_from)
            session.commit()
            svc.refresh_data()
            return redirect(url_for("admin.admin_season_form", season=f"Season {season_num}"))

        if action == "save_roster":
            season_num, err = _season_number_from_request()
            if err:
                raise ValueError(err)
            teams = _parse_teams_form()
            save_season_roster(session, season_num, teams)
            session.commit()
            svc.refresh_data()
            return redirect(url_for("admin.admin_season_form", season=f"Season {season_num}"))

        if action == "delete_season":
            season_num, err = _season_number_from_request()
            if err:
                raise ValueError(err)
            delete_season(session, season_num)
            session.commit()
            svc.refresh_data()
            return redirect(url_for("admin.admin_home"))

        raise ValueError(f"Unknown action: {action}")
    except Exception as exc:
        session.rollback()
        return render_template("error.html", message=str(exc)), 400
    finally:
        session.close()


def _team_indices_from_form() -> list[int]:
    indices: set[int] = set()
    for key in request.form:
        if not key.startswith("teams["):
            continue
        try:
            idx_s = key.split("[", 2)[1].split("]", 1)[0]
            indices.add(int(idx_s))
        except (ValueError, IndexError):
            continue
    return sorted(indices)


def _players_for_team_index(team_idx: int) -> list[str]:
    picks = request.form.getlist(f"teams[{team_idx}][player_pick][]")
    news = request.form.getlist(f"teams[{team_idx}][player_new][]")
    players: list[str] = []
    for i, pick in enumerate(picks):
        pick = (pick or "").strip()
        if pick == "__new__":
            name = (news[i] if i < len(news) else "").strip()
            if name:
                players.append(name)
        elif pick:
            players.append(pick)
    if players:
        return players
    raw = request.form.get(f"teams[{team_idx}][players]", "")
    return [p.strip() for p in raw.splitlines() if p.strip()]


def _parse_teams_form() -> list[dict]:
    """Parse teams[N][name] and player picks from the roster form."""
    teams = []
    for idx in _team_indices_from_form():
        name = (request.form.get(f"teams[{idx}][name]") or "").strip()
        if not name:
            continue
        players = _players_for_team_index(idx)
        teams.append({"name": name, "players": players})
    return teams
