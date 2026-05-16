"""Flask app — bowling league stats from Google Sheets."""
import os
from os.path import dirname, join

from dotenv import load_dotenv
from flask import Flask

from league_service import LeagueService
from sheets_handler import get_sheet_handler


def create_app() -> Flask:
    _root = dirname(dirname(__file__))
    app = Flask(
        __name__,
        template_folder=join(_root, "templates"),
        static_folder=join(_root, "static"),
    )

    load_dotenv(join(_root, ".env"))

    sheet = _init_sheet_handler()
    app.config["SHEET_HANDLER"] = sheet
    app.config["LEAGUE_SERVICE"] = LeagueService(sheet) if sheet else None

    from app import routes

    app.register_blueprint(routes.bp)
    return app


def _init_sheet_handler():
    stype = os.environ.get("SHEET_HANDLER_TYPE", "gsheets")
    try:
        if stype == "gsheets":
            return get_sheet_handler(
                "gsheets",
                sheet_id=os.environ["GOOGLE_SHEET_ID"],
                credentials_json=os.environ["GOOGLE_CREDENTIALS"],
            )
        path = os.environ.get("EXCEL_FILE_PATH", "Bowling-Friends League v5.xlsx")
        return get_sheet_handler("excel", file_path=path)
    except Exception as e:
        print(f"Sheet handler init failed: {e}")
        return None
