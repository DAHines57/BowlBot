"""Bowling scoreboard photo scan via Claude Vision (scores-only, no names to API)."""
from __future__ import annotations

import base64
import os
from typing import Any, List

from league_admin import parse_game_score

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_MODEL = "claude-sonnet-4-20250514"

EXTRACT_TOOL = {
    "name": "report_scoreboard",
    "description": "Numeric game scores from a cropped scoreboard image (game columns only).",
    "input_schema": {
        "type": "object",
        "properties": {
            "player_rows": {
                "type": "array",
                "description": "Bowler rows top to bottom; each row is one player's game scores only.",
                "items": {
                    "type": "object",
                    "properties": {
                        "games": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Pin scores for games 1–4 (or 5 if visible).",
                        },
                    },
                    "required": ["games"],
                },
            },
            "team_scratch_by_game": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional team scratch total per game column from footer row.",
            },
            "team_grand_scratch": {
                "type": "integer",
                "description": "Optional team scratch total across all games from footer.",
            },
        },
        "required": ["player_rows"],
    },
}

SCAN_PROMPT = """You are reading a cropped image of a bowling scoreboard that shows ONLY numeric game columns (no player names).

Extract one object per bowler row, ordered top to bottom as shown on screen.
Each row should include only the game pin scores (columns 1, 2, 3, 4, and 5 if present).

IGNORE summary/footer rows (Scratch, Handicap, Total) if they appear in the crop.
Do not infer or return any player names or team names.

Return integers only. If a cell is unreadable, omit that game rather than guessing."""


def scan_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def scan_scoreboard_image(image_bytes: bytes, media_type: str) -> dict[str, Any]:
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported image type: {media_type}")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image too large (max 8 MB).")
    if not scan_configured():
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    import anthropic

    client = anthropic.Anthropic()
    model = os.environ.get("SCOREBOARD_SCAN_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "report_scoreboard"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": SCAN_PROMPT},
                ],
            }
        ],
    )
    for block in msg.content:
        if block.type == "tool_use" and block.name == "report_scoreboard":
            return dict(block.input)
    raise ValueError("Claude did not return scoreboard tool output")


def _player_rows_from_extract(extract: dict[str, Any]) -> List[dict[str, Any]]:
    rows = extract.get("player_rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    # Legacy shape from earlier implementation (tests may still use "players")
    legacy = extract.get("players")
    if isinstance(legacy, list):
        return [r for r in legacy if isinstance(r, dict)]
    return []


def validate_extract(extract: dict[str, Any]) -> List[str]:
    """Arithmetic checks on numeric rows; catches many OCR mistakes."""
    errors: List[str] = []
    player_rows = _player_rows_from_extract(extract)
    if not player_rows:
        return ["No player score rows found in scan."]

    team_by_game: List[int] = []

    for i, row in enumerate(player_rows):
        games = [g for g in (row.get("games") or []) if isinstance(g, int)]
        label = f"Row {i + 1}"

        if len(games) >= 4:
            scratch = row.get("scratch_total")
            if isinstance(scratch, int) and sum(games[:4]) != scratch:
                errors.append(
                    f"{label}: games 1–4 sum {sum(games[:4])} != scratch {scratch}"
                )

        for gi, g in enumerate(games):
            while len(team_by_game) <= gi:
                team_by_game.append(0)
            team_by_game[gi] += g

    expected_team = extract.get("team_scratch_by_game") or []
    if isinstance(expected_team, list):
        for gi, exp in enumerate(expected_team):
            if not isinstance(exp, int):
                continue
            if gi < len(team_by_game) and team_by_game[gi] != exp:
                errors.append(
                    f"Team game {gi + 1}: row sum {team_by_game[gi]} != board {exp}"
                )

    grand = extract.get("team_grand_scratch")
    if isinstance(grand, int) and team_by_game:
        calc = sum(team_by_game[:4])
        if calc != grand:
            errors.append(f"Team grand scratch: sum {calc} != board {grand}")

    return errors


def extract_score_rows(extract: dict[str, Any]) -> List[dict[str, Any]]:
    """Turn Claude extract into editable score rows (no player assignment)."""
    out: List[dict[str, Any]] = []
    for i, row in enumerate(_player_rows_from_extract(extract)):
        item: dict[str, Any] = {
            "row_index": i,
            "game1": None,
            "game2": None,
            "game3": None,
            "game4": None,
            "game5": None,
        }
        games = row.get("games") or []
        if isinstance(games, list):
            for idx, g in enumerate(games[:5]):
                score, err = parse_game_score(g)
                key = f"game{idx + 1}"
                if err:
                    item[f"{key}_error"] = err
                elif score is not None:
                    item[key] = int(score)
        out.append(item)
    return out
