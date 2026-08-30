"""The unified stats page shell and its static assets."""

import os

from flask import Flask

import app as app_pkg
from app import routes


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _StubSvc:
    class data:
        @staticmethod
        def get_current_season():
            return "Season 14"

    @staticmethod
    def seasons_sorted():
        return ["Season 14"]


def _client(service=_StubSvc()):
    flask_app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, "templates"),
        static_folder=os.path.join(ROOT, "static"),
    )
    flask_app.config["LEAGUE_SERVICE"] = service
    flask_app.register_blueprint(routes.bp)
    return flask_app.test_client()


def test_app_page_renders_shell():
    html = _client().get("/app").get_data(as_text=True)
    assert "app.css" in html
    assert "app.js" in html
    for anchor in [
        'id="range-pill"',
        'id="filter-panel"',
        'id="leaderboard"',
        'id="sort-field"',
        'id="sort-dir"',
        'id="settings-panel"',
        'id="playoff-group"',
        'id="playoff-flip"',
        'id="range-pill-tag"',
        'id="filter-range-tag"',
        'data-playoffs="regular"',
        'data-playoffs="both"',
        'data-playoffs="only"',
        'data-view="players"',
        'data-view="teams"',
    ]:
        assert anchor in html, anchor


def test_app_page_needs_a_service():
    assert _client(service=None).get("/app").status_code == 503


def test_static_assets_exist_and_are_wired():
    css = os.path.join(ROOT, "static", "app.css")
    js = os.path.join(ROOT, "static", "app.js")
    assert os.path.exists(css)
    assert os.path.exists(js)

    css_text = open(css, encoding="utf-8").read()
    # Colours come from the token layer, not scattered literals.
    assert "--accent: #ffb86c" in css_text
    assert "@media (min-width: 900px)" in css_text

    js_text = open(js, encoding="utf-8").read()
    assert "/api/leaderboard" in js_text
    assert "/api/meta" in js_text


def test_bracket_routes_are_gone():
    c = _client()
    assert c.get("/bracket").status_code == 404
    assert c.get("/playoffs").status_code == 404


def test_bracket_view_is_parked_and_unimported():
    """The bracket module still exists but nothing in the app imports it."""
    import importlib

    assert importlib.util.find_spec("bracket_view") is not None

    for module in ("league_service", "image_generator", "app.routes", "app.api"):
        src_name = module.replace(".", os.sep) + ".py"
        text = open(os.path.join(ROOT, src_name), encoding="utf-8").read()
        assert "bracket_view" not in text, f"{module} imports the parked bracket module"


def test_champion_detection_still_available_for_badges():
    from playoff_champion import champion_from_playoff_snapshots

    assert callable(champion_from_playoff_snapshots)
    # league_service must source it from the new module, not image_generator.
    text = open(os.path.join(ROOT, "league_service.py"), encoding="utf-8").read()
    assert "from playoff_champion import champion_from_playoff_snapshots" in text
