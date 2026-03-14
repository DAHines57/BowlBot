"""
Generates a weekly summary PNG using Playwright to screenshot an HTML template.
Returns raw PNG bytes suitable for sending directly via WhatsApp.
"""
import json
import os
from typing import Optional


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
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>{css}</style>
</head>
<body>
<div class="container">

  <div class="header">
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

</div>
</body>
</html>"""


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) > 1:
        return f"{parts[0]} {parts[-1][0]}."
    return full_name


def build_html(data: dict) -> str:
    """Build the weekly summary HTML string from week summary data."""
    high = data.get("high_game") or {}
    low  = data.get("low_game")  or {}

    # Player rows
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
        avg_str  = f"{p['avg']:.1f}" if p["avg"] else "—"
        high_str = str(p["high"]) if p["high"] else "—"

        team_style = _team_color_style(p['team'])
        rows.append(f"""
        <tr {row_class}>
          <td class="right rank">{rank_str}</td>
          <td class="player-col">{_short_name(p['name'])}{absent_badge}</td>
          <td class="team-col" style="{team_style}">{p['team']}</td>
          <td class="right">{avg_str}</td>
          <td class="right">{high_str}</td>
        </tr>""")

    return _HTML_TEMPLATE.format(
        css=_CSS,
        season=data.get("season", ""),
        week=data.get("week", ""),
        high_score=high.get("score", "—"),
        high_player=_short_name(high.get("player", "—")) if high.get("player") else "—",
        high_team=f'<span style="{_team_color_style(high.get("team",""))}">{high.get("team","")}</span>',
        low_score=low.get("score", "—"),
        low_player=_short_name(low.get("player", "—")) if low.get("player") else "—",
        low_team=f'<span style="{_team_color_style(low.get("team",""))}">{low.get("team","")}</span>',
        player_rows="".join(rows),
        league_avg=data.get("league_avg", "—"),
        total_players=data.get("total_players", 0),
        games_200_plus=data.get("games_200_plus", 0),
        total_games=data.get("total_games", 0),
    )


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
"""

_MATCHUPS_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>{css}</style></head>
<body>
<div class="container">
  <div class="header">
    <div class="title">🎳 WEEKLY RESULTS</div>
    <div class="subtitle">{season} &nbsp;·&nbsp; Week {week}</div>
  </div>
  <div class="section-title">Matchups</div>
  {matchup_cards}
</div>
</body>
</html>"""


def build_matchups_html(data: dict) -> str:
    """Build the weekly matchup results HTML."""
    cards = []
    for m in data.get("matchups", []):
        home = m["home"]
        away = m.get("away")
        game_results = m.get("game_results", [])

        h_res = home["result"]
        h_badge = f'<div class="badge {h_res}">{h_res}</div>'

        h_color = _team_color_style(home['name'])
        if away:
            a_res = away["result"]
            a_badge = f'<div class="badge {a_res}">{a_res}</div>'
            a_color = _team_color_style(away['name'])
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

        # Per-game breakdown row
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

        cards.append(f"""
    <div class="matchup-card">
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
    </div>""")

    return _MATCHUPS_TEMPLATE.format(
        css=_MATCHUPS_CSS,
        season=data.get("season", ""),
        week=data.get("week", ""),
        matchup_cards="".join(cards),
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

_LIST_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>{css}</style></head>
<body><div class="container">
  <div class="header">
    <div class="title">{title}</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  {sections}
</div></body></html>"""


def _list_section(title, headers, rows):
    """Helper to build a titled table section."""
    th = "".join(
        f'<th class="{"right" if h.get("right") else ""}">{h["label"]}</th>'
        for h in headers
    )
    def _td(c):
        style_attr = f' style="{c["style"]}"' if c.get("style") else ""
        return f'<td class="{c.get("cls", "")}"{style_attr}>{c["val"]}</td>'
    trs = "".join(
        "<tr>" + "".join(_td(c) for c in row) + "</tr>"
        for row in rows
    )
    return f"""
    <div class="section">
      <div class="section-title">{title}</div>
      <table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>
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
            {"val": _short_name(name), "cls": "name-col"},
            {"val": team,              "cls": "sub-col", "style": _team_color_style(team)},
            {"val": f"{avg:.1f}",      "cls": "right gold"},
            {"val": high,              "cls": "right green"},
            {"val": low,               "cls": "right sub-col"},
            {"val": weeks,             "cls": "right sub-col"},
        ])
    section = _list_section("Season Averages", headers, rows)
    return _LIST_TEMPLATE.format(
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
            {"val": name,         "cls": "name-col", "style": _team_color_style(name)},
            {"val": record,       "cls": "record"},
            {"val": f"{avg:.1f}", "cls": "right gold"},
            {"val": f"{pins:,}",  "cls": "right sub-col"},
        ])
    section = _list_section("Standings", headers, rows)
    return _LIST_TEMPLATE.format(
        css=_LIST_CSS, title="🏆 TEAMS", subtitle=season, sections=section
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
            {"val": _short_name(player), "cls": "name-col"},
            {"val": team,                "cls": "sub-col", "style": _team_color_style(team)},
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
            {"val": _short_name(player), "cls": "name-col"},
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
        tw_rows.append([
            {"val": i,            "cls": "right rank"},
            {"val": team,         "cls": "name-col", "style": _team_color_style(team)},
            {"val": week,         "cls": "right sub-col"},
            {"val": int(total),   "cls": "right green"},
            {"val": games or "—", "cls": "right sub-col"},
            {"val": avg,          "cls": "right gold"},
        ])

    sections = (
        _list_section("Top Individual Games", game_headers, game_rows) +
        _list_section("Top Player Weeks", pw_headers, pw_rows) +
        _list_section("Top Team Weeks", tw_headers, tw_rows)
    )
    return _LIST_TEMPLATE.format(
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
        rows.append([
            {"val": week,                           "cls": "right rank"},
            {"val": opp,                            "cls": "sub-col", "style": _team_color_style(opp)},
            {"val": rec,                            "cls": "record"},
            {"val": f"{wi.get('pins_for',0):,}",    "cls": "right green"},
            {"val": f"{wi.get('pins_against',0):,}", "cls": "right sub-col"},
            {"val": f"{wi.get('avg',0):.1f}",       "cls": "right gold"},
        ])

    subtitle = f"{season} &nbsp;·&nbsp; {record_str}"
    section = _list_section("Week by Week", headers, rows)
    return _LIST_TEMPLATE.format(
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
            {"val": _short_name(player), "cls": "name-col"},
            {"val": team,                "cls": "sub-col", "style": _team_color_style(team)},
            {"val": week,                "cls": "right sub-col"},
            {"val": int(score),          "cls": "right gold"},
        ])
    section = _list_section(f"Top {n} Individual Games", headers, rows)
    return _LIST_TEMPLATE.format(
        css=_LIST_CSS, title="🎳 TOP SCORES", subtitle=season, sections=section
    )


def generate_image(html: str) -> bytes:
    """Render the HTML to a PNG using Playwright and return raw bytes.
    Connects to a remote Browserless instance if BROWSERLESS_URL is set,
    otherwise launches a local Chromium (for local dev)."""
    from playwright.sync_api import sync_playwright
    browserless_url = os.environ.get("BROWSERLESS_URL")
    with sync_playwright() as p:
        if browserless_url:
            browser = p.chromium.connect(browserless_url)
        else:
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 600, "height": 800})
        page.set_content(html, wait_until="networkidle")
        # Resize viewport to actual content height so there's no empty space
        content_height = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({"width": 600, "height": content_height})
        buf = page.screenshot()
        browser.close()
    return buf
