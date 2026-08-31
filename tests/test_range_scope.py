"""Cross-season range scoping and aggregation modes."""

import pytest

from stats.compute import compute_player_par
from stats.facts import fact_counts_for_stats, filter_facts
from stats.range_stats import (
    absence_penalty,
    get_player_range_detail,
    get_range_stats,
    get_team_range_detail,
)
from stats.scope import (
    MODE_CAREER,
    MODE_RANGE,
    MODE_SEASON,
    Scope,
    format_position,
    parse_position,
)


def _fact(player, season, week, *, games=(200, 200, 200, 200), absent=False,
          team="Team A", playoffs=False, substitute=False, missed_slots=()):
    row = {
        "season_number": season,
        "season_label": f"Season {season}",
        "week": week,
        "team": team,
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": substitute,
        "absent": absent,
        "playoffs": playoffs,
        "week_average": sum(games) / len(games) if games else 0,
    }
    for i, g in enumerate(games, start=1):
        row[f"game{i}"] = g
    for slot in missed_slots:
        row[f"game{slot}_absent"] = True
    return row


# --- Scope basics ---------------------------------------------------------


def test_parse_and_format_position_round_trip():
    assert parse_position("14.3") == (14, 3)
    assert parse_position("7") == (7, 1)
    assert format_position((14, 3)) == "14.3"
    assert parse_position("") is None
    assert parse_position(None) is None
    assert parse_position("garbage") is None


def test_scope_rejects_unknown_mode():
    with pytest.raises(ValueError):
        Scope(mode="sideways")


def test_single_season_only_when_range_within_one_season():
    assert Scope(start=(9, 1), end=(9, 10)).single_season == 9
    assert Scope(start=(9, 1), end=(10, 4)).single_season is None
    assert Scope.career().single_season is None
    assert Scope().single_season is None


# --- Range filtering -----------------------------------------------------


def test_filter_facts_range_spans_seasons_lexicographically():
    facts = [
        _fact("Alice", 1, 1),
        _fact("Alice", 1, 5),
        _fact("Alice", 2, 2),
        _fact("Alice", 7, 8),
        _fact("Alice", 8, 1),
    ]
    scope = Scope(start=(1, 2), end=(7, 8))
    kept = filter_facts(facts, scope=scope)
    got = {(f["season_number"], f["week"]) for f in kept}
    assert got == {(1, 5), (2, 2), (7, 8)}


def test_filter_facts_range_boundaries_are_inclusive():
    facts = [_fact("Alice", 3, 4), _fact("Alice", 5, 6)]
    kept = filter_facts(facts, scope=Scope(start=(3, 4), end=(5, 6)))
    assert len(kept) == 2


def test_career_mode_ignores_range_bounds():
    facts = [_fact("Alice", 1, 1), _fact("Alice", 9, 9)]
    scope = Scope(start=(1, 1), end=(1, 1), mode=MODE_CAREER)
    assert len(filter_facts(facts, scope=scope)) == 2


def _playoff_facts():
    return [
        _fact("Alice", 9, 1),
        _fact("Alice", 9, 11, playoffs=True),
    ]


def test_scope_can_exclude_playoffs():
    scope = Scope(start=(9, 1), end=(9, 20), playoffs="regular")
    kept = filter_facts(_playoff_facts(), scope=scope)
    assert [f["week"] for f in kept] == [1]


def test_scope_can_isolate_playoffs():
    scope = Scope(start=(9, 1), end=(9, 20), playoffs="only")
    kept = filter_facts(_playoff_facts(), scope=scope)
    assert [f["week"] for f in kept] == [11]


def test_scope_keeps_both_halves_by_default():
    scope = Scope(start=(9, 1), end=(9, 20))
    assert scope.playoffs == "both"
    kept = filter_facts(_playoff_facts(), scope=scope)
    assert [f["week"] for f in kept] == [1, 11]


def test_playoff_filter_applies_to_career_scopes():
    """The check sits ahead of the unbounded short-circuit, so it still bites."""
    kept = filter_facts(
        _playoff_facts(), scope=Scope.career(playoffs="only")
    )
    assert [f["week"] for f in kept] == [11]


def test_unknown_playoff_filter_is_rejected():
    with pytest.raises(ValueError):
        Scope(playoffs="semifinals")


def test_scope_composes_with_existing_filters():
    facts = [
        _fact("Alice", 9, 1, team="Team A"),
        _fact("Bob", 9, 1, team="Team B"),
    ]
    kept = filter_facts(facts, scope=Scope(start=(9, 1), end=(9, 1)), team="Team B")
    assert [f["player_display_name"] for f in kept] == ["Bob"]


# --- Cross-season key collision ------------------------------------------


def test_same_week_number_in_different_seasons_does_not_merge():
    """S1 W3 and S7 W3 are distinct team-weeks, not one merged bucket."""
    facts = [
        _fact("Alice", 1, 3, games=(100, 100, 100, 100)),
        _fact("Alice", 7, 3, games=(300, 300, 300, 300)),
    ]
    data = get_range_stats(facts, Scope(start=(1, 1), end=(7, 10), mode=MODE_RANGE))
    team = next(t for t in data["teams"] if t["team"] == "Team A")
    assert team["weeks"] == 2, "week labels must be season-qualified"

    alice = next(p for p in data["players"] if p["player"] == "Alice")
    assert alice["weeks_played"] == 2
    assert alice["games"] == 8
    assert alice["highest_game"] == 300
    assert alice["lowest_game"] == 100


# --- Aggregation modes ---------------------------------------------------


def _two_season_facts():
    """Season 1: one week of 100s. Season 2: three weeks of 200s.

    Pooled mean is 175 (2 games of 100, 6 of 200 -> 1400/8).
    Mean of season means is 150 ((100 + 200) / 2).
    """
    return [
        _fact("Alice", 1, 1, games=(100, 100)),
        _fact("Alice", 2, 1, games=(200, 200)),
        _fact("Alice", 2, 2, games=(200, 200)),
        _fact("Alice", 2, 3, games=(200, 200)),
    ]


def test_range_mode_pools_every_game():
    data = get_range_stats(
        _two_season_facts(), Scope(start=(1, 1), end=(2, 9), mode=MODE_RANGE)
    )
    alice = data["players"][0]
    assert alice["average"] == 175.0
    assert alice["games"] == 8


def test_season_mode_averages_the_season_averages():
    data = get_range_stats(
        _two_season_facts(), Scope(start=(1, 1), end=(2, 9), mode=MODE_SEASON)
    )
    alice = data["players"][0]
    assert alice["average"] == 150.0


def test_career_mode_pools_everything_regardless_of_range():
    narrow = Scope(start=(2, 1), end=(2, 1), mode=MODE_CAREER)
    data = get_range_stats(_two_season_facts(), narrow)
    alice = data["players"][0]
    assert alice["average"] == 175.0
    assert alice["games"] == 8


def test_range_mode_respects_narrow_window():
    data = get_range_stats(
        _two_season_facts(), Scope(start=(2, 1), end=(2, 2), mode=MODE_RANGE)
    )
    alice = data["players"][0]
    assert alice["average"] == 200.0
    assert alice["games"] == 4


# --- Payload shape -------------------------------------------------------


def test_range_stats_reports_league_and_highlights():
    facts = [
        _fact("Alice", 9, 1, games=(250, 100)),
        _fact("Bob", 9, 1, games=(200, 150), team="Team B"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["league"]["total_games"] == 4
    assert data["league"]["total_players"] == 2
    assert data["league"]["games_200_plus"] == 2
    assert data["highlights"]["high_game"]["score"] == 250
    assert data["highlights"]["high_game"]["player"] == "Alice"
    assert data["highlights"]["low_game"]["score"] == 100
    assert data["highlights"]["high_game"]["when"] == "S9 W1"


def test_team_high_week_names_the_winning_week():
    """The card shows which week it was, so the label must track the best week.

    Guards against reducing weeks with a plain max(), which yields the right
    number attached to the wrong week.
    """
    facts = [
        _fact("Alice", 9, 1, games=(150, 150)),
        _fact("Alice", 9, 2, games=(250, 250)),
        _fact("Alice", 9, 3, games=(200, 200)),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    team_high = data["highlights"]["team_high"]
    assert team_high["score"] == 250
    assert team_high["when"] == "S9 W2"

    team_low = data["highlights"]["team_low"]
    assert team_low["score"] == 150
    assert team_low["when"] == "S9 W1"

    team = next(t for t in data["teams"] if t["team"] == "Team A")
    assert team["high_week_avg_label"] == "S9 W2"
    assert team["low_week_avg"] == 150
    assert team["low_week"] == 300


def test_team_week_average_weights_players_equally():
    """A short week for one player must not drag the whole team-week down.

    Alice bowls two games, Bob one. Pooling games gives (200+200+140)/3 = 180;
    averaging the players' averages gives (200+140)/2 = 170.
    """
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Bob", 9, 1, games=(140,)),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    team = next(t for t in data["teams"] if t["team"] == "Team A")
    assert team["high_week_avg"] == 170
    assert team["avg_per_game"] == 180
    assert data["highlights"]["team_high"]["score"] == 170
    # Over one week the week average is the high week, which is what the
    # single-week view shows in place of the two identical figures.
    assert team["week_avg"] == 170
    assert team["week_avg"] == team["low_week_avg"]


def test_team_week_avg_weights_weeks_equally():
    """A light week counts as one week, not as its share of the games pool.

    Week 1 has two bowlers at 200 and 100 (week avg 150); week 2 has one
    bowler at 210. Pooling games gives (200+100+210)/3 = 170; averaging the
    weeks gives (150+210)/2 = 180.
    """
    facts = [
        _fact("Alice", 9, 1, games=(200,)),
        _fact("Bob", 9, 1, games=(100,)),
        _fact("Alice", 9, 2, games=(210,)),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 2)))
    team = next(t for t in data["teams"] if t["team"] == "Team A")
    assert team["avg_per_game"] == 170
    assert team["week_avg"] == 180


def test_scope_block_exposes_single_season_for_par_gating():
    facts = [_fact("Alice", 9, 1)]
    within = get_range_stats(facts, Scope(start=(9, 1), end=(9, 5)))
    assert within["scope"]["single_season"] == 9
    across = get_range_stats(facts, Scope(start=(8, 1), end=(9, 5)))
    assert across["scope"]["single_season"] is None


def test_absences_counted_but_not_averaged():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(), absent=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    alice = data["players"][0]
    assert alice["absences"] == 1
    assert alice["average"] == 200.0
    assert alice["games"] == 2


def test_sub_games_reported_separately_from_roster_games():
    """The player card shows a sub count, so the payload must carry one."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(180, 190), team="Team B", substitute=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    alice = next(p for p in data["players"] if p["player"] == "Alice")
    assert alice["sub_games"] == 2


def test_sub_games_is_zero_for_a_plain_roster_player():
    facts = [_fact("Alice", 9, 1, games=(200, 200))]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    assert data["players"][0]["sub_games"] == 0


# --- Player detail -------------------------------------------------------


def test_player_range_detail_lists_individual_games_in_order():
    facts = [
        _fact("Alice", 1, 2, games=(120, 130)),
        _fact("Alice", 2, 1, games=(210, 220)),
    ]
    detail = get_player_range_detail(facts, "Alice", Scope(start=(1, 1), end=(2, 9)))
    assert detail is not None
    assert [g["score"] for g in detail["games"]] == [120, 130, 210, 220]
    assert [g["label"] for g in detail["games"]] == ["S1 W2", "S1 W2", "S2 W1", "S2 W1"]
    assert detail["summary"]["games"] == 4


def test_player_range_detail_missing_player_is_none():
    facts = [_fact("Alice", 9, 1)]
    assert get_player_range_detail(facts, "Nobody", Scope()) is None


def test_missed_game_keeps_its_book_average_score_and_slot():
    """The card has to show what score was taken for a game the player missed."""
    facts = [_fact("Alice", 9, 1, games=(150, 200, 210, 220), missed_slots=(1,))]
    detail = get_player_range_detail(facts, "Alice", Scope(start=(9, 1), end=(9, 1)))

    assert [g["score"] for g in detail["games"]] == [150, 200, 210, 220]
    assert [g["game"] for g in detail["games"]] == [1, 2, 3, 4]
    missed = detail["games"][0]
    assert missed["game_absent"] is True
    assert missed["counts"] is False
    assert all(g["counts"] for g in detail["games"][1:])


def test_missed_game_stays_out_of_the_average():
    facts = [_fact("Alice", 9, 1, games=(100, 200, 200, 200), missed_slots=(1,))]
    detail = get_player_range_detail(facts, "Alice", Scope(start=(9, 1), end=(9, 1)))
    assert detail["summary"]["average"] == 200.0
    assert detail["summary"]["games"] == 3
    assert detail["summary"]["lowest_game"] == 200


def test_absent_weeks_are_listed_for_the_card():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(), absent=True),
        _fact("Alice", 9, 3, games=(210, 210)),
    ]
    detail = get_player_range_detail(facts, "Alice", Scope(start=(9, 1), end=(9, 9)))
    assert [w["label"] for w in detail["absent_weeks"]] == ["S9 W2"]
    assert detail["absent_weeks"][0]["week"] == 2
    assert 2 not in [g["week"] for g in detail["games"]]


def test_sub_only_player_is_ranked_on_their_sub_games():
    """Showing up to fill in still counts, so they slot in by average."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Zoe", 9, 1, games=(180, 190), team="Team B", substitute=True),
        _fact("Cara", 9, 1, games=(150, 150), team="Team C"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    zoe = next(p for p in data["players"] if p["player"] == "Zoe")
    assert zoe["sub_games"] == 2
    assert zoe["games"] == 2
    assert zoe["average"] == 185.0
    assert zoe["highest_game"] == 190
    assert zoe["weeks_played"] == 1
    # Between the 200 and the 150 bowler, not pinned to the bottom.
    assert [p["player"] for p in data["players"]] == ["Alice", "Zoe", "Cara"]


def test_sub_games_join_the_roster_average():
    facts = [
        _fact("Alice", 9, 1, games=(100, 100)),
        _fact("Alice", 9, 2, games=(200, 200), team="Team B", substitute=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    alice = data["players"][0]
    assert alice["average"] == 150.0
    assert alice["games"] == 4
    assert alice["weeks_played"] == 2
    assert alice["sub_games"] == 2
    # The roster team wins over whichever team they filled in for.
    assert alice["team"] == "Team A"


def test_membership_lists_tag_a_sub_only_appearance():
    """An appearance is not membership, so the filled-in team is marked."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(180, 180), team="Team B", substitute=True),
        _fact("Bob", 9, 2, games=(190, 190), team="Team B"),
    ]
    scope = Scope(start=(9, 1), end=(9, 9))

    seasons = get_player_range_detail(facts, "Alice", scope)["teams_by_season"]
    assert [g["season"] for g in seasons] == [9]
    assert seasons[0]["members"] == [
        {"name": "Team A", "sub": False, "average": 200.0},
        {"name": "Team B", "sub": True, "average": 180.0},
    ]

    # Same rule from the team's side: Alice only filled in for Team B.
    rosters = get_team_range_detail(facts, "Team B", scope)["rosters"]
    assert rosters[0]["members"] == [
        {"name": "Bob", "sub": False, "average": 190.0},
        {"name": "Alice", "sub": True, "average": 180.0},
    ]


def test_roster_members_carry_their_average_over_the_range():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(100, 100)),
        _fact("Bob", 9, 1, games=(190, 190)),
    ]
    rosters = get_team_range_detail(
        facts, "Team A", Scope(start=(9, 1), end=(9, 9))
    )["rosters"]

    members = {m["name"]: m["average"] for m in rosters[0]["members"]}
    assert members == {"Alice": 150.0, "Bob": 190.0}


def test_a_member_absent_all_season_has_no_average():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Bob", 9, 1, games=(), absent=True),
    ]
    rosters = get_team_range_detail(
        facts, "Team A", Scope(start=(9, 1), end=(9, 9))
    )["rosters"]

    bob = next(m for m in rosters[0]["members"] if m["name"] == "Bob")
    assert bob["average"] is None


def test_a_subs_roster_average_covers_only_their_games_there():
    facts = [
        _fact("Alice", 9, 1, games=(100, 100)),
        _fact("Alice", 9, 2, games=(240, 240), team="Team B", substitute=True),
        _fact("Bob", 9, 2, games=(190, 190), team="Team B"),
    ]
    scope = Scope(start=(9, 1), end=(9, 9))

    rosters = get_team_range_detail(facts, "Team B", scope)["rosters"]
    alice = next(m for m in rosters[0]["members"] if m["name"] == "Alice")
    # Her Team A games are not part of the team she filled in for.
    assert alice["average"] == 240.0

    # From her own side, the per-team split holds too.
    seasons = get_player_range_detail(facts, "Alice", scope)["teams_by_season"]
    assert {m["name"]: m["average"] for m in seasons[0]["members"]} == {
        "Team A": 100.0,
        "Team B": 240.0,
    }


def test_rosters_are_grouped_by_season_and_exclude_other_teams():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Bob", 9, 1, games=(190, 190)),
        _fact("Cara", 10, 1, games=(180, 180)),
        _fact("Dan", 10, 1, games=(170, 170), team="Team B"),
    ]
    rosters = get_team_range_detail(
        facts, "Team A", Scope(start=(9, 1), end=(10, 9))
    )["rosters"]

    assert [g["label"] for g in rosters] == ["Season 9", "Season 10"]
    assert [m["name"] for m in rosters[0]["members"]] == ["Alice", "Bob"]
    assert [m["name"] for m in rosters[1]["members"]] == ["Cara"]


def test_sub_row_seen_first_does_not_claim_the_roster_team():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200), team="Team B", substitute=True),
        _fact("Alice", 9, 2, games=(200, 200), team="Team A"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    assert data["players"][0]["team"] == "Team A"


def test_roster_and_sub_row_in_one_week_count_as_one_week():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 1, games=(180, 180), team="Team B", substitute=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["players"][0]["weeks_played"] == 1
    assert data["players"][0]["games"] == 4


def test_season_mode_weighting_survives_sub_games():
    """Sub games join their own season's pool, so the mode still balances."""
    facts = [
        _fact("Alice", 1, 1, games=(100, 100)),
        _fact("Alice", 2, 1, games=(200, 200)),
        _fact("Alice", 2, 2, games=(200, 200), team="Team B", substitute=True),
    ]
    data = get_range_stats(
        facts, Scope(start=(1, 1), end=(2, 9), mode=MODE_SEASON)
    )
    assert data["players"][0]["average"] == 150.0


def test_sub_for_names_are_carried_on_the_row_and_the_games():
    facts = [
        {
            **_fact("Zoe", 9, 1, games=(180, 190), team="Team B", substitute=True),
            "substituted_for": "Bob",
        }
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["players"][0]["sub_for"] == ["Bob"]

    detail = get_player_range_detail(facts, "Zoe", Scope(start=(9, 1), end=(9, 1)))
    assert all(g["substituted_for"] == "Bob" for g in detail["games"])


def test_roster_season_stats_still_exclude_subs():
    """Blending subs is scoped to the range page; the roster rule is untouched."""
    sub = _fact("Zoe", 9, 1, games=(180, 190), team="Team B", substitute=True)
    assert fact_counts_for_stats(sub) is False


def test_subs_earn_par_for_the_games_they_bowl():
    """Long-standing behaviour: sub games score PAR against a sub-free baseline."""
    sub = _fact("Zoe", 9, 1, games=(180, 190), team="Team B", substitute=True)
    facts = [_fact("Alice", 9, w, games=(200, 200)) for w in range(1, 6)] + [sub]
    par = compute_player_par(facts, season_num=9)
    assert par["Zoe"] == -30
    assert par["Alice"] == 0


def test_sub_for_is_absent_when_the_row_is_not_a_sub():
    facts = [_fact("Alice", 9, 1, games=(200, 200))]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["players"][0]["sub_for"] == []

    detail = get_player_range_detail(facts, "Alice", Scope(start=(9, 1), end=(9, 1)))
    assert all(g["substituted_for"] is None for g in detail["games"])


def test_absence_only_player_is_sorted_by_what_they_were_credited():
    """An absent week has a credited score, so the row ranks on it, not last."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Zoe", 9, 1, games=(170, 170), absent=True),
        _fact("Cara", 9, 1, games=(150, 150), team="Team C"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    zoe = next(p for p in data["players"] if p["player"] == "Zoe")
    assert zoe["average"] == 170.0
    assert zoe["absent_average"] == 170.0
    assert zoe["average_from_absences"] is True
    assert zoe["games"] == 0
    assert [p["player"] for p in data["players"]] == ["Alice", "Zoe", "Cara"]


def test_absences_do_not_touch_a_bowling_players_average():
    """Matches the legacy page: credited weeks are shown, never averaged in.

    The credited figure is projected from the player's own average rather than
    read off the absent week, so the 100s stored on that row stay out of it.
    """
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(100, 100), absent=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    alice = data["players"][0]
    assert alice["average"] == 200.0
    # One miss taken, so the next one is her second and costs 5 percent.
    assert alice["absent_average"] == 190.0
    assert alice["average_from_absences"] is False
    assert alice["games"] == 2


def test_absence_penalty_ladder():
    assert absence_penalty(1) == 0.0
    assert absence_penalty(2) == 0.05
    assert absence_penalty(3) == 0.10
    # Everything past the third sits on the last rung.
    assert absence_penalty(9) == 0.10


@pytest.mark.parametrize(
    "taken, expected",
    [(0, 200.0), (1, 190.0), (2, 180.0), (4, 180.0)],
)
def test_projection_prices_the_next_miss(taken, expected):
    """The figure is what the next absence costs, so it moves a rung ahead of
    the misses already taken, and stops at the third."""
    facts = [_fact("Alice", 9, 1, games=(200, 200))] + [
        _fact("Alice", 9, wk, games=(100, 100), absent=True)
        for wk in range(2, 2 + taken)
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 9)))
    assert data["players"][0]["absent_average"] == expected


def test_absence_penalty_resets_each_season():
    """One miss in each of two seasons leaves the latest season holding one, so
    the next miss there is a second at 5 percent rather than a third at 10."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(100, 100), absent=True),
        _fact("Alice", 10, 1, games=(200, 200)),
        _fact("Alice", 10, 2, games=(100, 100), absent=True),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(10, 9)))
    alice = data["players"][0]
    assert alice["absences"] == 2
    assert alice["absent_average"] == 190.0


def test_projection_ignores_misses_from_an_earlier_season():
    """A next miss lands in the latest season, which here is a clean slate."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(100, 100), absent=True),
        _fact("Alice", 9, 3, games=(100, 100), absent=True),
        _fact("Alice", 10, 1, games=(200, 200)),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(10, 9)))
    assert data["players"][0]["absent_average"] == 200.0


def test_absent_weeks_carry_the_credited_average_and_scores():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Alice", 9, 2, games=(170, 172), absent=True),
    ]
    detail = get_player_range_detail(facts, "Alice", Scope(start=(9, 1), end=(9, 9)))
    week = detail["absent_weeks"][0]
    assert week["label"] == "S9 W2"
    assert week["games"] == [170, 172]
    assert week["average"] == 171.0


def test_absent_credit_prefers_the_stored_week_average():
    f = _fact("Alice", 9, 1, games=(170, 172), absent=True)
    f["week_average"] = 165
    data = get_range_stats([f], Scope(start=(9, 1), end=(9, 1)))
    assert data["players"][0]["absent_average"] == 165.0


def test_absent_credit_falls_back_to_the_stored_scores():
    f = _fact("Alice", 9, 1, games=(170, 172), absent=True)
    f["week_average"] = None
    data = get_range_stats([f], Scope(start=(9, 1), end=(9, 1)))
    assert data["players"][0]["absent_average"] == 171.0


def test_absence_with_no_scores_has_no_credited_average():
    facts = [_fact("Zoe", 9, 1, games=(), absent=True)]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    zoe = data["players"][0]
    assert zoe["absent_average"] is None
    assert zoe["average"] is None
    assert zoe["average_from_absences"] is False
    assert zoe["absences"] == 1


def test_absence_only_player_still_gets_a_row():
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Zoe", 9, 1, games=(), absent=True, team="Team A"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    zoe = next(p for p in data["players"] if p["player"] == "Zoe")
    assert zoe["absences"] == 1
    assert zoe["games"] == 0
    assert zoe["average"] is None


def test_absence_only_rows_do_not_skew_league_totals():
    """League figures come from the facts, so the new rows must not reach them."""
    facts = [
        _fact("Alice", 9, 1, games=(200, 200)),
        _fact("Zoe", 9, 1, games=(), absent=True, team="Team A"),
    ]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["league"]["total_players"] == 1
    assert data["league"]["total_games"] == 2


def test_missed_games_stay_out_of_league_totals():
    facts = [_fact("Alice", 9, 1, games=(100, 200, 200, 200), missed_slots=(1,))]
    data = get_range_stats(facts, Scope(start=(9, 1), end=(9, 1)))
    assert data["league"]["total_games"] == 3
    assert data["highlights"]["low_game"]["score"] == 200
