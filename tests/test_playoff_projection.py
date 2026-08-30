"""Seeding, bracket projection, and round labelling."""

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


def test_seeding_orders_by_wins_then_pins():
    # Descending pins means Team 1 beats Team 2, Team 3 beats Team 4, and so on,
    # so every odd team is 2-0 and every even team 0-2.
    pins = {team: 250 - i * 10 for i, team in enumerate(TEAMS)}
    seeds = playoffs.season_seeding(_regular_season(pins), 14)

    assert [row["team"] for row in seeds] == [
        "Team 1", "Team 3", "Team 5", "Team 7",
        "Team 2", "Team 4", "Team 6", "Team 8",
    ]
    assert seeds[0]["seed"] == 1
    # Records count games, not weeks: two games a week across two weeks.
    assert seeds[0]["record"] == "4-0"
    assert seeds[-1]["record"] == "0-4"


def test_projected_first_round_uses_standard_seeded_order():
    pairs = playoffs.projected_first_round(TEAMS)

    assert pairs == [
        ("Team 1", "Team 8"),
        ("Team 4", "Team 5"),
        ("Team 2", "Team 7"),
        ("Team 3", "Team 6"),
    ]


def test_upcoming_is_first_round_before_any_playoff_week_is_bowled():
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(TEAMS)]

    upcoming = playoffs.upcoming_round([8, 9, 10], [None, None, None], seeds)

    assert upcoming["week"] == 8
    assert upcoming["label"] == "Quarterfinals"
    assert upcoming["projected"] is True
    assert [(m["home"], m["away"]) for m in upcoming["matchups"]] == [
        ("Team 1", "Team 8"),
        ("Team 4", "Team 5"),
        ("Team 2", "Team 7"),
        ("Team 3", "Team 6"),
    ]
    assert upcoming["matchups"][0]["away_seed"] == 8


def test_upcoming_advances_winners_and_losers_after_round_one():
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(TEAMS)]
    # Every better seed wins its quarterfinal.
    week_one = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 4", "Team 5", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 3", "Team 6", 900, 800),
        ]
    }

    upcoming = playoffs.upcoming_round([8, 9, 10], [week_one, None, None], seeds)

    assert upcoming["week"] == 9
    assert upcoming["label"] == "Semifinals"
    pairs = {frozenset({m["home"], m["away"]}) for m in upcoming["matchups"]}
    assert frozenset({"Team 1", "Team 4"}) in pairs
    assert frozenset({"Team 2", "Team 3"}) in pairs
    # Quarterfinal losers keep bowling, on the 5th-8th track.
    assert frozenset({"Team 8", "Team 5"}) in pairs
    labels = [m["label"] for m in upcoming["matchups"]]
    assert labels.count("1st-4th Semifinal") == 2
    assert labels.count("5th-8th Semifinal") == 2


def test_upcoming_is_none_once_every_playoff_week_is_bowled():
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(TEAMS)]
    week = {"matchups": [_matchup("Team 1", "Team 8", 900, 800)]}

    assert playoffs.upcoming_round([8], [week], seeds) is None


def test_played_rounds_label_placement_games_in_the_finals_week():
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(TEAMS)]
    week_one = {
        "matchups": [
            _matchup("Team 1", "Team 8", 900, 800),
            _matchup("Team 4", "Team 5", 900, 800),
            _matchup("Team 2", "Team 7", 900, 800),
            _matchup("Team 3", "Team 6", 900, 800),
        ]
    }
    week_two = {
        "matchups": [
            _matchup("Team 1", "Team 4", 900, 800),
            _matchup("Team 2", "Team 3", 900, 800),
            _matchup("Team 5", "Team 8", 900, 800),
            _matchup("Team 6", "Team 7", 900, 800),
        ]
    }
    week_three = {
        "matchups": [
            _matchup("Team 1", "Team 2", 900, 800),
            _matchup("Team 4", "Team 3", 800, 900),
            _matchup("Team 5", "Team 6", 900, 800),
            _matchup("Team 8", "Team 7", 800, 900),
        ]
    }

    rounds = playoffs.played_rounds(
        [8, 9, 10], [week_one, week_two, week_three], seeds
    )

    assert [r["label"] for r in rounds] == [
        "Quarterfinals",
        "Semifinals",
        "Finals",
    ]
    finals = rounds[-1]["matchups"]
    title_game = next(m for m in finals if m["label"] == "1st & 2nd place")
    assert {title_game["home"], title_game["away"]} == {"Team 1", "Team 2"}
    assert title_game["projected"] is False
    assert title_game["home_pins"] == 900


def test_odd_field_size_still_projects_with_byes():
    six = TEAMS[:6]
    seeds = [{"seed": i + 1, "team": t} for i, t in enumerate(six)]

    upcoming = playoffs.upcoming_round([], [], seeds, next_week=8)

    assert upcoming["week"] == 8
    # An eight-slot bracket over six teams gives the top two seeds a bye.
    byes = [m["home"] for m in upcoming["matchups"] if m["away"] is None]
    assert sorted(byes) == ["Team 1", "Team 2"]
