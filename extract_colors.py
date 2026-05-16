"""
Print team colors from the league Excel workbook.

Colors are stored in Postgres on teams.color_hex when you run: python sync_db.py
"""
from __future__ import annotations

import os
import sys

from db.excel_colors import extract_all_team_colors

EXCEL_FILE = "Bowling-Friends League v5.xlsx"


def main() -> int:
    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: {EXCEL_FILE} not found.", file=sys.stderr)
        return 1
    colors = extract_all_team_colors(EXCEL_FILE)
    print(f"{len(colors)} team colors in workbook (newest season wins per name):")
    for team, color in sorted(colors.items()):
        print(f"  {color}  {team}")
    print("\nRun python sync_db.py to persist colors on teams.color_hex.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
