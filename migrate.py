"""
migrate.py — One-time migration script from v4 to v5 Excel format.

v4 format (wide):  one row per player, weekly averages in columns
v5 format (tall):  one row per player per week, with game scores and opponent

Since v4 only stores weekly averages (not individual games), each week's
average is repeated as Game 1–4 so season averages calculate correctly.
Game 5 is left blank (v4 has no 5-game data).

Output: Bowling-Friends League migrated.xlsx
  — one sheet per season, ready to copy into v5 as needed.
  — Season 9 is skipped since it already exists in v5 with real game scores.
"""

import re
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Border, Side

V4_FILE  = "Bowling- Friends League v4.xlsx"
OUTPUT_FILE = "Bowling-Friends League migrated.xlsx"

# Seasons already present in v5 with real game data — skip these.
SKIP_SEASONS = {9}

# Seasons where weekly values are 4-game pin totals instead of averages.
# The script will divide by 4 before writing game scores.
TOTAL_SEASONS = {3}

V5_HEADER = [
    "Index", "Team", "Player", "Season", "Week",
    "Game 1", "Game 2", "Game 3", "Game 4", "Game 5",
    "Average", "Playoffs?", "Absent?", "Substitute?", "Opponent"
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_week_label(label):
    """
    Parse a week column header into (week_number, is_playoff).
    e.g. 'Week 3' -> (3, False), 'Playoff Week 2' -> (2, True)
    Returns (None, False) if the label doesn't match.
    """
    if not label:
        return None, False
    s = str(label).strip()
    if re.search(r'playoff', s, re.IGNORECASE):
        m = re.search(r'(\d+)', s)
        return (int(m.group(1)), True) if m else (None, False)
    m = re.search(r'week\s+(\d+)', s, re.IGNORECASE)
    return (int(m.group(1)), False) if m else (None, False)


def find_vs_offset(ws, row, start_col, end_col):
    """Return the column offset (relative to start_col) where 'Vs' appears."""
    for c in range(start_col, end_col + 1):
        if ws.cell(row, c).value == 'Vs':
            return c - start_col
    return None


def parse_matchups(ws, matchup_start_col, max_regular_week):
    """
    Parse the matchup section and return a dict:
        (team_name_lower, absolute_week_number) -> opponent_name

    Handles both formats:
      - With Ties:    TeamA, W, L, T, Pins, Vs, TeamB, ...
      - Without Ties: TeamA, W, L, Pins, Vs, TeamB, ...
    """
    matchups = {}
    current_week = None

    for row in range(1, ws.max_row + 1):
        cell_val = ws.cell(row, matchup_start_col).value
        if cell_val is None:
            continue
        cell_str = str(cell_val).strip()

        # Week header line?
        wn, is_playoff = parse_week_label(cell_str)
        if wn is not None:
            current_week = max_regular_week + wn if is_playoff else wn
            continue

        if current_week is None:
            continue

        # Try to find 'Vs' somewhere in this row
        vs_offset = find_vs_offset(ws, row, matchup_start_col, matchup_start_col + 8)
        if vs_offset is None:
            continue

        team_a = ws.cell(row, matchup_start_col).value
        team_b = ws.cell(row, matchup_start_col + vs_offset + 1).value

        if not (team_a and isinstance(team_a, str) and
                team_b and isinstance(team_b, str)):
            continue

        # Skip bracket/placement label rows (e.g. "Winners Bracket")
        # Real team rows have a numeric value in column 2 (Wins)
        wins_a = ws.cell(row, matchup_start_col + 1).value
        if not isinstance(wins_a, (int, float)):
            continue

        team_a = team_a.strip()
        team_b = team_b.strip()
        matchups[(team_a.lower(), current_week)] = team_b
        matchups[(team_b.lower(), current_week)] = team_a

    return matchups


# ---------------------------------------------------------------------------
# Per-season migration
# ---------------------------------------------------------------------------

def parse_formula_games(formula):
    """
    Extract individual game scores from a formula like =(171+203+126+166)/4.
    Returns a list of floats on success, None if the pattern doesn't match.
    """
    if not formula or not isinstance(formula, str):
        return None
    m = re.match(r'=\(([\d.]+(?:\+[\d.]+)+)\)/\d+', formula.strip())
    if m:
        return [float(x) for x in m.group(1).split('+')]
    return None


def _cell_is_highlighted(ws_styles, row, col):
    """Return True if the cell has any fill (indicating an absent week)."""
    cell = ws_styles.cell(row, col)
    ft = cell.fill.fill_type
    return ft is not None and ft != 'none'


def _get_team_color(ws_styles, row, team_col):
    """
    Return the ARGB color string for a team row, or None if no fill is set.
    The team name cell carries the team's color consistently across all seasons.
    """
    cell = ws_styles.cell(row, team_col)
    ft = cell.fill.fill_type
    if not ft or ft == 'none':
        return None
    fg = cell.fill.fgColor
    return fg.rgb if fg.type == 'rgb' else None


def build_team_colors(ws_styles, team_col, player_col):
    """Return a dict of {team_name_lower: rgb_color} from the style sheet."""
    colors = {}
    for r in range(3, ws_styles.max_row + 1):
        team = ws_styles.cell(r, team_col).value
        if not team or not isinstance(team, str):
            continue
        color = _get_team_color(ws_styles, r, team_col)
        if color:
            colors[team.strip().lower()] = color
    return colors


def migrate_season(ws, ws_styles, season_num):
    """
    Read one v4 season sheet and return a list of v5 rows (as plain lists).
    """
    header = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]

    # Locate the player section by finding 'Player' column
    player_col = None
    for i, val in enumerate(header):
        if val == 'Player':
            player_col = i + 1  # 1-based
            break

    if player_col is None:
        print(f"  WARNING: 'Player' column not found — skipping Season {season_num}")
        return []

    team_col = player_col - 1  # 'Team' is immediately left of 'Player'

    # Collect week columns and locate matchup start
    week_cols = {}       # column_index -> (week_number, is_playoff)
    avg_col = None
    matchup_start_col = None

    for i, val in enumerate(header):
        col = i + 1
        if col <= player_col:
            continue  # only look right of Player
        if isinstance(val, str):
            if 'Matchup' in val and matchup_start_col is None:
                # Must be checked before parse_week_label — "Week 1 Matchups"
                # contains "Week 1" and would be misidentified as a week column.
                matchup_start_col = col
            elif val == 'Average' and avg_col is None:
                avg_col = col
            else:
                wn, is_p = parse_week_label(val)
                if wn is not None:
                    week_cols[col] = (wn, is_p)

    if not week_cols:
        print(f"  WARNING: No week columns found — skipping Season {season_num}")
        return []

    # Compute max regular week for playoff offset
    max_regular_week = max(
        wn for wn, is_p in week_cols.values() if not is_p
    )

    # Build absolute week map: col -> absolute_week_num
    col_to_abs_week = {}
    col_to_is_playoff = {}
    for col, (wn, is_p) in week_cols.items():
        abs_week = max_regular_week + wn if is_p else wn
        col_to_abs_week[col] = abs_week
        col_to_is_playoff[col] = is_p

    # Parse opponent lookup
    matchups = {}
    if matchup_start_col:
        matchups = parse_matchups(ws, matchup_start_col, max_regular_week)

    # Build team color lookup (team_name_lower -> rgb)
    team_colors = build_team_colors(ws_styles, team_col, player_col)

    # Iterate player rows
    rows_out = []
    index = 1

    for row in range(3, ws.max_row + 1):
        team = ws.cell(row, team_col).value
        player = ws.cell(row, player_col).value

        if not player or not isinstance(player, str):
            continue
        if not team or not isinstance(team, str):
            continue

        team = team.strip()
        player = player.strip()

        # Skip header/label rows that accidentally pass the string check
        if player.lower() in ('player', 'team', 'wins', 'losses', 'average'):
            continue

        for col in sorted(col_to_abs_week.keys()):
            abs_week = col_to_abs_week[col]
            is_playoff = col_to_is_playoff[col]
            weekly_avg = ws.cell(row, col).value

            # Non-numeric value in a week cell means stray data — skip it
            if weekly_avg is not None and not isinstance(weekly_avg, (int, float)):
                continue

            # A highlighted cell = player was absent (their average was substituted).
            # Fall back to None/0 check for seasons without consistent highlighting.
            is_absent = (
                _cell_is_highlighted(ws_styles, row, col)
                or weekly_avg is None
                or weekly_avg == 0
            )
            opponent = matchups.get((team.lower(), abs_week), "")

            # Extract game scores for every row (absent or not).
            # ws_styles holds the raw formula string (loaded without data_only).
            formula = ws_styles.cell(row, col).value
            games = parse_formula_games(formula)

            if games and len(games) >= 4:
                g1 = round(games[0])
                g2 = round(games[1])
                g3 = round(games[2])
                g4 = round(games[3])
                g5 = round(games[4]) if len(games) >= 5 else None
                avg = round(sum(games) / len(games), 2)
            elif weekly_avg is not None:
                raw = float(weekly_avg)
                avg = round(raw / 4, 2) if season_num in TOTAL_SEASONS else round(raw, 2)
                g1 = g2 = g3 = g4 = avg
                g5 = None
            else:
                g1 = g2 = g3 = g4 = g5 = avg = None

            v5_row = [
                index, team, player, season_num, abs_week,
                g1, g2, g3, g4, g5,
                avg,
                "Y" if is_playoff else "N",
                "Y" if is_absent else "N", "N",
                opponent
            ]

            team_color = _get_team_color(ws_styles, row, team_col)
            rows_out.append((v5_row, team_color, opponent, team_colors))
            index += 1

    return rows_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Reading {V4_FILE} ...")
    # Load twice: data_only for cached numeric values, normal for cell styles/fills
    wb_vals   = load_workbook(V4_FILE, data_only=True)
    wb_styles = load_workbook(V4_FILE, data_only=False)

    season_sheets = sorted(
        [s for s in wb_vals.sheetnames if s.startswith('Season')],
        key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0
    )
    print(f"Seasons found: {[s for s in season_sheets]}")
    if SKIP_SEASONS:
        print(f"Skipping seasons (already in v5): {SKIP_SEASONS}\n")

    wb_out = Workbook()
    wb_out.remove(wb_out.active)  # remove default blank sheet

    for sheet_name in season_sheets:
        season_num = int(sheet_name.split()[-1])

        if season_num in SKIP_SEASONS:
            print(f"Skipping {sheet_name} (in SKIP_SEASONS)")
            continue

        print(f"Migrating {sheet_name} ...")
        ws_vals   = wb_vals[sheet_name]
        ws_styles = wb_styles[sheet_name]
        ws_out = wb_out.create_sheet(title=sheet_name)

        # Write header row
        ws_out.append(V5_HEADER)
        for cell in ws_out[1]:
            cell.font = Font(bold=True)

        thin = Side(style='thin')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        rows = migrate_season(ws_vals, ws_styles, season_num)
        for row_data, team_color, opponent, team_colors in rows:
            ws_out.append(row_data)
            current_row = ws_out.max_row

            team_fill = PatternFill(patternType='solid', fgColor=team_color) if team_color else None
            opp_rgb   = team_colors.get(opponent.lower()) if opponent else None
            opp_fill  = PatternFill(patternType='solid', fgColor=opp_rgb) if opp_rgb else None

            # Team=2, Player=3 — own team color
            for col in (2, 3):
                cell = ws_out.cell(current_row, col)
                cell.font = Font(bold=True)
                cell.border = border
                if team_fill:
                    cell.fill = team_fill

            # Opponent=15 — opponent's color
            opp_cell = ws_out.cell(current_row, 15)
            opp_cell.font = Font(bold=True)
            opp_cell.border = border
            if opp_fill:
                opp_cell.fill = opp_fill

        print(f"  -> {len(rows)} rows written")

    print(f"\nSaving to {OUTPUT_FILE} ...")
    wb_out.save(OUTPUT_FILE)
    print("Done! Review the output file, then copy any sheets you want into v5.")


if __name__ == "__main__":
    main()
