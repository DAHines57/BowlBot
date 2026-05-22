"""
Generates HTML templates that match the historical PNG card style (purple + amber).
Used by the Flask web app; no browser/screenshot step required.
"""
import itertools
import os
import re
import html as html_module
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union, cast

from stats.compute import sort_teams_by_standings
from placement_bracket import (
    BYE_LOSER,
    SlotWL,
    expected_week2_cross_sets,
    expected_week2_groups,
    expected_week3_groups,
    expected_week3_groups_cross,
    matchups_by_cross_ordered_groups,
    matchups_by_ordered_groups,
    order_matchups_by_labeled_groups,
    prefer_crossover_week2,
    qf_slot_results_in_order,
    sheet_matchup_matches_expected_pair,
    winner_loser_from_matchup,
)


# ---------------------------------------------------------------------------
# Team colors — loaded from PostgreSQL teams.color_hex (db/team_colors.py)
# ---------------------------------------------------------------------------

_REGISTERED_TEAM_COLORS: dict = {}


def register_team_colors(colors: dict) -> None:
    """Called at app startup / after sync to load colors from the database."""
    global _REGISTERED_TEAM_COLORS
    _REGISTERED_TEAM_COLORS = dict(colors)


def _team_color_style(team_name: str) -> str:
    """Return an inline style coloring just the text in the team's color.
    Lightens dark colors so they remain readable on the dark background."""
    if not team_name:
        return ""
    from stats.facts import canonical_team_name

    lookup = canonical_team_name(team_name.strip())
    raw = team_name.strip()
    color = _REGISTERED_TEAM_COLORS.get(lookup) or _REGISTERED_TEAM_COLORS.get(raw)
    if not color:
        return ""
    hex_c = color.lstrip("#")
    r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    # Lighten colors that are too dark to read on the dark image background
    if luminance < 0.4:
        factor = 0.6
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        color = f"#{r:02x}{g:02x}{b:02x}"
    return f"color:{color};font-weight:600;"


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Arial', sans-serif;
    background: #12101a;
    color: #e0e0e0;
    width: 600px;
    padding: 0;
}
.container { padding: 24px; }

/* Header */
.header {
    text-align: center;
    margin-bottom: 20px;
}
.header .title {
    font-size: 26px;
    font-weight: bold;
    color: #ffb86c;
    letter-spacing: 2px;
}
.header .subtitle {
    font-size: 14px;
    color: #888;
    margin-top: 4px;
}

/* Highlights row */
.highlights {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
}
.highlight-card {
    flex: 1;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.highlight-card.high { background: #1a2e1a; border: 1px solid #50fa7b; }
.highlight-card.low  { background: #2e1a1a; border: 1px solid #ff6b81; }
.highlight-card .label {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 8px;
    text-transform: uppercase;
}
.highlight-card.high .label { color: #50fa7b; }
.highlight-card.low  .label { color: #ff6b81; }
.highlight-card .score {
    font-size: 42px;
    font-weight: bold;
    line-height: 1;
}
.highlight-card.high .score { color: #50fa7b; }
.highlight-card.low  .score { color: #ff6b81; }
.highlight-card .player-name {
    font-size: 15px;
    font-weight: bold;
    color: #fff;
    margin-top: 6px;
}
.highlight-card .team-name {
    font-size: 12px;
    color: #888;
    margin-top: 2px;
}

/* Section */
.section { margin-bottom: 20px; }
.section-note {
    font-size: 11px;
    color: #888;
    margin: -6px 0 10px;
    line-height: 1.4;
}
.section-title {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
    color: #888;
    text-transform: uppercase;
    margin-bottom: 10px;
    border-bottom: 1px solid #2a2050;
    padding-bottom: 6px;
}

/* Leaderboard table */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
thead tr { background: #2d1b69; }
thead th {
    padding: 8px 10px;
    text-align: left;
    color: #aaa;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
thead th.right { text-align: right; }
thead th.sortable-th { cursor: pointer; user-select: none; white-space: nowrap; }
thead th.sortable-th:hover { color: #ffb86c; }
thead th.sortable-th .sort-ind {
  display: inline-block; font-size: 9px; margin-left: 4px; min-width: 0.65em; opacity: 0.78;
  vertical-align: middle;
}
thead th.right.sortable-th .sort-ind {
  margin-left: 0;
  margin-right: 4px;
}
tbody tr { border-bottom: 1px solid #2a2050; }
tbody tr:nth-child(even) { background: #1a1730; }
tbody tr.absent { opacity: 0.45; }
tbody td {
    padding: 7px 10px;
    color: #ddd;
}
tbody td.right { text-align: right; }
.rank { color: #555; width: 24px; }
.player-col { font-weight: bold; color: #fff; }
.team-col { color: #888; font-size: 12px; }
.sub-col { color: #888; font-size: 12px; }
.absent-badge {
    display: inline-block;
    background: #2e1a1a;
    color: #ff6b81;
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 1px;
    vertical-align: middle;
    margin-left: 4px;
}

/* League stats */
.stats-grid {
    display: flex;
    gap: 10px;
}
.stat {
    flex: 1;
    background: #1a1730;
    border: 1px solid #2a2050;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
}
.stat .stat-value {
    font-size: 26px;
    font-weight: bold;
    color: #ffb86c;
}
.stat .stat-label {
    font-size: 11px;
    color: #666;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stat { min-width: 0; }
html {
    overflow-x: hidden;
    scrollbar-gutter: stable both-edges;
}
.container {
    width: 100%;
    max-width: 100%;
    margin-left: auto;
    margin-right: auto;
    padding-block: 24px;
    padding-inline: 22px;
}
.highlights,
.stats-grid {
    width: 100%;
}
.table-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    width: 100%;
    max-width: 100%;
    padding-bottom: 2px;
}
.table-scroll table {
    width: max-content;
    min-width: 100%;
}
@media (max-width: 700px) {
    .highlights {
        flex-direction: column;
    }
}
@media (max-width: 520px) {
    .container {
        padding-block: 16px;
        padding-inline: 20px;
    }
    .highlights {
        flex-direction: column;
    }
    .highlight-card .score {
        font-size: 36px;
    }
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }
    .stat {
        flex: none;
        padding: 10px 8px;
    }
    .stat .stat-value {
        font-size: 22px;
    }
    .stat .stat-label {
        font-size: 10px;
        letter-spacing: 0.04em;
    }
    thead th,
    tbody td {
        padding: 6px 8px;
    }
    table {
        font-size: 12px;
    }
}
.week-block {
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid #2a2050;
}
.week-block:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}
.multi-week-head {
    text-align: center;
    margin-bottom: 22px;
    padding: 14px 16px;
    background: #1a1730;
    border-radius: 10px;
    border: 1px solid #2a2050;
}
.multi-week-head .mw-title {
    font-size: 18px;
    font-weight: bold;
    color: #ffb86c;
    letter-spacing: 2px;
}
.multi-week-head .mw-sub {
    font-size: 13px;
    color: #888;
    margin-top: 6px;
}
"""

_WEEK_SUMMARY_DOC = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>{css}</style>
</head>
<body>
<div class="container">
{inner}
</div>
</body>
</html>"""


_SUMMARY_INNER_FR = """  <div class="header">
    <div class="title">🎳 WEEKLY RECAP</div>
    <div class="subtitle">{season} &nbsp;·&nbsp; Week {week}</div>
  </div>

  {league_summary_blocks}

  <div class="section">
    <div class="section-title">Leaderboard</div>
    <div class="table-scroll">
    <table class="sortable-table" data-has-rank-col="1">
      <thead>
        <tr>
          <th class="right sortable-th" data-sort-col="0" data-sort-type="number"><span class="sort-ind" aria-hidden="true"></span>#</th>
          <th class="sortable-th" data-sort-col="1" data-sort-type="string">Player<span class="sort-ind" aria-hidden="true"></span></th>
          <th class="sortable-th" data-sort-col="2" data-sort-type="string">Team<span class="sort-ind" aria-hidden="true"></span></th>
          <th class="right sortable-th" data-sort-col="3" data-sort-type="number"><span class="sort-ind" aria-hidden="true"></span>Wk Avg</th>
          <th class="right sortable-th" data-sort-col="4" data-sort-type="number"><span class="sort-ind" aria-hidden="true"></span>High</th>
          <th class="right sortable-th" data-sort-col="5" data-sort-type="number"><span class="sort-ind" aria-hidden="true"></span>Low</th>
        </tr>
      </thead>
      <tbody>
        {player_rows}
      </tbody>
    </table>
    </div>
  </div>
"""


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) > 1:
        return f"{parts[0]} {parts[-1][0]}."
    return full_name


def _highlight_game_context_html(game: dict) -> str:
    """Season and/or week line for high/low game cards."""
    season = game.get("season")
    week = game.get("week")
    if week is None:
        return ""
    try:
        week_n = int(week)
    except (TypeError, ValueError):
        return ""
    if week_n <= 0:
        return ""
    if season:
        label = f"{html_module.escape(str(season))} · Week {week_n}"
    else:
        label = f"Week {week_n}"
    return f'<div class="game-context">{label}</div>'


def _build_league_summary_blocks(data: dict) -> str:
    """High/low game cards and league stats row (weekly summary style)."""
    high = data.get("high_game") or {}
    low = data.get("low_game") or {}
    high_score = high.get("score", "—")
    low_score = low.get("score", "—")
    high_player = (
        _short_name(high.get("player", "—")) if high.get("player") else "—"
    )
    low_player = (
        _short_name(low.get("player", "—")) if low.get("player") else "—"
    )
    high_team = high.get("team", "") or ""
    low_team = low.get("team", "") or ""
    league_avg = data.get("league_avg", "—")
    return f"""
  <div class="highlights">
    <div class="highlight-card high">
      <div class="label">🏆 High Game</div>
      <div class="score">{high_score}</div>
      <div class="player-name">{html_module.escape(high_player)}</div>
      <div class="team-name"><span style="{_team_color_style(high_team)}">{html_module.escape(high_team)}</span></div>
      {_highlight_game_context_html(high)}
    </div>
    <div class="highlight-card low">
      <div class="label">📉 Low Game</div>
      <div class="score">{low_score}</div>
      <div class="player-name">{html_module.escape(low_player)}</div>
      <div class="team-name"><span style="{_team_color_style(low_team)}">{html_module.escape(low_team)}</span></div>
      {_highlight_game_context_html(low)}
    </div>
  </div>

  <div class="section">
    <div class="section-title">League Stats</div>
    <div class="stats-grid">
      <div class="stat">
        <div class="stat-value">{league_avg}</div>
        <div class="stat-label">League Avg</div>
      </div>
      <div class="stat">
        <div class="stat-value">{data.get("total_players", 0)}</div>
        <div class="stat-label">Players</div>
      </div>
      <div class="stat">
        <div class="stat-value">{data.get("games_200_plus", 0)}</div>
        <div class="stat-label">200+ Games</div>
      </div>
      <div class="stat">
        <div class="stat-value">{data.get("total_games", 0)}</div>
        <div class="stat-label">Total Games</div>
      </div>
    </div>
  </div>"""


def _week_summary_player_rows(data: dict) -> str:
    rows = []
    rank = 0
    for p in data.get("players", []):
        absent = p.get("absent", False)
        if not absent:
            rank += 1
            rank_str = str(rank)
        else:
            rank_str = "—"

        absent_badge = '<span class="absent-badge">ABSENT</span>' if absent else ""
        row_class = 'class="absent"' if absent else ""
        avg_str = f"{p['avg']:.1f}" if p["avg"] else "—"
        high_str = str(p["high"]) if p["high"] else "—"
        low_str = str(p["low"]) if p.get("low") else "—"

        team_style = _team_color_style(p["team"])
        rank_sort = rank if not absent else 99999
        avg_sort = p["avg"] if p.get("avg") else -1
        high_sort = p["high"] if p.get("high") else -1
        low_sort = p["low"] if p.get("low") else -1
        orig_rank = (
            f' data-orig-rank="{html_module.escape(rank_str, quote=True)}"'
            if not absent
            else ""
        )
        rows.append(f"""
        <tr {row_class}>
          <td class="right rank" data-sort="{rank_sort}"{orig_rank}>{rank_str}</td>
          <td class="player-col" data-sort="{html_module.escape(p["name"].lower(), quote=True)}">{_short_name(p['name'])}{absent_badge}</td>
          <td class="team-col" data-sort="{html_module.escape(p["team"].lower(), quote=True)}" style="{team_style}">{p['team']}</td>
          <td class="right" data-sort="{avg_sort}">{avg_str}</td>
          <td class="right" data-sort="{high_sort}">{high_str}</td>
          <td class="right sub-col" data-sort="{low_sort}">{low_str}</td>
        </tr>""")
    return "".join(rows)


def _build_week_summary_inner(data: dict) -> str:
    return _SUMMARY_INNER_FR.format(
        season=data.get("season", ""),
        week=data.get("week", ""),
        league_summary_blocks=_build_league_summary_blocks(data),
        player_rows=_week_summary_player_rows(data),
    )


def _week_summary_page_html(inner: str) -> str:
    """Weekly recap document with client-side table sorting."""
    doc = _WEEK_SUMMARY_DOC.format(css=_CSS, inner=inner)
    return doc.replace("</body>", _LIST_SORT_SCRIPT + "\n</body>", 1)


def build_html(data: dict) -> str:
    """Build the weekly summary HTML string from week summary data."""
    return _week_summary_page_html(_build_week_summary_inner(data))


def build_all_weeks_summary_html(season_display: str, week_data: list[dict]) -> str:
    """Stacked weekly recaps for every week in ``week_data`` (non-empty only)."""
    import html as html_module

    blocks = []
    for d in week_data:
        if d.get("players"):
            blocks.append(f'<div class="week-block">\n{_build_week_summary_inner(d)}\n</div>')
    banner = (
        f'<div class="multi-week-head">'
        f'<div class="mw-title">ALL WEEKS</div>'
        f'<div class="mw-sub">{html_module.escape(season_display)}</div>'
        f"</div>"
    )
    return _week_summary_page_html(banner + "\n" + "\n".join(blocks))


_MATCHUPS_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Arial', sans-serif;
    background: #12101a;
    color: #e0e0e0;
    width: 600px;
}
.container { padding: 24px; }
.header { text-align: center; margin-bottom: 20px; }
.header .title { font-size: 26px; font-weight: bold; color: #ffb86c; letter-spacing: 2px; }
.header .subtitle { font-size: 14px; color: #888; margin-top: 4px; }
.section-title {
    font-size: 11px; font-weight: bold; letter-spacing: 2px; color: #888;
    text-transform: uppercase; margin-bottom: 12px;
    border-bottom: 1px solid #2a2050; padding-bottom: 6px;
}
.matchup-card {
    background: #1a1730;
    border: 1px solid #2a2050;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.matchup-top {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.team-side { flex: 1; }
.team-side.away { text-align: right; }
.team-name { font-size: 14px; font-weight: bold; color: #fff; }
.team-stats { font-size: 12px; color: #888; margin-top: 3px; }
.team-stats .pins { color: #ccc; }
.vs-col { text-align: center; min-width: 60px; }
.vs-label { font-size: 11px; color: #555; margin-bottom: 4px; }
.results { display: flex; gap: 6px; justify-content: center; }
.badge {
    width: 28px; height: 28px; border-radius: 6px;
    font-size: 13px; font-weight: bold; line-height: 28px; text-align: center;
}
.badge.W { background: #1a2e1a; color: #50fa7b; border: 1px solid #50fa7b; }
.badge.L { background: #2e1a1a; color: #ff6b81; border: 1px solid #ff6b81; }
.badge.T { background: #2a2010; color: #ffb86c; border: 1px solid #ffb86c; }
.badge.none { background: #1e1a2e; color: #555; border: 1px solid #2a2050; }
/* Per-game breakdown */
.games-row {
    display: flex;
    gap: 6px;
    border-top: 1px solid #2a2050;
    padding-top: 8px;
}
.game-cell {
    flex: 1;
    text-align: center;
    background: #1e1a2e;
    border-radius: 6px;
    padding: 5px 4px;
}
.game-label { font-size: 9px; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.game-score { font-size: 12px; color: #aaa; margin: 2px 0; }
.game-score.winner { color: #fff; font-weight: bold; }
.game-result { font-size: 9px; font-weight: bold; }
.game-result.W { color: #50fa7b; }
.game-result.L { color: #ff6b81; }
.game-result.T { color: #ffb86c; }
.week-block {
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid #2a2050;
}
.week-block:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}
.multi-week-head {
    text-align: center;
    margin-bottom: 22px;
    padding: 14px 16px;
    background: #1a1730;
    border-radius: 10px;
    border: 1px solid #2a2050;
}
.multi-week-head .mw-title {
    font-size: 18px;
    font-weight: bold;
    color: #ffb86c;
    letter-spacing: 2px;
}
.multi-week-head .mw-sub {
    font-size: 13px;
    color: #888;
    margin-top: 6px;
}
.pw-week-head {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #c9a86a;
    margin-bottom: 10px;
}
.matchup-player-details {
    margin-top: 8px;
    border-top: 1px solid #2a2050;
    padding-top: 6px;
}
.matchup-player-details summary {
    cursor: pointer;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #9cbcff;
    list-style: none;
    user-select: none;
}
.matchup-player-details summary::-webkit-details-marker { display: none; }
.matchup-player-details[open] summary { margin-bottom: 10px; color: #c4d4ff; }
.player-scores-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    width: 100%;
    max-width: 100%;
    padding-bottom: 4px;
    margin: 0 -2px;
}
.player-scores-grid {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    width: max-content;
    min-width: 100%;
}
.player-side { flex: 0 0 auto; }
.player-team-label {
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #666;
    margin-bottom: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.player-side--away .player-team-label { text-align: right; }
.player-score-table {
    width: max-content;
    border-collapse: collapse;
    table-layout: auto;
    font-size: 11px;
}
.player-score-table th,
.player-score-table td {
    padding: 3px 2px;
    vertical-align: middle;
}
.player-score-table th.pst-g,
.player-score-table td.pst-g {
    width: 2.15rem;
    text-align: center;
    font-variant-numeric: tabular-nums;
}
.player-score-table thead th.pst-g {
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 0.06em;
    color: #555;
    text-transform: uppercase;
    padding-bottom: 5px;
}
.player-score-table td.pst-name {
    color: #ccc;
    white-space: nowrap;
    padding-right: 6px;
    padding-left: 6px;
}
.player-score-table--home td.pst-name,
.player-score-table--home th.pst-name { padding-left: 0; }
.player-score-table--away td.pst-name,
.player-score-table--away th.pst-name { padding-right: 0; }
.player-score-table--home td.pst-name,
.player-score-table--home th.pst-name { text-align: left; }
.player-score-table--away td.pst-name,
.player-score-table--away th.pst-name { text-align: right; }
.player-score-table--home th.pst-name,
.player-score-table--home td.pst-name { width: auto; }
.player-score-table--away th.pst-name,
.player-score-table--away td.pst-name { width: auto; }
.pst-score {
    display: inline-block;
    min-width: 2rem;
    text-align: center;
    background: #1e1a2e;
    border-radius: 4px;
    padding: 2px 4px;
    color: #bbb;
}
.pst-score--empty { color: #444; background: transparent; }
.pst-score--miss { color: #ff6b81; }
.player-tag {
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 0.05em;
    color: #ff6b81;
    margin-right: 4px;
    vertical-align: middle;
}
.player-side-empty { font-size: 12px; color: #444; padding: 8px 0; }
"""

_MATCHUPS_DOC = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>{css}</style></head>
<body>
<div class="container">
{inner}
</div>
</body>
</html>"""


def _matchup_winner_summary_html(m: dict) -> str:
    """Bold one-line 'Who won' for bracket view."""
    home = m["home"]
    away = m.get("away")
    hn, hstyle = html_module.escape(home["name"]), _team_color_style(home["name"])
    if not away:
        return (
            f'<div class="bracket-outcome bracket-outcome--bye">'
            f'<span class="bracket-outcome-main" style="{hstyle}">{hn}</span> advances'
            f"</div>"
        )
    an, astyle = html_module.escape(away["name"]), _team_color_style(away["name"])
    hr, ar = home.get("result", ""), away.get("result", "")
    if hr == "W" and ar == "L":
        main = f'<span class="bracket-outcome-main" style="{hstyle}">{hn}</span>'
        sub = f'<span class="bracket-outcome-sub">def. <span style="{astyle}">{an}</span></span>'
    elif ar == "W" and hr == "L":
        main = f'<span class="bracket-outcome-main" style="{astyle}">{an}</span>'
        sub = f'<span class="bracket-outcome-sub">def. <span style="{hstyle}">{hn}</span></span>'
    elif hr == "T" and ar == "T":
        return (
            f'<div class="bracket-outcome bracket-outcome--tie">'
            f"Tie: <span style=\"{hstyle}\">{hn}</span> &nbsp;·&nbsp; <span style=\"{astyle}\">{an}</span>"
            f"</div>"
        )
    else:
        return (
            f'<div class="bracket-outcome bracket-outcome--pending">'
            f"<span style=\"{hstyle}\">{hn}</span> vs <span style=\"{astyle}\">{an}</span>"
            f"</div>"
        )
    return f'<div class="bracket-outcome">{main} {sub}</div>'


def _matchup_player_name_html(p: dict, *, away: bool) -> str:
    """Short display name; away-side absent tag sits left of the name."""
    name = html_module.escape(_short_name(str(p.get("name", ""))))
    tag = '<span class="player-tag">ABS</span>' if p.get("absent") else ""
    if away:
        return f"{tag}{' ' if tag else ''}{name}"
    return f"{name}{' ' if tag else ''}{tag}"


def _matchup_game_cells_html(
    games: list, num_games: int, game_absent: Optional[list] = None
) -> str:
    flags = game_absent or []
    cells = []
    for i in range(num_games):
        val = games[i] if i < len(games) else None
        if val is None:
            cells.append('<td class="pst-g"><span class="pst-score pst-score--empty">—</span></td>')
        else:
            miss = i < len(flags) and bool(flags[i])
            score_cls = "pst-score pst-score--miss" if miss else "pst-score"
            cells.append(
                f'<td class="pst-g"><span class="{score_cls}">{int(val):,}</span></td>'
            )
    return "".join(cells)


def _matchup_player_table_html(players: list, num_games: int, *, away: bool) -> str:
    if not players:
        return ""
    g_hdrs = "".join(f'<th class="pst-g">G{i + 1}</th>' for i in range(num_games))
    if away:
        thead = f"<thead><tr>{g_hdrs}<th class=\"pst-name\"></th></tr></thead>"
    else:
        thead = f"<thead><tr><th class=\"pst-name\"></th>{g_hdrs}</tr></thead>"
    body_rows = []
    for p in players:
        games = p.get("games") or []
        name_td = f'<td class="pst-name">{_matchup_player_name_html(p, away=away)}</td>'
        game_tds = _matchup_game_cells_html(games, num_games, p.get("game_absent"))
        if away:
            body_rows.append(f"<tr>{game_tds}{name_td}</tr>")
        else:
            body_rows.append(f"<tr>{name_td}{game_tds}</tr>")
    cls = "player-score-table--away" if away else "player-score-table--home"
    return (
        f'<table class="player-score-table {cls}">'
        f"{thead}<tbody>{''.join(body_rows)}</tbody></table>"
    )


def _matchup_player_details_html(
    home: dict, away: Optional[dict], num_games: int
) -> str:
    """Expandable per-bowler G1–Gn for weekly results (not bracket embed)."""
    home_players = home.get("players") or []
    away_players = (away or {}).get("players") or []
    if not home_players and not away_players:
        return ""

    num_games = max(1, min(int(num_games or 4), 5))

    def _side_block(side: dict, *, away: bool) -> str:
        label = html_module.escape(str(side.get("name", "")))
        table = _matchup_player_table_html(side.get("players") or [], num_games, away=away)
        if not table:
            table = '<div class="player-side-empty">No roster</div>'
        side_cls = "player-side player-side--away" if away else "player-side"
        return (
            f'<div class="{side_cls}">'
            f'<div class="player-team-label">{label}</div>'
            f"{table}"
            f"</div>"
        )

    away_side = away if away else {"name": "—", "players": away_players}
    inner = (
        f'<div class="player-scores-scroll">'
        f'<div class="player-scores-grid">'
        f"{_side_block(home, away=False)}"
        f"{_side_block(away_side, away=True)}"
        f"</div></div>"
    )
    return (
        '<details class="matchup-player-details">'
        '<summary>Player scores</summary>'
        f"{inner}"
        "</details>"
    )



def _build_matchup_card_list(data: dict, *, for_bracket: bool = False) -> str:
    """HTML for matchup cards only (no page header); used by bracket and weekly results."""
    cards = []
    for m in data.get("matchups", []):
        home = m["home"]
        away = m.get("away")
        game_results = m.get("game_results", [])

        h_res = home["result"]
        h_badge = f'<div class="badge {h_res}">{h_res}</div>'

        h_color = _team_color_style(home["name"])
        if away:
            a_res = away["result"]
            a_badge = f'<div class="badge {a_res}">{a_res}</div>'
            a_color = _team_color_style(away["name"])
            away_html = f"""
              <div class="team-side away">
                <div class="team-name" style="{a_color}">{away['name']}</div>
                <div class="team-stats">
                  <span class="pins">{away['pins']:,} pins</span> &nbsp;·&nbsp; {away['avg']} avg
                  &nbsp;·&nbsp; {away['wins']}W
                </div>
              </div>"""
        else:
            a_badge = '<div class="badge none">—</div>'
            away_html = '<div class="team-side away"><div class="team-name">—</div></div>'

        game_cells = ""
        for i, (h_r, a_r, h_p, a_p) in enumerate(game_results):
            h_class = "winner" if h_r == "W" else ""
            a_class = "winner" if a_r == "W" else ""
            game_cells += f"""
            <div class="game-cell">
              <div class="game-label">G{i+1}</div>
              <div class="game-score {h_class}">{h_p:,}</div>
              <div class="game-result {h_r}">{h_r}</div>
              <div class="game-result {a_r}" style="color:#555">—</div>
              <div class="game-score {a_class}">{a_p:,}</div>
            </div>"""

        games_row = f'<div class="games-row">{game_cells}</div>' if game_cells else ""

        player_details = ""
        if not for_bracket:
            n_games = len(game_results) if game_results else max(
                len(home.get("game_pins") or []),
                len((away or {}).get("game_pins") or []),
                4,
            )
            player_details = _matchup_player_details_html(home, away, n_games)

        headline = _matchup_winner_summary_html(m) if for_bracket else ""
        if for_bracket and games_row:
            games_row = (
                '<details class="bracket-game-details">'
                '<summary class="bracket-game-summary">Game-by-game pins</summary>'
                f"{games_row}"
                "</details>"
            )

        bracket_cls = " matchup-card--bracket" if for_bracket else ""
        cards.append(f"""
    <div class="matchup-card bracket-embed-card{bracket_cls}">
      {headline}
      <div class="matchup-top">
        <div class="team-side">
          <div class="team-name" style="{h_color}">{home['name']}</div>
          <div class="team-stats">
            <span class="pins">{home['pins']:,} pins</span> &nbsp;·&nbsp; {home['avg']} avg
            &nbsp;·&nbsp; {home['wins']}W
          </div>
        </div>
        <div class="vs-col">
          <div class="vs-label">vs</div>
          <div class="results">{h_badge}{a_badge}</div>
        </div>
        {away_html}
      </div>
      {games_row}
      {player_details}
    </div>""")

    return "".join(cards)


def _build_matchups_cards(data: dict) -> str:
    header = f"""  <div class="header">
    <div class="title">🎳 WEEKLY RESULTS</div>
    <div class="subtitle">{data.get("season", "")} &nbsp;·&nbsp; Week {data.get("week", "")}</div>
  </div>
  <div class="section-title">Matchups</div>
"""
    return header + _build_matchup_card_list(data)


def build_matchups_html(data: dict) -> str:
    """Build the weekly matchup results HTML."""
    return _MATCHUPS_DOC.format(css=_MATCHUPS_CSS, inner=_build_matchups_cards(data))


def _multi_week_cards_inner_html(
    banner_title: str, season_display: str, week_data: list[dict]
) -> str:
    """Inner HTML for stacked week matchup cards (no document wrapper)."""
    blocks: List[str] = []
    for d in week_data:
        if not d.get("matchups"):
            continue
        wk = d.get("week", "")
        head = ""
        if wk != "" and wk is not None:
            head = (
                f'<div class="pw-week-head">Week {html_module.escape(str(wk))}</div>'
            )
        blocks.append(f'<div class="week-block">{head}\n{_build_matchups_cards(d)}\n</div>')
    banner = (
        f'<div class="multi-week-head">'
        f'<div class="mw-title">{html_module.escape(banner_title)}</div>'
        f'<div class="mw-sub">{html_module.escape(season_display)}</div>'
        f"</div>"
    )
    return banner + "\n" + "\n".join(blocks)


def _playoff_week_cards_inner_html(season_display: str, week_data: list[dict]) -> str:
    return _multi_week_cards_inner_html("PLAYOFF WEEKS", season_display, week_data)


def build_all_weeks_matchups_html(season_display: str, week_data: list[dict]) -> str:
    return _MATCHUPS_DOC.format(
        css=_MATCHUPS_CSS,
        inner=_multi_week_cards_inner_html("ALL WEEKS — RESULTS", season_display, week_data),
    )


_LIST_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: Arial, sans-serif; background: #12101a; color: #e0e0e0; width: 600px; }
.container { padding: 24px; }
.header { text-align: center; margin-bottom: 20px; }
.header .title { font-size: 26px; font-weight: bold; color: #ffb86c; letter-spacing: 2px; }
.header .subtitle { font-size: 14px; color: #888; margin-top: 4px; }
.section { margin-bottom: 20px; }
.section-title {
    font-size: 11px; font-weight: bold; letter-spacing: 2px; color: #888;
    text-transform: uppercase; margin-bottom: 10px;
    border-bottom: 1px solid #2a2050; padding-bottom: 6px;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead tr { background: #2d1b69; }
thead th { padding: 8px 10px; text-align: left; color: #aaa; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
thead th.right { text-align: right; }
thead th.sortable-th { cursor: pointer; user-select: none; white-space: nowrap; }
thead th.sortable-th:hover { color: #ffb86c; }
thead th.sortable-th .sort-ind {
  display: inline-block; font-size: 9px; margin-left: 4px; min-width: 0.65em; opacity: 0.78;
  vertical-align: middle;
}
thead th.right.sortable-th .sort-ind {
  margin-left: 0;
  margin-right: 4px;
}
tbody tr { border-bottom: 1px solid #2a2050; }
tbody tr:nth-child(even) { background: #1a1730; }
tbody td { padding: 7px 10px; color: #ddd; }
tbody td.right { text-align: right; }
.rank { color: #555; }
.name-col { font-weight: bold; color: #fff; }
.sub-col { color: #888; font-size: 12px; }
.gold { color: #ffb86c; font-weight: bold; }
.green { color: #50fa7b; }
.record { font-weight: bold; color: #fff; }
.standings-champion {
    margin-right: 0.2em;
    filter: drop-shadow(0 0 4px rgba(255, 184, 108, 0.45));
}
html {
    overflow-x: hidden;
    scrollbar-gutter: stable both-edges;
}
.container {
    width: 100%;
    max-width: 100%;
    margin-left: auto;
    margin-right: auto;
    padding-block: 24px;
    padding-inline: 22px;
}
.table-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    width: 100%;
    max-width: 100%;
    padding-bottom: 2px;
}
.table-scroll table {
    width: max-content;
    min-width: 100%;
}
@media (max-width: 520px) {
    .container {
        padding-block: 16px;
        padding-inline: 20px;
    }
    thead th,
    tbody td {
        padding: 6px 8px;
    }
    table {
        font-size: 12px;
    }
    thead th {
        font-size: 10px;
        letter-spacing: 0.04em;
    }
    .sub-col {
        font-size: 11px;
    }
}
"""

_HIGHLIGHTS_CSS = """
.highlights {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    width: 100%;
}
.highlight-card {
    flex: 1;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.highlight-card.high { background: #1a2e1a; border: 1px solid #50fa7b; }
.highlight-card.low  { background: #2e1a1a; border: 1px solid #ff6b81; }
.highlight-card .label {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 8px;
    text-transform: uppercase;
}
.highlight-card.high .label { color: #50fa7b; }
.highlight-card.low  .label { color: #ff6b81; }
.highlight-card .score {
    font-size: 42px;
    font-weight: bold;
    line-height: 1;
}
.highlight-card.high .score { color: #50fa7b; }
.highlight-card.low  .score { color: #ff6b81; }
.highlight-card .player-name {
    font-size: 15px;
    font-weight: bold;
    color: #fff;
    margin-top: 6px;
}
.highlight-card .team-name {
    font-size: 12px;
    color: #888;
    margin-top: 2px;
}
.highlight-card .game-context {
    font-size: 11px;
    color: #666;
    margin-top: 4px;
    letter-spacing: 0.02em;
}
.stats-grid {
    display: flex;
    gap: 10px;
    width: 100%;
}
.stat {
    flex: 1;
    min-width: 0;
    background: #1a1730;
    border: 1px solid #2a2050;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
}
.stat .stat-value {
    font-size: 26px;
    font-weight: bold;
    color: #ffb86c;
}
.stat .stat-label {
    font-size: 11px;
    color: #666;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
@media (max-width: 700px) {
    .highlights { flex-direction: column; }
}
@media (max-width: 520px) {
    .highlights { flex-direction: column; }
    .highlight-card .score { font-size: 36px; }
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }
    .stat { flex: none; padding: 10px 8px; }
    .stat .stat-value { font-size: 22px; }
    .stat .stat-label { font-size: 10px; letter-spacing: 0.04em; }
}
"""

_PLAYER_DETAIL_CSS_EXTRA = """
.player-detail-team { font-size: 15px; font-weight: 600; color: #fff; line-height: 1.45; }
.player-stat-rows { border: 1px solid #2a2050; border-radius: 2px; overflow: hidden; }
.player-stat-row {
    display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
    padding: 10px 12px; border-bottom: 1px solid #2a2050; background: #16132a;
}
.player-stat-row:last-child { border-bottom: none; }
.player-stat-row:nth-child(even) { background: #1a1730; }
.player-stat-label {
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: #888; flex-shrink: 0;
}
.player-stat-val { font-size: 15px; font-weight: 700; color: #ddd; text-align: right; }
.player-stat-val--gold { color: #ffb86c; }
.player-stat-val--green { color: #50fa7b; }
.player-stat-val--muted { color: #888; font-weight: 600; }
.player-empty {
    margin: 0; padding: 12px; color: #888; font-size: 13px; line-height: 1.5;
    background: #16132a; border: 1px solid #2a2050; border-radius: 2px;
}
.player-chart-wrap {
    position: relative;
    overflow: visible;
    background: #16132a;
    border: 1px solid #2a2050;
    border-radius: 6px;
    padding: 10px 8px 6px 8px;
}
.player-chart-tip {
    position: absolute;
    z-index: 5;
    pointer-events: none;
    transform: translateY(calc(-100% - 12px));
    min-width: 128px;
    max-width: calc(100% - 16px);
    box-sizing: border-box;
    padding: 9px 12px 10px 12px;
    background: linear-gradient(180deg, #2a2448 0%, #1a1730 100%);
    border: 1px solid #6a5f9e;
    border-radius: 8px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
    text-align: center;
    line-height: 1.35;
}
.player-chart-tip[hidden] { display: none !important; }
.player-chart-tip-score {
    font-size: 1.45rem;
    font-weight: 800;
    color: #ffb86c;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
}
.player-chart-tip-meta {
    margin-top: 3px;
    font-size: 10px;
    color: #9a94b0;
    letter-spacing: 0.03em;
}
.player-chart-tip-vs {
    display: inline-block;
    margin-top: 5px;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.player-chart-tip-vs--up {
    color: #7bf5a8;
    background: rgba(80, 250, 123, 0.14);
    border: 1px solid rgba(80, 250, 123, 0.35);
}
.player-chart-tip-vs--down {
    color: #ff9aaa;
    background: rgba(255, 107, 129, 0.12);
    border: 1px solid rgba(255, 107, 129, 0.32);
}
.player-chart-point { cursor: pointer; }
.player-chart-point:focus { outline: none; }
.player-chart-point:focus-visible .player-chart-dot {
    stroke: #ffb86c;
    stroke-width: 2;
}
.player-chart-point--active .player-chart-dot {
    fill: #7bf5a8;
    stroke: #ffb86c;
    stroke-width: 2;
    transform: scale(1.45);
    transform-box: fill-box;
    transform-origin: center;
}
.player-chart-hit { fill: transparent; stroke: none; pointer-events: all; }
.player-chart-caption {
    margin: 0 0 8px 0;
    font-size: 11px;
    color: #8b849c;
    line-height: 1.4;
}
.player-chart-caption strong { color: #ffb86c; font-weight: 700; }
.player-chart {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
}
.player-chart-grid { stroke: #2a2445; stroke-width: 1; }
.player-chart-axis { fill: #6d6785; font-size: 9px; font-family: inherit; }
.player-chart-line { fill: none; stroke: #ffb86c; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.player-chart-avg {
    stroke: #7c6ec4; stroke-width: 1.25; stroke-dasharray: 5 4; opacity: 0.9;
}
.player-chart-league-avg {
    stroke: #6ec4e8; stroke-width: 1.25; stroke-dasharray: 3 4; opacity: 0.85;
}
.player-chart-dot { fill: #50fa7b; stroke: #0d0c14; stroke-width: 1; pointer-events: none; }
"""

_PLAYER_CHART_TIP_SCRIPT = r"""<script>
(function () {
  document.querySelectorAll("[data-player-chart]").forEach(function (wrap) {
    var tip = wrap.querySelector(".player-chart-tip");
    var avg = parseFloat(wrap.getAttribute("data-chart-avg") || "0");
    if (!tip) return;
    var active = null;

    function hide() {
      tip.setAttribute("hidden", "");
      if (active) active.classList.remove("player-chart-point--active");
      active = null;
    }

    function place(g) {
      var wr = wrap.getBoundingClientRect();
      var gr = g.getBoundingClientRect();
      var cx = gr.left - wr.left + gr.width / 2;
      var top = gr.top - wr.top;
      var pad = 8;
      tip.style.top = top + "px";
      tip.style.transform = "translateY(calc(-100% - 12px))";
      var maxW = Math.max(128, wr.width - pad * 2);
      tip.style.maxWidth = maxW + "px";
      var tipW = tip.offsetWidth;
      var left = cx - tipW / 2;
      if (left < pad) {
        left = pad;
      }
      if (left + tipW > wr.width - pad) {
        left = Math.max(pad, wr.width - pad - tipW);
      }
      tip.style.left = left + "px";
    }

    function show(g) {
      var score = parseInt(g.getAttribute("data-score"), 10);
      if (isNaN(score)) return;
      if (active) active.classList.remove("player-chart-point--active");
      active = g;
      g.classList.add("player-chart-point--active");
      var vs = score - avg;
      var vsStr = (vs >= 0 ? "+" : "") + vs.toFixed(1) + " vs avg";
      var vsCls =
        vs >= 0 ? "player-chart-tip-vs--up" : "player-chart-tip-vs--down";
      var season = g.getAttribute("data-season") || "";
      var week = g.getAttribute("data-week") || "";
      var game = g.getAttribute("data-game") || "";
      var idx = g.getAttribute("data-index") || "";
      tip.innerHTML =
        '<div class="player-chart-tip-score">' +
        score +
        "</div>" +
        '<div class="player-chart-tip-meta">' +
        (season ? season + " \u00b7 " : "") +
        "Week " +
        week +
        " \u00b7 Game " +
        game +
        (idx ? " \u00b7 #" + idx : "") +
        "</div>" +
        '<span class="player-chart-tip-vs ' +
        vsCls +
        '">' +
        vsStr +
        "</span>";
      tip.removeAttribute("hidden");
      place(g);
    }

    wrap.querySelectorAll(".player-chart-point").forEach(function (g) {
      g.addEventListener("mouseenter", function () {
        show(g);
      });
      g.addEventListener("mouseleave", function () {
        hide();
      });
      g.addEventListener("pointerdown", function (e) {
        if (e.pointerType === "touch") show(g);
      });
      g.addEventListener("focusin", function () {
        show(g);
      });
      g.addEventListener("focusout", function (e) {
        if (!g.contains(e.relatedTarget)) hide();
      });
    });

    document.addEventListener(
      "pointerdown",
      function (e) {
        if (!active) return;
        if (wrap.contains(e.target)) return;
        hide();
      },
      true
    );

    wrap.addEventListener(
      "scroll",
      function () {
        if (active) place(active);
      },
      true
    );
    window.addEventListener(
      "resize",
      function () {
        if (active) place(active);
      },
      { passive: true }
    );
  });
})();
</script>"""


_LIST_SORT_SCRIPT = r"""<script>
(function () {
  function cmpRaw(a, b, type) {
    if (type === "number") {
      var an = parseFloat(a), bn = parseFloat(b);
      if (isNaN(an)) { an = 0; }
      if (isNaN(bn)) { bn = 0; }
      if (an !== bn) { return an < bn ? -1 : 1; }
      return 0;
    }
    var as = String(a || "").toLowerCase();
    var bs = String(b || "").toLowerCase();
    if (as < bs) { return -1; }
    if (as > bs) { return 1; }
    return 0;
  }

  function cmpRow(trA, trB, col, types) {
    var type = types[col] || "string";
    var tdA = trA.cells[col];
    var tdB = trB.cells[col];
    var a = tdA ? tdA.getAttribute("data-sort") : "";
    var b = tdB ? tdB.getAttribute("data-sort") : "";
    var c = cmpRaw(a, b, type);
    if (c !== 0) { return c; }
    return parseInt(trA.getAttribute("data-default-index"), 10) - parseInt(trB.getAttribute("data-default-index"), 10);
  }

  function tbodyUnits(tbody) {
    var units = [];
    var i = 0;
    var rows = tbody.rows;
    while (i < rows.length) {
      var tr = rows[i];
      if (
        tr.classList.contains("team-standings-row") &&
        i + 1 < rows.length &&
        rows[i + 1].classList.contains("team-standings-detail")
      ) {
        units.push([tr, rows[i + 1]]);
        i += 2;
      } else {
        units.push([tr]);
        i += 1;
      }
    }
    return units;
  }

  function appendUnits(tbody, units, rankCol) {
    units.forEach(function (unit, idx) {
      unit.forEach(function (tr) { tbody.appendChild(tr); });
      if (rankCol) {
        var r = unit[0].cells[0];
        if (r && r.classList.contains("rank")) {
          r.textContent = String(idx + 1);
        }
      }
    });
  }

  function clearInds(table) {
    table.querySelectorAll("thead th.sortable-th .sort-ind").forEach(function (el) { el.textContent = ""; });
  }

  function applySort(table, col, phase, types, rankCol) {
    var tbody = table.tBodies[0];
    if (!tbody) { return; }
    var units = tbodyUnits(tbody);
    clearInds(table);
    if (phase === 0) {
      units.sort(function (a, b) {
        return (
          parseInt(a[0].getAttribute("data-default-index"), 10) -
          parseInt(b[0].getAttribute("data-default-index"), 10)
        );
      });
      units.forEach(function (unit) {
        unit.forEach(function (tr) { tbody.appendChild(tr); });
        if (rankCol) {
          var r = unit[0].cells[0];
          if (r && r.hasAttribute("data-orig-rank")) {
            r.textContent = r.getAttribute("data-orig-rank");
          }
        }
      });
      return;
    }
    units.sort(function (a, b) {
      var x = cmpRow(a[0], b[0], col, types);
      return phase === 1 ? x : -x;
    });
    appendUnits(tbody, units, rankCol);
    var th = table.querySelector('thead th.sortable-th[data-sort-col="' + col + '"]');
    var ind = th && th.querySelector(".sort-ind");
    if (ind) { ind.textContent = phase === 1 ? "\u25b2" : "\u25bc"; }
  }

  document.querySelectorAll("table.sortable-table").forEach(function (table) {
    var tbody = table.tBodies[0];
    if (!tbody) { return; }
    var types = [];
    table.querySelectorAll("thead th[data-sort-col]").forEach(function (th) {
      types[parseInt(th.getAttribute("data-sort-col"), 10)] = th.getAttribute("data-sort-type") || "string";
    });
    var rankCol = table.getAttribute("data-has-rank-col") === "1";
    tbodyUnits(tbody).forEach(function (unit, i) {
      unit[0].setAttribute("data-default-index", String(i));
    });
    var state = { col: null, phase: 0 };
    table.querySelectorAll("thead th.sortable-th").forEach(function (th) {
      th.setAttribute("tabindex", "0");
      th.setAttribute("role", "button");
      var col = parseInt(th.getAttribute("data-sort-col"), 10);
      function act() {
        if (state.col !== col) {
          state = { col: col, phase: 1 };
        } else {
          state.phase = (state.phase + 1) % 3;
          if (state.phase === 0) { state.col = null; }
        }
        if (state.phase === 0) {
          applySort(table, 0, 0, types, rankCol);
        } else {
          applySort(table, state.col, state.phase, types, rankCol);
        }
      }
      th.addEventListener("click", act);
      th.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          act();
        }
      });
    });
  });
})();
</script>"""

def _bracket_zoom_viewport_html(inner: str) -> str:
    """Wrap bracket markup in a zoom/pan viewport (toolbar + stage)."""
    return (
        '<div class="bracket-zoom-controls" role="toolbar" aria-label="Bracket zoom">'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="out" '
        'title="Zoom out" aria-label="Zoom out">−</button>'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="fit" '
        'title="Zoom to fit" aria-label="Zoom to fit">Fit</button>'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="in" '
        'title="Zoom in" aria-label="Zoom in">+</button>'
        '<span class="bracket-zoom-label" aria-live="polite">—</span>'
        "</div>"
        '<div class="bracket-zoom-viewport">'
        '<div class="bracket-zoom-spacer">'
        f'<div class="bracket-zoom-stage">{inner}</div>'
        "</div></div>"
    )


_BRACKET_PAN_SCRIPT = r"""<script>
(function () {
  var THRESH = 5;
  var ZMIN = 0.2;
  var ZMAX = 2.5;
  var ZSTEP = 1.12;
  var activePopOuter = null;
  var pendingTap = null;

  function matchOuterFrom(el) {
    return el && el.closest ? el.closest(".bracket-cl-outer, .bracket-pair-wrap") : null;
  }

  function clamp(z) {
    return Math.max(ZMIN, Math.min(ZMAX, z));
  }

  function popLayer() {
    var layer = document.getElementById("bracket-pop-layer");
    if (!layer) {
      layer = document.createElement("div");
      layer.id = "bracket-pop-layer";
      document.body.appendChild(layer);
    }
    return layer;
  }

  function viewportSize() {
    var doc = document.documentElement;
    return {
      w: Math.min(window.innerWidth, doc.clientWidth || window.innerWidth),
      h: Math.min(window.innerHeight, doc.clientHeight || window.innerHeight),
    };
  }

  function measurePop(pop) {
    pop.style.position = "fixed";
    pop.style.display = "block";
    pop.style.visibility = "hidden";
    pop.style.left = "0";
    pop.style.top = "0";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.style.maxHeight = "none";
    pop.style.overflowY = "";
    var rect = pop.getBoundingClientRect();
    return {
      w: rect.width || pop.scrollWidth || 280,
      h: rect.height || pop.scrollHeight || 180,
    };
  }

  function layoutFloatedPop(outer, pop) {
    var gap = 8;
    var pad = 10;
    var vp = viewportSize();
    var anchor = outer.getBoundingClientRect();
    var size = measurePop(pop);
    var w = size.w;
    var h = size.h;

    var spaceBelow = vp.h - pad - (anchor.bottom + gap);
    var spaceAbove = anchor.top - gap - pad;
    var placeAbove = spaceBelow < h && spaceAbove >= spaceBelow;
    if (spaceBelow < h && spaceAbove < h) {
      placeAbove = spaceAbove > spaceBelow;
    }

    var left = Math.max(pad, Math.min(anchor.left, vp.w - w - pad));
    var top = placeAbove ? anchor.top - h - gap : anchor.bottom + gap;

    if (placeAbove && top < pad) {
      top = pad;
    }
    if (!placeAbove && top + h > vp.h - pad) {
      top = Math.max(pad, anchor.top - h - gap);
      placeAbove = true;
    }

    pop.style.position = "fixed";
    pop.style.display = "block";
    pop.style.visibility = "visible";
    pop.style.left = left + "px";
    pop.style.top = top + "px";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.classList.toggle("bracket-pop--above", placeAbove);

    var placed = pop.getBoundingClientRect();
    if (placed.bottom > vp.h - pad) {
      top = Math.max(pad, vp.h - pad - placed.height);
      pop.style.top = top + "px";
    }
    if (placed.top < pad) {
      pop.style.top = pad + "px";
    }
    placed = pop.getBoundingClientRect();
    if (placed.height > vp.h - pad * 2) {
      pop.style.maxHeight = vp.h - pad * 2 + "px";
      pop.style.overflowY = "auto";
    } else {
      pop.style.maxHeight = "";
      pop.style.overflowY = "";
    }
  }

  function placePop(outer) {
    var pop = outer._bracketPopEl || outer.querySelector(".bracket-pop");
    if (!pop) return;
    if (outer._bracketPopShown && pop.classList.contains("bracket-pop--floated")) {
      layoutFloatedPop(outer, pop);
      return;
    }
    outer._bracketPopEl = pop;
    pop._bracketPopHome = outer;
    popLayer().appendChild(pop);
    pop.classList.add("bracket-pop--floated");
    layoutFloatedPop(outer, pop);
    outer._bracketPopShown = true;
  }

  function clearPop(outer) {
    if (!outer._bracketPopShown) return;
    var pop = outer._bracketPopEl;
    var home = (pop && pop._bracketPopHome) || outer;
    if (!pop) return;
    pop.classList.remove("bracket-pop--floated");
    pop.classList.remove("bracket-pop--above");
    pop.style.position = "";
    pop.style.left = "";
    pop.style.top = "";
    pop.style.right = "";
    pop.style.bottom = "";
    pop.style.display = "";
    pop.style.visibility = "";
    pop.style.maxHeight = "";
    pop.style.overflowY = "";
    home.appendChild(pop);
    outer._bracketPopShown = false;
    outer._bracketPopEl = null;
    outer.classList.remove("bracket-match--tap-active");
    if (activePopOuter === outer) activePopOuter = null;
  }

  function clearActivePop() {
    if (activePopOuter) clearPop(activePopOuter);
  }

  function togglePopTap(outer) {
    if (activePopOuter === outer) {
      clearActivePop();
      return;
    }
    clearActivePop();
    placePop(outer);
    activePopOuter = outer;
    outer.classList.add("bracket-match--tap-active");
  }

  function viewportInsets(viewport) {
    var cs = window.getComputedStyle(viewport);
    return {
      l: parseFloat(cs.paddingLeft) || 0,
      t: parseFloat(cs.paddingTop) || 0,
      r: parseFloat(cs.paddingRight) || 0,
      b: parseFloat(cs.paddingBottom) || 0,
    };
  }

  function measureNatural(wrap) {
    var stage = wrap.querySelector(".bracket-zoom-stage");
    var spacer = wrap.querySelector(".bracket-zoom-spacer");
    if (!stage) return;
    stage.style.transform = "none";
    if (spacer) {
      spacer.style.width = "";
      spacer.style.height = "";
    }
    var shell = stage.querySelector(".bracket-shell");
    var sel =
      ".bracket-headers-row,.bracket-hcell,.bracket-subsec-h," +
      ".bracket-cl-outer,.bracket-cl-pending,.bracket-pair-wrap";
    var nodes = stage.querySelectorAll(sel);
    var minL = Infinity;
    var minT = Infinity;
    var maxR = -Infinity;
    var maxB = -Infinity;
    for (var i = 0; i < nodes.length; i++) {
      var r = nodes[i].getBoundingClientRect();
      if (r.width < 2 && r.height < 2) continue;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    }
    if (maxR > minL && maxB > minT) {
      wrap._bracketNaturalW = Math.ceil(maxR - minL + 20);
      wrap._bracketNaturalH = Math.ceil(maxB - minT + 20);
      return;
    }
    if (shell) {
      var dw = parseFloat(shell.getAttribute("data-bracket-w"));
      var dh = parseFloat(shell.getAttribute("data-bracket-h"));
      if (dw > 0 && dh > 0) {
        wrap._bracketNaturalW = dw;
        wrap._bracketNaturalH = dh;
        return;
      }
    }
    var w = stage.scrollWidth || stage.offsetWidth;
    var h = stage.scrollHeight || stage.offsetHeight;
    if (w > 0 && h > 0) {
      wrap._bracketNaturalW = w;
      wrap._bracketNaturalH = h;
    }
  }

  function setZoom(wrap, z, opts) {
    opts = opts || {};
    var stage = wrap.querySelector(".bracket-zoom-stage");
    var spacer = wrap.querySelector(".bracket-zoom-spacer");
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    var label = wrap.querySelector(".bracket-zoom-label");
    if (!stage || !spacer || !viewport) return;
    var nw = wrap._bracketNaturalW || stage.offsetWidth;
    var nh = wrap._bracketNaturalH || stage.offsetHeight;
    z = clamp(z);
    wrap._bracketZoom = z;
    stage.style.transform = "scale(" + z + ")";
    spacer.style.width = Math.ceil(nw * z) + "px";
    spacer.style.height = Math.ceil(nh * z) + "px";
    if (label) label.textContent = Math.round(z * 100) + "%";
    if (opts.center) {
      var ins = viewportInsets(viewport);
      var vw = viewport.clientWidth - ins.l - ins.r;
      var vh = viewport.clientHeight - ins.t - ins.b;
      var sl = spacer.offsetWidth;
      var st = spacer.offsetHeight;
      viewport.scrollLeft = sl > vw ? Math.max(0, (sl - vw) / 2) : 0;
      viewport.scrollTop = st > vh ? Math.max(0, (st - vh) / 2) : 0;
    }
  }

  function setZoomAt(wrap, z, clientX, clientY) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;
    var oldZ = wrap._bracketZoom || 1;
    z = clamp(z);
    if (Math.abs(z - oldZ) < 0.0001) return;
    var rect = viewport.getBoundingClientRect();
    var ins = viewportInsets(viewport);
    var localX = clientX - rect.left - ins.l;
    var localY = clientY - rect.top - ins.t;
    var ratio = z / oldZ;
    var sl = viewport.scrollLeft;
    var st = viewport.scrollTop;
    setZoom(wrap, z, { center: false });
    viewport.scrollLeft = (sl + localX) * ratio - localX;
    viewport.scrollTop = (st + localY) * ratio - localY;
  }

  function fitZoom(wrap) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;
    measureNatural(wrap);
    var nw = wrap._bracketNaturalW;
    var nh = wrap._bracketNaturalH;
    if (!nw || !nh) return;
    var ins = viewportInsets(viewport);
    var availW = viewport.clientWidth - ins.l - ins.r;
    var availH = viewport.clientHeight - ins.t - ins.b;
    var z = Math.min(availW / nw, availH / nh);
    if (!isFinite(z) || z <= 0) z = 1;
    wrap._bracketFitMode = true;
    setZoom(wrap, z, { center: true });
  }

  document.querySelectorAll(".bracket-wrap").forEach(function (wrap) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;

    wrap._bracketZoom = 1;
    wrap._bracketFitMode = true;

    wrap.querySelectorAll("[data-zoom-action]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var act = btn.getAttribute("data-zoom-action");
        if (act === "fit") {
          fitZoom(wrap);
          return;
        }
        wrap._bracketFitMode = false;
        var cur = wrap._bracketZoom || 1;
        if (act === "in") setZoom(wrap, cur * ZSTEP, { center: false });
        else if (act === "out") setZoom(wrap, cur / ZSTEP, { center: false });
      });
    });

    function initFit() {
      measureNatural(wrap);
      fitZoom(wrap);
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(initFit);
    });

    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (wrap._bracketFitMode) fitZoom(wrap);
      }, 120);
    });

    var dragging = false;
    var moved = false;
    var startX = 0;
    var startY = 0;
    var scroll0 = 0;
    var scroll0Y = 0;
    var pid = null;
    var pointers = new Map();
    var pinching = false;
    var pinchStartDist = 0;
    var pinchStartZoom = 1;

    function pinchDistance() {
      var pts = Array.from(pointers.values());
      if (pts.length < 2) return 0;
      var dx = pts[1].x - pts[0].x;
      var dy = pts[1].y - pts[0].y;
      return Math.sqrt(dx * dx + dy * dy);
    }

    function pinchCenter() {
      var pts = Array.from(pointers.values());
      return {
        x: (pts[0].x + pts[1].x) / 2,
        y: (pts[0].y + pts[1].y) / 2,
      };
    }

    function beginPinch() {
      pendingTap = null;
      endDrag();
      pinching = true;
      moved = true;
      wrap._bracketFitMode = false;
      pinchStartDist = pinchDistance();
      pinchStartZoom = wrap._bracketZoom || 1;
      wrap.classList.add("bracket-wrap--pinching");
    }

    function endPinch() {
      if (!pinching) return;
      pinching = false;
      pinchStartDist = 0;
      wrap.classList.remove("bracket-wrap--pinching");
    }

    function endDrag() {
      if (!dragging) return;
      dragging = false;
      wrap.classList.remove("bracket-wrap--dragging");
      try {
        if (pid !== null) viewport.releasePointerCapture(pid);
      } catch (e) {}
      pid = null;
    }

    viewport.addEventListener(
      "pointerdown",
      function (e) {
        if (e.target.closest(".bracket-zoom-controls")) return;
        if (e.pointerType === "mouse" && e.button !== 0) return;
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pointers.size >= 2) {
          beginPinch();
          return;
        }
        var match = matchOuterFrom(e.target);
        if (match) {
          pendingTap = {
            outer: match,
            x: e.clientX,
            y: e.clientY,
            pid: e.pointerId,
            wrap: wrap,
            viewport: viewport,
          };
          return;
        }
        clearActivePop();
        dragging = true;
        moved = false;
        startX = e.clientX;
        startY = e.clientY;
        scroll0 = viewport.scrollLeft;
        scroll0Y = viewport.scrollTop;
        pid = e.pointerId;
        wrap.classList.add("bracket-wrap--dragging");
        viewport.setPointerCapture(e.pointerId);
      },
      { passive: true }
    );

    viewport.addEventListener(
      "pointermove",
      function (e) {
        if (pointers.has(e.pointerId)) {
          pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        }
        if (pinching && pointers.size >= 2) {
          var dist = pinchDistance();
          if (pinchStartDist > 8 && dist > 0) {
            var center = pinchCenter();
            setZoomAt(
              wrap,
              pinchStartZoom * (dist / pinchStartDist),
              center.x,
              center.y
            );
          }
          e.preventDefault();
          return;
        }
        if (pendingTap && e.pointerId === pendingTap.pid) {
          var dx0 = e.clientX - pendingTap.x;
          var dy0 = e.clientY - pendingTap.y;
          if (Math.sqrt(dx0 * dx0 + dy0 * dy0) < THRESH) return;
          dragging = true;
          moved = true;
          startX = pendingTap.x;
          startY = pendingTap.y;
          scroll0 = viewport.scrollLeft;
          scroll0Y = viewport.scrollTop;
          pid = e.pointerId;
          pendingTap = null;
          wrap.classList.add("bracket-wrap--dragging");
          try {
            viewport.setPointerCapture(e.pointerId);
          } catch (err) {}
          viewport.scrollLeft = scroll0 - dx0;
          viewport.scrollTop = scroll0Y - dy0;
          e.preventDefault();
          return;
        }
        if (!dragging || e.pointerId !== pid) return;
        var dx = e.clientX - startX;
        var dy = e.clientY - startY;
        if (!moved && Math.sqrt(dx * dx + dy * dy) < THRESH) return;
        moved = true;
        viewport.scrollLeft = scroll0 - dx;
        viewport.scrollTop = scroll0Y - dy;
        e.preventDefault();
      },
      { passive: false }
    );

    function finishPointer(e) {
      var wasPinching = pinching;
      pointers.delete(e.pointerId);
      if (pinching && pointers.size < 2) endPinch();
      if (wasPinching) {
        pendingTap = null;
        endDrag();
        return;
      }
      if (pendingTap && e.pointerId === pendingTap.pid) {
        togglePopTap(pendingTap.outer);
        pendingTap = null;
        return;
      }
      if (dragging) endDrag();
      if (!dragging && !pendingTap && activePopOuter) {
        var pop = activePopOuter._bracketPopEl;
        if (!activePopOuter.contains(e.target) && !(pop && pop.contains(e.target))) {
          clearActivePop();
        }
      }
    }

    viewport.addEventListener("pointerup", finishPointer);
    viewport.addEventListener("pointercancel", function (e) {
      pointers.delete(e.pointerId);
      if (pinching && pointers.size < 2) endPinch();
      pendingTap = null;
      endDrag();
    });
    viewport.addEventListener("lostpointercapture", endDrag);

    viewport.addEventListener(
      "click",
      function (e) {
        if (moved) {
          e.preventDefault();
          e.stopImmediatePropagation();
          moved = false;
        }
      },
      true
    );

    viewport.addEventListener("scroll", function () {
      if (activePopOuter && activePopOuter._bracketPopEl) {
        layoutFloatedPop(activePopOuter, activePopOuter._bracketPopEl);
      }
    });
  });
})();
</script>"""


_LIST_PAGE_HEAD = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>{css}</style></head>
<body{body_attr}><div class="container">
  <div class="header">
    <div class="title">{title}</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  {sections}
</div>"""


def _render_list_page(
    css: str,
    title: str,
    subtitle: str,
    sections: str,
    *,
    extra_script: str = "",
    body_class: str = "",
) -> str:
    """Build list-style document; JS is appended so braces are not interpreted by str.format."""
    body_attr = f' class="{body_class}"' if body_class else ""
    return (
        _LIST_PAGE_HEAD.format(
            css=css,
            title=title,
            subtitle=subtitle,
            sections=sections,
            body_attr=body_attr,
        )
        + _LIST_SORT_SCRIPT
        + extra_script
        + "\n</body></html>"
    )


def _player_game_chart_html(
    points: List[dict],
    *,
    chart_scope: str = "",
    league_avg: Optional[float] = None,
) -> str:
    """SVG line chart of individual game scores (oldest → newest, left to right)."""
    if not points:
        return '<p class="player-empty">No games to chart for this scope.</p>'

    scores = [int(p["score"]) for p in points]
    n = len(scores)
    avg = sum(scores) / n
    league_ref = float(league_avg) if league_avg is not None else 0.0
    show_league = league_ref > 0
    scope_esc = html_module.escape(chart_scope) if chart_scope else ""
    scope_note = f" · {scope_esc}" if scope_esc else ""

    w, h = 420, 200
    ml, mr, mt, mb = 38, 10, 14, 26
    plot_w = w - ml - mr
    plot_h = h - mt - mb

    y_vals = list(scores)
    if show_league:
        y_vals.append(league_ref)
    y_lo = max(0, min(y_vals) - 25)
    y_hi = min(300, max(y_vals) + 25)
    if y_hi - y_lo < 50:
        y_hi = min(300, y_lo + 50)

    def x_at(i: int) -> float:
        if n == 1:
            return ml + plot_w / 2
        return ml + (i / (n - 1)) * plot_w

    def y_at(score: float) -> float:
        span = y_hi - y_lo
        if span <= 0:
            return mt + plot_h / 2
        return mt + plot_h - ((score - y_lo) / span) * plot_h

    y_ticks = [y_lo, int(round(avg)), y_hi]
    grid_lines = []
    for yt in y_ticks:
        gy = y_at(float(yt))
        grid_lines.append(
            f'<line class="player-chart-grid" x1="{ml}" y1="{gy:.1f}" '
            f'x2="{w - mr}" y2="{gy:.1f}"/>'
        )
        grid_lines.append(
            f'<text class="player-chart-axis" x="{ml - 6}" y="{gy + 3:.1f}" '
            f'text-anchor="end">{yt}</text>'
        )

    poly_pts = " ".join(f"{x_at(i):.1f},{y_at(s):.1f}" for i, s in enumerate(scores))
    ay = y_at(avg)
    avg_line = (
        f'<line class="player-chart-avg" x1="{ml}" y1="{ay:.1f}" '
        f'x2="{w - mr}" y2="{ay:.1f}"/>'
    )
    league_line = ""
    if show_league:
        ly = y_at(league_ref)
        league_line = (
            f'<line class="player-chart-league-avg" x1="{ml}" y1="{ly:.1f}" '
            f'x2="{w - mr}" y2="{ly:.1f}"/>'
        )

    dots: List[str] = []
    for i, (pt, score) in enumerate(zip(points, scores)):
        sl = str(pt.get("season_label") or "")
        wk = pt.get("week", "")
        g = pt.get("game", "")
        sl_attr = html_module.escape(sl, quote=True)
        aria = html_module.escape(f"Game {g}, week {wk}, {score} pins")
        cx, cy = x_at(i), y_at(score)
        dots.append(
            f'<g class="player-chart-point" tabindex="0" role="graphics-symbol" '
            f'aria-label="{aria}" data-score="{score}" data-season="{sl_attr}" '
            f'data-week="{wk}" data-game="{g}" data-index="{i + 1}">'
            f'<circle class="player-chart-hit" cx="{cx:.1f}" cy="{cy:.1f}" r="14"/>'
            f'<circle class="player-chart-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5"/>'
            f"</g>"
        )

    x_labels: List[str] = []
    if n >= 1:
        x_labels.append(
            f'<text class="player-chart-axis" x="{x_at(0):.1f}" y="{h - 6}" text-anchor="middle">1</text>'
        )
    if n >= 10:
        x_labels.append(
            f'<text class="player-chart-axis" x="{x_at(9):.1f}" y="{h - 6}" text-anchor="middle">10</text>'
        )
    if n >= 20:
        x_labels.append(
            f'<text class="player-chart-axis" x="{x_at(19):.1f}" y="{h - 6}" text-anchor="middle">20</text>'
        )
    if n >= 2:
        x_labels.append(
            f'<text class="player-chart-axis" x="{x_at(n - 1):.1f}" y="{h - 6}" '
            f'text-anchor="middle">{n}</text>'
        )

    league_note = (
        f' · league avg <strong>{league_ref:.1f}</strong>'
        if show_league
        else ""
    )
    caption = (
        f'<p class="player-chart-caption">Last <strong>{n}</strong> game'
        f'{"s" if n != 1 else ""}{scope_note}'
        f' · player avg <strong>{avg:.1f}</strong>'
        f"{league_note}</p>"
    )
    svg = (
        f'<svg class="player-chart" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Last {n} game scores">'
        + "".join(grid_lines)
        + league_line
        + avg_line
        + f'<polyline class="player-chart-line" points="{poly_pts}"/>'
        + "".join(dots)
        + "".join(x_labels)
        + "</svg>"
    )
    return (
        caption
        + f'<div class="player-chart-wrap" data-player-chart data-chart-avg="{avg:.2f}">'
        + '<div class="player-chart-tip" hidden></div>'
        + svg
        + "</div>"
        + _PLAYER_CHART_TIP_SCRIPT
    )


def build_player_detail_html(
    *,
    page_title: str,
    subtitle: str,
    team: str,
    stats_title: str,
    stat_rows: Optional[List[Tuple[str, str, str]]] = None,
    empty_message: Optional[str] = None,
    game_history: Optional[List[dict]] = None,
    chart_scope: str = "",
    league_avg: Optional[float] = None,
) -> str:
    """Single-player lookup: same header/section styling as list pages (players, teams, leaders)."""
    sub_esc = html_module.escape(subtitle)
    team_esc = html_module.escape(team)
    tstyle = _team_color_style(team)
    team_inner = f'<span style="{tstyle}">{team_esc}</span>'

    stats_body = ""
    if empty_message:
        stats_body = f'<p class="player-empty">{html_module.escape(empty_message)}</p>'
    elif stat_rows:
        parts: List[str] = ['<div class="player-stat-rows">']
        for label, val, mod in stat_rows:
            cls = "player-stat-val"
            if mod == "gold":
                cls += " player-stat-val--gold"
            elif mod == "green":
                cls += " player-stat-val--green"
            elif mod == "muted":
                cls += " player-stat-val--muted"
            parts.append(
                '<div class="player-stat-row">'
                f'<span class="player-stat-label">{html_module.escape(label)}</span>'
                f'<span class="{cls}">{html_module.escape(val)}</span>'
                "</div>"
            )
        parts.append("</div>")
        stats_body = "".join(parts)

    sections = f"""
    <div class="section">
      <div class="section-title">Team</div>
      <div class="player-detail-team">{team_inner}</div>
    </div>
    <div class="section">
      <div class="section-title">{html_module.escape(stats_title)}</div>
      {stats_body}
    </div>
    <div class="section">
      <div class="section-title">Recent games</div>
      {_player_game_chart_html(game_history or [], chart_scope=chart_scope, league_avg=league_avg)}
    </div>
    """
    css = _LIST_CSS + _PLAYER_DETAIL_CSS_EXTRA
    doc = _render_list_page(css=css, title="👤 PLAYER", subtitle=sub_esc, sections=sections)
    title_esc = html_module.escape(page_title)
    doc = doc.replace(
        '<head><meta charset="UTF-8"><style>',
        f'<head><meta charset="UTF-8"><title>{title_esc}</title><style>',
        1,
    )
    return doc


def _header_sort_type(h: dict) -> str:
    if "sort_type" in h:
        return str(h["sort_type"])
    lab = str(h.get("label", "")).strip().lower()
    if lab in (
        "#",
        "seed",
        "wk",
        "avg",
        "high",
        "low",
        "score",
        "games",
        "weeks",
        "total",
        "record",
        "w-l",
        "absences",
    ):
        return "number"
    if any(
        x in lab
        for x in ("avg", "high", "low", "score", "pin", "for", "agn", "std", "absen")
    ):
        return "number"
    return "string"


def _sortable_th_content(label: str, *, right: bool = False, hint: Optional[str] = None) -> str:
    """Header label + sort indicator. Numeric (right) columns put the indicator first so
    right-aligned headers line up with right-aligned values (indicator after label would
    shift the label left)."""
    ind = '<span class="sort-ind" aria-hidden="true"></span>'
    if right:
        body = f"{ind}{label}"
    else:
        body = f"{label}{ind}"
    if hint:
        esc = html_module.escape(hint)
        return f'<span title="{esc}">{body}</span>'
    return body


def _cell_data_sort_value(c: dict) -> str:
    if "sort" in c:
        return str(c["sort"])
    v = c.get("val")
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(float(v))
    if isinstance(v, str):
        s = v.replace(",", "").strip()
        try:
            float(s)
            return s
        except ValueError:
            pass
        return v.strip().lower()
    return str(v).lower()


def _render_sortable_table(headers: List[dict], rows: List[List[dict]]) -> str:
    """Sortable table inside a table-scroll wrapper."""
    rank_track = bool(headers) and str(headers[0].get("label", "")).strip() in ("#", "Seed")
    table_attr = ' class="sortable-table" data-has-rank-col="1"' if rank_track else ' class="sortable-table"'

    th_parts: List[str] = []
    for i, h in enumerate(headers):
        cls_parts: List[str] = []
        if h.get("right"):
            cls_parts.append("right")
        cls_parts.append("sortable-th")
        st = html_module.escape(_header_sort_type(h))
        th_parts.append(
            f'<th class="{" ".join(cls_parts)}" data-sort-col="{i}" data-sort-type="{st}">'
            f'{_sortable_th_content(h["label"], right=bool(h.get("right")), hint=h.get("hint"))}</th>'
        )
    th = "".join(th_parts)

    def _td(c: dict, col_idx: int) -> str:
        style_attr = f' style="{c["style"]}"' if c.get("style") else ""
        sort_raw = _cell_data_sort_value(c)
        esc_sort = html_module.escape(sort_raw, quote=True)
        orig = ""
        if rank_track and col_idx == 0:
            orig = f' data-orig-rank="{html_module.escape(str(c["val"]), quote=True)}"'
        return (
            f'<td class="{c.get("cls", "")}" data-sort="{esc_sort}"{orig}{style_attr}>'
            f'{c["val"]}</td>'
        )

    trs = "".join(
        "<tr>" + "".join(_td(c, j) for j, c in enumerate(row)) + "</tr>" for row in rows
    )
    return (
        f'<div class="table-scroll">'
        f"<table{table_attr}><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"
        f"</div>"
    )


def _section_note(text: str) -> str:
    return f'<p class="section-note">{html_module.escape(text)}</p>'


def _list_section(
    title: str,
    headers: List[dict],
    rows: List[List[dict]],
    *,
    note: Optional[str] = None,
) -> str:
    """Titled table section with client-side sort (asc / desc / default) on headers."""
    note_html = _section_note(note) if note else ""
    return f"""
    <div class="section">
      <div class="section-title">{title}</div>
      {note_html}
      {_render_sortable_table(headers, rows)}
    </div>"""


def _player_games_bowled_count(stats: dict) -> int:
    """Games that count toward player average (excludes book-average slots)."""
    scores = stats.get("scores")
    if scores is not None:
        return len(scores)
    return int(stats.get("games_bowled", 0) or 0)


def _format_roster_score_value(value: float) -> str:
    iv = int(round(value))
    if abs(value - iv) < 0.01:
        return f"{iv:,}"
    return f"{value:.1f}"


_PLAYERS_STATS_TOGGLE_CSS = """
.players-stats-section .section-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px 14px;
    margin-bottom: 10px;
    border-bottom: 1px solid #2a2050;
    padding-bottom: 6px;
}
.players-stats-section .section-head .section-title {
    margin-bottom: 0;
    border-bottom: none;
    padding-bottom: 0;
}
.players-stats-toggle {
    font: inherit;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid #4a4068;
    background: #1e1a32;
    color: #c4b8e8;
    cursor: pointer;
}
.players-stats-toggle:hover {
    border-color: #7c6ec4;
    color: #fff;
}
.players-stats-toggle[aria-pressed="true"] {
    border-color: #7c6ec4;
    background: #2d1b69;
    color: #ffb86c;
}
.players-stats-panel[hidden] { display: none !important; }
.players-stats-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
}
.players-par-help {
    font: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid #3d5a4a;
    background: #1a2e24;
    color: #7bf5a8;
    cursor: pointer;
}
.players-par-help:hover {
    border-color: #50fa7b;
    color: #fff;
}
.players-par-help[hidden] { display: none !important; }
.players-par-dialog {
    margin: auto;
    max-width: min(420px, calc(100vw - 32px));
    padding: 0;
    border: 1px solid #6a5f9e;
    border-radius: 10px;
    background: linear-gradient(180deg, #2a2448 0%, #1a1730 100%);
    color: #ddd;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
}
.players-par-dialog::backdrop {
    background: rgba(8, 6, 14, 0.72);
}
.players-par-dialog-inner {
    padding: 18px 20px 16px;
}
.players-par-dialog h2 {
    margin: 0 0 10px;
    font-size: 15px;
    font-weight: 700;
    color: #ffb86c;
    letter-spacing: 0.04em;
}
.players-par-dialog p {
    margin: 0 0 10px;
    font-size: 13px;
    line-height: 1.55;
    color: #c8c2dc;
}
.players-par-dialog p:last-of-type { margin-bottom: 14px; }
.players-par-dialog-close {
    font: inherit;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 8px 14px;
    border-radius: 6px;
    border: 1px solid #4a4068;
    background: #1e1a32;
    color: #c4b8e8;
    cursor: pointer;
}
.players-par-dialog-close:hover {
    border-color: #7c6ec4;
    color: #fff;
}
"""

_PAR_HELP_DIALOG_BODY = """
        <h2>What is PAR?</h2>
        <p><strong>PAR</strong> (pins above replacement) is a running total of how many pins
        you have scored <em>above</em> the league average for each game you bowled.</p>
        <p>Think of it as &ldquo;extra credit&rdquo; on every game: if you shot 210 and the
        league bar that week was 190, you earned +20 PAR for that game. Miss the bar and
        PAR goes down for that game.</p>
        <p><strong>Early in the season</strong> (weeks 1&ndash;3), we compare your games to
        last season&rsquo;s league average&mdash;a fair baseline before this year&rsquo;s
        averages settle in.</p>
        <p><strong>From week 4 on</strong>, each game is compared to this season&rsquo;s
        average through that week (year-to-date), so the bar moves with how the league is
        bowling right now.</p>
        <p>Your PAR total adds up every game that way across your career. Higher PAR means
        you have consistently outscored the league over time.</p>
        <p><strong>PAR/G</strong> is your total PAR divided by games bowled&mdash;a per-game rate
        so you can compare players who have bowled different amounts.</p>
        <p>Sort by <strong>PAR</strong>, <strong>PAR/G</strong>, and <strong>games</strong> to see
        volume vs efficiency.</p>
"""

_PLAYERS_STATS_TOGGLE_SCRIPT = (
    "<script>\n"
    "(function () {\n"
    '  document.querySelectorAll(".players-stats-section").forEach(function (sec) {\n'
    '    var btn = sec.querySelector(".players-stats-toggle");\n'
    '    var helpBtn = sec.querySelector(".players-par-help");\n'
    '    var dialog = sec.querySelector(".players-par-dialog");\n'
    '    var main = sec.querySelector(\'[data-panel="main"]\');\n'
    '    var other = sec.querySelector(\'[data-panel="other"]\');\n'
    "    if (!btn || !main || !other) return;\n"
    "    function setView(onOther) {\n"
    "      other.hidden = !onOther;\n"
    "      main.hidden = onOther;\n"
    '      btn.setAttribute("aria-pressed", onOther ? "true" : "false");\n'
    '      btn.textContent = onOther ? "Main stats" : "Other stats";\n'
    "      if (helpBtn) helpBtn.hidden = !onOther;\n"
    "      if (dialog && dialog.open && !onOther) dialog.close();\n"
    "    }\n"
    '    btn.addEventListener("click", function () {\n'
    "      setView(other.hidden);\n"
    "    });\n"
    "    if (helpBtn && dialog) {\n"
    '      helpBtn.addEventListener("click", function () {\n'
    "        if (typeof dialog.showModal === \"function\") dialog.showModal();\n"
    "      });\n"
    '      dialog.querySelector(".players-par-dialog-close").addEventListener("click", function () {\n'
    "        dialog.close();\n"
    "      });\n"
    "    }\n"
    "  });\n"
    "})();\n"
    "</script>"
)


def _player_identity_cells(i: int, name: str, team: str) -> List[dict]:
    return [
        {"val": i, "cls": "right rank"},
        {"val": _short_name(name), "cls": "name-col", "sort": name.lower()},
        {
            "val": team,
            "cls": "sub-col",
            "style": _team_color_style(team),
            "sort": team.lower(),
        },
    ]


def _format_par(value: int) -> str:
    n = int(value)
    if n > 0:
        return f"+{n}"
    return str(n)


def _player_par_game_count(stats: dict, all_time: bool) -> int:
    """Games counted in PAR (same pool as cumulative PAR)."""
    if all_time:
        return int(stats.get("weeks_played", 0))
    scores = stats.get("scores")
    if scores is not None:
        return len(scores)
    return int(stats.get("games_played", 0) or stats.get("games", 0))


def _format_par_per_game(par: int, games: int) -> tuple:
    """Display and numeric sort key for PAR per game."""
    if games <= 0:
        return "—", 0.0
    per = int(par) / games
    if per > 0:
        return f"+{per:.1f}", per
    return f"{per:.1f}", per


def build_players_html(
    data: dict,
    season: str,
    ascending: bool = False,
    *,
    summary: Optional[dict] = None,
) -> str:
    all_time = season in ("All Time",) or "All Time" in season
    count_label = "Games" if all_time else "Weeks"
    show_par = True
    main_headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Avg", "right": True},
        {"label": "High", "right": True},
        {"label": "Low", "right": True},
        {"label": count_label, "right": True},
    ]
    other_headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Games", "right": True, "sort_type": "number"},
        {"label": "Std dev", "right": True, "sort_type": "number"},
    ]
    if show_par:
        other_headers.extend(
            [
                {"label": "PAR", "right": True, "sort_type": "number"},
                {"label": "PAR/G", "right": True, "sort_type": "number"},
            ]
        )
    other_headers.append(
        {"label": "Absences", "right": True, "sort_type": "number"},
    )
    main_rows: List[List[dict]] = []
    other_rows: List[List[dict]] = []
    sorted_players = sorted(
        data.items(), key=lambda x: x[1].get("average", 0), reverse=not ascending
    )
    for i, (name, stats) in enumerate(sorted_players, 1):
        avg = stats.get("average", 0)
        high = stats.get("highest_game", 0)
        low = stats.get("lowest_game", 0)
        weeks = stats.get("weeks_played", 0)
        absences = stats.get("weeks_absent", 0)
        std_dev = stats.get("std_dev", 0)
        par = int(stats.get("par", 0))
        games = _player_par_game_count(stats, all_time)
        par_per_game, par_per_game_sort = _format_par_per_game(par, games)
        team = stats.get("team", "")
        ident = _player_identity_cells(i, name, team)
        main_rows.append(
            ident
            + [
                {"val": f"{avg:.1f}", "cls": "right gold"},
                {"val": high, "cls": "right green"},
                {"val": low, "cls": "right sub-col"},
                {"val": weeks, "cls": "right sub-col"},
            ]
        )
        other_cells = [
            {"val": games, "cls": "right sub-col", "sort": games},
            {"val": f"{std_dev:.1f}", "cls": "right gold", "sort": std_dev},
        ]
        if show_par:
            other_cells.extend(
                [
                    {"val": _format_par(par), "cls": "right gold", "sort": par},
                    {
                        "val": par_per_game,
                        "cls": "right gold",
                        "sort": par_per_game_sort,
                    },
                ]
            )
        other_cells.append(
            {"val": absences, "cls": "right sub-col", "sort": absences},
        )
        other_rows.append(ident + other_cells)
    par_help_btn = """
          <button type="button" class="players-par-help" hidden>
            What is PAR?
          </button>"""
    par_dialog = (
        """
        <dialog class="players-par-dialog">
          <div class="players-par-dialog-inner">"""
        + _PAR_HELP_DIALOG_BODY
        + """
            <button type="button" class="players-par-dialog-close">Got it</button>
          </div>
        </dialog>"""
    )
    summary_blocks = (
        _build_league_summary_blocks(summary) if summary else ""
    )
    section = (
        summary_blocks
        + f"""
    <div class="section players-stats-section">
      <div class="section-head">
        <div class="section-title">Season Averages</div>
        <div class="players-stats-actions">{par_help_btn}
          <button type="button" class="players-stats-toggle" aria-pressed="false">
            Other stats
          </button>
        </div>
      </div>
      <div class="players-stats-panel" data-panel="main">
        """
        + _render_sortable_table(main_headers, main_rows)
        + """
      </div>
      <div class="players-stats-panel" data-panel="other" hidden>
        """
        + _render_sortable_table(other_headers, other_rows)
        + par_dialog
        + """
      </div>
    </div>"""
    )
    css = _LIST_CSS + _PLAYERS_STATS_TOGGLE_CSS
    if summary:
        css += _HIGHLIGHTS_CSS
    return _render_list_page(
        css=css,
        title="🎳 PLAYERS",
        subtitle=season,
        sections=section,
        extra_script=_PLAYERS_STATS_TOGGLE_SCRIPT,
    )


# ---------------------------------------------------------------------------
# Team standings
# ---------------------------------------------------------------------------

def _team_name_cell_html(name: str, champion_team: Optional[str] = None) -> str:
    name_cell = html_module.escape(name)
    if champion_team and name == champion_team:
        name_cell = (
            '<span class="standings-champion" title="Playoff champion" aria-label="Season champion">'
            "👑</span> " + name_cell
        )
    return name_cell


def _team_name_cell_expandable(name: str, champion_team: Optional[str] = None) -> str:
    chevron = '<span class="team-expand-chevron" aria-hidden="true">▸</span> '
    return chevron + _team_name_cell_html(name, champion_team)


def _team_roster_breakdown_sort_key(item: Tuple[str, Any]) -> tuple:
    pname, info = item
    if isinstance(info, dict):
        if info.get("absent"):
            return (2, 0.0, pname.lower())
        val = info.get("value")
        if val is None:
            return (1, 0.0, pname.lower())
        return (0, -float(val), pname.lower())
    return (0, -float(info), pname.lower())


def _roster_absence_tags(info: dict) -> str:
    """Whole-week ABS, or ABS G1 / ABS G1,2,3 for per-game book averages."""
    if info.get("absent"):
        return ' <span class="player-tag">ABS</span>'
    missed = info.get("missed_games") or []
    if not missed:
        return ""
    games_label = ",".join(str(g) for g in missed)
    return f' <span class="player-tag">ABS G{games_label}</span>'


def _team_roster_score_html(info: dict) -> tuple[str, str]:
    """Score span and list item class for expandable team roster rows."""
    absent = bool(info.get("absent"))
    missed = bool(info.get("missed_game"))
    if absent:
        item_cls = "team-roster-item team-roster-item--absent"
        if info.get("value") is not None:
            val_html = (
                f'<span class="team-roster-avg">'
                f'{_format_roster_score_value(float(info["value"]))}</span>'
            )
        else:
            val_html = '<span class="team-roster-avg team-roster-avg--empty">—</span>'
        return item_cls, val_html
    if info.get("value") is None:
        return "team-roster-item", '<span class="team-roster-avg team-roster-avg--empty">—</span>'
    avg_cls = "team-roster-avg team-roster-avg--miss" if missed else "team-roster-avg"
    val_html = (
        f'<span class="{avg_cls}">'
        f'{_format_roster_score_value(float(info["value"]))}</span>'
    )
    return "team-roster-item", val_html


def _team_roster_detail_html(players: Dict[str, Any]) -> str:
    if not players:
        return '<p class="team-roster-empty">No player averages for this team.</p>'
    sample = next(iter(players.values()))
    if isinstance(sample, dict):
        items = []
        for pname, info in sorted(players.items(), key=_team_roster_breakdown_sort_key):
            label = html_module.escape(_short_name(pname))
            tag = _roster_absence_tags(info)
            item_cls, val_html = _team_roster_score_html(info)
            items.append(
                f'<li class="{item_cls}">'
                f'<span class="team-roster-name">{label}{tag}</span>'
                f"{val_html}"
                "</li>"
            )
        return f'<ul class="team-roster-list">{"".join(items)}</ul>'
    items = []
    for pname, avg in sorted(players.items(), key=lambda x: (-float(x[1]), x[0].lower())):
        label = html_module.escape(_short_name(pname))
        items.append(
            '<li class="team-roster-item">'
            f'<span class="team-roster-name">{label}</span>'
            f'<span class="team-roster-avg">{float(avg):.1f}</span>'
            "</li>"
        )
    return f'<ul class="team-roster-list">{"".join(items)}</ul>'


def _teams_standings_section(
    title: str,
    headers: List[dict],
    team_rows: List[Tuple[List[dict], Dict[str, Any]]],
    *,
    note: Optional[str] = None,
) -> str:
    """Standings table with expandable per-team player rosters."""
    ncols = len(headers)
    note_html = _section_note(note) if note else ""
    th_parts: List[str] = []
    for i, h in enumerate(headers):
        cls_parts: List[str] = []
        if h.get("right"):
            cls_parts.append("right")
        cls_parts.append("sortable-th")
        st = html_module.escape(_header_sort_type(h))
        th_parts.append(
            f'<th class="{" ".join(cls_parts)}" data-sort-col="{i}" data-sort-type="{st}">'
            f'{_sortable_th_content(h["label"], right=bool(h.get("right")), hint=h.get("hint"))}</th>'
        )
    th = "".join(th_parts)

    def _td(c: dict, col_idx: int) -> str:
        style_attr = f' style="{c["style"]}"' if c.get("style") else ""
        sort_raw = _cell_data_sort_value(c)
        esc_sort = html_module.escape(sort_raw, quote=True)
        orig = ""
        if col_idx == 0:
            orig = f' data-orig-rank="{html_module.escape(str(c["val"]), quote=True)}"'
        return (
            f'<td class="{c.get("cls", "")}" data-sort="{esc_sort}"{orig}{style_attr}>'
            f'{c["val"]}</td>'
        )

    body_parts: List[str] = []
    for main_cells, players in team_rows:
        main_tr = (
            '<tr class="team-standings-row" tabindex="0" role="button" '
            'aria-expanded="false">'
            + "".join(_td(c, j) for j, c in enumerate(main_cells))
            + "</tr>"
        )
        detail_tr = (
            f'<tr class="team-standings-detail hidden">'
            f'<td colspan="{ncols}">'
            f"{_team_roster_detail_html(players)}"
            f"</td></tr>"
        )
        body_parts.append(main_tr + detail_tr)

    return f"""
    <div class="section">
      <div class="section-title">{title}</div>
      {note_html}
      <div class="table-scroll">
      <table class="sortable-table teams-standings-table" data-has-rank-col="1">
        <thead><tr>{th}</tr></thead>
        <tbody>{"".join(body_parts)}</tbody>
      </table>
      </div>
    </div>"""


_TEAMS_STANDINGS_CSS = """
.team-standings-row { cursor: pointer; }
.team-standings-row:hover td { background: rgba(255, 184, 108, 0.06); }
.team-standings-row.expanded td { background: #221e3d; }
.team-expand-chevron {
    display: inline-block;
    width: 0.85em;
    margin-right: 5px;
    color: #666;
    font-size: 11px;
    transition: transform 0.15s ease, color 0.15s ease;
    vertical-align: middle;
}
.team-standings-row.expanded .team-expand-chevron {
    transform: rotate(90deg);
    color: #ffb86c;
}
.team-standings-detail td {
    padding: 2px 12px 14px 28px;
    background: #141226;
    border-bottom: 1px solid #2a2050;
}
.team-standings-detail.hidden { display: none; }
.team-roster-list {
    list-style: none;
    margin: 0;
    padding: 0;
    max-width: 220px;
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.team-roster-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 20px;
    font-size: 12px;
    line-height: 1.45;
}
.team-roster-name { color: #9a94b0; font-weight: 500; }
.team-roster-avg {
    color: #ffb86c;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}
.team-roster-empty { margin: 0; color: #888; font-size: 12px; }
.team-roster-item--absent { opacity: 0.55; }
.team-roster-avg--empty { color: #555; font-weight: 500; }
.team-roster-avg--miss { color: #ff6b81; }
.player-tag {
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 0.05em;
    color: #ff6b81;
    margin-left: 4px;
    vertical-align: middle;
}
"""

_TEAMS_EXPAND_SCRIPT = r"""<script>
(function () {
  document.querySelectorAll(".teams-standings-table").forEach(function (table) {
    table.querySelectorAll(".team-standings-row").forEach(function (row) {
      function toggle() {
        var detail = row.nextElementSibling;
        if (!detail || !detail.classList.contains("team-standings-detail")) {
          return;
        }
        var open = !row.classList.contains("expanded");
        row.classList.toggle("expanded", open);
        detail.classList.toggle("hidden", !open);
        row.setAttribute("aria-expanded", open ? "true" : "false");
      }
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      });
    });
  });
})();
</script>"""


def build_teams_html(
    data: dict, season: str, *, champion_team: Optional[str] = None
) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Record"},
        {"label": "Avg", "right": True},
        {"label": "Total Pins", "right": True},
    ]
    team_rows: List[Tuple[List[dict], Dict[str, float]]] = []
    sorted_teams = sort_teams_by_standings(data)
    for i, (name, stats) in enumerate(sorted_teams, 1):
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        t = stats.get("ties", 0)
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        players = stats.get("players") or {}
        main_cells = [
            {"val": i, "cls": "right rank"},
            {
                "val": _team_name_cell_expandable(name, champion_team),
                "cls": "name-col",
                "style": _team_color_style(name),
                "sort": name.lower(),
            },
            {
                "val": record,
                "cls": "record",
                "sort": w * 1_000_000 - l * 1_000 - t,
            },
            {"val": f"{avg:.1f}", "cls": "right gold"},
            {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
        ]
        team_rows.append((main_cells, players))
    section = _teams_standings_section("Standings", headers, team_rows)
    return _render_list_page(
        css=_LIST_CSS + _TEAMS_STANDINGS_CSS,
        title="🏆 TEAMS",
        subtitle=season,
        sections=section,
        extra_script=_TEAMS_EXPAND_SCRIPT,
    )


def build_bracket_index_html(seasons: List[str], *, embed: bool = False) -> str:
    """Index of /bracket?season=… links for each sheet season."""
    from urllib.parse import quote

    embed_qs = "&embed=1" if embed else ""
    items = []
    for s in seasons:
        items.append(
            f'<li><a href="/bracket?season={quote(s)}{embed_qs}">'
            f"{html_module.escape(s)}</a></li>"
        )
    extra = "\n.bracket-index-list { margin: 0; padding-left: 1.25rem; line-height: 1.9; }\n"
    inner = (
        '<div class="section"><div class="section-title">Seasons</div>'
        '<ul class="bracket-index-list">'
        f'{"".join(items)}</ul></div>'
    )
    return _render_list_page(
        css=_LIST_CSS + extra,
        title="🏆 PLAYOFFS",
        subtitle="Choose a season — bracket and playoff week scores on one page",
        sections=inner,
    )


# Fixed layout for winner-bracket SVG connectors (must match CSS .bracket-hcell / .bracket-tcell width + gap)
BRACKET_COL_W_PX = 260
BRACKET_GAP_PX = 20
BRACKET_MATCH_SLOT_PX = 58
BRACKET_HEADER_ROW_PX = 52


def _bracket_center_rows(n_first: int, slot_px: float) -> List[List[float]]:
    rows: List[List[float]] = []
    n = n_first
    cur = [(i + 0.5) * slot_px for i in range(n)]
    rows.append(cur)
    while n > 1:
        n //= 2
        cur = [(rows[-1][2 * j] + rows[-1][2 * j + 1]) / 2 for j in range(n)]
        rows.append(cur)
    return rows


def _bracket_connectors_svg(
    center_rows: List[List[float]],
    n_rounds_draw: int,
    w_px: float,
    h_px: float,
    *,
    stroke: str = "#7c6ec4",
    stroke_opacity: float = 0.95,
) -> str:
    if n_rounds_draw < 2 or len(center_rows) < 2:
        return ""
    COL_W, GAP = BRACKET_COL_W_PX, BRACKET_GAP_PX
    d_parts: List[str] = []
    for r in range(min(n_rounds_draw - 1, len(center_rows) - 1)):
        for j in range(len(center_rows[r + 1])):
            y_lo = center_rows[r][2 * j]
            y_hi = center_rows[r][2 * j + 1]
            y_mid = (y_lo + y_hi) / 2
            xR = r * (COL_W + GAP) + COL_W - 14
            xM = r * (COL_W + GAP) + COL_W + GAP / 2
            xN = (r + 1) * (COL_W + GAP) + 16
            d_parts.append(f"M{xR:.1f},{y_lo:.1f}H{xM:.1f}")
            d_parts.append(f"M{xR:.1f},{y_hi:.1f}H{xM:.1f}")
            d_parts.append(f"M{xM:.1f},{y_lo:.1f}V{y_hi:.1f}")
            d_parts.append(f"M{xM:.1f},{y_mid:.1f}H{xN:.1f}")
    path_d = "".join(d_parts)
    return (
        f'<svg class="bracket-lines" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w_px:.0f} {h_px:.0f}" width="100%" height="100%" '
        f'style="min-height:{h_px:.0f}px" '
        f'preserveAspectRatio="xMinYMin meet" aria-hidden="true">'
        f'<path d="{path_d}" fill="none" stroke="{stroke}" stroke-width="1.65" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="{stroke_opacity}"/></svg>'
    )


def _elimination_rows_from_playoffs(
    pweeks: List[int],
    snapshots: List[Optional[dict]],
    num_rounds: int,
) -> List[Tuple[str, str, str, str, str]]:
    """(round_title, week_str, loser, winner, pins_blurb)."""
    out: List[Tuple[str, str, str, str, str]] = []
    for ri, snap in enumerate(snapshots):
        if not snap or not snap.get("matchups"):
            continue
        pw = str(pweeks[ri]) if ri < len(pweeks) else "—"
        title = (
            _bracket_round_title(ri, num_rounds)
            if ri < num_rounds and num_rounds
            else f"Round {ri + 1}"
        )
        for m in snap["matchups"]:
            away = m.get("away")
            if not away:
                continue
            home = m["home"]
            hr, ar = home.get("result", ""), away.get("result", "")
            hp, ap = int(home.get("pins", 0)), int(away.get("pins", 0))
            if hr == "W" and ar == "L":
                loser_n, winner_n = away["name"], home["name"]
                lp, wp = ap, hp
            elif ar == "W" and hr == "L":
                loser_n, winner_n = home["name"], away["name"]
                lp, wp = hp, ap
            else:
                continue
            pins_b = f"{lp:,}–{wp:,} pins"
            out.append((title, pw, loser_n, winner_n, pins_b, lp))
    return out


def _elimination_section_html(rows: List[Tuple[str, str, str, str, str, int]]) -> str:
    if not rows:
        return (
            '<div class="section bracket-losers-section">'
            '<div class="section-title">Eliminated</div>'
            "<p class=\"bracket-note\">Teams appear here after each playoff week has matchup scores "
            "(loser of each game).</p></div>"
        )
    h = "".join(
        "<tr>"
        f"<td class=\"sub-col\" data-sort=\"{html_module.escape(t.lower(), quote=True)}\">"
        f"{html_module.escape(t)}</td>"
        f"<td class=\"right rank\" data-sort=\"{html_module.escape(str(int(wk)) if str(wk).isdigit() else str(wk), quote=True)}\">"
        f"{html_module.escape(wk)}</td>"
        f"<td class=\"name-col\" style=\"{_team_color_style(l)}\" "
        f"data-sort=\"{html_module.escape(l.lower(), quote=True)}\">"
        f"{html_module.escape(l)}</td>"
        "<td class=\"sub-col\" data-sort=\"0\">lost to</td>"
        f"<td class=\"name-col\" style=\"{_team_color_style(w)}\" "
        f"data-sort=\"{html_module.escape(w.lower(), quote=True)}\">"
        f"{html_module.escape(w)}</td>"
        f"<td class=\"sub-col right\" data-sort=\"{html_module.escape(str(lp), quote=True)}\">"
        f"{html_module.escape(pb)}</td>"
        "</tr>"
        for t, wk, l, w, pb, lp in rows
    )
    thead = (
        '<thead><tr>'
        '<th class="sortable-th" data-sort-col="0" data-sort-type="string">'
        'Round<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="right sortable-th" data-sort-col="1" data-sort-type="number">'
        f'{_sortable_th_content("Week", right=True)}</th>'
        '<th class="sortable-th" data-sort-col="2" data-sort-type="string">'
        'Team out<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="sortable-th" data-sort-col="3" data-sort-type="string">'
        '<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="sortable-th" data-sort-col="4" data-sort-type="string">'
        'Lost to<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="right sortable-th" data-sort-col="5" data-sort-type="number">'
        f'{_sortable_th_content("Pins (L–W)", right=True)}</th>'
        "</tr></thead>"
    )
    return (
        '<div class="section bracket-losers-section">'
        '<div class="section-title">Eliminated</div>'
        '<table class="bracket-losers-table sortable-table">'
        f"{thead}<tbody>{h}</tbody></table></div>"
    )


def _playoff_snapshots_with_matchups(
    snapshots: List[Optional[dict]],
) -> List[dict]:
    return [s for s in (snapshots or []) if s and s.get("matchups")]


def _champion_from_labeled_finals(valid: List[dict], ms: List[dict]) -> Optional[str]:
    """Winner of the 1st-place game when the finals week has placement matchups."""
    w3_groups: List[Tuple[FrozenSet[str], str]] = []
    if len(valid) >= 3:
        qf_ms = list(valid[0]["matchups"])
        ms1 = list(valid[1]["matchups"])
        teams: Set[str] = set()
        for s in valid:
            for m in s["matchups"]:
                teams.add(cast(str, m["home"]["name"]))
                away = m.get("away")
                if away:
                    teams.add(cast(str, away["name"]))
        round_pairs = compute_bracket_rounds(sorted(teams))[0] if len(teams) >= 2 else []
        w3_groups = _best_w3_groups(qf_ms, ms1, ms, round_pairs, snapshots=valid)
    elif len(valid) == 2:
        parallel = _resolve_two_week_parallel_playoffs(valid, seed_rank=None)
        if parallel:
            w3_groups = list(parallel.get("w3_groups") or [])
    if not w3_groups:
        return None
    ordered, _ = order_matchups_by_labeled_groups(ms, w3_groups)
    for label, mm in ordered:
        if label.startswith("1st") and mm:
            wl = winner_loser_from_matchup(mm)
            if wl:
                return wl[0]
    return None


def _champion_from_unbeaten_final(valid: List[dict], ms: List[dict]) -> Optional[str]:
    """Fallback: finals game between two teams still undefeated in prior playoff weeks."""
    losses: Dict[str, int] = {}
    for s in valid[:-1]:
        for m in _playoff_matchups_with_opponent(list(s["matchups"])):
            wl = winner_loser_from_matchup(m)
            if not wl:
                continue
            winner, loser = wl
            losses[loser] = losses.get(loser, 0) + 1
            losses.setdefault(winner, losses.get(winner, 0))
    for m in ms:
        away = m.get("away")
        if not away:
            continue
        h, a = cast(str, m["home"]["name"]), cast(str, away["name"])
        if losses.get(h, 0) != 0 or losses.get(a, 0) != 0:
            continue
        wl = winner_loser_from_matchup(m)
        if wl:
            return wl[0]
    return None


def champion_from_playoff_snapshots(snapshots: List[Optional[dict]]) -> Optional[str]:
    """Playoff champion: winner of the 1st-place game (or sole finals matchup)."""
    valid = _playoff_snapshots_with_matchups(snapshots)
    if not valid:
        return None
    ms = _playoff_matchups_with_opponent(list(valid[-1]["matchups"]))
    if not ms:
        return None
    if len(ms) == 1:
        wl = winner_loser_from_matchup(ms[0])
        return wl[0] if wl else None
    champ = _champion_from_labeled_finals(valid, ms)
    if champ:
        return champ
    return _champion_from_unbeaten_final(valid, ms)


def _champion_callout_html(snapshots: List[Optional[dict]]) -> str:
    nm = champion_from_playoff_snapshots(snapshots)
    if not nm:
        return ""
    return (
        f'<div class="bracket-champion"><span class="bracket-champion-label">Champion</span>'
        f'<span class="bracket-champion-name" style="{_team_color_style(nm)}">'
        f"{html_module.escape(nm)}</span></div>"
    )


# ---------------------------------------------------------------------------
# Playoff bracket (single elimination from seeds)
# ---------------------------------------------------------------------------

_BRACKET_EXTRA_CSS = """
html { overflow-x: hidden; }
body { overflow-y: auto; min-width: 0; }
.container { max-width: none; overflow: visible; }
.bracket-wrap {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: 0 -6px;
  padding: 6px 12px 16px 12px;
  max-width: 100%;
  max-height: min(72vh, 760px);
  min-height: 360px;
}
.bracket-zoom-controls {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.bracket-zoom-btn {
  font: inherit;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  min-width: 2rem;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #4a4068;
  background: #1e1a32;
  color: #d4cce8;
  cursor: pointer;
}
.bracket-zoom-btn:hover { border-color: #7c6ec4; color: #fff; }
.bracket-zoom-btn[data-zoom-action="fit"] {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 6px 12px;
}
.bracket-zoom-label {
  font-size: 11px;
  color: #8b849c;
  min-width: 3.2rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.bracket-zoom-viewport {
  flex: 1 1 auto;
  min-height: 280px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  border-radius: 8px;
  background: rgba(10, 9, 16, 0.35);
  box-sizing: border-box;
  padding: 14px 12px 10px 18px;
}
.bracket-wrap.bracket-wrap--dragging .bracket-zoom-viewport,
.bracket-wrap.bracket-wrap--pinching .bracket-zoom-viewport {
  cursor: grabbing;
  user-select: none;
}
.bracket-wrap.bracket-wrap--dragging .bracket-zoom-viewport *,
.bracket-wrap.bracket-wrap--pinching .bracket-zoom-viewport * {
  user-select: none;
}
.bracket-zoom-spacer {
  position: relative;
  display: block;
}
.bracket-zoom-stage {
  transform-origin: 0 0;
  display: inline-block;
  vertical-align: top;
}
.bracket-shell { display: flex; flex-direction: column; gap: 4px; overflow: visible; }
.bracket-winners-title {
  font-size: 10px; font-weight: bold; letter-spacing: 1px; color: #6b6b80;
  text-transform: uppercase; margin: 6px 0 2px 0;
}
.bracket-headers-row {
  display: flex; flex-direction: row;
  gap: """ + str(BRACKET_GAP_PX) + """px;
  align-items: flex-end;
}
.bracket-hcell {
  width: """ + str(BRACKET_COL_W_PX) + """px;
  flex: 0 0 """ + str(BRACKET_COL_W_PX) + """px;
  min-height: 2.75rem;
}
.bracket-grid-main {
  position: relative;
  overflow: visible;
}
.bracket-main-tracks {
  position: relative;
  min-height: calc(var(--bf-slots, 4) * """ + str(BRACKET_MATCH_SLOT_PX) + """px);
  overflow: visible;
}
.bracket-tracks-row {
  display: flex; flex-direction: row;
  align-items: stretch;
  gap: """ + str(BRACKET_GAP_PX) + """px;
  position: relative;
  z-index: 1;
  min-height: calc(var(--bf-slots, 4) * """ + str(BRACKET_MATCH_SLOT_PX) + """px);
  overflow: visible;
}
.bracket-tcell {
  width: """ + str(BRACKET_COL_W_PX) + """px;
  flex: 0 0 """ + str(BRACKET_COL_W_PX) + """px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
  background: transparent;
  border-radius: 0;
  padding: 4px 0 8px 1px;
  box-sizing: border-box;
  overflow: visible;
}
.bracket-tcell .bracket-pair-wrap {
  flex: 0 0 auto;
  width: 100%;
  min-height: 3.65rem;
  box-sizing: border-box;
}
.bracket-tcell-inner {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  justify-content: flex-start;
}
.bracket-format-note {
  font-size: 12px;
  line-height: 1.5;
  color: #9a94b0;
  margin: 0 0 8px 0;
  padding: 8px 10px;
  background: rgba(26, 23, 48, 0.65);
  border-radius: 6px;
  border-left: 3px solid #7c6ec4;
}
.bracket-lines {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 0;
  pointer-events: none;
  overflow: visible;
}
.bracket-champion {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2d1b69 0%, #1a1730 100%);
  border: 1px solid #ffb86c44;
  text-align: center;
}
.bracket-champion-label {
  display: block;
  font-size: 10px;
  letter-spacing: 0.15em;
  color: #888;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.bracket-champion-name { font-size: 1.15rem; font-weight: 800; }
.bracket-losers-section table.bracket-losers-table { font-size: 12px; }
.bracket-losers-table td, .bracket-losers-table th { padding: 6px 8px; color: #ddd; }
.bracket-losers-table tbody tr:nth-child(even) { background: #1a1730; }
.bracket-pair-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: auto;
  overflow: visible;
  cursor: pointer;
}
.bracket-pair-wrap:hover,
.bracket-pair-wrap:focus-within { z-index: 80; }
.bracket-pair {
  cursor: default;
  border: none;
  border-right: 2px solid rgba(124, 110, 196, 0.55);
  border-radius: 0;
  padding: 7px 10px 7px 4px;
  background: rgba(15, 14, 22, 0.35);
  margin: 0 2px 0 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  transition: background 0.12s ease;
}
.bracket-pair-wrap:hover .bracket-pair,
.bracket-pair-wrap:focus-within .bracket-pair {
  background: rgba(45, 27, 105, 0.25);
}
.bracket-pair--bye {
  border-right-color: rgba(90, 84, 120, 0.45);
  background: rgba(15, 14, 22, 0.2);
}
.bracket-pair--pending { border-right-color: rgba(100, 92, 140, 0.4); }
.bracket-pair--path-title { border-right-color: rgba(212, 184, 122, 0.65); background: rgba(45, 35, 20, 0.2); }
.bracket-pair--path-place { border-right-color: rgba(120, 130, 155, 0.5); background: rgba(20, 22, 32, 0.35); }
.bracket-pair--path-mixed { border-right-color: rgba(154, 138, 191, 0.45); }
.bracket-path-chip {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 3px;
  color: #8b849c;
}
.bracket-path-chip--title { color: #d4b87a; }
.bracket-path-chip--place { color: #95a0b8; }
.bracket-path-chip--mixed { color: #b8a8d8; }
.bracket-subsec {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding-bottom: 4px;
}
.bracket-subsec-h {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 4px 0 8px 2px;
  margin-bottom: 4px;
  border-bottom: 1px solid #2a2445;
  color: #7a7394;
}
.bracket-subsec-h--title { color: #d4b87a; border-bottom-color: #4a3d28; }
.bracket-subsec-h--place { color: #8b93a8; border-bottom-color: #2a3040; }
.bracket-subsec-h--mixed { color: #9a8abf; border-bottom-color: #352a55; }
.bracket-pair-side {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}
.bracket-pair-line { line-height: 1.35; margin: 1px 0; }
.bracket-pair-line--row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.bracket-pair-line--row .bracket-line {
  flex: 1 1 auto;
  min-width: 0;
}
.bracket-line-with-hint {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  flex: 1 1 auto;
  min-width: 0;
}
.bracket-pair-line--champ {
  border-left: 3px solid rgba(212, 184, 122, 0.9);
  padding-left: 8px;
  margin-left: 0;
  border-radius: 0 5px 5px 0;
  background: linear-gradient(
    90deg,
    rgba(212, 184, 122, 0.12) 0%,
    rgba(212, 184, 122, 0.02) 55%,
    transparent 100%
  );
}
.bracket-pair-line--place {
  border-left: 3px solid rgba(139, 147, 168, 0.65);
  padding-left: 8px;
  margin-left: 0;
  border-radius: 0 5px 5px 0;
  background: linear-gradient(
    90deg,
    rgba(100, 110, 140, 0.14) 0%,
    rgba(100, 110, 140, 0.03) 55%,
    transparent 100%
  );
}
.bracket-track-hint {
  flex-shrink: 0;
  display: inline-block;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 3px 7px;
  border-radius: 4px;
  line-height: 1.15;
}
.bracket-track-hint--champ {
  color: #f0dfb8;
  background: rgba(212, 184, 122, 0.22);
  border: 1px solid rgba(232, 210, 160, 0.45);
  box-shadow: 0 0 0 1px rgba(212, 184, 122, 0.12);
}
.bracket-track-hint--place {
  color: #c8ccd8;
  background: rgba(105, 115, 145, 0.28);
  border: 1px solid rgba(139, 147, 168, 0.45);
  box-shadow: 0 0 0 1px rgba(90, 100, 130, 0.15);
}
.bracket-badge {
  flex-shrink: 0;
  display: inline-block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1.15;
}
.bracket-badge--w {
  background: rgba(80, 250, 123, 0.2);
  color: #7bf5a8;
  border: 1px solid rgba(80, 250, 123, 0.45);
}
.bracket-badge--l {
  background: rgba(255, 107, 129, 0.12);
  color: #ff9aaa;
  border: 1px solid rgba(255, 107, 129, 0.4);
}
.bracket-badge--t {
  background: rgba(255, 184, 108, 0.16);
  color: #ffc890;
  border: 1px solid rgba(255, 184, 108, 0.4);
}
.bracket-pair-mid {
  text-align: center;
  font-size: 8px;
  color: #4a4860;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 1px 0;
}
.bracket-line {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
}
.bracket-cl-row-main .bracket-line,
.bracket-pair-line--row .bracket-line {
  white-space: nowrap;
}
.bracket-line--ghost { color: #555; font-style: italic; font-weight: 500; font-size: 11px; }
.bracket-line--mini { font-size: 10px; color: #a8a4bc; font-weight: 500; }
.bracket-line--pending { color: #666; font-style: italic; font-size: 10.5px; font-weight: 500; }
.bracket-name--w { font-weight: 800; }
.bracket-name--l { opacity: 1; font-weight: 600; }
.bracket-name--tie { font-weight: 700; color: #e8c490; }
.bracket-name--pending { opacity: 0.7; }
.bracket-bye-note, .bracket-bye-tag {
  font-size: 9px;
  color: #5c5a70;
  font-style: italic;
  text-align: left;
  margin-top: 1px;
}
#bracket-pop-layer {
  position: fixed;
  inset: 0;
  width: 0;
  height: 0;
  overflow: visible;
  pointer-events: none;
  z-index: 2147483646;
}
.bracket-pop--floated {
  position: fixed !important;
  left: 0;
  top: 0;
  opacity: 1 !important;
  visibility: visible !important;
  pointer-events: auto;
  z-index: 2147483647;
  max-width: min(320px, calc(100vw - 24px));
}
.bracket-cl-outer.bracket-match--tap-active,
.bracket-pair-wrap.bracket-match--tap-active {
  outline: 2px solid #7c6ec4;
  outline-offset: 2px;
  z-index: 75;
}
.bracket-pop--floated.bracket-pop--above {
  box-shadow: 0 -8px 28px rgba(0,0,0,0.5);
}
.bracket-pop {
  position: absolute;
  left: 0;
  right: auto;
  top: calc(100% + 6px);
  bottom: auto;
  transform: none;
  width: max-content;
  max-width: min(320px, calc(100vw - 24px));
  padding: 9px 11px;
  background: linear-gradient(180deg, #252038 0%, #171528 100%);
  border: 1px solid #6a5f9e;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.55);
  font-size: 11px;
  line-height: 1.4;
  color: #dcd6ec;
  text-align: left;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.12s ease, visibility 0.12s ease;
  pointer-events: none;
  z-index: 2;
}
.bracket-cl-outer .bracket-pop {
  left: calc(1.1rem + 6px);
}
.bracket-pop-path {
  font-size: 10px;
  line-height: 1.4;
  color: #c4b8e8;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #322a50;
}
.bracket-pop-h {
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8b849c;
  margin-bottom: 6px;
  padding-bottom: 5px;
  border-bottom: 1px solid #322a50;
}
.bracket-pop-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-top: 3px;
}
.bracket-pop-n { font-weight: 700; flex: 1; min-width: 0; font-size: 11px; }
.bracket-pop-pins { font-variant-numeric: tabular-nums; color: #ada5c8; font-size: 10px; }
.bracket-pop-res { font-weight: 800; width: 1.1rem; text-align: right; color: #ffb86c; font-size: 11px; }
.bracket-pop-meta { color: #948ca8; font-size: 10px; margin-top: 5px; }
.record-override-mark {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  color: #9b8ec4;
  cursor: help;
  line-height: 1;
}
.list-table .record-override-mark { font-size: 11px; margin-left: 3px; }
.bracket-cl-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bracket-cl-trail {
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
}
.bracket-cl-override-slot {
  flex: 0 0 0.65rem;
  width: 0.65rem;
  text-align: center;
  line-height: 1;
}
.bracket-cl-trail .record-override-mark { margin: 0; }
.bracket-pop-gh {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6d6785;
  margin: 8px 0 3px 0;
}
.bracket-pop-g {
  font-size: 10px;
  color: #aaa;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.bracket-pop-gr { color: #7d7694; }
.bracket-pop-seed {
  font-size: 10px;
  color: #b4aecc;
  margin-top: 4px;
}
.bracket-pop-seed-l {
  display: inline-block;
  min-width: 3.5rem;
  color: #6d6788;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.bracket-idle {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #4a4858;
}
.bracket-wrap--classic {
  background: #232329;
  background-image: radial-gradient(circle at center, rgba(255,255,255,0.07) 1px, transparent 1px);
  background-size: 11px 11px;
  border-radius: 12px;
  border: 1px solid #353540;
  padding: 10px 8px 14px 8px;
}
.bracket-cl-outer {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 6px;
  margin-bottom: 12px;
  z-index: 1;
  cursor: pointer;
}
.bracket-cl-outer:hover,
.bracket-cl-outer:focus-within { z-index: 80; }
.bracket-cl-outer:last-child { margin-bottom: 0; }
.bracket-cl-outer:focus { outline: 2px solid #7c6ec4; outline-offset: 2px; }
.bracket-cl-match {
  flex: 1 1 auto;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid #3d3d48;
  background: linear-gradient(180deg, #2c2c34 0%, #25252d 100%);
  overflow: hidden;
  cursor: help;
}
.bracket-cl-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0;
  min-height: 1.75rem;
  border-bottom: 1px solid #1a1a22;
}
.bracket-cl-row:last-child { border-bottom: none; }
.bracket-cl-seed {
  flex: 0 0 1.65rem;
  width: 1.65rem;
  text-align: center;
  font-size: 10px;
  font-weight: 800;
  color: #d0ccd8;
  background: #3a3a44;
  border-right: 1px solid #2a2a32;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bracket-cl-seed--empty { color: #5c5a68; font-weight: 600; }
.bracket-cl-row-main {
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 10px;
  min-width: 0;
}
.bracket-cl-pending {
  font-size: 11px;
  color: #6d6a7a;
  font-style: italic;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px dashed #454254;
  margin-bottom: 10px;
}
.bracket-grid-main--classic .bracket-lines path {
  stroke: rgba(238, 240, 252, 0.78);
}
.bracket-note { font-size: 13px; color: #888; line-height: 1.5; margin-bottom: 18px; }
.bracket-hcell .wk-chip {
  font-size: 9px; color: #c9a86a; font-weight: 600; letter-spacing: 0.04em;
  margin: -2px 0 6px 0;
}
"""


def _bracket_next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return max(p, 2)


def _bracket_seed_order(size: int) -> List[int]:
    if size < 2:
        return [1]
    if size == 2:
        return [1, 2]
    prev = _bracket_seed_order(size // 2)
    out: List[int] = []
    for s in prev:
        out.append(s)
        out.append(size + 1 - s)
    return out


# Bracket slot: None = empty, str = team, (L, R) = two(sub-)slots whose winner advances
BracketSlot = Union[None, str, Tuple["BracketSlot", "BracketSlot"]]


def _advance_bracket_slot(left: Optional[str], right: Optional[str]) -> BracketSlot:
    """Promote winners from one first-round-style matchup (optional team names)."""
    if left is None and right is None:
        return None
    if left is None:
        return right  # type: ignore[return-value]
    if right is None:
        return left
    return (left, right)


def _combine_slots(left: BracketSlot, right: BracketSlot) -> BracketSlot:
    """Pair two advancing slots into the next round's matchup side (nested pending)."""
    if left is None and right is None:
        return None
    if left is None:
        return right
    if right is None:
        return left
    return (left, right)


def compute_bracket_rounds(seeded_teams: List[str]) -> List[List[Tuple[BracketSlot, BracketSlot]]]:
    """seeded_teams[0] is 1-seed. Standard adjacent pairing; byes for non-power-of-2.
    After round 0, undecided games become nested (A, B) tuples so later rounds show
    'Winner advances' trees instead of BYE placeholders."""
    n = len(seeded_teams)
    if n < 1:
        return []
    size = _bracket_next_pow2(n)
    order = _bracket_seed_order(size)
    leaf: List[Optional[str]] = []
    for sn in order:
        if sn <= n:
            leaf.append(seeded_teams[sn - 1])
        else:
            leaf.append(None)
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]] = []
    cur_q: List[Tuple[Optional[str], Optional[str]]] = [
        (leaf[i], leaf[i + 1]) for i in range(0, len(leaf), 2)
    ]
    rounds.append([(a, b) for a, b in cur_q])  # type: ignore[list-item]
    cur_slots: List[BracketSlot] = [_advance_bracket_slot(L, R) for L, R in cur_q]
    while len(cur_slots) > 1:
        next_matchups = [
            (cur_slots[i], cur_slots[i + 1])
            for i in range(0, len(cur_slots), 2)
        ]
        rounds.append(next_matchups)
        cur_slots = [_combine_slots(L, R) for L, R in next_matchups]
    return rounds


def _slot_team_names(slot: BracketSlot) -> FrozenSet[str]:
    if slot is None:
        return frozenset()
    if isinstance(slot, str):
        return frozenset({slot})
    L, R = slot
    return _slot_team_names(L) | _slot_team_names(R)


def _theoretical_pair_team_pool(left: BracketSlot, right: BracketSlot) -> FrozenSet[str]:
    return _slot_team_names(left) | _slot_team_names(right)


def _matchup_fits_theoretical_pool(m: dict, pool: FrozenSet[str]) -> bool:
    away = m.get("away")
    if not away:
        return m["home"]["name"] in pool
    return frozenset({m["home"]["name"], away["name"]}).issubset(pool)


def _match_matchups_to_theoretical_round(
    matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> Tuple[List[dict], List[bool]]:
    """Order sheet matchups like the seeded bracket (not alphabetically by home).

    The first len(round_pairs) entries that get assigned from the main loop are
    *theoretically aligned* to bracket slots (one try per slot). Remaining sheet
    games are full-field extras (e.g. cross-bracket); flags mark aligned ones.
    """
    used: Set[int] = set()
    out: List[dict] = []
    aligned: List[bool] = []
    for left, right in round_pairs:
        pool = _theoretical_pair_team_pool(left, right)
        for i, m in enumerate(matchups):
            if i in used:
                continue
            if _matchup_fits_theoretical_pool(m, pool):
                used.add(i)
                out.append(m)
                aligned.append(True)
                break
    for i, m in enumerate(matchups):
        if i not in used:
            out.append(m)
            aligned.append(False)
    return out, aligned


def _solo_teams_in_week(matchups: List[dict]) -> List[str]:
    return [m["home"]["name"] for m in matchups if not m.get("away")]


def _slot_wl_from_matchup(m: Optional[dict]) -> Optional[SlotWL]:
    if not m:
        return None
    if m.get("_bye_pair"):
        return (cast(str, m["home"]["name"]), BYE_LOSER)
    if not m.get("away"):
        return (cast(str, m["home"]["name"]), BYE_LOSER)
    return winner_loser_from_matchup(m)


def qf_matchups_in_bracket_slot_order(
    matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[Optional[dict]]:
    """One entry per bracket QF slot; None if no sheet game uses that seed pairing."""
    slots: List[Optional[dict]] = [None] * len(round_pairs)
    used: Set[int] = set()
    for i, (left, right) in enumerate(round_pairs):
        pool = _theoretical_pair_team_pool(left, right)
        for j, m in enumerate(matchups):
            if j in used:
                continue
            if _matchup_fits_theoretical_pool(m, pool):
                used.add(j)
                slots[i] = m
                break
    leftover_idxs = [
        j
        for j in range(len(matchups))
        if j not in used and matchups[j].get("away")
    ]
    while leftover_idxs:
        best_j: Optional[int] = None
        best_i: Optional[int] = None
        best_ov = 0
        empty = [i for i in range(len(slots)) if slots[i] is None]
        for j in leftover_idxs:
            m = matchups[j]
            away = m.get("away")
            if not away:
                continue
            teams = frozenset({m["home"]["name"], away["name"]})
            for i in empty:
                pool = _theoretical_pair_team_pool(round_pairs[i][0], round_pairs[i][1])
                ov = len(teams & pool)
                if ov > best_ov:
                    best_ov = ov
                    best_j = j
                    best_i = i
        if best_j is None or best_i is None:
            j = leftover_idxs.pop(0)
            for i in range(len(slots)):
                if slots[i] is None:
                    slots[i] = matchups[j]
                    used.add(j)
                    break
            continue
        slots[best_i] = matchups[best_j]
        used.add(best_j)
        leftover_idxs.remove(best_j)

    teams_in_slots: Set[str] = set()
    for s in slots:
        if not s:
            continue
        teams_in_slots.add(s["home"]["name"])
        away = s.get("away")
        if away:
            teams_in_slots.add(away["name"])
    solo = [t for t in _solo_teams_in_week(matchups) if t not in teams_in_slots]
    solo_used: Set[str] = set()
    for i, (left, right) in enumerate(round_pairs):
        if slots[i] is not None:
            continue
        pool = _theoretical_pair_team_pool(left, right)
        in_pool = [t for t in solo if t in pool and t not in solo_used]
        if len(in_pool) == 1:
            nm = in_pool[0]
            solo_used.add(nm)
            slots[i] = {
                "home": {"name": nm, "result": "W", "pins": 0, "avg": 0, "game_pins": [], "wins": 0},
                "away": None,
            }
        elif len(in_pool) >= 2:
            for nm in in_pool[:2]:
                solo_used.add(nm)
            slots[i] = {
                "home": {
                    "name": in_pool[0],
                    "result": "W",
                    "pins": 0,
                    "avg": 0,
                    "game_pins": [],
                    "wins": 0,
                },
                "away": {
                    "name": in_pool[1],
                    "result": "W",
                    "pins": 0,
                    "avg": 0,
                    "game_pins": [],
                    "wins": 0,
                },
                "_bye_pair": True,
            }

    return slots


def _qf_results_for_bracket_placement(
    qf_matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[Optional[SlotWL]]:
    """Use true bracket-slot QF order when all four games match theory; else theory-then-sheet order."""
    slots = qf_matchups_in_bracket_slot_order(qf_matchups, round_pairs)
    if len(slots) >= 4 and all(slots):
        wl = [_slot_wl_from_matchup(s) for s in slots[:4]]
        if all(wl):
            return wl
    qf_ord, _ = _match_matchups_to_theoretical_round(qf_matchups, round_pairs)
    return qf_slot_results_in_order(qf_ord)


def _qf_res_candidates(
    qf_matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[List[Optional[SlotWL]]]:
    """Distinct 4-slot QF outcomes (W/L per bracket slot) to try for crossover vs parallel fit."""
    acc: List[List[Optional[SlotWL]]] = []
    seen: Set[Tuple[Optional[SlotWL], ...]] = set()

    def push(seq: List[Optional[SlotWL]]) -> None:
        if len(seq) < 4:
            return
        s4 = seq[:4]
        if not all(s4):
            return
        key = tuple(s4)
        if key in seen:
            return
        seen.add(key)
        acc.append(list(s4))

    push(_qf_results_for_bracket_placement(qf_matchups, round_pairs))
    slot_wl = [
        _slot_wl_from_matchup(s)
        for s in qf_matchups_in_bracket_slot_order(qf_matchups, round_pairs)
    ]
    if len(slot_wl) >= 4 and all(slot_wl):
        push(slot_wl[:4])
    sheet_full = qf_slot_results_in_order(qf_matchups)
    if len(sheet_full) >= 4:
        s4 = sheet_full[:4]
        for k in range(4):
            push(s4[k:] + s4[:k])
    row_wl: List[Optional[SlotWL]] = []
    for m in qf_matchups[:4]:
        row_wl.append(winner_loser_from_matchup(m))
    if len(row_wl) == 4 and all(row_wl):
        for perm in itertools.permutations((0, 1, 2, 3)):
            push([row_wl[perm[i]] for i in range(4)])
    return acc


def _qf_winner_loser_sets(qf_ms: List[dict]) -> Tuple[Set[str], Set[str]]:
    """QF winners and losers from the first four decided games."""
    w: Set[str] = set()
    l: Set[str] = set()
    for m in qf_ms[:4]:
        wl = winner_loser_from_matchup(m)
        if wl:
            w.add(wl[0])
            l.add(wl[1])
    return w, l


def _split_semis_by_playoff_loss_band(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
    *,
    losses_before_col: int = 1,
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Winners-bracket semis = both teams with 0 playoff losses; losers-bracket = both with 1+."""
    losses = _playoff_losses_through_prior_rounds(snapshots, losses_before_col)
    wb: List[dict] = []
    lb: List[dict] = []
    other: List[dict] = []
    for m in _playoff_matchups_with_opponent(ms1):
        away = m.get("away")
        if not away:
            continue
        h, a = m["home"]["name"], away["name"]
        lh, la = losses.get(h, 0), losses.get(a, 0)
        if lh == 0 and la == 0:
            wb.append(m)
        elif lh >= 1 and la >= 1:
            lb.append(m)
        else:
            other.append(m)
    return wb, lb, other


def _parallel_model_from_loss_band(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
    ms2: List[dict],
    qf_ms: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> Optional[dict]:
    """Sheet-style parallel semis: QF winners play winners, QF losers play losers."""
    wb_ms, lb_ms, other = _split_semis_by_playoff_loss_band(snapshots, ms1)
    if len(wb_ms) != 2 or len(lb_ms) != 2:
        return None
    wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
    lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
    if not all(wb_semis) or not all(lb_semis):
        return None
    w3_groups = expected_week3_groups(wb_semis[:2], lb_semis[:2])
    ms2_played = _playoff_matchups_with_opponent(ms2)
    sheet_qf = qf_slot_results_in_order(_playoff_matchups_with_opponent(qf_ms))
    if len(sheet_qf) >= 4 and all(sheet_qf):
        qf_res = sheet_qf[:4]
    else:
        qf_res = _qf_results_for_bracket_placement(qf_ms, round_pairs)
    return {
        "kind": "parallel",
        "qf_res": list(qf_res[:4]) if qf_res else [],
        "wb_ord": wb_ms,
        "lb_ord": lb_ms,
        "rest": other,
        "w3_groups": w3_groups,
        "w3_hits": _week3_match_count(ms2_played, w3_groups),
    }


def _semis_week_parallel_shape(
    qf_ms: List[dict],
    ms1: List[dict],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> bool:
    """True if semis has two unbeaten-vs-unbeaten games and two one-loss-vs-one-loss games."""
    if snapshots is not None:
        wb, lb, other = _split_semis_by_playoff_loss_band(snapshots, ms1)
        if len(wb) == 2 and len(lb) == 2 and not other:
            return True
    W, L = _qf_winner_loser_sets(qf_ms)
    if len(W) != 4 or len(L) != 4:
        return False
    ww = ll = 0
    for m in ms1:
        away = m.get("away")
        if not away:
            continue
        a, b = m["home"]["name"], away["name"]
        if a in W and b in W:
            ww += 1
        elif a in L and b in L:
            ll += 1
    return ww == 2 and ll == 2


def _backfill_cross_ord(
    cross_ord: List[Optional[dict]],
    cross_sets: List[Optional[FrozenSet[str]]],
    rest: List[dict],
) -> Tuple[List[Optional[dict]], List[dict]]:
    filled: List[Optional[dict]] = list(cross_ord)
    pool = list(rest)
    for i in range(min(4, len(filled))):
        if filled[i] is not None:
            continue
        teams = cross_sets[i] if i < len(cross_sets) else None
        pick_idx: Optional[int] = None
        if teams:
            for strict in (True, False):
                for j, m in enumerate(pool):
                    away = m.get("away")
                    if not away:
                        continue
                    if sheet_matchup_matches_expected_pair(m, teams, strict=strict):
                        pick_idx = j
                        break
                if pick_idx is not None:
                    break
        if pick_idx is None and pool:
            pick_idx = 0
        if pick_idx is not None:
            filled[i] = pool.pop(pick_idx)
    return filled, pool


def _backfill_parallel_sl(
    slots: List[Optional[dict]],
    groups: List[FrozenSet[str]],
    pool: List[dict],
) -> Tuple[List[Optional[dict]], List[dict]]:
    out: List[Optional[dict]] = []
    p = list(pool)
    for i, m in enumerate(slots):
        if m is not None:
            out.append(m)
            continue
        g = groups[i] if i < len(groups) else frozenset()
        pick_idx: Optional[int] = None
        if g:
            for strict in (True, False):
                for j, cand in enumerate(p):
                    away = cand.get("away")
                    if not away:
                        continue
                    if sheet_matchup_matches_expected_pair(cand, g, strict=strict):
                        pick_idx = j
                        break
                if pick_idx is not None:
                    break
        if pick_idx is None and p:
            pick_idx = 0
        if pick_idx is not None:
            out.append(p.pop(pick_idx))
        else:
            out.append(None)
    return out, p


def _week3_match_count(ms2: List[dict], w3_groups: List[Tuple[FrozenSet[str], str]]) -> int:
    if not ms2 or not w3_groups:
        return 0
    ord3, _ = order_matchups_by_labeled_groups(ms2, w3_groups)
    return sum(1 for _lab, mm in ord3 if mm is not None)


def _playoff_matchups_with_opponent(ms: List[dict]) -> List[dict]:
    """Sheet rows that are head-to-head (exclude lone 'advances' placeholders)."""
    return [m for m in ms if m.get("away")]


def _backfill_ordered_matchups(
    ordered: List[Tuple[str, Optional[dict]]],
    rest: List[dict],
) -> List[Tuple[str, Optional[dict]]]:
    pool = list(rest)
    out: List[Tuple[str, Optional[dict]]] = []
    for label, mm in ordered:
        if mm is None and pool:
            mm = pool.pop(0)
        out.append((label, mm))
    return out


def _w3_groups_from_snapshots_parallel(
    snapshots: List[Optional[dict]],
    ms1: List[dict],
) -> List[Tuple[FrozenSet[str], str]]:
    """Finals pairings from parallel semis (0-loss vs 0-loss, 1+ vs 1+)."""
    wb_ms, lb_ms, _other = _split_semis_by_playoff_loss_band(
        snapshots, ms1, losses_before_col=1
    )
    if len(wb_ms) != 2 or len(lb_ms) != 2:
        return []
    wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
    lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
    if not all(wb_semis) or not all(lb_semis):
        return []
    return expected_week3_groups(wb_semis[:2], lb_semis[:2])


def _w3_groups_from_ms1_parallel(
    qf_ms: List[dict], ms1: List[dict]
) -> List[Tuple[FrozenSet[str], str]]:
    """Finals pairings from parallel semis (WW / LL games in week 2)."""
    w_set, l_set = _qf_winner_loser_sets(qf_ms)
    if len(w_set) != 4 or len(l_set) != 4:
        return []
    wb_semis: List[Optional[SlotWL]] = []
    lb_semis: List[Optional[SlotWL]] = []
    for m in ms1:
        wl = winner_loser_from_matchup(m)
        if not wl:
            continue
        win, lose = wl
        if win in w_set and lose in w_set:
            wb_semis.append(wl)
        elif win in l_set and lose in l_set:
            lb_semis.append(wl)
    while len(wb_semis) < 2:
        wb_semis.append(None)
    while len(lb_semis) < 2:
        lb_semis.append(None)
    if not all(wb_semis[:2]) or not all(lb_semis[:2]):
        return []
    return expected_week3_groups(wb_semis[:2], lb_semis[:2])


def _collect_w3_group_candidates(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> List[List[Tuple[FrozenSet[str], str]]]:
    """Every plausible finals-week pairing model to score against the sheet."""
    candidates: List[List[Tuple[FrozenSet[str], str]]] = []
    seen: Set[Tuple[Tuple[str, ...], ...]] = set()

    def add(groups: List[Tuple[FrozenSet[str], str]]) -> None:
        if not groups:
            return
        key = tuple(
            tuple(sorted(t for t in teams)) + (label,)
            for teams, label in groups
        )
        if key in seen:
            return
        seen.add(key)
        candidates.append(groups)

    if snapshots is not None:
        loss_par = _parallel_model_from_loss_band(
            snapshots, ms1, ms2, qf_ms, round_pairs
        )
        if loss_par and loss_par.get("w3_groups"):
            add(list(loss_par["w3_groups"]))

    model = _pick_best_eight_team_placement_model(
        qf_ms, ms1, ms2, round_pairs, snapshots=snapshots
    )
    if model and model.get("w3_groups"):
        add(list(model["w3_groups"]))

    for qf_res in _qf_res_candidates(qf_ms, round_pairs):
        if not all(qf_res):
            continue
        cross_sets = expected_week2_cross_sets(qf_res)
        cross_ord, _ = matchups_by_cross_ordered_groups(ms1, cross_sets)
        semis_x = [winner_loser_from_matchup(m) if m else None for m in cross_ord]
        if len(semis_x) >= 4 and all(semis_x):
            add(expected_week3_groups_cross(semis_x))
        wb_g, lb_g = expected_week2_groups(qf_res)
        wb_ord, r1 = matchups_by_ordered_groups(ms1, wb_g)
        lb_ord, _ = matchups_by_ordered_groups(r1, lb_g)
        wb_semis = [winner_loser_from_matchup(m) if m else None for m in wb_ord]
        lb_semis = [winner_loser_from_matchup(m) if m else None for m in lb_ord]
        if (
            len(wb_semis) >= 2
            and len(lb_semis) >= 2
            and all(wb_semis[:2])
            and all(lb_semis[:2])
        ):
            add(expected_week3_groups(wb_semis[:2], lb_semis[:2]))

    add(_w3_groups_from_ms1_parallel(qf_ms, ms1))
    return candidates


def _best_w3_groups(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> List[Tuple[FrozenSet[str], str]]:
    ms2_played = _playoff_matchups_with_opponent(ms2)
    parallel_shape = _semis_week_parallel_shape(qf_ms, ms1, snapshots=snapshots)
    best_groups: List[Tuple[FrozenSet[str], str]] = []
    best_n = -1

    if parallel_shape:
        if snapshots is not None:
            snap_par = _w3_groups_from_snapshots_parallel(snapshots, ms1)
            if snap_par and _week3_match_count(ms2_played, snap_par) >= 3:
                return snap_par
        ms1_par = _w3_groups_from_ms1_parallel(qf_ms, ms1)
        if ms1_par and _week3_match_count(ms2_played, ms1_par) >= 3:
            return ms1_par
        if snapshots is not None:
            loss_par = _parallel_model_from_loss_band(
                snapshots, ms1, ms2, qf_ms, round_pairs
            )
            if loss_par and loss_par.get("w3_groups"):
                w3g = list(loss_par["w3_groups"])
                if _week3_match_count(ms2_played, w3g) >= 2:
                    return w3g

    for groups in _collect_w3_group_candidates(
        qf_ms, ms1, ms2_played, round_pairs, snapshots=snapshots
    ):
        n = _week3_match_count(ms2_played, groups)
        if n > best_n:
            best_n = n
            best_groups = groups

    if best_groups and best_n >= 2:
        return best_groups

    if parallel_shape:
        if snapshots is not None:
            snap_par = _w3_groups_from_snapshots_parallel(snapshots, ms1)
            if snap_par:
                return snap_par
        ms1_par = _w3_groups_from_ms1_parallel(qf_ms, ms1)
        if ms1_par:
            return ms1_par

    return best_groups


def _pick_best_eight_team_placement_model(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
    *,
    snapshots: Optional[List[Optional[dict]]] = None,
) -> Optional[dict]:
    """Choose QF slot labeling + cross vs parallel so week-2 fits 2+2 and week-3 placement groups match the sheet."""
    if snapshots is not None:
        loss_par = _parallel_model_from_loss_band(snapshots, ms1, ms2, qf_ms, round_pairs)
        if loss_par is not None and loss_par.get("w3_hits", 0) >= 3:
            out = dict(loss_par)
            out.pop("w3_hits", None)
            return out

    candidates = _qf_res_candidates(qf_ms, round_pairs)
    if not candidates:
        return None
    ms2_played = _playoff_matchups_with_opponent(ms2)
    best: Optional[dict] = None
    best_key: Tuple[int, int, int] = (-1, -1, -1)  # (week3 matches, week2 matches, shape bonus)
    shape_parallel = _semis_week_parallel_shape(qf_ms, ms1, snapshots=snapshots)

    def maybe_take(key: Tuple[int, int, int], row: dict) -> None:
        nonlocal best, best_key
        if key > best_key:
            best_key = key
            best = row
        elif key == best_key and best is not None:
            if row["kind"] == "parallel" and best["kind"] == "cross":
                best = row
            elif row["kind"] == "cross" and best["kind"] == "parallel":
                pass
            else:
                pr = prefer_crossover_week2(ms1, row["qf_res"])
                if (pr and row["kind"] == "cross") or (not pr and row["kind"] == "parallel"):
                    best = row

    for qf_res in candidates:
        cross_sets = expected_week2_cross_sets(qf_res)
        cross_ord, rest_c = matchups_by_cross_ordered_groups(ms1, cross_sets)
        cross_f, rest_xf = _backfill_cross_ord(cross_ord, cross_sets, rest_c)
        w2x = sum(1 for x in cross_f if x is not None)
        semis_x = [winner_loser_from_matchup(m) if m else None for m in cross_f]
        w3g_x: List[Tuple[FrozenSet[str], str]] = []
        if all(semis_x):
            w3g_x = expected_week3_groups_cross(semis_x)
        w3x = _week3_match_count(ms2_played, w3g_x)
        fit_bonus = 0 if shape_parallel else 1
        maybe_take(
            (w3x, w2x, fit_bonus),
            {"kind": "cross", "qf_res": qf_res, "cross_ord": cross_f, "cross_sets": cross_sets, "rest": rest_xf, "w3_groups": w3g_x},
        )

        wb_g, lb_g = expected_week2_groups(qf_res)
        if len(wb_g) >= 2 and len(lb_g) >= 2:
            wb_ord, r1 = matchups_by_ordered_groups(ms1, wb_g)
            lb_ord, r2 = matchups_by_ordered_groups(r1, lb_g)
            wb_f, pool2 = _backfill_parallel_sl(list(wb_ord), list(wb_g), list(r2))
            lb_f, rest_pf = _backfill_parallel_sl(list(lb_ord), list(lb_g), pool2)
            w2p = sum(1 for x in wb_f + lb_f if x is not None)
            wb_semis = [winner_loser_from_matchup(m) if m else None for m in wb_f]
            lb_semis = [winner_loser_from_matchup(m) if m else None for m in lb_f]
            w3g_p: List[Tuple[FrozenSet[str], str]] = []
            if len(wb_semis) >= 2 and len(lb_semis) >= 2 and all(wb_semis) and all(lb_semis):
                w3g_p = expected_week3_groups(wb_semis[:2], lb_semis[:2])
            w3p = _week3_match_count(ms2_played, w3g_p)
            par_bonus = 1 if shape_parallel else 0
            maybe_take(
                (w3p, w2p, par_bonus),
                {
                    "kind": "parallel",
                    "qf_res": qf_res,
                    "wb_ord": wb_f,
                    "lb_ord": lb_f,
                    "rest": rest_pf,
                    "w3_groups": w3g_p,
                },
            )

    return best


def _matchup_identity(m: dict) -> Tuple[str, ...]:
    away = m.get("away")
    if not away:
        return (m["home"]["name"],)
    return tuple(sorted((m["home"]["name"], away["name"])))


def _matchup_seed_sort_key(m: dict, seed_rank: Dict[str, int]) -> Tuple[int, int, str]:
    h = m["home"]["name"]
    a = m.get("away")
    if not a:
        return (seed_rank.get(h, 999), 999, h)
    an = a["name"]
    i1, i2 = seed_rank.get(h, 999), seed_rank.get(an, 999)
    return (min(i1, i2), max(i1, i2), h)


def _sort_matchups_with_alignment(
    matchups: List[dict], aligned: List[bool], seed_rank: Dict[str, int]
) -> Tuple[List[dict], List[bool]]:
    paired = list(zip(matchups, aligned))
    paired.sort(key=lambda p: _matchup_seed_sort_key(p[0], seed_rank))
    if not paired:
        return [], []
    ms, flags = zip(*paired)
    return list(ms), list(flags)


def _should_show_row_track_hints(ri: int, nr: int, aligned_to_slot: bool) -> bool:
    """When to show 1st/Lower row chrome: not first round; final round all; middle = aligned only."""
    if nr < 1:
        return False
    if ri == 0:
        return False
    if ri >= nr - 1:
        return True
    return aligned_to_slot


def _playoff_losses_through_prior_rounds(
    snapshots: List[Optional[dict]], before_col: int
) -> Dict[str, int]:
    """Playoff losses before column `before_col` begins (sheet weeks prior only)."""
    losses: Dict[str, int] = {}
    for ri in range(before_col):
        snap = snapshots[ri] if ri < len(snapshots) else None
        if not snap or not snap.get("matchups"):
            continue
        for m in snap["matchups"]:
            away = m.get("away")
            if not away:
                continue
            home, a = m["home"], away
            hr, ar = home.get("result", ""), away.get("result", "")
            if hr == "W" and ar == "L":
                losses[a["name"]] = losses.get(a["name"], 0) + 1
            elif ar == "W" and hr == "L":
                losses[home["name"]] = losses.get(home["name"], 0) + 1
    return losses


def _path_band(
    losses_before: Dict[str, int], hn: str, an: str
) -> Tuple[str, str, str]:
    """(short label, css suffix, hover blurb)."""
    la, lb = losses_before.get(hn, 0), losses_before.get(an, 0)
    if la == 0 and lb == 0:
        return (
            "1st place",
            "title",
            "Neither team had a playoff loss before this week — winner can still finish 1st.",
        )
    if la >= 1 and lb >= 1:
        return (
            "5th–8th place",
            "place",
            "Both teams already had a playoff loss — this game sorts the bottom half of the standings.",
        )
    return (
        "2nd–4th place",
        "mixed",
        "One team was still unbeaten in the playoffs and one had one loss before this week.",
    )


def _seed_rank_map(sorted_teams: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, int]:
    return {name: i for i, (name, _) in enumerate(sorted_teams)}


def _use_single_elim_connectors(
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
) -> bool:
    """False when the sheet runs a full field each week (everyone plays; placement rounds)."""
    nr = len(rounds)
    if nr < 2:
        return False
    for ri in range(nr):
        snap = snapshots[ri] if ri < len(snapshots) else None
        if not snap or not snap.get("matchups"):
            continue
        if len(snap["matchups"]) != len(rounds[ri]):
            return False
    return True


def _enriched_path_keys_distinct(enriched: List[Tuple[dict, Optional[str], Optional[str], Optional[str]]]) -> bool:
    keys = {e[2] for e in enriched if e[2]}
    return len(keys) > 1


def _slot_short_label(slot: BracketSlot) -> str:
    """Plain label for tooltips / compact bracket."""
    if slot is None:
        return "BYE"
    if isinstance(slot, str):
        return slot
    L, R = slot
    if isinstance(L, str) and isinstance(R, str):
        return f"{L} · {R}"
    return "Winner TBD"


def _theoretical_hover_inner_html(left: BracketSlot, right: BracketSlot) -> str:
    tl = html_module.escape(_slot_short_label(left))
    tr = html_module.escape(_slot_short_label(right))
    return (
        '<div class="bracket-pop-h">Seeded matchup</div>'
        f'<div class="bracket-pop-seed"><span class="bracket-pop-seed-l">Top</span>{tl}</div>'
        f'<div class="bracket-pop-seed"><span class="bracket-pop-seed-l">Bottom</span>{tr}</div>'
        '<div class="bracket-pop-meta">Winner advances to the next round.</div>'
    )


def _simple_theoretical_pair_html(left: BracketSlot, right: BracketSlot) -> str:
    def side_block(slot: BracketSlot) -> str:
        if slot is None:
            return '<span class="bracket-line bracket-line--ghost">—</span>'
        if isinstance(slot, str):
            st = _team_color_style(slot)
            return (
                f'<span class="bracket-line bracket-line--team" style="{st}">'
                f"{html_module.escape(slot)}</span>"
            )
        Ls, Rs = slot
        if isinstance(Ls, str) and isinstance(Rs, str):
            return (
                f'<span class="bracket-line bracket-line--mini">'
                f"{html_module.escape(Ls)} · {html_module.escape(Rs)}</span>"
            )
        return '<span class="bracket-line bracket-line--pending">Winner TBD</span>'

    extra = ""
    if (left is None) != (right is None):
        extra = '<span class="bracket-bye-tag">bye</span>'
    face = (
        f'<div class="bracket-pair bracket-pair--pending">'
        f'<div class="bracket-pair-side">{side_block(left)}</div>'
        f'<div class="bracket-pair-mid">vs</div>'
        f'<div class="bracket-pair-side">{side_block(right)}</div>'
        f"{extra}</div>"
    )
    pop = f'<aside class="bracket-pop">{_theoretical_hover_inner_html(left, right)}</aside>'
    return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'


def _hover_game_line_html(
    game_num: int,
    h_p: int,
    a_p: int,
    h_r: str,
    a_r: str,
    home_name: str,
    away_name: str,
) -> str:
    if h_p <= 0 and a_p <= 0:
        return ""
    if h_r == "W":
        winner_html = (
            f'<span style="{_team_color_style(home_name)}">'
            f"{html_module.escape(home_name)}</span>"
        )
    elif a_r == "W":
        winner_html = (
            f'<span style="{_team_color_style(away_name)}">'
            f"{html_module.escape(away_name)}</span>"
        )
    elif h_r == "T":
        winner_html = '<span class="bracket-pop-gr">Tie</span>'
    else:
        winner_html = '<span class="bracket-pop-gr">—</span>'
    return (
        f'<div class="bracket-pop-g">G{game_num}: {h_p:,}–{a_p:,} · {winner_html}</div>'
    )


def _matchup_hover_inner_html(m: dict, *, extra_meta: Optional[str] = None) -> str:
    """Structured HTML for bracket hover card (not a native tooltip)."""
    meta = ""
    if extra_meta:
        meta = f'<div class="bracket-pop-path">{html_module.escape(extra_meta)}</div>'
    home = m["home"]
    away = m.get("away")
    if not away:
        hp = int(home.get("pins", 0))
        nm = home["name"]
        return (
            meta
            + '<div class="bracket-pop-h">Bye</div>'
            f'<div class="bracket-pop-n" style="{_team_color_style(nm)}">{html_module.escape(nm)}</div>'
            f'<div class="bracket-pop-meta">Advances · Total pins {hp:,}</div>'
        )
    hn, an = home["name"], away["name"]
    hp, ap = int(home.get("pins", 0)), int(away.get("pins", 0))
    hr, ar = home.get("result", ""), away.get("result", "")

    def score_row(name: str, pins: int, res: str, style: str) -> str:
        return (
            f'<div class="bracket-pop-row">'
            f'<span class="bracket-pop-n" style="{style}">{html_module.escape(name)}</span>'
            f'<span class="bracket-pop-pins">{pins:,}</span>'
            f'<span class="bracket-pop-res">{html_module.escape(res)}</span></div>'
        )

    head = '<div class="bracket-pop-h">Match totals</div>'
    body = score_row(hn, hp, hr, _team_color_style(hn)) + score_row(an, ap, ar, _team_color_style(an))
    gbits: List[str] = []
    for i, row in enumerate(m.get("game_results") or []):
        if len(row) >= 4:
            line = _hover_game_line_html(i + 1, row[2], row[3], row[0], row[1], hn, an)
            if line:
                gbits.append(line)
    gp_h = home.get("game_pins") or []
    gp_a = away.get("game_pins") or []
    if (len(gp_h) > 4 or len(gp_a) > 4) and len(m.get("game_results") or []) < 5:
        hp5 = int(gp_h[4]) if len(gp_h) > 4 else 0
        ap5 = int(gp_a[4]) if len(gp_a) > 4 else 0
        if hp5 > 0 or ap5 > 0:
            if hp5 > ap5:
                h5_r, a5_r = "W", "L"
            elif ap5 > hp5:
                h5_r, a5_r = "L", "W"
            else:
                h5_r, a5_r = "T", "T"
            line = _hover_game_line_html(5, hp5, ap5, h5_r, a5_r, hn, an)
            if line:
                gbits.append(line)
    games_h = ""
    if gbits:
        games_h = '<div class="bracket-pop-gh">Games</div>' + "".join(gbits)
    return meta + head + body + games_h


def _bracket_name_result_class(res: str) -> str:
    if res == "W":
        return "bracket-name--w"
    if res == "L":
        return "bracket-name--l"
    if res == "T":
        return "bracket-name--tie"
    return "bracket-name--pending"


def _record_override_marker_html() -> str:
    return (
        '<span class="record-override-mark" '
        'title="Regular-season win–loss from sheet override (pin totals unchanged)">†</span>'
    )


def _bracket_result_badge_html(res: str) -> str:
    """Small inline badge so winners/losers are obvious without hovering."""
    if res == "W":
        return '<span class="bracket-badge bracket-badge--w" title="Won match">W</span>'
    if res == "L":
        return '<span class="bracket-badge bracket-badge--l" title="Lost match">L</span>'
    if res == "T":
        return '<span class="bracket-badge bracket-badge--t" title="Tie">T</span>'
    return ""


def _seed_display_map(sorted_teams: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, int]:
    return {name: i + 1 for i, (name, _) in enumerate(sorted_teams)}


def _matchup_series_games_won(side: Optional[dict], matchup: dict) -> Optional[int]:
    """Games won in this week's head-to-head (e.g. 3 in a 3–2 series)."""
    if not side:
        return None
    if not matchup.get("game_results") and side.get("result") in ("—", "", None):
        return None
    return int(side.get("wins", 0) or 0)


def _classic_team_row_cl(
    name: str,
    res: str,
    games_won: Optional[int],
    *,
    show_override_mark: bool = False,
) -> str:
    seed_el = (
        f'<span class="bracket-cl-seed" title="Games won in this matchup">{games_won}</span>'
        if games_won is not None
        else '<span class="bracket-cl-seed bracket-cl-seed--empty" title="Games won in this matchup">—</span>'
    )
    override_slot = (
        f'<span class="bracket-cl-override-slot">{_record_override_marker_html()}</span>'
        if show_override_mark
        else ""
    )
    trail = (
        f'<span class="bracket-cl-trail">'
        f"{override_slot}{_bracket_result_badge_html(res)}"
        f"</span>"
    )
    return (
        f'<div class="bracket-cl-row">'
        f"{seed_el}"
        f'<div class="bracket-cl-row-main">'
        f'<span class="bracket-line bracket-cl-name {_bracket_name_result_class(res)}" '
        f'style="{_team_color_style(name)}">{html_module.escape(name)}</span>'
        f"{trail}</div></div>"
    )



def _classic_match_block_html(
    m: dict,
    *,
    extra_meta: Optional[str] = None,
) -> str:
    overridden = bool(m.get("record_overridden"))
    away = m.get("away")
    if not away:
        nm = m["home"]["name"]
        row = _classic_team_row_cl(
            nm,
            m["home"].get("result", ""),
            _matchup_series_games_won(m["home"], m),
            show_override_mark=overridden,
        )
        pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
        return (
            f'<div class="bracket-cl-outer" tabindex="0">'
            f'<div class="bracket-cl-match">{row}</div>{pop}</div>'
        )
    home = m["home"]
    hn, an = home["name"], away["name"]
    hr, ar = home.get("result", ""), away.get("result", "")
    rowh = _classic_team_row_cl(
        hn, hr, _matchup_series_games_won(home, m), show_override_mark=overridden
    )
    rowa = _classic_team_row_cl(
        an, ar, _matchup_series_games_won(away, m), show_override_mark=overridden
    )
    pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
    return (
        f'<div class="bracket-cl-outer" tabindex="0">'
        f'<div class="bracket-cl-match">{rowh}{rowa}</div>{pop}</div>'
    )


def _classic_pending_line(label: str) -> str:
    return f'<div class="bracket-cl-pending">{html_module.escape(label)}</div>'


def _eight_team_week0_classic_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
) -> str:
    slots = qf_matchups_in_bracket_slot_order(list(snap["matchups"]), rounds[0])
    parts: List[str] = []
    for i, m in enumerate(slots):
        if m is None:
            parts.append(
                _classic_pending_line(
                    "Quarterfinal slot — not on the sheet yet, or pairings differ from standard seeds."
                )
            )
            continue
        meta = "Quarterfinal — winners bracket"
        if m.get("_bye_pair"):
            meta = "Quarterfinal bye — both teams advance without a head-to-head week"
        parts.append(
            _classic_match_block_html(
                m,
                extra_meta=meta,
            )
        )
    return "".join(parts)


def _eight_team_week2_cross_layout_html(
    cross_ord: List[Optional[dict]],
    cross_sets: List[Optional[FrozenSet[str]]],
    rest: List[dict],
) -> str:
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">'
        "Winners bracket — playing for 1st–4th place</div>"
    )
    for i, match_idx in enumerate((1, 2), start=1):
        mm = cross_ord[match_idx] if match_idx < len(cross_ord) else None
        meta = (
            "Semifinal on the winners side: the winner is still alive for 1st; "
            "the loser can still finish as high as 4th after finals week."
        )
        cs = cross_sets[match_idx] if match_idx < len(cross_sets) else None
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=meta,
                )
            )
        elif cs is not None:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">'
        "Losers bracket — playing for 5th–8th place</div>"
    )
    for i, match_idx in enumerate((0, 3), start=1):
        mm = cross_ord[match_idx] if match_idx < len(cross_ord) else None
        meta = (
            "Semifinal on the losers side: both teams already lost a quarterfinal; "
            "this week sorts who can still reach 5th vs who is in the 7th–8th game next week."
        )
        cs = cross_sets[match_idx] if match_idx < len(cross_sets) else None
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=meta,
                )
            )
        elif cs is not None:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m,
                extra_meta="Playoff game (could not match to winners/losers semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_cross_column(
    ms: List[dict],
    qf_res: List[Optional[Tuple[str, str]]],
) -> str:
    cross_sets = expected_week2_cross_sets(qf_res)
    cross_ord, rest = matchups_by_cross_ordered_groups(ms, cross_sets)
    return _eight_team_week2_cross_layout_html(cross_ord, cross_sets, rest)


def _eight_team_week2_parallel_layout_html(
    wb_ord: List[Optional[dict]],
    lb_ord: List[Optional[dict]],
    rest: List[dict],
) -> str:
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">Winners bracket — playing for 1st–4th place</div>'
    )
    for idx, mm in enumerate(wb_ord):
        meta = "Winners bracket semifinal — quarterfinal winners from the same half of the draw"
        if mm:
            sec.append(_classic_match_block_html(mm, extra_meta=meta))
        elif idx < 2:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">Losers bracket — playing for 5th–8th place</div>'
    )
    for idx, mm in enumerate(lb_ord):
        meta = (
            "Losers bracket semifinal — quarterfinal losers from the same half of the draw "
            "(same pattern as the winners semifinal in that half)."
        )
        if mm:
            sec.append(_classic_match_block_html(mm, extra_meta=meta))
        elif idx < 2:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m,
                extra_meta="Playoff game (could not match to semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_loss_bucket_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    """When QF pairings are non-standard, split week-2 games by playoff-loss count before this week."""
    losses_before = _playoff_losses_through_prior_rounds(snapshots, 1)
    ms = list(snap["matchups"])
    upper: List[dict] = []
    lower: List[dict] = []
    upper_solos: List[dict] = []
    lower_solos: List[dict] = []
    for m in ms:
        away = m.get("away")
        if not away:
            continue
        hn, an = m["home"]["name"], away["name"]
        la, lb = losses_before.get(hn, 0), losses_before.get(an, 0)
        if la >= 1 and lb >= 1:
            lower.append(m)
        else:
            upper.append(m)
    paired_sf = set()
    for m in upper + lower:
        away = m.get("away")
        if away:
            paired_sf.add(m["home"]["name"])
            paired_sf.add(away["name"])
    for m in ms:
        if m.get("away"):
            continue
        hn = m["home"]["name"]
        if hn in paired_sf:
            continue
        if losses_before.get(hn, 0) >= 1:
            lower_solos.append(m)
        else:
            upper_solos.append(m)
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">'
        "Winners bracket — playing for 1st–4th place</div>"
    )
    meta_u = (
        "Semifinal week — at least one team has no quarterfinal loss "
        "(or custom draw: mixed winner/loser games are listed here when the sheet does not follow standard seeds)."
    )
    for mm in upper:
        sec.append(_classic_match_block_html(mm, extra_meta=meta_u))
    for mm in upper_solos:
        sec.append(
            _classic_match_block_html(
                mm,
                extra_meta="Bye week — advances without a head-to-head semifinal matchup on the sheet.",
            )
        )
    if len(upper) + len(upper_solos) < 2:
        sec.append(
            _classic_pending_line(
                "Expected winners-bracket semifinal — not on the sheet yet, or still a bye week."
            )
        )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">'
        "Losers bracket — playing for 5th–8th place</div>"
    )
    meta_l = (
        "Both teams lost in the quarterfinals — this week sorts placement in the bottom half of the playoffs."
    )
    for mm in lower:
        sec.append(_classic_match_block_html(mm, extra_meta=meta_l))
    for mm in lower_solos:
        sec.append(
            _classic_match_block_html(
                mm,
                extra_meta="Bye week — advances without a head-to-head semifinal matchup on the sheet.",
            )
        )
    if len(lower) + len(lower_solos) < 2:
        sec.append(
            _classic_pending_line(
                "Expected losers-bracket semifinal — not on the sheet yet, or still a bye week."
            )
        )
    sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_placement_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    if not snap0 or not snap0.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap["matchups"])
    ms2: List[dict] = []
    if len(snapshots) > 2 and snapshots[2] and snapshots[2].get("matchups"):
        ms2 = list(snapshots[2]["matchups"])
    model = _pick_best_eight_team_placement_model(
        qf_ms, ms1, ms2, rounds[0], snapshots=snapshots
    )
    if model is None:
        return _eight_team_week2_loss_bucket_column(snap, snapshots)
    if model["kind"] == "cross":
        n_filled = sum(1 for x in model["cross_ord"] if x is not None)
    else:
        n_filled = sum(1 for x in model["wb_ord"] + model["lb_ord"] if x is not None)
    if n_filled < 4:
        return _eight_team_week2_loss_bucket_column(snap, snapshots)
    if model["kind"] == "cross":
        return _eight_team_week2_cross_layout_html(
            model["cross_ord"], model["cross_sets"], model["rest"]
        )
    return _eight_team_week2_parallel_layout_html(
        model["wb_ord"], model["lb_ord"], model["rest"]
    )


def _eight_team_path_band_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    *,
    losses_before_col: int,
) -> str:
    """Group matchups by playoff-loss bands (1st, 3rd–4th, 5th–8th, etc.)."""
    all_ms = list(snap["matchups"])
    ms2 = _playoff_matchups_with_opponent(all_ms)
    solos = [m for m in all_ms if not m.get("away")]
    losses = _playoff_losses_through_prior_rounds(snapshots, losses_before_col)
    title_g: List[dict] = []
    mixed_g: List[dict] = []
    place_g: List[dict] = []
    title_s: List[dict] = []
    mixed_s: List[dict] = []
    place_s: List[dict] = []
    for m in ms2:
        away = m.get("away")
        if not away:
            continue
        hn, an = m["home"]["name"], away["name"]
        _lbl, key, _blur = _path_band(losses, hn, an)
        if key == "title":
            title_g.append(m)
        elif key == "mixed":
            mixed_g.append(m)
        else:
            place_g.append(m)
    for m in solos:
        hn = m["home"]["name"]
        n = losses.get(hn, 0)
        if n == 0:
            title_s.append(m)
        elif len(mixed_g) + len(mixed_s) < 2:
            mixed_s.append(m)
        else:
            place_s.append(m)
    sections: List[Tuple[str, str, List[dict]]] = [
        ("title", "1st & 2nd place", title_g + title_s),
        ("mixed", "3rd & 4th place", mixed_g + mixed_s),
        ("place", "5th & 6th place", place_g[:1] + place_s[:1]),
        ("place", "7th & 8th place", place_g[1:2] + place_s[1:2]),
    ]
    sec: List[str] = []
    for hkey, label, items in sections:
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">'
            f"{html_module.escape(label)}</div>"
        )
        if items:
            for mm in items:
                sec.append(
                    _classic_match_block_html(
                        mm,
                        extra_meta=label,
                    )
                )
        else:
            sec.append(
                _classic_pending_line(
                    "Placement game not on the sheet yet, or team had a bye this week."
                )
            )
        sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week3_path_band_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    return _eight_team_path_band_column(
        snap, snapshots, losses_before_col=2
    )


def _eight_team_two_week_finals_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    """Week 2 of a two-week playoff: placement games after quarterfinals only."""
    return _eight_team_path_band_column(
        snap, snapshots, losses_before_col=1
    )


def _is_two_week_eight_team_playoffs(
    pweeks: List[int],
    snapshots: List[Optional[dict]],
    n_teams: int,
) -> bool:
    if n_teams != 8 or len(pweeks) != 2:
        return False
    return any(s and s.get("matchups") for s in snapshots[:2])


def _labeled_placement_column_html(
    snap: dict,
    w3_groups: List[Tuple[FrozenSet[str], str]],
    *,
    pending_msg: str,
) -> str:
    """Four placement games with 1st–2nd, 3rd–4th, etc. labels."""
    ms2 = _playoff_matchups_with_opponent(list(snap["matchups"]))
    ordered, rest = order_matchups_by_labeled_groups(ms2, w3_groups)
    ordered = _backfill_ordered_matchups(ordered, rest)
    used_ids = {_matchup_identity(mm) for _lb, mm in ordered if mm is not None}
    rest_ms = [m for m in ms2 if _matchup_identity(m) not in used_ids]
    sec: List[str] = []
    for label, mm in ordered:
        if label.startswith("1st"):
            hkey = "title"
        elif "3rd" in label or "4th" in label:
            hkey = "mixed"
        else:
            hkey = "place"
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">'
            f"{html_module.escape(label)}</div>"
        )
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=label,
                )
            )
        else:
            sec.append(_classic_pending_line(pending_msg))
        sec.append("</div>")
    if rest_ms:
        sec.append(
            '<div class="bracket-subsec">'
            '<div class="bracket-subsec-h bracket-subsec-h--mixed">Other matchups</div>'
        )
        for m in rest_ms:
            sec.append(
                _classic_match_block_html(
                    m, extra_meta="Playoff matchup"
                )
            )
        sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _matchup_seed_rank_sum(m: dict, seed_rank: Dict[str, int]) -> int:
    away = m.get("away")
    if not away:
        return 9999
    h, a = m["home"]["name"], away["name"]
    return seed_rank.get(h, 99) + seed_rank.get(a, 99)


def _resolve_two_week_parallel_playoffs(
    snapshots: List[Optional[dict]],
    seed_rank: Optional[Dict[str, int]] = None,
) -> Optional[dict]:
    """Semifinals week (parallel WB/LB) + labeled placement finals — no quarterfinals."""
    if len(snapshots) < 2:
        return None
    snap0, snap1 = snapshots[0], snapshots[1]
    if not snap0 or not snap1 or not snap0.get("matchups") or not snap1.get("matchups"):
        return None
    ms1 = _playoff_matchups_with_opponent(list(snap0["matchups"]))
    ms2 = _playoff_matchups_with_opponent(list(snap1["matchups"]))
    if len(ms1) != 4 or len(ms2) < 2:
        return None

    sr = seed_rank or {}
    best: Optional[dict] = None
    best_key: Tuple[int, int] = (-1, -9999)  # (finals hits, -wb seed sum)
    for wb_idx in itertools.combinations(range(4), 2):
        lb_idx = [i for i in range(4) if i not in wb_idx]
        wb_ms = [ms1[i] for i in wb_idx]
        lb_ms = [ms1[i] for i in lb_idx]
        wb_semis = [winner_loser_from_matchup(m) for m in wb_ms]
        lb_semis = [winner_loser_from_matchup(m) for m in lb_ms]
        if not all(wb_semis) or not all(lb_semis):
            continue
        w3g = expected_week3_groups(wb_semis[:2], lb_semis[:2])
        hits = _week3_match_count(ms2, w3g)
        wb_seed_sum = sum(_matchup_seed_rank_sum(m, sr) for m in wb_ms)
        key = (hits, -wb_seed_sum)
        if key > best_key:
            best_key = key
            used = {_matchup_identity(m) for m in wb_ms + lb_ms}
            rest = [m for m in ms1 if _matchup_identity(m) not in used]
            best = {
                "wb_ord": wb_ms,
                "lb_ord": lb_ms,
                "w3_groups": w3g,
                "rest": rest,
                "hits": hits,
            }
    if best is None or best["hits"] < 2:
        return None
    return best


def _eight_team_two_week_labeled_finals_column(
    snap: dict,
    w3_groups: List[Tuple[FrozenSet[str], str]],
) -> str:
    return _labeled_placement_column_html(
        snap,
        w3_groups,
        pending_msg=(
            "Placement game not on the sheet yet, or teams still TBD from semifinals."
        ),
    )


def _eight_team_week3_placement_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    snap1 = snapshots[1] if len(snapshots) > 1 else None
    if not snap0 or not snap0.get("matchups") or not snap1 or not snap1.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap1["matchups"])
    ms2 = _playoff_matchups_with_opponent(list(snap["matchups"]))
    if not ms2:
        return _eight_team_week3_path_band_column(snap, snapshots)
    w3 = _best_w3_groups(qf_ms, ms1, ms2, rounds[0], snapshots=snapshots)
    if not w3 or _week3_match_count(ms2, w3) < 2:
        return _eight_team_week3_path_band_column(snap, snapshots)
    ordered, rest = order_matchups_by_labeled_groups(ms2, w3)
    ordered = _backfill_ordered_matchups(ordered, rest)
    used_ids = {_matchup_identity(mm) for _lb, mm in ordered if mm is not None}
    rest = [m for m in ms2 if _matchup_identity(m) not in used_ids]
    sec: List[str] = []
    for label, mm in ordered:
        if label.startswith("1st"):
            hkey = "title"
        elif "3rd" in label or "4th" in label:
            hkey = "mixed"
        else:
            hkey = "place"
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">{html_module.escape(label)}</div>'
        )
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=label,
                )
            )
        else:
            sec.append(
                _classic_pending_line(
                    "Matchup not in data or teams still TBD from the prior playoff week."
                )
            )
        sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m, extra_meta="Playoff matchup (extra)"
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _bracket_team_track_hint_html(team_name: str, losses_before: Dict[str, int]) -> Tuple[str, str]:
    """Row modifier class + hint markup from playoff losses before this week."""
    n = losses_before.get(team_name, 0)
    if n == 0:
        return (
            " bracket-pair-line--champ",
            '<span class="bracket-track-hint bracket-track-hint--champ" '
            'title="Still in the hunt for 1st place — no playoff losses before this week">1st</span>',
        )
    return (
        " bracket-pair-line--place",
        '<span class="bracket-track-hint bracket-track-hint--place" '
        'title="Already took a playoff loss — still bowling for final rank (often 3rd–8th)">Lower</span>',
    )


def _bracket_team_rows_html(
    hn: str,
    an: str,
    hr: str,
    ar: str,
    losses_before: Optional[Dict[str, int]],
) -> str:
    """Two team lines with optional row hints for who is still playing for 1st vs lower spots."""

    def one(name: str, res: str) -> str:
        if losses_before is None:
            track = ""
            hint = ""
        else:
            track, hint = _bracket_team_track_hint_html(name, losses_before)
        return (
            f'<div class="bracket-pair-line bracket-pair-line--row{track}">'
            f'<div class="bracket-line-with-hint">'
            f'<span class="bracket-line {_bracket_name_result_class(res)}" style="{_team_color_style(name)}">'
            f"{html_module.escape(name)}</span>"
            f"{hint}</div>"
            f"{_bracket_result_badge_html(res)}</div>"
        )

    return one(hn, hr) + one(an, ar)


def _snapshot_matchup_wrap(
    m: dict,
    *,
    path_label: Optional[str],
    path_key: Optional[str],
    path_blurb: Optional[str],
    show_path_chip: bool,
    losses_before: Optional[Dict[str, int]] = None,
) -> str:
    pair_mod = f" bracket-pair--path-{path_key}" if path_key else ""
    chip = ""
    if show_path_chip and path_label and path_key:
        chip = (
            f'<div class="bracket-path-chip bracket-path-chip--{path_key}">'
            f"{html_module.escape(path_label)}</div>"
        )
    home = m["home"]
    away = m.get("away")
    pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=path_blurb)}</aside>'
    if not away:
        nm = home["name"]
        if losses_before is None:
            face = (
                f'<div class="bracket-pair bracket-pair--bye{pair_mod}">'
                f"{chip}"
                f'<span class="bracket-line bracket-line--team" style="{_team_color_style(nm)}">'
                f"{html_module.escape(nm)}</span>"
                f'<span class="bracket-bye-note">advances</span></div>'
            )
        else:
            track, hint = _bracket_team_track_hint_html(nm, losses_before)
            face = (
                f'<div class="bracket-pair bracket-pair--bye{pair_mod}">'
                f"{chip}"
                f'<div class="bracket-pair-line bracket-pair-line--row{track}">'
                f'<div class="bracket-line-with-hint">'
                f'<span class="bracket-line bracket-line--team" style="{_team_color_style(nm)}">'
                f"{html_module.escape(nm)}</span>"
                f"{hint}</div></div>"
                f'<span class="bracket-bye-note">advances</span></div>'
            )
        return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'
    hn, an = home["name"], away["name"]
    hr, ar = home.get("result", ""), away.get("result", "")
    face = (
        f'<div class="bracket-pair{pair_mod}">'
        f"{chip}"
        f"{_bracket_team_rows_html(hn, an, hr, ar, losses_before)}"
        f"</div>"
    )
    return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'


def _playoff_snapshot_column_html(
    snap: dict,
    ri: int,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    *,
    split_placement_groups: bool,
    eight_placement_layout: bool = False,
    classic_skin: bool = False,
    two_week_playoffs: bool = False,
    two_week_parallel: Optional[dict] = None,
) -> str:
    seed_rank = _seed_rank_map(sorted_teams)
    nr = len(rounds)
    if (
        eight_placement_layout
        and nr == 3
        and len(rounds[0]) == 4
        and snap
        and snap.get("matchups")
    ):
        if ri == 0 and classic_skin:
            if two_week_parallel:
                return _eight_team_week2_parallel_layout_html(
                    two_week_parallel["wb_ord"],
                    two_week_parallel["lb_ord"],
                    two_week_parallel.get("rest", []),
                )
            return _eight_team_week0_classic_column(snap, rounds)
        if ri == 1 and two_week_playoffs:
            if two_week_parallel and two_week_parallel.get("w3_groups"):
                return _eight_team_two_week_labeled_finals_column(
                    snap, two_week_parallel["w3_groups"]
                )
            return _eight_team_two_week_finals_column(snap, snapshots)
        if ri == 1:
            w2 = _eight_team_week2_placement_column(
                snap, rounds, snapshots
            )
            if w2 is not None:
                return w2
        if ri == 2:
            w3 = _eight_team_week3_placement_column(snap, snapshots, rounds)
            if w3 is not None:
                return w3

    ms = list(snap["matchups"])
    if ri < len(rounds):
        ms, track_aligned = _match_matchups_to_theoretical_round(ms, rounds[ri])
    else:
        track_aligned = [True] * len(ms)
    ms, track_aligned = _sort_matchups_with_alignment(ms, track_aligned, seed_rank)
    losses_before = _playoff_losses_through_prior_rounds(snapshots, ri)
    align_by = {_matchup_identity(m): a for m, a in zip(ms, track_aligned)}
    enriched: List[Tuple[dict, Optional[str], Optional[str], Optional[str]]] = []
    for m in ms:
        away = m.get("away")
        if not away:
            enriched.append((m, None, None, None))
            continue
        hn, an = m["home"]["name"], away["name"]
        label, pkey, blurb = _path_band(losses_before, hn, an)
        enriched.append((m, label, pkey, blurb))

    multi = split_placement_groups and ri > 0 and _enriched_path_keys_distinct(enriched)
    if not multi:
        parts: List[str] = []
        for j, (m, label, pkey, blurb) in enumerate(enriched):
            af = track_aligned[j]
            show_row_track = _should_show_row_track_hints(ri, nr, af)
            lb = losses_before if show_row_track else None
            chip_on = ri > 0 and not multi and show_row_track
            parts.append(
                _snapshot_matchup_wrap(
                    m,
                    path_label=label,
                    path_key=pkey,
                    path_blurb=blurb,
                    show_path_chip=chip_on,
                    losses_before=lb,
                )
            )
        return "".join(parts)

    buckets: Dict[str, List[Tuple[dict, Optional[str], Optional[str], Optional[str]]]] = {
        "title": [],
        "mixed": [],
        "place": [],
    }
    for row in enriched:
        _m, _lab, pk, _b = row
        if pk is None:
            buckets["title"].append(row)
        elif pk in buckets:
            buckets[pk].append(row)
        else:
            buckets["mixed"].append(row)

    titles = {
        "title": "1st place (no playoff losses yet)",
        "mixed": "2nd–4th place",
        "place": "5th–8th place",
    }
    section_parts: List[str] = []
    for key in ("title", "mixed", "place"):
        rows = buckets[key]
        if not rows:
            continue
        inner = "".join(
            _snapshot_matchup_wrap(
                m,
                path_label=lab,
                path_key=pk,
                path_blurb=blob,
                show_path_chip=False,
                losses_before=(
                    losses_before
                    if _should_show_row_track_hints(
                        ri, nr, align_by.get(_matchup_identity(m), False)
                    )
                    else None
                ),
            )
            for (m, lab, pk, blob) in rows
        )
        section_parts.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{key}">{html_module.escape(titles[key])}</div>'
            f"{inner}</div>"
        )
    return f'<div class="bracket-tcell-inner">{"".join(section_parts)}</div>'


def _bracket_round_title(
    round_idx: int,
    num_rounds: int,
    *,
    two_week_playoffs: bool = False,
    two_week_parallel_semis: bool = False,
) -> str:
    if two_week_playoffs and num_rounds == 2:
        if two_week_parallel_semis:
            return ("Semifinals", "Placement finals")[round_idx]
        return ("Quarterfinals", "Placement finals")[round_idx]
    dist = num_rounds - 1 - round_idx
    if dist == 0:
        return "Final"
    if dist == 1:
        return "Semifinals"
    if dist == 2:
        return "Quarterfinals"
    return f"Round {round_idx + 1}"


def build_playoff_bracket_html(
    season: str,
    seeding_week: int,
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    playoff_week_numbers: Optional[List[int]] = None,
    playoff_matchups_by_round: Optional[List[Optional[dict]]] = None,
) -> str:
    """sorted_teams: best first, (name, stats).

    If playoff_week_numbers / playoff_matchups_by_round are set, each index aligns with a bracket
    column and shows compact names with a styled hover card for scores and games; otherwise seeds.
    """
    snapshots = playoff_matchups_by_round or []
    champion_team = champion_from_playoff_snapshots(snapshots)
    headers = [
        {"label": "Seed", "right": True},
        {"label": "Team"},
        {"label": "Record"},
        {"label": "Avg", "right": True},
        {"label": "Pins", "right": True},
    ]
    rows = []
    for i, (name, stats) in enumerate(sorted_teams, 1):
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        t = stats.get("ties", 0)
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        if stats.get("record_override_mark"):
            record += _record_override_marker_html()
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _team_name_cell_html(name, champion_team),
                "cls": "name-col",
                "style": _team_color_style(name),
                "sort": name.lower(),
            },
            {"val": record, "cls": "record", "sort": w * 10000 + l * 100 + t},
            {"val": f"{avg:.1f}", "cls": "right gold"},
            {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
        ])
    seed_section = _list_section(
        f"Seeds (record through week {seeding_week})",
        headers,
        rows,
    )
    nr = len(rounds)
    pweeks = playoff_week_numbers or []
    num_cols = max(len(rounds), len(pweeks))

    use_elim_svg = _use_single_elim_connectors(rounds, snapshots)
    split_placement = not use_elim_svg
    has_playoff_data = any(s and s.get("matchups") for s in snapshots)
    n_teams = len(sorted_teams)
    eight_placement_layout = (
        split_placement
        and has_playoff_data
        and n_teams == 8
        and nr == 3
        and bool(rounds)
        and len(rounds[0]) == 4
    )
    classic_skin = eight_placement_layout
    two_week_playoffs = _is_two_week_eight_team_playoffs(pweeks, snapshots, n_teams)
    seed_rank_for_resolve = {name: i for i, (name, _) in enumerate(sorted_teams)}
    two_week_parallel = (
        _resolve_two_week_parallel_playoffs(snapshots, seed_rank_for_resolve)
        if two_week_playoffs
        else None
    )
    if two_week_playoffs:
        num_cols = 2

    header_frag: List[str] = []
    track_frag: List[str] = []
    title_rounds = 2 if two_week_playoffs else nr
    two_week_parallel_semis = bool(two_week_parallel)
    for ri in range(num_cols):
        snap = snapshots[ri] if ri < len(snapshots) else None
        pw = pweeks[ri] if ri < len(pweeks) else None
        has_actual = bool(snap and snap.get("matchups"))

        if has_actual and pw is not None:
            disp = (
                _bracket_round_title(
                    ri,
                    title_rounds,
                    two_week_playoffs=two_week_playoffs,
                    two_week_parallel_semis=two_week_parallel_semis,
                )
                if ri < title_rounds
                else f"Week {pw}"
            )
            col_title = html_module.escape(disp)
            wk_line = f'<div class="wk-chip">Week {pw}</div>'
            body = _playoff_snapshot_column_html(
                snap,
                ri,
                rounds,
                snapshots,
                sorted_teams,
                split_placement_groups=split_placement,
                eight_placement_layout=eight_placement_layout,
                classic_skin=classic_skin,
                two_week_playoffs=two_week_playoffs,
                two_week_parallel=two_week_parallel,
            )
            header_frag.append(
                f'<div class="bracket-hcell">'
                f'<div class="section-title" style="margin-bottom:4px;">{col_title}</div>{wk_line}</div>'
            )
            track_frag.append(f'<div class="bracket-tcell">{body}</div>')
        elif ri < len(rounds):
            title_disp = html_module.escape(
                _bracket_round_title(
                    ri,
                    title_rounds,
                    two_week_playoffs=two_week_playoffs,
                    two_week_parallel_semis=two_week_parallel_semis,
                )
                if title_rounds
                else f"Round {ri + 1}"
            )
            matches = rounds[ri]
            blocks = [_simple_theoretical_pair_html(left, right) for left, right in matches]
            wk_pending = ""
            if pw is not None and not has_actual:
                wk_pending = f'<div class="wk-chip">Week {pw} · no matchup data yet</div>'
            header_frag.append(
                f'<div class="bracket-hcell">'
                f'<div class="section-title" style="margin-bottom:4px;">{title_disp}</div>{wk_pending}</div>'
            )
            track_frag.append(f'<div class="bracket-tcell">{"".join(blocks)}</div>')
        else:
            if pw is not None:
                header_frag.append(
                    f'<div class="bracket-hcell">'
                    f'<div class="section-title" style="margin-bottom:4px;">'
                    f'{html_module.escape(f"Week {pw}")}</div>'
                    f'<div class="wk-chip">No matchup data yet</div></div>'
                )
                track_frag.append(
                    '<div class="bracket-tcell"><span class="bracket-idle">—</span></div>'
                )
            else:
                title_disp = html_module.escape(
                    _bracket_round_title(
                        ri,
                        title_rounds,
                        two_week_playoffs=two_week_playoffs,
                        two_week_parallel_semis=two_week_parallel_semis,
                    )
                    if title_rounds
                    else f"Round {ri + 1}"
                )
                header_frag.append(
                    f'<div class="bracket-hcell">'
                    f'<div class="section-title" style="margin-bottom:4px;">{title_disp}</div></div>'
                )
                track_frag.append(
                    '<div class="bracket-tcell"><span class="bracket-idle">—</span></div>'
                )

    n_leaf = len(rounds[0]) * 2 if rounds else 1
    h_px = float(n_leaf * BRACKET_MATCH_SLOT_PX)
    w_px = float(num_cols * BRACKET_COL_W_PX + max(0, num_cols - 1) * BRACKET_GAP_PX)
    center_rows = _bracket_center_rows(n_leaf, float(BRACKET_MATCH_SLOT_PX))
    n_draw = min(num_cols, len(center_rows))
    svg = (
        _bracket_connectors_svg(
            center_rows,
            n_draw,
            w_px,
            h_px,
            stroke="rgba(238, 240, 252, 0.78)" if classic_skin else "#7c6ec4",
            stroke_opacity=1.0 if classic_skin else 0.95,
        )
        if use_elim_svg and n_leaf >= 2 and n_draw >= 2
        else ""
    )
    wrap_cls = "bracket-wrap" + (" bracket-wrap--classic" if classic_skin else "")
    grid_cls = "bracket-grid-main" + (" bracket-grid-main--classic" if classic_skin else "")
    bracket_fit_w = int(w_px)
    bracket_fit_h = int(h_px + BRACKET_HEADER_ROW_PX + 4)
    bracket_inner = (
        f'<div class="bracket-shell" style="--bf-slots: {n_leaf};" '
        f'data-bracket-w="{bracket_fit_w}" data-bracket-h="{bracket_fit_h}">'
        f'<div class="bracket-headers-row">{"".join(header_frag)}</div>'
        f'<div class="{grid_cls}">'
        '<div class="bracket-main-tracks">'
        f"{svg}"
        f'<div class="bracket-tracks-row">{"".join(track_frag)}</div>'
        "</div>"
        "</div></div>"
    )
    bracket_section = (
        f'<div class="section"><div class="section-title">Bracket</div>'
        f'<div class="{wrap_cls}">{_bracket_zoom_viewport_html(bracket_inner)}</div></div>'
    )
    css = (
        _LIST_CSS
        + _BRACKET_EXTRA_CSS
        + """
body.page-playoffs {
  width: 100% !important;
  max-width: min(1320px, 98vw) !important;
  margin: 0 auto !important;
}
body.page-playoffs .container {
  max-width: none !important;
  width: 100% !important;
  padding: 20px 16px !important;
}
"""
    )
    subtitle = (
        f"{html_module.escape(season)} &nbsp;·&nbsp; "
        f"Seeding through week {seeding_week} &nbsp;·&nbsp; "
        f"{len(sorted_teams)} teams"
    )
    return _render_list_page(
        css=css,
        title="🏆 PLAYOFFS",
        subtitle=subtitle,
        sections=seed_section + bracket_section,
        extra_script=_BRACKET_PAN_SCRIPT,
        body_class="page-playoffs",
    )


# ---------------------------------------------------------------------------
# Best scores hub (players / teams with view tabs)
# ---------------------------------------------------------------------------

_BEST_SCORES_HUB_CSS = """
.best-scores-hub-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0 0 14px;
}
.best-scores-hub-tab {
    font: inherit;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 7px 12px;
    border-radius: 6px;
    border: 1px solid #4a4068;
    background: #1e1a32;
    color: #c4b8e8;
    cursor: pointer;
}
.best-scores-hub-tab:hover {
    border-color: #7c6ec4;
    color: #fff;
}
.best-scores-hub-tab.is-active,
.best-scores-hub-tab[aria-pressed="true"] {
    border-color: #7c6ec4;
    background: #2d1b69;
    color: #ffb86c;
}
.best-scores-hub-panel[hidden] { display: none !important; }
.best-scores-hub-empty {
    margin: 0;
    padding: 12px 0 4px;
    color: #9a96a8;
    font-size: 13px;
    line-height: 1.5;
}
"""

_BEST_SCORES_HUB_SCRIPT = r"""<script>
(function () {
  document.querySelectorAll(".best-scores-hub").forEach(function (hub) {
    var tabs = hub.querySelectorAll("[data-view-tab]");
    var panels = hub.querySelectorAll("[data-view-panel]");
    var initial = hub.getAttribute("data-initial-view") || "weeks";
    function activate(view) {
      tabs.forEach(function (t) {
        var on = t.getAttribute("data-view-tab") === view;
        t.setAttribute("aria-pressed", on ? "true" : "false");
        t.classList.toggle("is-active", on);
      });
      panels.forEach(function (p) {
        p.hidden = p.getAttribute("data-view-panel") !== view;
      });
    }
    function notifyParentCloseNav() {
      if (window.self === window.top) return;
      try {
        parent.postMessage({ type: "bowlbot-close-nav" }, window.location.origin);
      } catch (err) { /* ignore */ }
    }
    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        activate(t.getAttribute("data-view-tab"));
        notifyParentCloseNav();
      });
    });
    activate(initial);
  });
})();
</script>"""


def _normalize_scores_hub_view(view: Optional[str]) -> str:
    v = (view or "weeks").strip().lower()
    if v in ("game", "games"):
        return "games"
    if v in ("average", "averages", "avg", "season"):
        return "averages"
    return "weeks"


def _scores_hub_tabs_html(initial_view: str) -> str:
    initial = _normalize_scores_hub_view(initial_view)
    tabs = (
        ("weeks", "Best weeks"),
        ("games", "Best games"),
        ("averages", "Best seasons"),
    )
    parts = ['<div class="best-scores-hub-tabs" role="tablist">']
    for key, label in tabs:
        pressed = "true" if key == initial else "false"
        active = " is-active" if key == initial else ""
        parts.append(
            f'<button type="button" class="best-scores-hub-tab{active}" '
            f'data-view-tab="{key}" role="tab" aria-pressed="{pressed}">'
            f"{html_module.escape(label)}</button>"
        )
    parts.append("</div>")
    return "".join(parts)


def _scores_hub_panel(view: str, inner: str, *, hidden: bool) -> str:
    hidden_attr = " hidden" if hidden else ""
    return (
        f'<div class="best-scores-hub-panel" data-view-panel="{view}"{hidden_attr}>'
        f"{inner}</div>"
    )


def _top_player_games_section(games: list, n: int) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Score", "right": True},
        {"label": "Wk", "right": True},
    ]
    rows = []
    for i, (player, team, week, score) in enumerate(games[:n], 1):
        rows.append([
            {"val": i, "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": team, "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": int(score), "cls": "right gold"},
            {"val": week, "cls": "right sub-col"},
        ])
    return _list_section(f"Top {n} individual games", headers, rows)


def _top_player_weeks_section(weeks: list, n: int) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Avg", "right": True},
        {"label": "Wk", "right": True},
        {"label": "Games", "right": True},
        {"label": "Total", "right": True},
    ]
    rows = []
    for i, week_data in enumerate(weeks[:n], 1):
        if len(week_data) == 5:
            player, team, week, total, num_games = week_data
        else:
            player, team, week, total = week_data
            num_games = 0
        week_avg = total / num_games if num_games else 0
        rows.append([
            {"val": i, "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": team, "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": f"{week_avg:.1f}", "cls": "right gold", "sort": week_avg},
            {"val": week, "cls": "right sub-col"},
            {"val": num_games, "cls": "right sub-col"},
            {"val": int(total), "cls": "right sub-col", "sort": total},
        ])
    return _list_section(f"Top {n} player weeks", headers, rows)


def _top_player_season_avg_section(
    player_data: Optional[dict],
    n: int,
    *,
    season_rows: Optional[List[dict]] = None,
) -> str:
    """One row per player for a single season, or per (player, season) when season_rows is set."""
    count_label = "Weeks"
    if season_rows is not None:
        headers = [
            {"label": "#", "right": True},
            {"label": "Player"},
            {"label": "Team"},
            {"label": "Avg", "right": True},
            {"label": "High", "right": True},
            {"label": "Low", "right": True},
            {"label": "Season"},
            {"label": count_label, "right": True},
            {"label": "Games", "right": True},
        ]
        rows = []
        for i, row in enumerate(season_rows[:n], 1):
            name = row["player"]
            team = row.get("team", "")
            season = row.get("season", "")
            avg = row.get("average", 0)
            high = row.get("highest_game", 0)
            low = row.get("lowest_game", 0)
            weeks = row.get("weeks_played", 0)
            games = row.get("games_bowled", 0)
            rows.append(
                [
                    {"val": i, "cls": "right rank"},
                    {"val": _short_name(name), "cls": "name-col", "sort": name.lower()},
                    {
                        "val": team,
                        "cls": "sub-col",
                        "style": _team_color_style(team),
                        "sort": team.lower(),
                    },
                    {"val": f"{avg:.1f}", "cls": "right gold", "sort": avg},
                    {"val": high, "cls": "right green"},
                    {"val": low, "cls": "right sub-col"},
                    {"val": season, "cls": "sub-col", "sort": season.lower()},
                    {"val": weeks, "cls": "right sub-col"},
                    {"val": games, "cls": "right sub-col"},
                ]
            )
        title = f"Top {n} best seasons"
        return _list_section(title, headers, rows)

    if not player_data:
        return '<p class="best-scores-hub-empty">No best seasons data for this selection.</p>'

    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Avg", "right": True},
        {"label": "High", "right": True},
        {"label": "Low", "right": True},
        {"label": count_label, "right": True},
        {"label": "Games", "right": True},
    ]
    rows = []
    sorted_players = sorted(
        player_data.items(), key=lambda x: x[1].get("average", 0), reverse=True
    )
    for i, (name, stats) in enumerate(sorted_players[:n], 1):
        avg = stats.get("average", 0)
        high = stats.get("highest_game", 0)
        low = stats.get("lowest_game", 0)
        weeks = stats.get("weeks_played", 0)
        games = _player_games_bowled_count(stats)
        team = stats.get("team", "")
        rows.append(
            _player_identity_cells(i, name, team)
            + [
                {"val": f"{avg:.1f}", "cls": "right gold"},
                {"val": high, "cls": "right green"},
                {"val": low, "cls": "right sub-col"},
                {"val": weeks, "cls": "right sub-col"},
                {"val": games, "cls": "right sub-col"},
            ]
        )
    return _list_section(f"Top {n} best seasons", headers, rows)


def _top_team_games_section(games: list, n: int) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Score", "right": True},
        {"label": "Wk", "right": True},
        {"label": "Game", "right": True},
    ]
    team_rows: List[Tuple[List[dict], Dict[str, Any]]] = []
    for i, entry in enumerate(games[:n], 1):
        if len(entry) >= 5:
            team, week, game_num, score, players = entry[:5]
        else:
            team, week, game_num, score = entry[:4]
            players = {}
        team_rows.append((
            [
                {"val": i, "cls": "right rank"},
                {
                    "val": _team_name_cell_expandable(team),
                    "cls": "name-col",
                    "style": _team_color_style(team),
                    "sort": team.lower(),
                },
                {"val": int(score), "cls": "right gold", "sort": int(score)},
                {"val": week, "cls": "right sub-col"},
                {"val": game_num, "cls": "right sub-col"},
            ],
            players if isinstance(players, dict) else {},
        ))
    return _teams_standings_section(f"Top {n} team games", headers, team_rows)


def _top_team_weeks_section(weeks: list, n: int) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Avg", "right": True},
        {"label": "Games", "right": True},
        {"label": "Total", "right": True},
    ]
    team_rows: List[Tuple[List[dict], Dict[str, Any]]] = []
    for i, entry in enumerate(weeks[:n], 1):
        if len(entry) >= 5:
            team, week, total, num_games, players = entry[:5]
        else:
            team, week, total, num_games = entry[:4]
            players = {}
        week_avg = total / num_games if num_games else 0
        team_rows.append((
            [
                {"val": i, "cls": "right rank"},
                {
                    "val": _team_name_cell_expandable(team),
                    "cls": "name-col",
                    "style": _team_color_style(team),
                    "sort": team.lower(),
                },
                {"val": week, "cls": "right sub-col"},
                {"val": f"{week_avg:.1f}", "cls": "right gold", "sort": week_avg},
                {"val": num_games, "cls": "right sub-col"},
                {"val": int(total), "cls": "right sub-col", "sort": total},
            ],
            players if isinstance(players, dict) else {},
        ))
    return _teams_standings_section(f"Top {n} team weeks", headers, team_rows)


def _top_team_season_avg_section(
    teams_data: Optional[dict],
    n: int,
    *,
    season_rows: Optional[List[dict]] = None,
    champion_team: Optional[str] = None,
) -> str:
    """One row per team for a single season, or per (team, season) when season_rows is set."""
    if season_rows is not None:
        headers = [
            {"label": "#", "right": True},
            {"label": "Team"},
            {"label": "Season"},
            {"label": "Record"},
            {"label": "Avg", "right": True},
            {"label": "Total Pins", "right": True},
        ]
        team_rows: List[Tuple[List[dict], Dict[str, Any]]] = []
        for i, row in enumerate(season_rows[:n], 1):
            name = row["team"]
            season = row.get("season", "")
            stats = row.get("stats") or {}
            champ = row.get("champion_team")
            w = stats.get("wins", 0)
            l = stats.get("losses", 0)
            t = stats.get("ties", 0)
            record = f"{w}-{l}" + (f"-{t}" if t else "")
            avg = stats.get("avg_per_game", 0)
            pins = stats.get("pins_for", 0)
            players = stats.get("players") or {}
            team_rows.append((
                [
                    {"val": i, "cls": "right rank"},
                    {
                        "val": _team_name_cell_expandable(name, champ),
                        "cls": "name-col",
                        "style": _team_color_style(name),
                        "sort": name.lower(),
                    },
                    {"val": season, "cls": "sub-col", "sort": season.lower()},
                    {
                        "val": record,
                        "cls": "record",
                        "sort": w * 1_000_000 - l * 1_000 - t,
                    },
                    {"val": f"{avg:.1f}", "cls": "right gold", "sort": avg},
                    {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
                ],
                players,
            ))
        return _teams_standings_section(f"Top {n} best seasons", headers, team_rows)

    if not teams_data:
        return (
            '<p class="best-scores-hub-empty">Pick a specific season above — '
            "not All seasons.</p>"
        )

    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Record"},
        {"label": "Avg", "right": True},
        {"label": "Total Pins", "right": True},
    ]
    team_rows = []
    sorted_teams = sorted(
        teams_data.items(),
        key=lambda x: x[1].get("avg_per_game", 0),
        reverse=True,
    )
    for i, (name, stats) in enumerate(sorted_teams[:n], 1):
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        t = stats.get("ties", 0)
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        players = stats.get("players") or {}
        team_rows.append((
            [
                {"val": i, "cls": "right rank"},
                {
                    "val": _team_name_cell_expandable(name, champion_team),
                    "cls": "name-col",
                    "style": _team_color_style(name),
                    "sort": name.lower(),
                },
                {
                    "val": record,
                    "cls": "record",
                    "sort": w * 1_000_000 - l * 1_000 - t,
                },
                {"val": f"{avg:.1f}", "cls": "right gold", "sort": avg},
                {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
            ],
            players,
        ))
    return _teams_standings_section(f"Top {n} best seasons", headers, team_rows)


def build_top_player_scores_hub_html(
    games: list,
    weeks: list,
    season: str,
    n: int,
    *,
    player_data: Optional[dict] = None,
    player_season_rows: Optional[List[dict]] = None,
    initial_view: str = "weeks",
) -> str:
    view = _normalize_scores_hub_view(initial_view)
    weeks_panel = _top_player_weeks_section(weeks, n)
    games_panel = _top_player_games_section(games, n)
    avg_panel = _top_player_season_avg_section(
        player_data, n, season_rows=player_season_rows
    )
    hub_inner = (
        f'<div class="best-scores-hub" data-initial-view="{view}">'
        + _scores_hub_tabs_html(view)
        + _scores_hub_panel("weeks", weeks_panel, hidden=view != "weeks")
        + _scores_hub_panel("games", games_panel, hidden=view != "games")
        + _scores_hub_panel("averages", avg_panel, hidden=view != "averages")
        + "</div>"
    )
    return _render_list_page(
        css=_LIST_CSS + _BEST_SCORES_HUB_CSS,
        title="🎳 BEST PLAYER SCORES",
        subtitle=season,
        sections=hub_inner,
        extra_script=_BEST_SCORES_HUB_SCRIPT,
    )


def build_top_team_scores_hub_html(
    games: list,
    weeks: list,
    season: str,
    n: int,
    *,
    teams_data: Optional[dict] = None,
    team_season_rows: Optional[List[dict]] = None,
    initial_view: str = "weeks",
    champion_team: Optional[str] = None,
) -> str:
    view = _normalize_scores_hub_view(initial_view)
    weeks_panel = _top_team_weeks_section(weeks, n)
    games_panel = _top_team_games_section(games, n)
    avg_panel = _top_team_season_avg_section(
        teams_data,
        n,
        season_rows=team_season_rows,
        champion_team=champion_team,
    )
    hub_inner = (
        f'<div class="best-scores-hub" data-initial-view="{view}">'
        + _scores_hub_tabs_html(view)
        + _scores_hub_panel("weeks", weeks_panel, hidden=view != "weeks")
        + _scores_hub_panel("games", games_panel, hidden=view != "games")
        + _scores_hub_panel("averages", avg_panel, hidden=view != "averages")
        + "</div>"
    )
    return _render_list_page(
        css=_LIST_CSS + _TEAMS_STANDINGS_CSS + _BEST_SCORES_HUB_CSS,
        title="🎳 BEST TEAM SCORES",
        subtitle=season,
        sections=hub_inner,
        extra_script=_BEST_SCORES_HUB_SCRIPT + _TEAMS_EXPAND_SCRIPT,
    )


# ---------------------------------------------------------------------------
# Top team games / weeks
# ---------------------------------------------------------------------------

def build_top_team_games_html(games: list, season: str, n: int) -> str:
    """games: (team, week, game_num, score[, players]) tuples, pre-sorted."""
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Score", "right": True},
        {"label": "Wk", "right": True},
        {"label": "Game", "right": True},
    ]
    team_rows: List[Tuple[List[dict], Dict[str, Any]]] = []
    for i, entry in enumerate(games[:n], 1):
        if len(entry) >= 5:
            team, week, game_num, score, players = entry[:5]
        else:
            team, week, game_num, score = entry[:4]
            players = {}
        team_rows.append((
            [
                {"val": i, "cls": "right rank"},
                {
                    "val": _team_name_cell_expandable(team),
                    "cls": "name-col",
                    "style": _team_color_style(team),
                    "sort": team.lower(),
                },
                {"val": int(score), "cls": "right gold", "sort": int(score)},
                {"val": week, "cls": "right sub-col"},
                {"val": game_num, "cls": "right sub-col"},
            ],
            players if isinstance(players, dict) else {},
        ))
    section = _teams_standings_section(f"Top {n} Team Games", headers, team_rows)
    return _render_list_page(
        css=_LIST_CSS + _TEAMS_STANDINGS_CSS,
        title="🎳 TOP TEAM GAMES",
        subtitle=season,
        sections=section,
        extra_script=_TEAMS_EXPAND_SCRIPT,
    )


def build_top_team_weeks_html(weeks: list, season: str, n: int) -> str:
    """weeks: (team, week, total, num_games[, players]) tuples, pre-sorted."""
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Avg", "right": True},
        {"label": "Games", "right": True},
        {"label": "Total", "right": True},
    ]
    team_rows: List[Tuple[List[dict], Dict[str, Any]]] = []
    for i, entry in enumerate(weeks[:n], 1):
        if len(entry) >= 5:
            team, week, total, num_games, players = entry[:5]
        else:
            team, week, total, num_games = entry[:4]
            players = {}
        week_avg = total / num_games if num_games else 0
        team_rows.append((
            [
                {"val": i, "cls": "right rank"},
                {
                    "val": _team_name_cell_expandable(team),
                    "cls": "name-col",
                    "style": _team_color_style(team),
                    "sort": team.lower(),
                },
                {"val": week, "cls": "right sub-col"},
                {"val": f"{week_avg:.1f}", "cls": "right gold", "sort": week_avg},
                {"val": num_games, "cls": "right sub-col"},
                {"val": int(total), "cls": "right sub-col", "sort": total},
            ],
            players if isinstance(players, dict) else {},
        ))
    section = _teams_standings_section(f"Top {n} Team Weeks", headers, team_rows)
    return _render_list_page(
        css=_LIST_CSS + _TEAMS_STANDINGS_CSS,
        title="🎳 TOP TEAM WEEKS",
        subtitle=season,
        sections=section,
        extra_script=_TEAMS_EXPAND_SCRIPT,
    )


# ---------------------------------------------------------------------------
# Team weekly breakdown
# ---------------------------------------------------------------------------

def build_team_weekly_html(team: str, season: str, weekly_summary: dict) -> str:
    total_w = sum(v.get("wins", 0)   for v in weekly_summary.values())
    total_l = sum(v.get("losses", 0) for v in weekly_summary.values())
    total_t = sum(v.get("ties", 0)   for v in weekly_summary.values())
    record_str = f"{total_w}-{total_l}" + (f"-{total_t}" if total_t else "")

    headers = [
        {"label": "Wk", "right": True},
        {"label": "Opponent"},
        {"label": "W-L"},
        {"label": "For", "right": True},
        {"label": "Agn", "right": True},
        {"label": "Avg", "right": True},
    ]
    rows = []
    for week in sorted(weekly_summary.keys()):
        wi = weekly_summary[week]
        w = wi.get("wins", 0); l = wi.get("losses", 0); t = wi.get("ties", 0)
        rec = f"{w}-{l}" + (f"-{t}" if t else "")
        opp = wi.get("opponent", "—")
        wk_sort: Union[int, float]
        if isinstance(week, (int, float)):
            wk_sort = int(week)
        elif str(week).strip().isdigit():
            wk_sort = int(str(week).strip())
        else:
            wk_sort = 0
        rows.append([
            {"val": week,                           "cls": "right rank", "sort": wk_sort},
            {"val": opp,                            "cls": "sub-col", "style": _team_color_style(opp), "sort": opp.lower()},
            {"val": rec,                            "cls": "record",      "sort": w * 10000 + l * 100 + t},
            {"val": f"{wi.get('pins_for',0):,}",    "cls": "right green", "sort": wi.get("pins_for", 0)},
            {"val": f"{wi.get('pins_against',0):,}", "cls": "right sub-col", "sort": wi.get("pins_against", 0)},
            {"val": f"{wi.get('avg',0):.1f}",       "cls": "right gold"},
        ])

    subtitle = f"{season} &nbsp;·&nbsp; {record_str}"
    section = _list_section("Week by Week", headers, rows)
    return _render_list_page(
        css=_LIST_CSS, title=team.upper(), subtitle=subtitle, sections=section
    )


def build_top_games_html(games: list, season: str, n: int) -> str:
    """Build image for top N individual game scores.
    games: list of (player, team, week, score) tuples, pre-sorted."""
    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Score", "right": True},
    ]
    rows = []
    for i, (player, team, week, score) in enumerate(games[:n], 1):
        rows.append([
            {"val": i,                   "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": team,                "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week,                "cls": "right sub-col"},
            {"val": int(score),          "cls": "right gold"},
        ])
    section = _list_section(f"Top {n} Individual Games", headers, rows)
    return _render_list_page(
        css=_LIST_CSS, title="🎳 TOP SCORES", subtitle=season, sections=section
    )


def build_top_weeks_html(weeks: list, season: str, n: int) -> str:
    """Build page for top N player weekly totals.
    weeks: list of (player, team, week, total, num_games) tuples, pre-sorted."""
    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Avg", "right": True},
        {"label": "Games", "right": True},
        {"label": "Total", "right": True},
    ]
    rows = []
    for i, week_data in enumerate(weeks[:n], 1):
        if len(week_data) == 5:
            player, team, week, total, num_games = week_data
        else:
            player, team, week, total = week_data
            num_games = 0
        week_avg = total / num_games if num_games else 0
        rows.append([
            {"val": i,                   "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": team,                "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week,                "cls": "right sub-col"},
            {"val": f"{week_avg:.1f}",   "cls": "right gold", "sort": week_avg},
            {"val": num_games,           "cls": "right sub-col"},
            {"val": int(total),          "cls": "right sub-col", "sort": total},
        ])
    section = _list_section(f"Top {n} Player Weeks", headers, rows)
    return _render_list_page(
        css=_LIST_CSS, title="🎳 TOP WEEKS", subtitle=season, sections=section
    )


_WEB_CHROME_CSS = """
.site-chrome { background: #1a1730; border-bottom: 1px solid #2a2050; padding: 12px 18px; margin: 0 0 16px 0; }
.site-chrome-inner { max-width: min(1320px, 96vw); margin: 0 auto; display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: center; }
.site-chrome a { color: #50fa7b; text-decoration: none; font-size: 14px; font-weight: 500;
  padding: 4px 6px; margin: -4px -6px; border-radius: 6px; transition: color 0.2s ease, background 0.2s ease, transform 0.15s ease; }
.site-chrome a:hover { color: #7bffc9; background: rgba(80,250,123,0.08); }
.site-chrome a:active { transform: scale(0.97); }
.site-chrome .brand { font-weight: 700; margin-right: 4px; }
.site-chrome .brand a { color: #ffb86c !important; }
.site-chrome .brand a:hover { background: rgba(255,184,108,0.12); }
@media (prefers-reduced-motion: reduce) {
  .site-chrome a { transition: none; }
  .site-chrome a:active { transform: none; }
}
@media (min-width: 960px) {
  .container { padding: 28px 32px !important; }
}
"""

_SITE_NAV = """
<div class="site-chrome"><div class="site-chrome-inner">
<span class="brand"><a href="/" style="color:#ffb86c;">Monday Night Friends</a></span>
<a href="/">Home</a>
<a href="/bracket">Playoffs</a>
</div></div>
"""

# When loaded inside home.html's preview iframe, Home must reset the parent — not load / in-frame.
_IFRAME_HOME_SCRIPT = """
<script>
(function () {
  if (window.self === window.top) return;
  function goHome(e) {
    if (e) e.preventDefault();
    parent.postMessage({ type: "bowlbot-embed-home" }, window.location.origin);
  }
  document.querySelectorAll('.site-chrome a[href="/"]').forEach(function (a) {
    a.addEventListener("click", goHome);
  });
  document.querySelectorAll('a.embed-home-link').forEach(function (a) {
    a.addEventListener("click", goHome);
  });
})();
</script>
"""

# Injected when ?embed=1 (home iframe preview): no site nav, tighter body for nested view.
_EMBED_HEAD_PATCH = """
<style>
html {
  overflow-x: hidden;
  scrollbar-gutter: stable both-edges;
}
body {
  margin: 0 !important;
  padding: 0 !important;
  width: 100% !important;
  max-width: 100% !important;
  overflow-x: hidden;
  box-sizing: border-box;
}
body.page-playoffs { padding: 8px 10px !important; max-width: none !important; width: 100% !important; }
body.page-playoffs .container {
  padding-block: 12px !important;
  padding-inline: 14px !important;
}
.container {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box;
  padding-block: 16px 18px !important;
  padding-inline: 20px !important;
}
@media (max-width: 520px) {
  .container {
    padding-block: 16px 18px !important;
    padding-inline: 20px !important;
  }
}
</style>
"""


def inject_web_chrome(full_html: str, *, embed: bool = False) -> str:
    """Widen fixed 600px layouts for responsive web; optionally add top nav (full page only)."""
    h = full_html.replace(
        "width: 600px;",
        "max-width: min(960px, 94vw); width: 100%; margin: 0 auto;",
    )
    if "page-playoffs" in h or "🏆 PLAYOFFS" in h:
        h = h.replace(
            "max-width: min(960px, 94vw); width: 100%; margin: 0 auto;",
            "max-width: min(1320px, 98vw); width: 100%; margin: 0 auto;",
            1,
        )
    h = re.sub(r"<head>", '<head><meta name="viewport" content="width=device-width, initial-scale=1">', h, count=1, flags=re.IGNORECASE)
    if embed:
        h = re.sub(r"</head>", _EMBED_HEAD_PATCH + "</head>", h, count=1, flags=re.IGNORECASE)
    else:
        h = re.sub(r"</head>", f"<style>{_WEB_CHROME_CSS}</style></head>", h, count=1, flags=re.IGNORECASE)
        h = re.sub(r"<body([^>]*)>", r"<body\1>" + _SITE_NAV, h, count=1, flags=re.IGNORECASE)
    h = re.sub(r"</body>", _IFRAME_HOME_SCRIPT + "</body>", h, count=1, flags=re.IGNORECASE)
    return h
