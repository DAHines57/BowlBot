"""
Generates HTML templates that match the historical PNG card style (purple + amber).
Used by the Flask web app; no browser/screenshot step required.
"""
import re
import html as html_module
from typing import Any, Dict, List, Optional, Tuple, Union

from stats.compute import sort_teams_by_standings


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
    from db.team_colors import readable_hex
    from stats.facts import canonical_team_name

    lookup = canonical_team_name(team_name.strip())
    raw = team_name.strip()
    color = readable_hex(
        _REGISTERED_TEAM_COLORS.get(lookup) or _REGISTERED_TEAM_COLORS.get(raw)
    )
    if not color:
        return ""
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
.sub-badge {
    display: inline-block;
    background: #1a2e2a;
    color: #50fa7b;
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 1px;
    vertical-align: middle;
    margin-left: 4px;
}
.sub-for-badge {
    font-size: 9px;
    color: #9a96a8;
    margin-left: 2px;
}
tbody tr.sub-row { opacity: 0.92; }
.week-summary-section .section-head,
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
.week-summary-section .section-head .section-title,
.players-stats-section .section-head .section-title {
    margin-bottom: 0;
    border-bottom: none;
    padding-bottom: 0;
}
.stats-panel-actions,
.players-stats-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
}
.summary-stats-toggle,
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
.summary-stats-toggle:hover,
.players-stats-toggle:hover {
    border-color: #7c6ec4;
    color: #fff;
}
.summary-stats-toggle[aria-pressed="true"],
.players-stats-toggle[aria-pressed="true"] {
    border-color: #7c6ec4;
    background: #2d1b69;
    color: #ffb86c;
}
.summary-stats-panel[hidden],
.players-stats-panel[hidden] { display: none !important; }

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

  <div class="section week-summary-section">
    <div class="section-head">
      <div class="section-title">Leaderboard</div>
    </div>
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
    if isinstance(league_avg, (int, float)):
        league_avg = _format_avg(league_avg)
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
    players = list(data.get("players", []))
    for p in players:
        absent = p.get("absent", False)
        is_sub = p.get("is_substitute", False)
        subbed_out = p.get("subbed_out", False)
        rank += 1
        rank_str = str(rank)

        badges = ""
        if is_sub:
            sub_for = p.get("sub_for")
            badges = '<span class="sub-badge">SUB</span>'
            if sub_for:
                badges += f' <span class="sub-for-badge">for {_short_name(str(sub_for))}</span>'
        elif absent or subbed_out:
            badges = '<span class="absent-badge">ABSENT</span>'

        row_class = 'class="absent"' if (absent or subbed_out) and not is_sub else ('class="sub-row"' if is_sub else "")
        avg_str = _format_avg(p['avg']) if p.get("avg") else "—"
        high_str = str(p["high"]) if p.get("high") else "—"
        low_str = str(p["low"]) if p.get("low") else "—"

        team_style = _team_color_style(p["team"])
        rank_sort = rank
        avg_sort = p["avg"] if p.get("avg") else -1
        high_sort = p["high"] if p.get("high") else -1
        low_sort = p["low"] if p.get("low") else -1
        if absent and not is_sub:
            avg_str = _format_avg(p['avg']) if p.get("avg") else "—"
            high_str = low_str = "—"
            high_sort = low_sort = -1
        orig_rank = f' data-orig-rank="{html_module.escape(rank_str, quote=True)}"'
        rows.append(f"""
        <tr {row_class}>
          <td class="right rank" data-sort="{rank_sort}"{orig_rank}>{rank_str}</td>
          <td class="player-col" data-sort="{html_module.escape(p["name"].lower(), quote=True)}">{_short_name(p['name'])}{badges}</td>
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
    return doc.replace(
        "</body>",
        _LIST_SORT_SCRIPT + "\n</body>",
        1,
    )


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
.player-tag--sub { color: #50fa7b; }
.sub-for-inline {
    font-size: 9px;
    color: #9a96a8;
    font-weight: normal;
}
.player-score-table tr.player-score-separator td {
    padding: 0;
    height: 0;
    line-height: 0;
    border: none;
    border-top: 1px solid #3a3060;
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


def _matchup_player_name_html(p: dict, *, away: bool) -> str:
    """Short display name; absent/sub tags beside the name."""
    name = html_module.escape(_short_name(str(p.get("name", ""))))
    tag = ""
    if p.get("is_substitute"):
        sub_for = p.get("sub_for")
        if sub_for:
            name = f"{name} <span class=\"sub-for-inline\">({_short_name(str(sub_for))})</span>"
        tag = '<span class="player-tag player-tag--sub">SUB</span>'
    elif p.get("absent") or p.get("subbed_out"):
        tag = '<span class="player-tag">ABS</span>'
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


def _matchup_player_score_counted(p: dict) -> bool:
    if p.get("subbed_out"):
        return False
    if p.get("is_substitute"):
        return bool(p.get("scores_count"))
    return True


def _matchup_player_table_html(players: list, num_games: int, *, away: bool) -> str:
    if not players:
        return ""
    counting = [p for p in players if _matchup_player_score_counted(p)]
    non_counting = [p for p in players if not _matchup_player_score_counted(p)]
    sorted_players = sorted(
        counting,
        key=lambda p: str(p.get("name", "")).lower(),
    ) + sorted(
        non_counting,
        key=lambda p: str(p.get("name", "")).lower(),
    )
    g_hdrs = "".join(f'<th class="pst-g">G{i + 1}</th>' for i in range(num_games))
    if away:
        thead = f"<thead><tr>{g_hdrs}<th class=\"pst-name\"></th></tr></thead>"
    else:
        thead = f"<thead><tr><th class=\"pst-name\"></th>{g_hdrs}</tr></thead>"
    body_rows = []
    col_span = num_games + 1

    def append_player_row(p: dict) -> None:
        games = p.get("games") or []
        name_td = f'<td class="pst-name">{_matchup_player_name_html(p, away=away)}</td>'
        game_tds = _matchup_game_cells_html(games, num_games, p.get("game_absent"))
        if away:
            body_rows.append(f"<tr>{game_tds}{name_td}</tr>")
        else:
            body_rows.append(f"<tr>{name_td}{game_tds}</tr>")

    for p in counting:
        append_player_row(p)
    if counting and non_counting:
        body_rows.append(
            f'<tr class="player-score-separator"><td colspan="{col_span}"></td></tr>'
        )
    for p in non_counting:
        append_player_row(p)
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


def _build_matchup_card_list(data: dict) -> str:
    """HTML for matchup cards only (no page header); used by weekly results."""
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
                  <span class="pins">{away['pins']:,} pins</span> &nbsp;·&nbsp; {_format_avg(away['avg'])} avg
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

        n_games = len(game_results) if game_results else max(
            len(home.get("game_pins") or []),
            len((away or {}).get("game_pins") or []),
            4,
        )
        player_details = _matchup_player_details_html(home, away, n_games)

        cards.append(f"""
    <div class="matchup-card">
      <div class="matchup-top">
        <div class="team-side">
          <div class="team-name" style="{h_color}">{home['name']}</div>
          <div class="team-stats">
            <span class="pins">{home['pins']:,} pins</span> &nbsp;·&nbsp; {_format_avg(home['avg'])} avg
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
.sub-badge {
    display: inline-block;
    background: #1a2e2a;
    color: #50fa7b;
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 1px;
    vertical-align: middle;
    margin-left: 4px;
}
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

# Mirrors the :root block in static/app.css so the pages that opt into it read
# as part of the unified app. Keep the two in step when a token changes.
_APP_TOKENS_CSS = """
:root {
  --bg: #12101a;
  --bg-elevated: #16121f;
  --card: #1a1730;
  --card-hi: #201c3a;
  --border: #2a2050;
  --border-soft: #241d45;
  --text: #e8e6ef;
  --muted: #9a96a8;
  --muted-dim: #6f6b80;

  --accent: #ffb86c;
  --mint: #50fa7b;
  --rose: #ff6b81;
  --violet: #bd93f9;

  --good-bg: rgba(80, 250, 123, 0.07);
  --good-border: rgba(80, 250, 123, 0.45);
  --bad-bg: rgba(255, 107, 129, 0.07);
  --bad-border: rgba(255, 107, 129, 0.45);
  --accent-bg: rgba(255, 184, 108, 0.08);
  --accent-border: rgba(255, 184, 108, 0.45);

  --shadow: rgba(0, 0, 0, 0.35);
  --radius: 14px;
  --radius-sm: 10px;
  --radius-pill: 999px;

  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
"""

_PLAYER_DETAIL_CSS_EXTRA = """
body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
}
/* Left-aligned like the panel headings on the app page. */
.header { margin-bottom: 1.1rem; text-align: left; }
.header .title {
    font-size: 1.5rem;
    letter-spacing: 0.04em;
    color: var(--accent);
}
.header .subtitle {
    margin-top: 0.35rem;
    font-size: 0.86rem;
    color: var(--muted);
}
.player-scope { color: var(--muted-dim); }
.player-team { font-weight: 700; }

.section-title {
    font-size: 0.76rem;
    letter-spacing: 0.08em;
    color: var(--muted);
    border-bottom: 1px solid var(--border-soft);
    padding-bottom: 0.4rem;
    margin-bottom: 0.6rem;
}

/* Same shape as the .detail-grid tiles inside an expanded row on the app page. */
.player-stat-rows {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(6.5rem, 1fr));
    gap: 0.5rem;
}
.player-stat-row {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
    padding: 0.55rem 0.5rem;
    background: var(--card);
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-sm);
    text-align: center;
}
.player-stat-label {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--muted-dim);
}
.player-stat-val {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text);
    font-variant-numeric: tabular-nums;
}
.player-stat-val--gold { color: var(--accent); }
.player-stat-val--green { color: var(--mint); }
.player-stat-val--muted { color: var(--muted); }
.player-empty {
    margin: 0;
    padding: 0.75rem 0.85rem;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.5;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
}
.player-chart-wrap {
    position: relative;
    overflow: visible;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.7rem 0.6rem 0.4rem;
}
.player-chart-tip {
    position: absolute;
    z-index: 5;
    pointer-events: none;
    transform: translateY(calc(-100% - 12px));
    min-width: 128px;
    max-width: calc(100% - 16px);
    box-sizing: border-box;
    padding: 0.55rem 0.75rem 0.6rem;
    background: var(--card-hi);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    box-shadow: 0 10px 28px var(--shadow);
    text-align: center;
    line-height: 1.35;
}
.player-chart-tip[hidden] { display: none !important; }
.player-chart-tip-score {
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
}
.player-chart-tip-meta {
    margin-top: 3px;
    font-size: 0.62rem;
    color: var(--muted);
    letter-spacing: 0.03em;
}
.player-chart-tip-vs {
    display: inline-block;
    margin-top: 5px;
    padding: 0.1rem 0.45rem;
    border-radius: var(--radius-pill);
    font-size: 0.62rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.player-chart-tip-vs--up {
    color: var(--mint);
    background: var(--good-bg);
    border: 1px solid var(--good-border);
}
.player-chart-tip-vs--down {
    color: var(--rose);
    background: var(--bad-bg);
    border: 1px solid var(--bad-border);
}
.player-chart-point { cursor: pointer; }
.player-chart-point:focus { outline: none; }
.player-chart-point:focus-visible .player-chart-dot {
    stroke: var(--accent);
    stroke-width: 2;
}
.player-chart-point--active .player-chart-dot {
    fill: var(--mint);
    stroke: var(--accent);
    stroke-width: 2;
    transform: scale(1.45);
    transform-box: fill-box;
    transform-origin: center;
}
.player-chart-hit { fill: transparent; stroke: none; pointer-events: all; }
.player-chart-caption {
    margin: 0 0 0.5rem;
    font-size: 0.7rem;
    color: var(--muted);
    line-height: 1.4;
}
.player-chart-caption strong { color: var(--accent); font-weight: 700; }
.player-chart {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
}
.player-chart-grid { stroke: var(--border); stroke-width: 1; }
.player-chart-axis { fill: var(--muted-dim); font-size: 9px; font-family: inherit; }
.player-chart-line {
    fill: none; stroke: var(--accent); stroke-width: 2;
    stroke-linejoin: round; stroke-linecap: round;
}
.player-chart-avg {
    stroke: var(--violet); stroke-width: 1.25; stroke-dasharray: 5 4; opacity: 0.9;
}
.player-chart-league-avg {
    stroke: var(--muted-dim); stroke-width: 1.25; stroke-dasharray: 3 4; opacity: 0.9;
}
/* The dot outline is the page background, so points read as lifted off the line. */
.player-chart-dot { fill: var(--mint); stroke: var(--bg); stroke-width: 1; pointer-events: none; }
.player-chart-point--sub .player-chart-dot { stroke: var(--good-border); stroke-width: 2; }
.player-chart-point--miss .player-chart-dot {
    fill: var(--rose); stroke: var(--bad-border); stroke-width: 2;
}
.player-chart-tip-miss,
.player-chart-tip-sub {
    display: inline-block;
    margin-left: 4px;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 0.05rem 0.4rem;
    border-radius: var(--radius-pill);
    letter-spacing: 0.08em;
    vertical-align: middle;
}
.player-chart-tip-miss {
    background: var(--bad-bg);
    border: 1px solid var(--bad-border);
    color: var(--rose);
}
.player-chart-tip-sub {
    background: var(--good-bg);
    border: 1px solid var(--good-border);
    color: var(--mint);
}
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
      var vsStr = (vs >= 0 ? "+" : "") + vs.toFixed(2) + " vs avg";
      var vsCls =
        vs >= 0 ? "player-chart-tip-vs--up" : "player-chart-tip-vs--down";
      var season = g.getAttribute("data-season") || "";
      var week = g.getAttribute("data-week") || "";
      var game = g.getAttribute("data-game") || "";
      var idx = g.getAttribute("data-index") || "";
      var isSub = g.getAttribute("data-sub") === "1";
      var subBadge = isSub
        ? ' <span class="player-chart-tip-sub">SUB</span>'
        : "";
      if (g.getAttribute("data-miss") === "1") {
        subBadge += ' <span class="player-chart-tip-miss">BOOK AVG</span>';
      }
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
        subBadge +
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
        is_sub = bool(pt.get("is_substitute"))
        is_miss = bool(pt.get("game_absent"))
        note = " (sub)" if is_sub else (" (missed, book average)" if is_miss else "")
        aria = html_module.escape(
            f"Game {g}, week {wk}, {score} pins{note}"
        )
        pt_cls = "player-chart-point"
        if is_sub:
            pt_cls += " player-chart-point--sub"
        elif is_miss:
            pt_cls += " player-chart-point--miss"
        sub_attr = ' data-sub="1"' if is_sub else ""
        if is_miss:
            sub_attr += ' data-miss="1"'
        cx, cy = x_at(i), y_at(score)
        dots.append(
            f'<g class="{pt_cls}" tabindex="0" role="graphics-symbol" '
            f'aria-label="{aria}" data-score="{score}" data-season="{sl_attr}" '
            f'data-week="{wk}" data-game="{g}" data-index="{i + 1}"{sub_attr}>'
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
        f' · league avg <strong>{_format_avg(league_ref)}</strong>'
        if show_league
        else ""
    )
    caption = (
        f'<p class="player-chart-caption">Last <strong>{n}</strong> game'
        f'{"s" if n != 1 else ""}{scope_note}'
        f' · player avg <strong>{_format_avg(avg)}</strong>'
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
    scope: str,
    team: str,
    stats_title: str,
    stat_rows: Optional[List[Tuple[str, str, str]]] = None,
    empty_message: Optional[str] = None,
    game_history: Optional[List[dict]] = None,
    chart_scope: str = "",
    league_avg: Optional[float] = None,
) -> str:
    """Single-player lookup, styled with the unified app's tokens and card shapes."""
    team_esc = html_module.escape(team)
    tstyle = _team_color_style(team)
    # The name is the page heading, so the subtitle carries the team and scope.
    subtitle = f'<span class="player-team" style="{tstyle}">{team_esc}</span>'
    if scope:
        subtitle += f' <span class="player-scope">&middot; {html_module.escape(scope)}</span>'

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
      <div class="section-title">{html_module.escape(stats_title)}</div>
      {stats_body}
    </div>
    <div class="section">
      <div class="section-title">Recent games</div>
      {_player_game_chart_html(game_history or [], chart_scope=chart_scope, league_avg=league_avg)}
    </div>
    """
    css = _LIST_CSS + _APP_TOKENS_CSS + _PLAYER_DETAIL_CSS_EXTRA
    title_esc = html_module.escape(page_title)
    doc = _render_list_page(css=css, title=title_esc, subtitle=subtitle, sections=sections)
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
    return f"{value:.2f}"


def _format_avg(value) -> str:
    """Sitewide bowling average / std-dev display (two decimal places)."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


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
    '    var otherBtn = sec.querySelector(".players-other-toggle");\n'
    '    var subsBtn = sec.querySelector(".players-subs-toggle");\n'
    '    var helpBtn = sec.querySelector(".players-par-help");\n'
    '    var dialog = sec.querySelector(".players-par-dialog");\n'
    '    var main = sec.querySelector(\'[data-panel="main"]\');\n'
    '    var other = sec.querySelector(\'[data-panel="other"]\');\n'
    '    var subs = sec.querySelector(\'[data-panel="subs"]\');\n'
    "    if (!main || !other) return;\n"
    '    var current = "main";\n'
    "    function showPanel(panel) {\n"
    "      current = panel;\n"
    "      main.hidden = panel !== \"main\";\n"
    "      other.hidden = panel !== \"other\";\n"
    "      if (subs) subs.hidden = panel !== \"subs\";\n"
    '      if (otherBtn) {\n'
    '        otherBtn.setAttribute("aria-pressed", panel === "other" ? "true" : "false");\n'
    '        otherBtn.textContent = panel === "other" ? "Main stats" : "Other stats";\n'
    "      }\n"
    '      if (subsBtn) {\n'
    '        subsBtn.setAttribute("aria-pressed", panel === "subs" ? "true" : "false");\n'
    '        subsBtn.textContent = panel === "subs" ? "Main stats" : "Subs";\n'
    "      }\n"
    "      if (helpBtn) helpBtn.hidden = panel !== \"other\";\n"
    "      if (dialog && dialog.open && panel !== \"other\") dialog.close();\n"
    "    }\n"
    "    if (otherBtn) {\n"
    '      otherBtn.addEventListener("click", function () {\n'
    '        showPanel(current === "other" ? "main" : "other");\n'
    "      });\n"
    "    }\n"
    "    if (subsBtn && subs) {\n"
    '      subsBtn.addEventListener("click", function () {\n'
    '        showPanel(current === "subs" ? "main" : "subs");\n'
    "      });\n"
    "    }\n"
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


def _player_name_display(name: str, *, sub_badge: bool = False) -> str:
    label = _short_name(name)
    if sub_badge:
        label += ' <span class="sub-badge">SUB</span>'
    return label


def _player_identity_cells(
    i: int, name: str, team: str, *, sub_badge: bool = False, include_team: bool = True
) -> List[dict]:
    cells = [
        {"val": i, "cls": "right rank"},
        {
            "val": _player_name_display(name, sub_badge=sub_badge),
            "cls": "name-col",
            "sort": name.lower(),
        },
    ]
    if include_team:
        cells.append(
            {
                "val": team,
                "cls": "sub-col",
                "style": _team_color_style(team),
                "sort": team.lower(),
            }
        )
    return cells


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
        return f"+{per:.2f}", per
    return f"{per:.2f}", per


def build_players_html(
    data: dict,
    season: str,
    ascending: bool = False,
    *,
    summary: Optional[dict] = None,
    subs_data: Optional[dict] = None,
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
    subs_rows: List[List[dict]] = []
    subs_headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Avg", "right": True},
        {"label": "High", "right": True},
        {"label": "Low", "right": True},
        {"label": "Weeks subbed", "right": True},
    ]
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
        sub_badge = bool(stats.get("weeks_subbed"))
        ident = _player_identity_cells(i, name, team, sub_badge=sub_badge)
        main_rows.append(
            ident
            + [
                {"val": _format_avg(avg), "cls": "right gold"},
                {"val": high, "cls": "right green"},
                {"val": low, "cls": "right sub-col"},
                {"val": weeks, "cls": "right sub-col"},
            ]
        )
        other_cells = [
            {"val": games, "cls": "right sub-col", "sort": games},
            {"val": _format_avg(std_dev), "cls": "right gold", "sort": std_dev},
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
    if subs_data:
        sorted_subs = sorted(
            subs_data.items(),
            key=lambda x: x[1].get("average", 0),
            reverse=not ascending,
        )
        for i, (name, stats) in enumerate(sorted_subs, 1):
            avg = stats.get("average", 0)
            high = stats.get("highest_game", 0)
            low = stats.get("lowest_game", 0)
            weeks_subbed = stats.get("weeks_subbed", 0)
            team = stats.get("team", "")
            subs_rows.append(
                _player_identity_cells(i, name, team, sub_badge=True, include_team=False)
                + [
                    {"val": _format_avg(avg), "cls": "right gold", "sort": avg},
                    {"val": high, "cls": "right green"},
                    {"val": low, "cls": "right sub-col"},
                    {"val": weeks_subbed, "cls": "right sub-col", "sort": weeks_subbed},
                ]
            )
    subs_toggle_btn = ""
    subs_panel_html = ""
    if subs_data:
        subs_toggle_btn = """
          <button type="button" class="players-stats-toggle players-subs-toggle" aria-pressed="false">
            Subs
          </button>"""
        subs_panel_html = (
            """
      <div class="players-stats-panel" data-panel="subs" hidden>
        """
            + _render_sortable_table(subs_headers, subs_rows)
            + """
      </div>"""
        )
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
        <div class="players-stats-actions">{par_help_btn}{subs_toggle_btn}
          <button type="button" class="players-stats-toggle players-other-toggle" aria-pressed="false">
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
      </div>"""
        + subs_panel_html
        + """
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
        if info.get("subbed_out") or (
            info.get("is_substitute") and not info.get("scores_count")
        ):
            return (2, 0.0, pname.lower())
        val = info.get("value")
        if val is None:
            return (1, 0.0, pname.lower())
        return (0, -float(val), pname.lower())
    return (0, -float(info), pname.lower())


def _roster_absence_tags(info: dict) -> str:
    """Whole-week ABS, per-game ABS, or SUB badge for counting substitutes."""
    if info.get("is_substitute"):
        return ' <span class="sub-badge">SUB</span>'
    if info.get("subbed_out"):
        return ' <span class="absent-badge">ABS</span>'
    if info.get("absent"):
        return ' <span class="absent-badge">ABS</span>'
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
            f'<span class="team-roster-avg">{_format_avg(avg)}</span>'
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
    data: dict,
    season: str,
    *,
    champion_team: Optional[str] = None,
    subtitle: Optional[str] = None,
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
            {"val": _format_avg(avg), "cls": "right gold"},
            {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
        ]
        team_rows.append((main_cells, players))
    section = _teams_standings_section("Standings", headers, team_rows)
    return _render_list_page(
        css=_LIST_CSS + _TEAMS_STANDINGS_CSS,
        title="🏆 TEAMS",
        subtitle=subtitle or season,
        sections=section,
        extra_script=_TEAMS_EXPAND_SCRIPT,
    )


# Fixed layout for winner-bracket SVG connectors (must match CSS .bracket-hcell / .bracket-tcell width + gap)


# ---------------------------------------------------------------------------
# Playoff bracket (single elimination from seeds)
# ---------------------------------------------------------------------------


# Bracket slot: None = empty, str = team, (L, R) = two(sub-)slots whose winner advances


def _seed_display_map(sorted_teams: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, int]:
    return {name: i + 1 for i, (name, _) in enumerate(sorted_teams)}


def _eight_team_week2_cross_column(
    ms: List[dict],
    qf_res: List[Optional[Tuple[str, str]]],
) -> str:
    cross_sets = expected_week2_cross_sets(qf_res)
    cross_ord, rest = matchups_by_cross_ordered_groups(ms, cross_sets)
    return _eight_team_week2_cross_layout_html(cross_ord, cross_sets, rest)


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
    for i, entry in enumerate(games[:n], 1):
        if len(entry) >= 5:
            player, team, week, score, is_sub = entry[:5]
        else:
            player, team, week, score = entry[:4]
            is_sub = False
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _player_name_display(player, sub_badge=bool(is_sub)),
                "cls": "name-col",
                "sort": player.lower(),
            },
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
        is_sub = False
        if len(week_data) >= 6:
            player, team, week, total, num_games, is_sub = week_data[:6]
        elif len(week_data) == 5:
            player, team, week, total, num_games = week_data
        else:
            player, team, week, total = week_data
            num_games = 0
        week_avg = total / num_games if num_games else 0
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _player_name_display(player, sub_badge=bool(is_sub)),
                "cls": "name-col",
                "sort": player.lower(),
            },
            {"val": team, "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": _format_avg(week_avg), "cls": "right gold", "sort": week_avg},
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
                    {"val": _format_avg(avg), "cls": "right gold", "sort": avg},
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
                {"val": _format_avg(avg), "cls": "right gold"},
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
                {"val": _format_avg(week_avg), "cls": "right gold", "sort": week_avg},
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
                    {"val": _format_avg(avg), "cls": "right gold", "sort": avg},
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
                {"val": _format_avg(avg), "cls": "right gold", "sort": avg},
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
                {"val": _format_avg(week_avg), "cls": "right gold", "sort": week_avg},
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
            {"val": _format_avg(wi.get('avg', 0)),       "cls": "right gold"},
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
    for i, entry in enumerate(games[:n], 1):
        if len(entry) >= 5:
            player, team, week, score, is_sub = entry[:5]
        else:
            player, team, week, score = entry[:4]
            is_sub = False
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _player_name_display(player, sub_badge=bool(is_sub)),
                "cls": "name-col",
                "sort": player.lower(),
            },
            {"val": team, "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week, "cls": "right sub-col"},
            {"val": int(score), "cls": "right gold"},
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
        is_sub = False
        if len(week_data) >= 6:
            player, team, week, total, num_games, is_sub = week_data[:6]
        elif len(week_data) == 5:
            player, team, week, total, num_games = week_data
        else:
            player, team, week, total = week_data
            num_games = 0
        week_avg = total / num_games if num_games else 0
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _player_name_display(player, sub_badge=bool(is_sub)),
                "cls": "name-col",
                "sort": player.lower(),
            },
            {"val": team, "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week, "cls": "right sub-col"},
            {"val": _format_avg(week_avg), "cls": "right gold", "sort": week_avg},
            {"val": num_games, "cls": "right sub-col"},
            {"val": int(total), "cls": "right sub-col", "sort": total},
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
    h = re.sub(r"<head>", '<head><meta name="viewport" content="width=device-width, initial-scale=1">', h, count=1, flags=re.IGNORECASE)
    if embed:
        h = re.sub(r"</head>", _EMBED_HEAD_PATCH + "</head>", h, count=1, flags=re.IGNORECASE)
    else:
        h = re.sub(r"</head>", f"<style>{_WEB_CHROME_CSS}</style></head>", h, count=1, flags=re.IGNORECASE)
        h = re.sub(r"<body([^>]*)>", r"<body\1>" + _SITE_NAV, h, count=1, flags=re.IGNORECASE)
    h = re.sub(r"</body>", _IFRAME_HOME_SCRIPT + "</body>", h, count=1, flags=re.IGNORECASE)
    return h
