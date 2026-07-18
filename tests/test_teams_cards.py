"""Team standings / best-scores mobile cards and home Teams range UI."""
from pathlib import Path

from image_generator import build_teams_html, build_top_team_scores_hub_html
from stats.compute import get_team_scores


def _fact(player, week, *, games=(200, 200, 200, 200), team="Team A", season=9):
    g1, g2, g3, g4 = games
    return {
        "season_number": season,
        "season_label": f"Season {season}",
        "team": team,
        "player_display_name": player,
        "week": week,
        "game1": float(g1),
        "game2": float(g2),
        "game3": float(g3),
        "game4": float(g4),
        "game5": None,
        "absent": False,
        "substitute": False,
        "substitute_scores_count": False,
        "substituted_for": None,
        "playoffs": False,
        "opponent": "Team B" if team == "Team A" else "Team A",
    }


def test_build_teams_html_has_mobile_cards():
    facts = [
        _fact("Alice", 1),
        _fact("Bob", 1, team="Team B", games=(180, 180, 180, 180)),
    ]
    data = get_team_scores(facts, season="Season 9", through_week=1, season_num=9)
    html = build_teams_html(
        data, "Season 9", subtitle="Season 9 &nbsp;·&nbsp; through week 1"
    )
    assert "through week 1" in html
    assert "teams-standings-section" in html
    assert 'class="lb-cards"' in html
    assert "team-card" in html
    assert "Roster" not in html
    assert "team-roster" in html or "Alice" in html
    assert "lb-card-sort-dir" in html
    assert 'value="record" selected' in html


def test_build_top_team_scores_hub_has_cards_per_panel():
    games = [("Team A", 1, 2, 800, {"Alice": 200.0})]
    weeks = [("Team A", 1, 800, 4, {"Alice": 200.0})]
    teams_data = {
        "Team A": {
            "wins": 1,
            "losses": 0,
            "ties": 0,
            "avg_per_game": 200.0,
            "pins_for": 800,
            "players": {"Alice": 200.0},
        }
    }
    # Single-season hub: Best seasons tab is hidden.
    html = build_top_team_scores_hub_html(
        games, weeks, "Season 9", 10, teams_data=teams_data
    )
    assert html.count("team-card") >= 2
    assert 'data-sort-kind="games"' in html
    assert 'data-sort-kind="weeks"' in html
    assert 'data-default-sort="avg"' in html
    assert '<option value="avg" selected>Avg</option>' in html
    assert "Best seasons" not in html
    assert 'data-view-tab="averages"' not in html

    # All-time hub: Best seasons tab is shown.
    season_rows = [
        {
            "team": "Team A",
            "season": "Season 9",
            "stats": {
                "wins": 1,
                "losses": 0,
                "ties": 0,
                "avg_per_game": 200.0,
                "pins_for": 800,
                "players": {"Alice": 200.0},
            },
        }
    ]
    all_time = build_top_team_scores_hub_html(
        games, weeks, "All Time", 10, team_season_rows=season_rows
    )
    assert "Best seasons" in all_time
    assert 'data-view-tab="averages"' in all_time
    assert 'data-sort-kind="averages"' in all_time
    assert 'class="team-season">Season 9</div>' in all_time
    assert 'data-disp-season="Season 9"' in all_time
    # Default Avg sort rewrite must keep season in the secondary line.
    assert "seasonPrefix" in all_time or "Season 9" in all_time.split('data-panel="averages"')[-1]


def test_home_teams_range_smoke_markers():
    home = Path(__file__).resolve().parents[1] / "templates" / "home.html"
    text = home.read_text(encoding="utf-8")
    assert 'id="range-custom-teams"' in text
    assert 'id="teams_season_sel"' in text
    assert "function teamsRangeMode" in text
    assert "function snapRangeToSingleSeason" in text
    assert "function applyTeamsCustomRange" in text
    assert "function applySingleWeek" in text
    assert "function earliestWeekFor" in text
    assert 'id="week-pick"' in text
    assert 'id="range-preset-all-time"' in text
    assert "teamsAllowsAllTime" in text
