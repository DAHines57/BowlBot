"""Player PAR (Pins Above Replacement) computation."""

from stats.compute import (
    build_par_baselines,
    compute_player_par,
    par_baseline_for_game,
)


def _fact(
    player,
    season_num,
    week,
    *,
    absent=False,
    substitute=False,
    games=(200, 200, 200, 200),
):
    return {
        "season_number": season_num,
        "season_label": f"Season {season_num}",
        "week": week,
        "team": "Team A",
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": substitute,
        "absent": absent,
        "game1": games[0],
        "game2": games[1],
        "game3": games[2],
        "game4": games[3],
        "week_average": sum(games) / len(games),
    }


def _league_row(season_num, week, games=(200, 200, 200, 200)):
    """Regular league row for baseline pool (non-sub, non-absent)."""
    return _fact(f"Baseline-{season_num}-w{week}", season_num, week, games=games)


def test_par_baseline_week2_uses_prior_season_full_avg():
    facts = [
        _league_row(9, 1, (180, 180, 180, 180)),
        _league_row(9, 2, (220, 220, 220, 220)),
        _fact("Alice", 10, 2, games=(210, 210, 210, 210)),
    ]
    full_avg, ytd_avg = build_par_baselines(facts)
    baseline = par_baseline_for_game(10, 2, full_avg, ytd_avg)
    assert baseline == 200.0


def test_par_baseline_week4_uses_current_season_ytd():
    facts = [
        _league_row(10, 1, (180, 180, 180, 180)),
        _league_row(10, 2, (220, 220, 220, 220)),
        _league_row(10, 3, (200, 200, 200, 200)),
        _league_row(10, 4, (240, 240, 240, 240)),
    ]
    full_avg, ytd_avg = build_par_baselines(facts)
    baseline = par_baseline_for_game(10, 4, full_avg, ytd_avg)
    assert baseline == 210.0


def test_par_first_season_week2_uses_ytd_not_prior():
    facts = [
        _league_row(8, 1, (190, 190, 190, 190)),
        _fact("Alice", 8, 2, games=(210, 210, 210, 210)),
    ]
    full_avg, ytd_avg = build_par_baselines(facts)
    baseline = par_baseline_for_game(8, 2, full_avg, ytd_avg)
    assert baseline == 200.0


def test_compute_player_par_season_totals():
    facts = [
        _league_row(9, 1, (200, 200, 200, 200)),
        _league_row(9, 2, (200, 200, 200, 200)),
        _fact("Alice", 10, 2, games=(210, 210, 210, 210)),
    ]
    par = compute_player_par(facts, season="Season 10", season_num=10)
    assert par["Alice"] == 40


def test_compute_player_par_career_sums_seasons():
    """All-season PAR equals the sum of per-season PAR on the same fact set."""
    facts = [
        _league_row(9, 1, (200, 200, 200, 200)),
        _league_row(10, 1, (200, 200, 200, 200)),
        _fact("Alice", 10, 2, games=(210, 210, 210, 210)),
        _league_row(11, 1, (200, 200, 200, 200)),
        _fact("Alice", 11, 2, games=(205, 205, 205, 205)),
    ]
    par_all = compute_player_par(facts, season=None)["Alice"]
    par_s10 = compute_player_par(facts, season="Season 10", season_num=10)["Alice"]
    par_s11 = compute_player_par(facts, season="Season 11", season_num=11)["Alice"]
    assert par_all == par_s10 + par_s11


def test_compute_player_par_absent_week_excluded():
    league = [
        _league_row(10, 1, (200, 200, 200, 200)),
        _league_row(10, 2, (200, 200, 200, 200)),
        _league_row(10, 3, (200, 200, 200, 200)),
    ]
    with_absent = league + [
        _fact("Alice", 10, 2, absent=True),
        _fact("Alice", 10, 4, games=(220, 220, 220, 220)),
    ]
    without_absent = league + [
        _fact("Alice", 10, 4, games=(220, 220, 220, 220)),
    ]
    par_with = compute_player_par(with_absent, season="Season 10", season_num=10)["Alice"]
    par_without = compute_player_par(without_absent, season="Season 10", season_num=10)[
        "Alice"
    ]
    assert par_with == par_without
