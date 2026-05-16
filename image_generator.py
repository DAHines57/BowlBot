"""
Generates HTML templates that match the historical PNG card style (purple + amber).
Used by the Flask web app; no browser/screenshot step required.
"""
import itertools
import json
import os
import re
import html as html_module
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

from placement_bracket import (
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
# Team colors — loaded from team_colors.json (run extract_colors.py to refresh)
# ---------------------------------------------------------------------------

def _load_team_colors() -> dict:
    path = os.path.join(os.path.dirname(__file__), "team_colors.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

_TEAM_COLORS: dict = _load_team_colors()


def _team_color_style(team_name: str) -> str:
    """Return an inline style coloring just the text in the team's color.
    Lightens dark colors so they remain readable on the dark background."""
    if not team_name:
        return ""
    color = _TEAM_COLORS.get(team_name.strip())
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

  <div class="highlights">
    <div class="highlight-card high">
      <div class="label">🏆 High Game</div>
      <div class="score">{high_score}</div>
      <div class="player-name">{high_player}</div>
      <div class="team-name">{high_team}</div>
    </div>
    <div class="highlight-card low">
      <div class="label">📉 Low Game</div>
      <div class="score">{low_score}</div>
      <div class="player-name">{low_player}</div>
      <div class="team-name">{low_team}</div>
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
        <div class="stat-value">{total_players}</div>
        <div class="stat-label">Players</div>
      </div>
      <div class="stat">
        <div class="stat-value">{games_200_plus}</div>
        <div class="stat-label">200+ Games</div>
      </div>
      <div class="stat">
        <div class="stat-value">{total_games}</div>
        <div class="stat-label">Total Games</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Leaderboard</div>
    <table>
      <thead>
        <tr>
          <th class="right">#</th>
          <th>Player</th>
          <th>Team</th>
          <th class="right">Wk Avg</th>
          <th class="right">High</th>
        </tr>
      </thead>
      <tbody>
        {player_rows}
      </tbody>
    </table>
  </div>
"""


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) > 1:
        return f"{parts[0]} {parts[-1][0]}."
    return full_name


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

        team_style = _team_color_style(p["team"])
        rows.append(f"""
        <tr {row_class}>
          <td class="right rank">{rank_str}</td>
          <td class="player-col">{_short_name(p['name'])}{absent_badge}</td>
          <td class="team-col" style="{team_style}">{p['team']}</td>
          <td class="right">{avg_str}</td>
          <td class="right">{high_str}</td>
        </tr>""")
    return "".join(rows)


def _build_week_summary_inner(data: dict) -> str:
    high = data.get("high_game") or {}
    low = data.get("low_game") or {}
    return _SUMMARY_INNER_FR.format(
        season=data.get("season", ""),
        week=data.get("week", ""),
        high_score=high.get("score", "—"),
        high_player=_short_name(high.get("player", "—")) if high.get("player") else "—",
        high_team=f'<span style="{_team_color_style(high.get("team", ""))}">{high.get("team", "")}</span>',
        low_score=low.get("score", "—"),
        low_player=_short_name(low.get("player", "—")) if low.get("player") else "—",
        low_team=f'<span style="{_team_color_style(low.get("team", ""))}">{low.get("team", "")}</span>',
        player_rows=_week_summary_player_rows(data),
        league_avg=data.get("league_avg", "—"),
        total_players=data.get("total_players", 0),
        games_200_plus=data.get("games_200_plus", 0),
        total_games=data.get("total_games", 0),
    )


def build_html(data: dict) -> str:
    """Build the weekly summary HTML string from week summary data."""
    return _WEEK_SUMMARY_DOC.format(css=_CSS, inner=_build_week_summary_inner(data))


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
    return _WEEK_SUMMARY_DOC.format(css=_CSS, inner=banner + "\n" + "\n".join(blocks))


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
.game5-series-note {
    font-size: 11px;
    color: #9cbcff;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed #3d3560;
    line-height: 1.35;
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
.pw-week-head {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #c9a86a;
    margin-bottom: 10px;
}
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

        g5_note = m.get("game5_series_note")
        g5_note_html = (
            f'<div class="game5-series-note">{html_module.escape(g5_note)}</div>'
            if g5_note
            else ""
        )

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
      {g5_note_html}
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
"""


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

  function clearInds(table) {
    table.querySelectorAll("thead th.sortable-th .sort-ind").forEach(function (el) { el.textContent = ""; });
  }

  function applySort(table, col, phase, types, rankCol) {
    var tbody = table.tBodies[0];
    if (!tbody) { return; }
    var rows = Array.prototype.slice.call(tbody.rows);
    clearInds(table);
    if (phase === 0) {
      rows.sort(function (a, b) {
        return parseInt(a.getAttribute("data-default-index"), 10) - parseInt(b.getAttribute("data-default-index"), 10);
      });
      rows.forEach(function (tr) {
        tbody.appendChild(tr);
        if (rankCol) {
          var r = tr.cells[0];
          if (r && r.hasAttribute("data-orig-rank")) {
            r.textContent = r.getAttribute("data-orig-rank");
          }
        }
      });
      return;
    }
    rows.sort(function (a, b) {
      var x = cmpRow(a, b, col, types);
      return phase === 1 ? x : -x;
    });
    rows.forEach(function (tr, idx) {
      tbody.appendChild(tr);
      if (rankCol) {
        var r = tr.cells[0];
        if (r && r.classList.contains("rank")) {
          r.textContent = String(idx + 1);
        }
      }
    });
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
    Array.prototype.forEach.call(tbody.rows, function (tr, i) {
      tr.setAttribute("data-default-index", String(i));
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
<body><div class="container">
  <div class="header">
    <div class="title">{title}</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  {sections}
</div>"""


def _render_list_page(css: str, title: str, subtitle: str, sections: str) -> str:
    """Build list-style document; JS is appended so braces are not interpreted by str.format."""
    return (
        _LIST_PAGE_HEAD.format(css=css, title=title, subtitle=subtitle, sections=sections)
        + _LIST_SORT_SCRIPT
        + "\n</body></html>"
    )


def build_player_detail_html(
    *,
    page_title: str,
    subtitle: str,
    team: str,
    stats_title: str,
    stat_rows: Optional[List[Tuple[str, str, str]]] = None,
    empty_message: Optional[str] = None,
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
    ):
        return "number"
    if any(x in lab for x in ("avg", "high", "low", "score", "pin", "for", "agn")):
        return "number"
    return "string"


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


def _list_section(title: str, headers: List[dict], rows: List[List[dict]]) -> str:
    """Titled table section with client-side sort (asc / desc / default) on headers."""
    rank_track = bool(headers) and str(headers[0].get("label", "")).strip() in ("#", "Seed")
    table_attr = ' class="sortable-table" data-has-rank-col="1"' if rank_track else ' class="sortable-table"'

    th_parts: List[str] = []
    for i, h in enumerate(headers):
        cls_parts: List[str] = []
        if h.get("right"):
            cls_parts.append("right")
        cls_parts.append("sortable-th")
        st = html_module.escape(_header_sort_type(h))
        ind = '<span class="sort-ind" aria-hidden="true"></span>'
        th_parts.append(
            f'<th class="{" ".join(cls_parts)}" data-sort-col="{i}" data-sort-type="{st}">'
            f'{h["label"]}{ind}</th>'
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
    return f"""
    <div class="section">
      <div class="section-title">{title}</div>
      <table{table_attr}><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>
    </div>"""


# ---------------------------------------------------------------------------
# Players season leaderboard
# ---------------------------------------------------------------------------

def build_players_html(data: dict, season: str, ascending: bool = False) -> str:
    count_label = "Games" if season in ("All Time",) or "All Time" in season else "Weeks"
    headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Avg", "right": True},
        {"label": "High", "right": True},
        {"label": "Low", "right": True},
        {"label": count_label, "right": True},
    ]
    rows = []
    sorted_players = sorted(data.items(), key=lambda x: x[1].get("average", 0), reverse=not ascending)
    for i, (name, stats) in enumerate(sorted_players, 1):
        avg = stats.get("average", 0)
        high = stats.get("highest_game", 0)
        low = stats.get("lowest_game", 0)
        weeks = stats.get("weeks_played", 0)
        team = stats.get("team", "")
        rows.append([
            {"val": i,                 "cls": "right rank"},
            {"val": _short_name(name), "cls": "name-col", "sort": name.lower()},
            {"val": team,              "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": f"{avg:.1f}",      "cls": "right gold"},
            {"val": high,              "cls": "right green"},
            {"val": low,               "cls": "right sub-col"},
            {"val": weeks,             "cls": "right sub-col"},
        ])
    section = _list_section("Season Averages", headers, rows)
    return _render_list_page(
        css=_LIST_CSS, title="🎳 PLAYERS", subtitle=season, sections=section
    )


# ---------------------------------------------------------------------------
# Team standings
# ---------------------------------------------------------------------------

def build_teams_html(data: dict, season: str) -> str:
    headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Record"},
        {"label": "Avg", "right": True},
        {"label": "Total Pins", "right": True},
    ]
    rows = []
    sorted_teams = sorted(data.items(), key=lambda x: x[1].get("avg_per_game", 0), reverse=True)
    for i, (name, stats) in enumerate(sorted_teams, 1):
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        t = stats.get("ties", 0)
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        rows.append([
            {"val": i,            "cls": "right rank"},
            {"val": name,         "cls": "name-col", "style": _team_color_style(name), "sort": name.lower()},
            {"val": record,       "cls": "record", "sort": w * 10000 + l * 100 + t},
            {"val": f"{avg:.1f}", "cls": "right gold"},
            {"val": f"{pins:,}",  "cls": "right sub-col", "sort": pins},
        ])
    section = _list_section("Standings", headers, rows)
    return _render_list_page(
        css=_LIST_CSS, title="🏆 TEAMS", subtitle=season, sections=section
    )


def build_bracket_index_html(seasons: List[str]) -> str:
    """Index of /bracket?season=… links for each sheet season."""
    from urllib.parse import quote

    items = []
    for s in seasons:
        items.append(
            f'<li><a href="/bracket?season={quote(s)}">{html_module.escape(s)}</a></li>'
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
BRACKET_COL_W_PX = 158
BRACKET_GAP_PX = 20
BRACKET_MATCH_SLOT_PX = 58


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
        'Week<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="sortable-th" data-sort-col="2" data-sort-type="string">'
        'Team out<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="sortable-th" data-sort-col="3" data-sort-type="string">'
        '<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="sortable-th" data-sort-col="4" data-sort-type="string">'
        'Lost to<span class="sort-ind" aria-hidden="true"></span></th>'
        '<th class="right sortable-th" data-sort-col="5" data-sort-type="number">'
        'Pins (L–W)<span class="sort-ind" aria-hidden="true"></span></th>'
        "</tr></thead>"
    )
    return (
        '<div class="section bracket-losers-section">'
        '<div class="section-title">Eliminated</div>'
        '<table class="bracket-losers-table sortable-table">'
        f"{thead}<tbody>{h}</tbody></table></div>"
    )


def _champion_callout_html(snapshots: List[Optional[dict]]) -> str:
    snap = None
    for s in reversed(snapshots or []):
        if s and s.get("matchups"):
            snap = s
            break
    if not snap:
        return ""
    ms = snap["matchups"]
    if len(ms) != 1:
        return ""
    m = ms[0]
    away = m.get("away")
    if not away:
        nm = m["home"]["name"]
        return (
            f'<div class="bracket-champion"><span class="bracket-champion-label">Champion</span>'
            f'<span class="bracket-champion-name" style="{_team_color_style(nm)}">'
            f"{html_module.escape(nm)}</span></div>"
        )
    home = m["home"]
    hr, ar = home.get("result", ""), away.get("result", "")
    if hr == "W" and ar == "L":
        nm = home["name"]
    elif ar == "W" and hr == "L":
        nm = away["name"]
    else:
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
html { overflow-x: auto; -webkit-overflow-scrolling: touch; }
body { overflow-y: auto; min-width: 0; }
.container { max-width: none; overflow: visible; }
.bracket-wrap {
  overflow-x: auto;
  overflow-y: visible;
  margin: 0 -6px;
  padding: 6px 12px 20px 12px;
  max-width: 100%;
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
  word-break: break-word;
  line-height: 1.35;
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
.bracket-pop {
  position: absolute;
  left: 0;
  right: auto;
  top: calc(100% + 6px);
  bottom: auto;
  transform: none;
  width: max-content;
  max-width: min(268px, calc(100vw - 24px));
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
.bracket-pair-wrap:hover .bracket-pop,
.bracket-pair-wrap:focus-within .bracket-pop {
  opacity: 1;
  visibility: visible;
}
.bracket-cl-outer:hover .bracket-pop,
.bracket-cl-outer:focus-within .bracket-pop {
  opacity: 1;
  visibility: visible;
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
}
.bracket-cl-outer:hover,
.bracket-cl-outer:focus-within { z-index: 80; }
.bracket-cl-outer:last-child { margin-bottom: 0; }
.bracket-cl-outer:focus { outline: 2px solid #7c6ec4; outline-offset: 2px; }
.bracket-cl-mnum {
  flex: 0 0 1.1rem;
  font-size: 11px;
  font-weight: 800;
  color: #9a96b0;
  text-align: center;
  padding-top: 10px;
  font-variant-numeric: tabular-nums;
}
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
  justify-content: space-between;
  gap: 8px;
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
    return slots


def _qf_results_for_bracket_placement(
    qf_matchups: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> List[Optional[SlotWL]]:
    """Use true bracket-slot QF order when all four games match theory; else theory-then-sheet order."""
    slots = qf_matchups_in_bracket_slot_order(qf_matchups, round_pairs)
    if len(slots) >= 4 and all(slots):
        wl = [winner_loser_from_matchup(s) for s in slots[:4]]
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


def _semis_week_parallel_shape(qf_ms: List[dict], ms1: List[dict]) -> bool:
    """True if this semis week has two winner–winner games and two loser–loser games (parallel brackets)."""
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


def _pick_best_eight_team_placement_model(
    qf_ms: List[dict],
    ms1: List[dict],
    ms2: List[dict],
    round_pairs: List[Tuple[BracketSlot, BracketSlot]],
) -> Optional[dict]:
    """Choose QF slot labeling + cross vs parallel so week-2 fits 2+2 and week-3 placement groups match the sheet."""
    candidates = _qf_res_candidates(qf_ms, round_pairs)
    if not candidates:
        return None
    best: Optional[dict] = None
    best_key: Tuple[int, int, int] = (-1, -1, -1)
    shape_parallel = _semis_week_parallel_shape(qf_ms, ms1)

    def maybe_take(key: Tuple[int, int, int], row: dict) -> None:
        nonlocal best, best_key
        if key > best_key:
            best_key = key
            best = row
        elif key == best_key and best is not None:
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
        w3x = _week3_match_count(ms2, w3g_x)
        fit_bonus = 0 if shape_parallel else 1
        maybe_take(
            (w2x, fit_bonus, w3x),
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
            w3p = _week3_match_count(ms2, w3g_p)
            par_bonus = 1 if shape_parallel else 0
            maybe_take(
                (w2p, par_bonus, w3p),
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
    gr = m.get("game_results") or []
    games_h = ""
    if gr:
        gbits: List[str] = []
        for i, row in enumerate(gr):
            if len(row) >= 4:
                h_r, a_r, h_p, a_p = row[0], row[1], row[2], row[3]
                gbits.append(
                    f'<div class="bracket-pop-g">G{i + 1}: {h_p:,}–{a_p:,} '
                    f'<span class="bracket-pop-gr">{html_module.escape(h_r)}/'
                    f'{html_module.escape(a_r)}</span></div>'
                )
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


def _classic_team_row_cl(name: str, res: str, seed: Optional[int]) -> str:
    seed_el = (
        f'<span class="bracket-cl-seed">{seed}</span>'
        if seed is not None
        else '<span class="bracket-cl-seed bracket-cl-seed--empty">—</span>'
    )
    return (
        f'<div class="bracket-cl-row">'
        f"{seed_el}"
        f'<div class="bracket-cl-row-main">'
        f'<span class="bracket-line {_bracket_name_result_class(res)}" style="{_team_color_style(name)}">'
        f"{html_module.escape(name)}</span>"
        f"{_bracket_result_badge_html(res)}</div></div>"
    )


def _classic_match_block_html(
    m: dict,
    *,
    seed_map: Dict[str, int],
    match_no: Optional[int],
    extra_meta: Optional[str] = None,
) -> str:
    away = m.get("away")
    if not away:
        nm = m["home"]["name"]
        sid = seed_map.get(nm)
        row = _classic_team_row_cl(nm, m["home"].get("result", ""), sid)
        pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
        num = (
            f'<div class="bracket-cl-mnum" aria-hidden="true">{match_no}</div>'
            if match_no is not None
            else '<div class="bracket-cl-mnum"></div>'
        )
        return (
            f'<div class="bracket-cl-outer" tabindex="0">{num}'
            f'<div class="bracket-cl-match">{row}</div>{pop}</div>'
        )
    home = m["home"]
    hn, an = home["name"], away["name"]
    hr, ar = home.get("result", ""), away.get("result", "")
    rowh = _classic_team_row_cl(hn, hr, seed_map.get(hn))
    rowa = _classic_team_row_cl(an, ar, seed_map.get(an))
    pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
    num = (
        f'<div class="bracket-cl-mnum" aria-hidden="true">{match_no}</div>'
        if match_no is not None
        else '<div class="bracket-cl-mnum"></div>'
    )
    return (
        f'<div class="bracket-cl-outer" tabindex="0">{num}'
        f'<div class="bracket-cl-match">{rowh}{rowa}</div>{pop}</div>'
    )


def _classic_pending_line(label: str) -> str:
    return f'<div class="bracket-cl-pending">{html_module.escape(label)}</div>'


def _eight_team_week0_classic_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    seed_map: Dict[str, int],
) -> str:
    ms, _al = _match_matchups_to_theoretical_round(list(snap["matchups"]), rounds[0])
    parts: List[str] = []
    for i, m in enumerate(ms):
        parts.append(
            _classic_match_block_html(
                m,
                seed_map=seed_map,
                match_no=i + 1,
                extra_meta="Quarterfinal — winners bracket",
            )
        )
    return "".join(parts)


def _eight_team_week2_cross_layout_html(
    cross_ord: List[Optional[dict]],
    cross_sets: List[Optional[FrozenSet[str]]],
    rest: List[dict],
    seed_map: Dict[str, int],
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
                    seed_map=seed_map,
                    match_no=4 + i,
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
                    seed_map=seed_map,
                    match_no=6 + i,
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
                seed_map=seed_map,
                match_no=None,
                extra_meta="Playoff game (could not match to winners/losers semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_cross_column(
    ms: List[dict],
    qf_res: List[Optional[Tuple[str, str]]],
    seed_map: Dict[str, int],
) -> str:
    cross_sets = expected_week2_cross_sets(qf_res)
    cross_ord, rest = matchups_by_cross_ordered_groups(ms, cross_sets)
    return _eight_team_week2_cross_layout_html(cross_ord, cross_sets, rest, seed_map)


def _eight_team_week2_parallel_layout_html(
    wb_ord: List[Optional[dict]],
    lb_ord: List[Optional[dict]],
    rest: List[dict],
    seed_map: Dict[str, int],
) -> str:
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">Winners bracket — playing for 1st–4th place</div>'
    )
    for idx, mm in enumerate(wb_ord):
        meta = "Winners bracket semifinal — quarterfinal winners from the same half of the draw"
        mn = 5 + idx if idx < 2 else None
        if mm:
            sec.append(_classic_match_block_html(mm, seed_map=seed_map, match_no=mn, extra_meta=meta))
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
            sec.append(_classic_match_block_html(mm, seed_map=seed_map, match_no=None, extra_meta=meta))
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
                seed_map=seed_map,
                match_no=None,
                extra_meta="Playoff game (could not match to semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_loss_bucket_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    seed_map: Dict[str, int],
) -> str:
    """When QF pairings are non-standard, split week-2 games by playoff-loss count before this week."""
    losses_before = _playoff_losses_through_prior_rounds(snapshots, 1)
    ms = list(snap["matchups"])
    upper: List[dict] = []
    lower: List[dict] = []
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
        sec.append(_classic_match_block_html(mm, seed_map=seed_map, match_no=None, extra_meta=meta_u))
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
        sec.append(_classic_match_block_html(mm, seed_map=seed_map, match_no=None, extra_meta=meta_l))
    sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'


def _eight_team_week2_placement_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
    seed_map: Dict[str, int],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    if not snap0 or not snap0.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap["matchups"])
    ms2: List[dict] = []
    if len(snapshots) > 2 and snapshots[2] and snapshots[2].get("matchups"):
        ms2 = list(snapshots[2]["matchups"])
    model = _pick_best_eight_team_placement_model(qf_ms, ms1, ms2, rounds[0])
    if model is None:
        return _eight_team_week2_loss_bucket_column(snap, snapshots, seed_map)
    if model["kind"] == "cross":
        n_filled = sum(1 for x in model["cross_ord"] if x is not None)
    else:
        n_filled = sum(1 for x in model["wb_ord"] + model["lb_ord"] if x is not None)
    if n_filled < 4:
        return _eight_team_week2_loss_bucket_column(snap, snapshots, seed_map)
    if model["kind"] == "cross":
        return _eight_team_week2_cross_layout_html(
            model["cross_ord"], model["cross_sets"], model["rest"], seed_map
        )
    return _eight_team_week2_parallel_layout_html(
        model["wb_ord"], model["lb_ord"], model["rest"], seed_map
    )


def _eight_team_week3_placement_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    seed_map: Dict[str, int],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    snap1 = snapshots[1] if len(snapshots) > 1 else None
    if not snap0 or not snap0.get("matchups") or not snap1 or not snap1.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap1["matchups"])
    ms2 = list(snap["matchups"])
    model = _pick_best_eight_team_placement_model(qf_ms, ms1, ms2, rounds[0])
    w3: List[Tuple[FrozenSet[str], str]] = []
    if model and model.get("w3_groups"):
        w3 = list(model["w3_groups"])
    if not w3:
        qf_res = _qf_results_for_bracket_placement(qf_ms, rounds[0])
        if prefer_crossover_week2(ms1, qf_res):
            cross_sets = expected_week2_cross_sets(qf_res)
            cross_ord, _ = matchups_by_cross_ordered_groups(ms1, cross_sets)
            n_cross_hit = sum(1 for x in cross_ord if x is not None)
            wb_g, lb_g = expected_week2_groups(qf_res)
            wb_try, r1 = matchups_by_ordered_groups(ms1, wb_g)
            lb_try, _ = matchups_by_ordered_groups(r1, lb_g)
            n_par_hit = sum(1 for x in wb_try if x is not None) + sum(1 for x in lb_try if x is not None)
            if n_cross_hit >= n_par_hit:
                semis_cross = [winner_loser_from_matchup(m) if m else None for m in cross_ord]
                w3 = expected_week3_groups_cross(semis_cross)
        if not w3:
            wb_g, lb_g = expected_week2_groups(qf_res)
            wb_ord, r1 = matchups_by_ordered_groups(ms1, wb_g)
            lb_ord, r2 = matchups_by_ordered_groups(r1, lb_g)
            wb_semis = [winner_loser_from_matchup(m) if m else None for m in wb_ord]
            lb_semis = [winner_loser_from_matchup(m) if m else None for m in lb_ord]
            while len(wb_semis) < 2:
                wb_semis.append(None)
            while len(lb_semis) < 2:
                lb_semis.append(None)
            w3 = expected_week3_groups(wb_semis[:2], lb_semis[:2])
    if not w3:
        return None
    ordered, rest = order_matchups_by_labeled_groups(ms2, w3)
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
                    seed_map=seed_map,
                    match_no=None,
                    extra_meta=label,
                )
            )
        else:
            sec.append(_classic_pending_line("Matchup not in sheet or teams still TBD from week 2."))
        sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m, seed_map=seed_map, match_no=None, extra_meta="Playoff matchup (extra)"
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
) -> str:
    seed_rank = _seed_rank_map(sorted_teams)
    nr = len(rounds)
    seed_map = _seed_display_map(sorted_teams)

    if (
        eight_placement_layout
        and nr == 3
        and len(rounds[0]) == 4
        and snap
        and snap.get("matchups")
    ):
        if ri == 0 and classic_skin:
            return _eight_team_week0_classic_column(snap, rounds, sorted_teams, seed_map)
        if ri == 1:
            w2 = _eight_team_week2_placement_column(
                snap, rounds, snapshots, seed_map
            )
            if w2 is not None:
                return w2
        if ri == 2:
            w3 = _eight_team_week3_placement_column(snap, snapshots, seed_map, rounds)
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


def _bracket_round_title(round_idx: int, num_rounds: int) -> str:
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
    seeding_note: str,
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    playoff_week_numbers: Optional[List[int]] = None,
    playoff_matchups_by_round: Optional[List[Optional[dict]]] = None,
    playoff_week_cards_data: Optional[List[dict]] = None,
) -> str:
    """sorted_teams: best first, (name, stats).

    If playoff_week_numbers / playoff_matchups_by_round are set, each index aligns with a bracket
    column and shows compact names with a styled hover card for scores and games; otherwise seeds.

    When playoff_week_cards_data is set, the same full matchup cards (pins, games) are appended below
    the bracket for every playoff week that had sheet data.
    """
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
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": html_module.escape(name),
                "cls": "name-col",
                "style": _team_color_style(name),
                "sort": name.lower(),
            },
            {"val": record, "cls": "record", "sort": w * 10000 + l * 100 + t},
            {"val": f"{avg:.1f}", "cls": "right gold"},
            {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
        ])
    seed_section = _list_section(
        f"Seeds (team avg through week {seeding_week})",
        headers,
        rows,
    )
    nr = len(rounds)
    pweeks = playoff_week_numbers or []
    snapshots = playoff_matchups_by_round or []
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

    header_frag: List[str] = []
    track_frag: List[str] = []
    for ri in range(num_cols):
        snap = snapshots[ri] if ri < len(snapshots) else None
        pw = pweeks[ri] if ri < len(pweeks) else None
        has_actual = bool(snap and snap.get("matchups"))

        if has_actual and pw is not None:
            disp = _bracket_round_title(ri, nr) if ri < nr else f"Week {pw}"
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
            )
            header_frag.append(
                f'<div class="bracket-hcell">'
                f'<div class="section-title" style="margin-bottom:4px;">{col_title}</div>{wk_line}</div>'
            )
            track_frag.append(f'<div class="bracket-tcell">{body}</div>')
        elif ri < len(rounds):
            title_disp = html_module.escape(_bracket_round_title(ri, nr) if nr else f"Round {ri + 1}")
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
                title_disp = html_module.escape(_bracket_round_title(ri, nr) if nr else f"Round {ri + 1}")
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
    elim_rows = _elimination_rows_from_playoffs(pweeks, snapshots, nr)
    elim_html = _elimination_section_html(elim_rows)
    champ = _champion_callout_html(snapshots)
    shell_title = (
        "Full field playoffs (every team each week)"
        if (split_placement and has_playoff_data)
        else "Winners bracket"
    )
    format_note = ""
    if eight_placement_layout:
        format_note = (
            '<p class="bracket-format-note">'
            "<strong>8 teams, full field:</strong> Quarterfinals use standard seeding. "
            "Semifinals are either <strong>winners vs winners / losers vs losers</strong> in each half of the draw, "
            "or <strong>winner vs loser</strong> from adjacent quarterfinals in each half — the page picks "
            "whichever matches your sheet. Finals are labeled by finishing spots (1st–2nd, 3rd–4th, etc.). "
            "Bracket placement uses each matchup&rsquo;s <strong>W/L</strong>. "
            "If the sheet has a <strong>Game 5 winner</strong> name but no Game 5 pin row, a 2–2 split "
            "after four games is resolved using that column.</p>"
        )
    elif split_placement and has_playoff_data:
        format_note = (
            '<p class="bracket-format-note">Every team plays each playoff week. '
            "Matchups with <strong>no playoff losses yet</strong> are still playing for <strong>1st place</strong>. "
            "When both teams already have a playoff loss, they are playing for <strong>5th–8th place</strong>. "
            "When it is one of each, think <strong>2nd–4th place</strong>. "
            "Connectors are hidden because everyone bowls each week, not strict single-elimination. "
            "Gold row edge + <strong>1st</strong> / gray + <strong>Lower</strong> row hints start after quarterfinals "
            "(semifinals: only on the two games that match each half of the seeded bracket). "
            "In the final week, every matchup shows them.</p>"
        )
    elif has_playoff_data:
        format_note = (
            '<p class="bracket-format-note">Quarterfinals have no row rank hints. After that, gold + '
            "<strong>1st</strong> vs gray + <strong>Lower</strong> show who is still in the hunt for 1st vs "
            "sorting lower spots; in full-field semifinals those hints only appear on the two games that "
            "match each half of the seeded bracket.</p>"
        )
    wrap_cls = "bracket-wrap" + (" bracket-wrap--classic" if classic_skin else "")
    grid_cls = "bracket-grid-main" + (" bracket-grid-main--classic" if classic_skin else "")
    bracket_inner = (
        f'<div class="bracket-shell" style="--bf-slots: {n_leaf};">'
        f'<div class="bracket-winners-title">{html_module.escape(shell_title)}</div>'
        f"{format_note}"
        f'<div class="bracket-headers-row">{"".join(header_frag)}</div>'
        f'<div class="{grid_cls}">'
        '<div class="bracket-main-tracks">'
        f"{svg}"
        f'<div class="bracket-tracks-row">{"".join(track_frag)}</div>'
        "</div>"
        f"{champ}"
        "</div></div>"
        f"{elim_html}"
    )
    bracket_section = (
        f'<div class="section"><div class="section-title">Bracket</div>'
        f'<div class="{wrap_cls}">{bracket_inner}</div></div>'
    )
    css = (
        _LIST_CSS
        + _BRACKET_EXTRA_CSS
        + ("\n" + _MATCHUPS_CSS if playoff_week_cards_data else "")
        + "\nbody { width: auto !important; max-width: none !important; }\n"
    )
    subtitle = (
        f"{html_module.escape(season)} &nbsp;·&nbsp; "
        f"Seeding through week {seeding_week} &nbsp;·&nbsp; "
        f"{len(sorted_teams)} teams"
    )
    cards_section = ""
    if playoff_week_cards_data:
        inner_cards = _playoff_week_cards_inner_html(
            f"{season} · Playoffs", playoff_week_cards_data
        )
        cards_section = (
            '<div class="section"><div class="section-title">Playoff weeks — scores &amp; games</div>'
            f'<div class="playoff-cards-embed">{inner_cards}</div></div>'
        )
    return _render_list_page(
        css=css,
        title="🏆 PLAYOFFS",
        subtitle=subtitle,
        sections=f'<p class="bracket-note">{html_module.escape(seeding_note)}</p>'
        + seed_section
        + bracket_section
        + cards_section,
    )


# ---------------------------------------------------------------------------
# League leaders
# ---------------------------------------------------------------------------

def build_leaders_html(data: dict) -> str:
    season = data.get("season", "")
    avg_lookup = {p["player"]: p["average"] for p in data.get("player_averages", [])}

    # Top games
    game_headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Score", "right": True},
    ]
    game_rows = []
    for i, (player, team, week, score) in enumerate(data.get("top_games", []), 1):
        game_rows.append([
            {"val": i,                   "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": team,                "cls": "sub-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week,                "cls": "right sub-col"},
            {"val": int(score),          "cls": "right gold"},
        ])

    # Top player weeks
    pw_headers = [
        {"label": "#", "right": True},
        {"label": "Player"},
        {"label": "Wk", "right": True},
        {"label": "Games", "right": True},
        {"label": "Avg", "right": True},
    ]
    pw_rows = []
    for i, week_data in enumerate(data.get("top_player_weeks", []), 1):
        if len(week_data) == 5:
            player, team, week, total, num_games = week_data
        else:
            player, team, week, total = week_data; num_games = 4
        week_avg = total / num_games if num_games else 0
        pw_rows.append([
            {"val": i,                   "cls": "right rank"},
            {"val": _short_name(player), "cls": "name-col", "sort": player.lower()},
            {"val": week,                "cls": "right sub-col"},
            {"val": num_games,           "cls": "right sub-col"},
            {"val": f"{week_avg:.1f}",   "cls": "right gold"},
        ])

    # Top team weeks
    tw_headers = [
        {"label": "#", "right": True},
        {"label": "Team"},
        {"label": "Wk", "right": True},
        {"label": "Total", "right": True},
        {"label": "Games", "right": True},
        {"label": "Avg", "right": True},
    ]
    tw_rows = []
    for i, entry in enumerate(data.get("top_team_totals", []), 1):
        team, week, total, games = entry if len(entry) == 4 else (*entry, None)
        avg = round(total / games, 1) if games else "—"
        avg_sort = round(total / games, 1) if games else -1.0
        tw_rows.append([
            {"val": i,            "cls": "right rank"},
            {"val": team,         "cls": "name-col", "style": _team_color_style(team), "sort": team.lower()},
            {"val": week,         "cls": "right sub-col"},
            {"val": int(total),   "cls": "right green"},
            {"val": games or "—", "cls": "right sub-col", "sort": -1 if games is None else games},
            {"val": avg,          "cls": "right gold", "sort": avg_sort},
        ])

    sections = (
        _list_section("Top Individual Games", game_headers, game_rows) +
        _list_section("Top Player Weeks", pw_headers, pw_rows) +
        _list_section("Top Team Weeks", tw_headers, tw_rows)
    )
    return _render_list_page(
        css=_LIST_CSS, title="🏅 LEADERS", subtitle=season, sections=sections
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


_WEB_CHROME_CSS = """
.site-chrome { background: #1a1730; border-bottom: 1px solid #2a2050; padding: 12px 18px; margin: 0 0 16px 0; }
.site-chrome-inner { max-width: min(1040px, 94vw); margin: 0 auto; display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: center; }
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
<span class="brand"><a href="/" style="color:#ffb86c;">Bowl League</a></span>
<a href="/">Home</a>
<a href="/bracket">Playoffs</a>
</div></div>
"""

# Injected when ?embed=1 (home iframe preview): no site nav, tighter body for nested view.
_EMBED_HEAD_PATCH = """
<style>
body { margin: 0 !important; padding: 12px 14px !important; }
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
    return h
