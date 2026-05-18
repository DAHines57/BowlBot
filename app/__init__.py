"""Flask app — bowling league stats from PostgreSQL."""
import os
from os.path import dirname, join

from dotenv import load_dotenv
from flask import Flask

from db.team_colors import refresh_team_colors_cache
from league_data import create_league_data
from league_service import LeagueService


def create_app() -> Flask:
    _root = dirname(dirname(__file__))
    app = Flask(
        __name__,
        template_folder=join(_root, "templates"),
        static_folder=join(_root, "static"),
    )

    load_dotenv(join(_root, ".env"))

    app.config["DEBUG"] = os.environ.get("DEBUG", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "bowlbot-dev-secret-change-me")

    data = create_league_data()
    app.config["LEAGUE_DATA"] = data
    app.config["LEAGUE_SERVICE"] = LeagueService(data) if data else None
    if data:
        refresh_team_colors_cache()

    from app import admin_routes, routes

    app.register_blueprint(routes.bp)
    app.register_blueprint(admin_routes.admin_bp)
    return app
