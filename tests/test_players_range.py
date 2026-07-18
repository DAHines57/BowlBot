"""Range-driven player aggregates and card HTML."""
from pathlib import Path

from image_generator import build_html
from stats.compute import get_players_range_summary, range_label
from stats.facts import filter_facts_season_week_range


def _fact(
    player,
    *,
    season=10,
    week=1,
    games=(200, 210, 190, 220),
    team="Team A",
    absent=False,
    playoffs=False,
):
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
        "absent": absent,
        "substitute": False,
        "substitute_scores_count": False,
        "substituted_for": None,
        "playoffs": playoffs,
        "opponent": "Team B",
    }


def _sample_facts():
    return [
        _fact("Alice", season=13, week=5, games=(180, 190, 200, 210)),
        _fact("Alice", season=13, week=6, games=(200, 200, 200, 200)),
        _fact("Alice", season=14, week=1, games=(220, 230, 210, 240)),
        _fact("Alice", season=14, week=7, games=(250, 240, 230, 260)),
        _fact("Bob", season=14, week=7, games=(150, 160, 155, 145)),
        _fact("Bob", season=14, week=1, games=(140, 150, 145, 155)),
        _fact("Carol", season=13, week=5, games=(100, 110, 105, 115), playoffs=True),
    ]


def test_filter_facts_single_week():
    facts = _sample_facts()
    rows = filter_facts_season_week_range(
        facts, from_season=14, from_week=7, to_season=14, to_week=7
    )
    assert len(rows) == 2
    assert {r["player_display_name"] for r in rows} == {"Alice", "Bob"}


def test_filter_facts_through_season():
    facts = _sample_facts()
    rows = filter_facts_season_week_range(
        facts, from_season=14, from_week=1, to_season=14, to_week=7
    )
    assert len(rows) == 4


def test_filter_facts_cross_season():
    facts = _sample_facts()
    rows = filter_facts_season_week_range(
        facts,
        from_season=13,
        from_week=5,
        to_season=14,
        to_week=7,
        exclude_playoffs=True,
    )
    names_weeks = {(r["player_display_name"], r["season_number"], r["week"]) for r in rows}
    assert ("Alice", 13, 5) in names_weeks
    assert ("Alice", 14, 7) in names_weeks
    assert ("Carol", 13, 5) not in names_weeks


def test_get_players_range_single_week_includes_games():
    facts = _sample_facts()
    data = get_players_range_summary(
        facts,
        mode="week",
        from_season=14,
        from_week=7,
        to_season=14,
        to_week=7,
    )
    assert data["range"]["single_week"] is True
    alice = next(p for p in data["players"] if p["name"] == "Alice")
    assert alice["games"] == [250, 240, 230, 260]
    assert alice["avg"] == 245.0


def test_get_players_range_multi_week_omits_games():
    facts = _sample_facts()
    data = get_players_range_summary(
        facts,
        mode="custom",
        from_season=14,
        from_week=1,
        to_season=14,
        to_week=7,
    )
    assert data["range"]["single_week"] is False
    alice = next(p for p in data["players"] if p["name"] == "Alice")
    assert "games" not in alice
    assert alice["weeks_played"] == 2
    assert alice["games_played"] == 8


def test_get_players_range_season_and_all_time():
    facts = _sample_facts()
    season = get_players_range_summary(facts, mode="season", to_season=14)
    assert season["range"]["label"] == "Season 14"
    assert season["range"]["single_week"] is False
    assert all("games" not in p for p in season["players"])

    all_time = get_players_range_summary(facts, mode="all_time")
    assert all_time["range"]["label"] == "All-time"
    alice = next(p for p in all_time["players"] if p["name"] == "Alice")
    assert alice["weeks_played"] == 4
    assert "games" not in alice


def test_get_players_range_includes_playoffs_by_default():
    facts = _sample_facts()
    data = get_players_range_summary(
        facts,
        mode="custom",
        from_season=13,
        from_week=5,
        to_season=14,
        to_week=7,
    )
    names = {p["name"] for p in data["players"]}
    assert "Carol" in names  # Carol only has a playoff week in the fixture

    excluded = get_players_range_summary(
        facts,
        mode="custom",
        from_season=13,
        from_week=5,
        to_season=14,
        to_week=7,
        exclude_playoffs=True,
    )
    assert "Carol" not in {p["name"] for p in excluded["players"]}


def test_range_label_formats():
    assert range_label(mode="all_time") == "All-time"
    assert range_label(mode="season", to_season=14) == "Season 14"
    assert (
        range_label(
            mode="week",
            from_season=14,
            from_week=7,
            to_season=14,
            to_week=7,
        )
        == "S14 W7"
    )
    assert (
        range_label(
            mode="custom",
            from_season=13,
            from_week=5,
            to_season=14,
            to_week=7,
        )
        == "S13 W5 – S14 W7"
    )
    assert (
        range_label(
            mode="custom",
            from_season=14,
            from_week=1,
            to_season=14,
            to_week=7,
        )
        == "S14 W1–W7"
    )


def test_build_html_single_week_shows_games():
    data = get_players_range_summary(
        _sample_facts(),
        mode="week",
        from_season=14,
        from_week=7,
        to_season=14,
        to_week=7,
    )
    for p in data["players"]:
        p["range_stats"] = {
            "average": p.get("avg"),
            "highest_game": p.get("high"),
            "lowest_game": p.get("low"),
            "weeks_played": 1,
            "weeks_absent": 0,
            "std_dev": p.get("std_dev"),
            "par": p.get("par", 0),
            "games_played": len(p.get("games") or []),
            "scores": list(p.get("games") or []),
        }
    html = build_html(data)
    assert 'data-single-week="1"' in html
    assert ">Avg</option>" in html or "selected>Avg</option>" in html
    assert 'class="card-detail-label">Games</div>' in html


def test_build_html_multi_week_shows_aggregates_not_games_label():
    data = get_players_range_summary(
        _sample_facts(),
        mode="custom",
        from_season=13,
        from_week=5,
        to_season=14,
        to_week=7,
    )
    for p in data["players"]:
        p["range_stats"] = {
            "average": p.get("avg"),
            "highest_game": p.get("high"),
            "lowest_game": p.get("low"),
            "weeks_played": p.get("weeks_played", 0),
            "weeks_absent": p.get("weeks_absent", 0),
            "std_dev": p.get("std_dev"),
            "par": p.get("par", 0),
            "games_played": p.get("games_played", 0),
            "scores": list(p.get("scores") or []),
        }
        p.pop("games", None)
    html = build_html(data)
    assert 'data-single-week="0"' in html
    assert "PLAYER STATS" in html
    assert "S13 W5 – S14 W7" in html
    assert 'class="card-detail-label">Games</div>' not in html
    assert "Weeks" in html
    assert "PAR/G" in html


def test_get_players_range_includes_substitutes_in_sorted_list():
    facts = _sample_facts() + [
        _fact(
            "Jane",
            season=14,
            week=1,
            games=(220, 210, 200, 215),
            team="Team B",
        ),
    ]
    facts[-1]["substitute"] = True
    facts[-1]["substituted_for"] = "Bob"
    facts[-1]["substitute_scores_count"] = True
    facts.append(
        {
            **_fact("Jane", season=14, week=7, games=(180, 190, 185, 195), team="Team C"),
            "substitute": True,
            "substituted_for": "Alice",
            "substitute_scores_count": True,
        }
    )
    data = get_players_range_summary(facts, mode="all_time")
    players = {p["name"]: p for p in data["players"]}
    assert "Jane" in players
    assert players["Jane"]["is_substitute"] is True
    assert players["Jane"]["weeks_subbed"] == 2
    assert players["Jane"]["high"] == 220
    html = build_html(data)
    assert "week-summary-subs-section" not in html
    assert "Jane" in html
    assert '<span class="sub-badge">SUB</span>' in html


def test_roster_player_with_sub_weeks_shows_sub_wks_not_badge():
    """Roster players who also subbed keep weeks-subbed in expand, no SUB badge."""
    facts = _sample_facts() + [
        {
            **_fact("Alice", season=14, week=2, games=(170, 180, 175, 185), team="Team B"),
            "substitute": True,
            "substituted_for": "Bob",
            "substitute_scores_count": True,
        },
    ]
    data = get_players_range_summary(facts, mode="all_time")
    alice = next(p for p in data["players"] if p["name"] == "Alice")
    assert alice["is_substitute"] is False
    assert alice["weeks_subbed"] == 1
    alice["range_stats"] = {
        "average": alice.get("avg"),
        "highest_game": alice.get("high"),
        "lowest_game": alice.get("low"),
        "weeks_played": alice.get("weeks_played", 0),
        "weeks_absent": alice.get("weeks_absent", 0),
        "weeks_subbed": alice.get("weeks_subbed", 0),
        "std_dev": alice.get("std_dev"),
        "par": alice.get("par", 0),
        "games_played": alice.get("games_played", 0),
        "scores": list(alice.get("scores") or []),
    }
    html = build_html(data)
    # No SUB badge on roster Alice (only substitute-only players get the badge).
    assert 'data-sort-name="alice"' in html
    card_start = html.index('data-sort-name="alice"')
    card_html = html[card_start : html.index("</details>", card_start)]
    assert "sub-badge" not in card_html
    assert "Sub wks" in card_html
    assert ">1</div>" in card_html or ">1<" in card_html

def test_week_summary_absents_sort_by_book_avg_with_actives():
    from stats.compute import get_week_summary

    facts = [
        {
            **_fact("Alice", season=10, week=1, games=(200, 200, 200, 200)),
            "absent": True,
        },
        _fact("Bob", season=10, week=1, games=(150, 150, 150, 150)),
        {
            **_fact("Jane", season=10, week=1, games=(180, 180, 180, 180), team="Team B"),
            "substitute": True,
            "substituted_for": "Alice",
            "substitute_scores_count": True,
        },
    ]
    facts[0]["team"] = "Team A"
    facts[1]["team"] = "Team A"
    summary = get_week_summary(facts, 1, "Season 10", season_num=10)
    names = [p["name"] for p in summary["players"]]
    # Alice book avg 200 > Jane 180 > Bob 150 — absents stay in avg order.
    assert names == ["Alice", "Jane", "Bob"]
    html = build_html(summary)
    assert "data-sort-pin" not in html
    assert 'data-sort-avg="200.0"' in html
    assert 'data-sort-avg="180.0"' in html
    assert 'data-sort-avg="150.0"' in html


def test_home_range_smoke_markers():
    home = Path(__file__).resolve().parents[1] / "templates" / "home.html"
    text = home.read_text(encoding="utf-8")
    assert 'STORAGE_KEY = "bowlbot-home-v4"' in text
    assert 'data-range-preset="week"' in text
    assert 'data-range-preset="season"' in text
    assert 'data-range-preset="all_time"' in text
    assert 'id="week-pick"' in text
    assert 'id="from_season_sel"' in text
    assert 'id="from_week_sel"' in text
    assert 'id="range-pill-btn"' in text
    assert "function applySingleWeek" in text
    assert "Custom range" in text
    assert 'id="range-week-apply"' not in text
    assert 'sp.set("range", "all_time")' in text
    assert 'sp.set("range", "season")' in text
    assert 'sp.set("from_season"' in text
    assert 'sp.set("to_week"' in text
