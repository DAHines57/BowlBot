"""Seeding, bracket projection, reseed pairing, and round labelling."""

from stats import playoffs

TEAMS = [f"Team {i}" for i in range(1, 9)]


def _fact(team, season, week, *, games=(200, 200), opponent=None, playoff=False):
    row = {
        "season_number": season,
        "season_label": f"Season {season}",
        "week": week,
        "team": team,
        "opponent": opponent,
        "player_display_name": f"{team} bowler",
        "substitute": False,
        "absent": False,
        "playoffs": playoff,
    }
    for i, g in enumerate(games, start=1):
        row[f"game{i}"] = g
    return row


def _regular_season(pin_by_team, weeks=2):
    """One matchup per week per pair, with per-team pins fixed by ``pin_by_team``."""
    facts = []
    pairs = [(TEAMS[i], TEAMS[i + 1]) for i in range(0, len(TEAMS), 2)]
    for week in range(1, weeks + 1):
        for home, away in pairs:
            for team, opp in ((home, away), (away, home)):
                pins = pin_by_team[team]
                facts.append(
                    _fact(team, 14, week, games=(pins, pins), opponent=opp)
                )
    return facts


def _matchup(home, away, home_pins, away_pins):
    home_result = "W" if home_pins > away_pins else "L"
    away_result = "L" if home_pins > away_pins else "W"
    return {
        "home": {
            "name": home,
            "pins": home_pins,
            "game_pins": [home_pins],
            "result": home_result,
        },
        "away": {
            "name": away,
            "pins": away_pins,
            "game_pins": [away_pins],
            "result": away_result,
        },
    }


def _seeds():
    return [{"seed": i + 1, "team": t} for i, t in enumerate(TEAMS)]


def test_seeding_orders_by_wins_then_pins():
    pins = {team: 250 - i * 10 for i, team in enumerate(TEAMS)}
    seeds = playoffs.season_seeding(_regular_season(pins), 14)

    assert [row["team"] for row in seeds] == [
        "Team 1", "Team 3", "Team 5", "Team 7",
        "Team 2", "Team 4", "Team 6", "Team 8",
    ]
    assert seeds[0]["seed"] == 1
    assert seeds[0]["record"] == "4-0"
    assert seeds[-1]["record"] == "0-4"


def test_projected_quarterfinals_use_fixed_seed_pairs():
    pairs = playoffs.projected_quarterfinals(_seeds())

    assert pairs == [
        ("Team 1", "Team 8"),
        ("Team 2", "Team 7"),
        ("Team 3", "Team 6"),
        ("Team 4", "Team 5"),
    ]


def test_projected_first_round_matches_quarterfinals_order():
    pairs = playoffs.projected_first_round(TEAMS)

    assert pairs == [
        ("Team 1", "Team 8"),
        ("Team 2", "Team 7"),
        ("Team 3", "Team 6"),
        ("Team 4", "Team 5"),
    ]


def test_pair_by_reseed_best_vs_worst():
    ranks = {t: i + 1 for i, t in enumerate(TEAMS)}
    # Winners 1, 2, 5, 6 → 1v6 and 2v5.
    pairs = playoffs.pair_by_reseed(
        ["Team 1", "Team 2", "Team 5", "Team 6"], ranks
    )
    assert pairs == [("Team 1", "Team 6"), ("Team 2", "Team 5")]


def test_before_week_8_upcoming_is_projected_quarterfinals():
    seeds = _seeds()
    bracket = playoffs.build_bracket([8, 9, 10], [None, None, None], seeds)

    upcoming = bracket["winners"]["upcoming"]
    assert upcoming["week"] == 8
    assert upcoming["label"] == "Quarterfinals"
    assert upcoming["projected"] is True
    assert [(m["home"], m["away"]) for m in upcoming["matchups"]] == [
        ("Team 1", "Team 8"),
        ("Team 2", "Team 7"),
        ("Team 3", "Team 6"),
        ("Team 4", "Team 5"),
    ]
    assert bracket["winners"]["rounds"] == []
    assert bracket["losers"]["upcoming"] is None
    assert bracket["losers"]["rounds"] == []
    assert bracket["champion"] is None


def test_after_week_8_projects_reseeded_semifinals():
    seeds = _seeds()
    # Seeds 1, 2, 5, 6 win their QFs.
    week_eight = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 6", "Team 3", 900, 800),  # 6 beats 3
            _matchup("Team 5", "Team 4", 900, 800),  # 5 beats 4
        ]
    }

    bracket = playoffs.build_bracket(
        [8, 9, 10], [week_eight, None, None], seeds
    )

    assert len(bracket["winners"]["rounds"]) == 1
    assert bracket["winners"]["rounds"][0]["label"] == "Quarterfinals"
    assert bracket["winners"]["rounds"][0]["week"] == 8

    w_up = bracket["winners"]["upcoming"]
    assert w_up["week"] == 9
    assert w_up["label"] == "Semifinals"
    assert [(m["home"], m["away"]) for m in w_up["matchups"]] == [
        ("Team 1", "Team 6"),
        ("Team 2", "Team 5"),
    ]

    l_up = bracket["losers"]["upcoming"]
    assert l_up["week"] == 9
    assert l_up["label"] == "Semifinals"
    pairs = {frozenset({m["home"], m["away"]}) for m in l_up["matchups"]}
    assert frozenset({"Team 3", "Team 8"}) in pairs
    assert frozenset({"Team 4", "Team 7"}) in pairs
    assert bracket["champion"] is None


def test_week_8_alone_is_never_labeled_finals():
    seeds = _seeds()
    week_eight = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 3", "Team 6", 900, 800),
            _matchup("Team 4", "Team 5", 900, 800),
        ]
    }
    bracket = playoffs.build_bracket(
        [8, 9, 10], [week_eight, None, None], seeds
    )
    assert bracket["winners"]["rounds"][0]["label"] == "Quarterfinals"
    assert bracket["winners"]["upcoming"]["label"] == "Semifinals"


def test_after_week_9_projects_finals_and_placement():
    seeds = _seeds()
    week_eight = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 3", "Team 6", 900, 800),
            _matchup("Team 4", "Team 5", 900, 800),
        ]
    }
    # SF: 1 beats 4, 2 beats 3; losers 5 beats 8, 6 beats 7.
    week_nine = {
        "matchups": [
            _matchup("Team 1", "Team 4", 900, 800),
            _matchup("Team 2", "Team 3", 900, 800),
            _matchup("Team 5", "Team 8", 900, 800),
            _matchup("Team 6", "Team 7", 900, 800),
        ]
    }

    bracket = playoffs.build_bracket(
        [8, 9, 10], [week_eight, week_nine, None], seeds
    )

    w_up = bracket["winners"]["upcoming"]
    assert w_up["week"] == 10
    assert w_up["label"] == "Finals"
    labels = [m["label"] for m in w_up["matchups"]]
    assert "1st & 2nd place" in labels
    assert "3rd & 4th place" in labels
    title = next(m for m in w_up["matchups"] if m["label"] == "1st & 2nd place")
    assert {title["home"], title["away"]} == {"Team 1", "Team 2"}

    l_up = bracket["losers"]["upcoming"]
    assert l_up["week"] == 10
    place_labels = [m["label"] for m in l_up["matchups"]]
    assert "5th & 6th place" in place_labels
    assert "7th & 8th place" in place_labels
    assert bracket["champion"] is None


def test_champion_requires_championship_final():
    seeds = _seeds()
    week_eight = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 3", "Team 6", 900, 800),
            _matchup("Team 4", "Team 5", 900, 800),
        ]
    }
    week_nine = {
        "matchups": [
            _matchup("Team 1", "Team 4", 900, 800),
            _matchup("Team 2", "Team 3", 900, 800),
            _matchup("Team 5", "Team 8", 900, 800),
            _matchup("Team 6", "Team 7", 900, 800),
        ]
    }
    week_ten = {
        "matchups": [
            _matchup("Team 1", "Team 2", 900, 800),
            _matchup("Team 4", "Team 3", 800, 900),
            _matchup("Team 5", "Team 6", 900, 800),
            _matchup("Team 8", "Team 7", 800, 900),
        ]
    }

    bracket = playoffs.build_bracket(
        [8, 9, 10], [week_eight, week_nine, week_ten], seeds
    )

    assert bracket["champion"] == "Team 1"
    assert bracket["winners"]["upcoming"] is None
    assert bracket["losers"]["upcoming"] is None
    assert [r["label"] for r in bracket["winners"]["rounds"]] == [
        "Quarterfinals",
        "Semifinals",
        "Finals",
    ]
    assert [r["label"] for r in bracket["losers"]["rounds"]] == [
        "Semifinals",
        "Finals",
    ]


def test_upcoming_compat_helper_returns_winners_side():
    seeds = _seeds()
    upcoming = playoffs.upcoming_round([8, 9, 10], [None, None, None], seeds)
    assert upcoming["label"] == "Quarterfinals"
    assert upcoming["week"] == 8


def test_odd_field_size_reseeds_available_teams():
    six = TEAMS[:6]
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(six)]

    upcoming = playoffs.upcoming_round([], [], seeds, next_week=8)

    assert upcoming["week"] == 8
    assert [(m["home"], m["away"]) for m in upcoming["matchups"]] == [
        ("Team 1", "Team 6"),
        ("Team 2", "Team 5"),
        ("Team 3", "Team 4"),
    ]
