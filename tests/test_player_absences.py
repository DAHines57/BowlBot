"""Player absence counts and players page stats toggle."""

from image_generator import build_players_html
from stats.compute import get_all_time_stats, get_player_scores


def _fact(player, week, *, absent=False, games=(200, 200, 200, 200)):
    return {
        "season_number": 9,
        "season_label": "Season 9",
        "week": week,
        "team": "Team A",
        "opponent": "Team B",
        "player_display_name": player,
        "substitute": False,
        "absent": absent,
        "game1": games[0],
        "game2": games[1],
        "game3": games[2],
        "game4": games[3],
        "week_average": sum(games) / len(games),
    }


def test_get_player_scores_counts_absences_per_season():
    facts = [
        _fact("Alice", 1),
        _fact("Alice", 2, absent=True),
        _fact("Alice", 3),
    ]
    data = get_player_scores(facts, season="Season 9", season_num=9)
    assert data["Alice"]["weeks_absent"] == 1
    assert data["Alice"]["weeks_played"] == 2


def test_get_all_time_stats_sums_absences_across_weeks():
    facts = [
        _fact("Alice", 1),
        _fact("Alice", 2, absent=True),
        _fact("Alice", 3, absent=True),
    ]
    stats = get_all_time_stats(facts)
    alice = next(p for p in stats["player_averages"] if p["player"] == "Alice")
    assert alice["absences"] == 2


def test_build_players_html_shows_substitutes_tab():
    html = build_players_html(
        {
            "Alice": {
                "team": "Team A",
                "average": 200.0,
                "highest_game": 220,
                "lowest_game": 180,
                "weeks_played": 10,
                "weeks_absent": 0,
                "std_dev": 10.0,
                "par": 5,
                "weeks_subbed": 1,
            },
        },
        "Season 10",
        subs_data={
            "Jane": {
                "team": "Team B",
                "average": 215.0,
                "highest_game": 230,
                "lowest_game": 200,
                "weeks_subbed": 2,
            },
        },
    )
    assert "players-subs-toggle" in html
    assert 'data-panel="subs"' in html
    assert "sub-badge" in html
    assert "Jane" in html
    subs_panel = html.split('data-panel="subs"')[1].split("</table>")[0]
    assert ">Team<" not in subs_panel


def test_build_players_html_main_view_hides_other_stats():
    html = build_players_html(
        {
            "Alice": {
                "team": "A",
                "average": 200,
                "highest_game": 220,
                "lowest_game": 180,
                "weeks_played": 3,
                "weeks_absent": 1,
                "std_dev": 12.5,
            }
        },
        "Season 9",
    )
    assert "Other stats" in html
    assert "players-stats-toggle" in html
    assert 'data-panel="other"' in html
    assert "Std dev" in html
    assert "Absences" in html
    # Main table header row should not include Absences (only in other panel)
    main_pos = html.index('data-panel="main"')
    other_pos = html.index('data-panel="other"')
    main_chunk = html[main_pos:other_pos]
    assert "Absences" not in main_chunk
    assert "Std dev" not in main_chunk
    other_chunk = html[other_pos:]
    assert "Games" in other_chunk
    assert "Weeks" in main_chunk


def test_build_players_html_absences_column_sorts_as_number():
    html = build_players_html(
        {
            "Alice": {
                "team": "A",
                "average": 200,
                "highest_game": 220,
                "lowest_game": 180,
                "weeks_played": 3,
                "weeks_absent": 0,
                "std_dev": 12.5,
            }
        },
        "Season 9",
    )
    other_pos = html.index('data-panel="other"')
    other_chunk = html[other_pos:]
    assert (
        'data-sort-col="3" data-sort-type="number">'
        '<span class="sort-ind" aria-hidden="true"></span>Games'
    ) in other_chunk
    assert (
        'data-sort-col="7" data-sort-type="number">'
        '<span class="sort-ind" aria-hidden="true"></span>Absences'
    ) in other_chunk


def test_build_players_html_par_help_button_and_dialog():
    html = build_players_html(
        {
            "Alice": {
                "team": "A",
                "average": 200,
                "highest_game": 220,
                "lowest_game": 180,
                "weeks_played": 3,
                "weeks_absent": 0,
                "std_dev": 12.5,
                "par": 42,
            }
        },
        "All Time",
    )
    assert "players-par-help" in html
    assert "What is PAR?" in html
    assert "players-par-dialog" in html
    assert "pins above replacement" in html.lower()
    assert "helpBtn.hidden = !onOther" in html or "helpBtn) helpBtn.hidden" in html
