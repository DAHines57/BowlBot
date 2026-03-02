# BowlBot Code Review

Issues are grouped by category and roughly ordered by priority/impact within each group.

---

## Bugs

### 1. `score 150 John` is parsed as a player query, not an add-score command
In `command_parser.py`, the `PLAYER_PATTERNS` list includes `r'score\s+(.+)'`, which is checked before `ADD_SCORE_PATTERNS`. So a message like `score 150 John` gets matched as a player lookup for someone named "150 John" instead of adding a score. The patterns need reordering or the `score` command needs to be disambiguated (require digits vs. name).

### 2. `get_team_scores` uses `week` instead of `week_param` on line 161
At the top of `get_team_scores`, the parameter is immediately saved as `week_param` to avoid shadowing by loop variables. However, line 161 still checks `if week is not None:` (the original parameter variable). It happens to work only because `week` hasn't been shadowed yet at that point, but it's fragile and inconsistent with the rest of the method. Change that check to `if week_param is not None:`.

### 3. `add_score` corrupts Excel formula cells
The workbook is loaded with `data_only=True`, which replaces formula cells with their last-cached values. When `add_score` calls `self.workbook.save(self.file_path)`, any formula cells in the file (e.g., the Average column) permanently lose their formulas and are replaced with static numbers. Any future edits to scores in Excel will not recalculate the Average column. Either reload the workbook without `data_only=True` for writes, or document this limitation prominently.

---

## Dead Code

### 4. `get_seasons` is defined twice in `ExcelHandler`
The method is defined at line 46 and again at line 961 with identical bodies. The second definition silently overrides the first. Remove the duplicate (the second one at the bottom).

### 5. Unused dependencies in `requirements.txt`
`pandas`, `gspread`, `google-auth`, and `google-auth-oauthlib` are all leftovers from an earlier Google Sheets implementation. None of these are imported anywhere in the current codebase. Remove them to keep the install lean.

### 6. Old Excel file still in the project directory
`Bowling- Friends League v4.xlsx` is the previous version of the spreadsheet and is no longer used. It can be deleted (or archived outside the project).

### 7. Dead regex pattern in `TEAM_PATTERNS`
`r'team\s+scores'` in the `TEAM_PATTERNS` list is never reachable because `r'team\s+(.+)'` (earlier in the same list) always matches first. Remove the dead entry.

### 8. Dead "backward compatibility" team record patterns
`TEAM_RECORD_PATTERNS` includes three patterns (`team [name] record`, `team record [name]`, `record [name]`) that are marked as "backward compatibility" but are not documented anywhere (not in `help`, not in `SETUP.md`). Either document them or remove them.

### 9. `_safe_float` and `_safe_int` duplicated across modules
Identical implementations of `_safe_float` and `_safe_int` exist in both `ExcelHandler` and `BotLogic`. Move them to a small shared utility module (e.g., `utils.py`) and import from there.

### 10. `CommandParser` imported inside a method body
In `bot_logic.py`, `from command_parser import CommandParser` is inside the `handle_command` method at line 57. Move it to the top of the file with the other imports.

---

## Performance

### 11. `get_team_scores` scans the full spreadsheet 3–4 times per call
The method does a first pass to build `team_data`, then for each team does another full pass to collect per-game totals, and for each week's opponent does yet another full pass to collect the opponent's games. For a 10-week season with 6 teams, this is dozens of full sheet scans per single bot command. Refactor to collect all per-game data for all teams in a single pass before the comparison step.

### 12. `get_league_stats` is called separately by each stats sub-command
`_handle_player_averages`, `_handle_best_player_weeks`, `_handle_best_team_weeks`, and `_handle_best_games` all call `get_league_stats` independently. That means the entire sheet is scanned four times when the user runs those commands back-to-back. Consider caching the result for the duration of the bot process, or combining them into one call.

### 13. No mechanism to reload Excel data without restarting
The workbook is loaded once in `__init__` and never refreshed. If the Excel file is updated while the bot is running, the bot will serve stale data until it is restarted. Adding a command (e.g., `reload` or `refresh`) that calls `_load_workbook()` again would let you update the spreadsheet without downtime.

---

## Stale Documentation

### 14. `SETUP.md` says "up to 4 games per week" in the Notes section
The Notes section at the bottom of `SETUP.md` still reads "Wins/losses are calculated per game … up to 4 games per week." The actual implementation now supports up to 5 games. Update the note.

### 15. `README.md` is significantly out of date
The README still lists the old column set (no Opponent column, no index column) and only mentions a handful of commands (`team`, `player`, `add score`, `seasons`, `help`). It does not mention the weekly record feature, the new stat commands (`averages`, `best games`, `best weeks`, `best team weeks`, `players`, `teams`), or the `w[N]`/`s[N]` week/season shorthand. Update it to match `SETUP.md`.

---

## Minor / Quality of Life

### 16. `teams` and `team` (no name) produce near-identical output
`teams` triggers `LIST_TEAMS` → `_handle_list_teams()` (bullet list titled "All Teams") while `team` with no name triggers `TEAM_SCORES` → `_handle_team_scores(None, …)` (numbered list titled "Team Standings"). Both show all teams with record and average. Consider removing the duplicate or making them meaningfully different (e.g., one shows standings with rank, the other is a flat alphabetical list).

### 17. `SheetHandler` abstract base class carries `add_score` even though it is barely used
The `add_score` abstraction implies write support is a first-class feature, but it has the formula-corruption issue noted above and there is no UI in the help text that encourages adding scores from the bot. If live score entry from WhatsApp is not a real use case, consider removing `add_score` from the ABC and from the help text, or at minimum flagging it as experimental.

### 18. WhatsApp API version is hardcoded in `main.py`
Line 101 uses `v18.0` in the Graph API URL. This should be an environment variable or config constant so it can be updated without a code change.
