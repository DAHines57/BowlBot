"""Bowling scoreboard photo scan via Claude Vision (teams, players, scores)."""
from __future__ import annotations

import base64
import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from league_admin import parse_game_score
from stats.facts import name_matches_team, normalize

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_MODEL = "claude-sonnet-4-20250514"

EXTRACT_TOOL = {
    "name": "report_scoreboard",
    "description": (
        "Team names, player names, and game scores from a bowling alley "
        "scoreboard photo (one or more team panels)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teams": {
                "type": "array",
                "description": (
                    "Scoreboard panels left-to-right (or top-to-bottom). "
                    "Each panel is one team."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Team name as shown on the board header.",
                        },
                        "players": {
                            "type": "array",
                            "description": "Bowler rows top to bottom (not footer rows).",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": (
                                            "Player name as shown (truncation OK)."
                                        ),
                                    },
                                    "games": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "description": (
                                            "Pin scores for games 1–4 (or 5 if visible)."
                                        ),
                                    },
                                },
                                "required": ["name", "games"],
                            },
                        },
                        "team_scratch_by_game": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Optional team scratch total per game from footer."
                            ),
                        },
                        "team_grand_scratch": {
                            "type": "integer",
                            "description": (
                                "Optional team scratch series total from footer."
                            ),
                        },
                    },
                    "required": ["name", "players"],
                },
            },
            # Legacy single-team shape (older prompts / tests)
            "player_rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "games": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": ["games"],
                },
            },
            "team_scratch_by_game": {
                "type": "array",
                "items": {"type": "integer"},
            },
            "team_grand_scratch": {"type": "integer"},
        },
        "required": [],
    },
}

SCAN_PROMPT = """You are reading a photo of bowling alley scoreboard monitor(s).

Extract every team panel visible (usually one or two side-by-side monitors).
For each team panel return:
- name: the team name in the header
- players: bowler rows top to bottom, each with name and game pin scores (columns 1–4, plus 5 if present)
- optional team_scratch_by_game and team_grand_scratch from the Scratch footer row (for validation)

IGNORE summary/footer rows labeled Scratch, Handicap, or Total when listing players.
Truncated names (e.g. JOHNNY MCCORM...) are fine — return exactly what is visible.
Do not invent names or scores. If a cell is unreadable, omit that game rather than guessing.
Order teams left-to-right when two monitors are shown."""


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
        max_tokens=4096,
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


def _strip_ocr_noise(name: str) -> str:
    s = str(name or "").strip()
    s = re.sub(r"\.{2,}$", "", s).strip()
    return s


def _player_rows_from_team_blob(blob: dict[str, Any]) -> List[dict[str, Any]]:
    players = blob.get("players")
    if isinstance(players, list):
        return [r for r in players if isinstance(r, dict)]
    rows = blob.get("player_rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    legacy = blob.get("players")
    if isinstance(legacy, list):
        return [r for r in legacy if isinstance(r, dict)]
    return []


def normalize_teams_extract(extract: dict[str, Any]) -> List[dict[str, Any]]:
    """Normalize Claude output to a list of team blobs with players[]."""
    teams = extract.get("teams")
    if isinstance(teams, list) and teams:
        out: List[dict[str, Any]] = []
        for t in teams:
            if not isinstance(t, dict):
                continue
            players = _player_rows_from_team_blob(t)
            out.append(
                {
                    "name": _strip_ocr_noise(str(t.get("name") or "")),
                    "players": players,
                    "team_scratch_by_game": t.get("team_scratch_by_game"),
                    "team_grand_scratch": t.get("team_grand_scratch"),
                }
            )
        if out:
            return out

    # Legacy flat single-team extract
    player_rows = extract.get("player_rows")
    if not isinstance(player_rows, list):
        legacy = extract.get("players")
        player_rows = legacy if isinstance(legacy, list) else []
    rows = [r for r in player_rows if isinstance(r, dict)]
    if not rows:
        return []
    return [
        {
            "name": "",
            "players": rows,
            "team_scratch_by_game": extract.get("team_scratch_by_game"),
            "team_grand_scratch": extract.get("team_grand_scratch"),
        }
    ]


def _validate_team_blob(blob: dict[str, Any], label: str) -> List[str]:
    errors: List[str] = []
    player_rows = _player_rows_from_team_blob(blob)
    if not player_rows:
        return [f"{label}: no player score rows found."]

    team_by_game: List[int] = []
    for i, row in enumerate(player_rows):
        games = [g for g in (row.get("games") or []) if isinstance(g, int)]
        row_label = f"{label} row {i + 1}"
        if len(games) >= 4:
            scratch = row.get("scratch_total")
            if isinstance(scratch, int) and sum(games[:4]) != scratch:
                errors.append(
                    f"{row_label}: games 1–4 sum {sum(games[:4])} != scratch {scratch}"
                )
        for gi, g in enumerate(games):
            while len(team_by_game) <= gi:
                team_by_game.append(0)
            team_by_game[gi] += g

    expected_team = blob.get("team_scratch_by_game") or []
    if isinstance(expected_team, list):
        for gi, exp in enumerate(expected_team):
            if not isinstance(exp, int):
                continue
            if gi < len(team_by_game) and team_by_game[gi] != exp:
                errors.append(
                    f"{label} game {gi + 1}: row sum {team_by_game[gi]} != board {exp}"
                )

    grand = blob.get("team_grand_scratch")
    if isinstance(grand, int) and team_by_game:
        calc = sum(team_by_game[:4])
        if calc != grand:
            errors.append(f"{label} grand scratch: sum {calc} != board {grand}")

    return errors


def validate_extract(extract: dict[str, Any]) -> List[str]:
    """Arithmetic checks on numeric rows; catches many OCR mistakes."""
    teams = normalize_teams_extract(extract)
    if not teams:
        return ["No player score rows found in scan."]

    errors: List[str] = []
    for i, blob in enumerate(teams):
        name = (blob.get("name") or "").strip()
        label = name if name else (f"Team {i + 1}" if len(teams) > 1 else "Team")
        # Preserve legacy wording for single unnamed team (old tests)
        if len(teams) == 1 and not name:
            # Reuse old "Team game N" / "Team grand scratch" phrasing
            team_errors = _validate_team_blob(blob, "Team")
            remapped: List[str] = []
            for e in team_errors:
                e = e.replace("Team game ", "Team game ")
                e = e.replace("Team grand scratch:", "Team grand scratch:")
                e = e.replace("Team: no player", "No player")
                remapped.append(e)
            # Fix "Team row N" -> "Row N" for legacy
            remapped = [
                re.sub(r"^Team row (\d+):", r"Row \1:", e) for e in remapped
            ]
            remapped = [
                e.replace("No player score rows found.", "No player score rows found in scan.")
                if e.startswith("No player")
                else e
                for e in remapped
            ]
            errors.extend(remapped)
        else:
            errors.extend(_validate_team_blob(blob, label))
    return errors


def _games_to_score_fields(games: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "game1": None,
        "game2": None,
        "game3": None,
        "game4": None,
        "game5": None,
    }
    if isinstance(games, list):
        for idx, g in enumerate(games[:5]):
            score, err = parse_game_score(g)
            key = f"game{idx + 1}"
            if err:
                item[f"{key}_error"] = err
            elif score is not None:
                item[key] = int(score)
    return item


def extract_score_rows(extract: dict[str, Any]) -> List[dict[str, Any]]:
    """Turn Claude extract into editable score rows (legacy flat list)."""
    out: List[dict[str, Any]] = []
    for blob in normalize_teams_extract(extract):
        for i, row in enumerate(_player_rows_from_team_blob(blob)):
            item = {
                "row_index": len(out),
                "ocr_name": _strip_ocr_noise(str(row.get("name") or "")),
                "ocr_team": blob.get("name") or "",
                **_games_to_score_fields(row.get("games")),
            }
            out.append(item)
            # keep i used for clarity when debugging single-team order
            _ = i
    return out


def player_name_score(ocr_name: str, roster_name: str) -> float:
    """Similarity 0–1 for OCR vs roster player names (handles truncation)."""
    a = normalize(_strip_ocr_noise(ocr_name))
    b = normalize(str(roster_name or "").strip())
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.95
    # Prefix match for truncated board names (JOHNNY MCCORM vs Johnny McCormack)
    a_toks = a.split()
    b_toks = b.split()
    if a_toks and b_toks and a_toks[0] == b_toks[0]:
        if len(a_toks) >= 2 and b_toks[-1].startswith(a_toks[-1]):
            return 0.92
        if len(a_toks) == 1:
            return 0.7
    return SequenceMatcher(None, a, b).ratio()


def match_player_name(
    ocr_name: str, roster: List[str], *, used: Optional[set] = None
) -> Tuple[Optional[str], float]:
    used = used or set()
    best_name: Optional[str] = None
    best_score = 0.0
    for cand in roster:
        if cand in used:
            continue
        score = player_name_score(ocr_name, cand)
        if score > best_score:
            best_score = score
            best_name = cand
    if best_score < 0.55:
        return None, best_score
    return best_name, best_score


def match_team_name(
    ocr_name: str, team_names: List[str], *, used: Optional[set] = None
) -> Optional[str]:
    used = used or set()
    ocr = _strip_ocr_noise(ocr_name)
    if not ocr:
        return None
    # Prefer exact/loose name_matches_team first
    for cand in team_names:
        if cand in used:
            continue
        if name_matches_team(ocr, cand):
            return cand
    best_name: Optional[str] = None
    best_score = 0.0
    for cand in team_names:
        if cand in used:
            continue
        score = SequenceMatcher(
            None, normalize(ocr), normalize(cand)
        ).ratio()
        if score > best_score:
            best_score = score
            best_name = cand
    if best_score >= 0.55:
        return best_name
    return None


def match_scan_to_rosters(
    extract: dict[str, Any],
    teams_rosters: Dict[str, List[str]],
) -> List[dict[str, Any]]:
    """
    Match OCR teams/players to season rosters.

    teams_rosters: { canonical_team_name: [player_display_name, ...] }
    """
    team_names = list(teams_rosters.keys())
    used_teams: set = set()
    result: List[dict[str, Any]] = []
    warnings: List[str] = []

    for blob in normalize_teams_extract(extract):
        ocr_team = _strip_ocr_noise(str(blob.get("name") or ""))
        matched = match_team_name(ocr_team, team_names, used=used_teams)
        if matched:
            used_teams.add(matched)
        roster = list(teams_rosters.get(matched) or []) if matched else []
        # If unmatched, allow picking from all roster players across teams later in UI
        all_roster_fallback: List[str] = []
        if not matched:
            for names in teams_rosters.values():
                all_roster_fallback.extend(names)

        used_players: set = set()
        players_out: List[dict[str, Any]] = []
        for i, row in enumerate(_player_rows_from_team_blob(blob)):
            ocr_player = _strip_ocr_noise(str(row.get("name") or ""))
            pool = roster if roster else all_roster_fallback
            suggested, score = match_player_name(ocr_player, pool, used=used_players)
            if suggested:
                used_players.add(suggested)
            elif roster and i < len(roster) and roster[i] not in used_players:
                # Fall back to order when OCR name missing/weak
                if not ocr_player:
                    suggested = roster[i]
                    used_players.add(suggested)
                    score = 0.5
            fields = _games_to_score_fields(row.get("games"))
            players_out.append(
                {
                    "row_index": i,
                    "ocr_name": ocr_player,
                    "suggested_player": suggested,
                    "match_score": round(score, 3),
                    **fields,
                }
            )
            if ocr_player and suggested and score < 0.75:
                warnings.append(
                    f"Low-confidence player match: {ocr_player!r} → {suggested!r}"
                )

        if ocr_team and not matched:
            warnings.append(f"Could not match team from board: {ocr_team!r}")

        result.append(
            {
                "ocr_name": ocr_team,
                "matched_team": matched,
                "suggested_opponent": None,
                "players": players_out,
                "roster_players": roster
                if roster
                else sorted(set(all_roster_fallback)),
                "warnings": warnings[-5:] if not matched else [],
            }
        )

    # Dual-monitor boards: the two teams played each other.
    matched_only = [t for t in result if t.get("matched_team")]
    if len(matched_only) == 2:
        a = matched_only[0]["matched_team"]
        b = matched_only[1]["matched_team"]
        if a != b:
            matched_only[0]["suggested_opponent"] = b
            matched_only[1]["suggested_opponent"] = a
    elif len(result) == 2:
        # Prefer OCR pairing even if one/both teams unmatched — UI can still edit.
        a = result[0].get("matched_team")
        b = result[1].get("matched_team")
        if a and b and a != b:
            result[0]["suggested_opponent"] = b
            result[1]["suggested_opponent"] = a

    return result


def build_scan_response(
    extract: dict[str, Any],
    teams_rosters: Dict[str, List[str]],
) -> dict[str, Any]:
    """Validation + roster matching payload for the admin enter UI."""
    validation_errors = validate_extract(extract)
    teams = match_scan_to_rosters(extract, teams_rosters)
    for t in teams:
        for w in t.get("warnings") or []:
            if w not in validation_errors:
                validation_errors.append(w)
        t.pop("warnings", None)
    # Flat score_rows for backward compatibility with older UI
    score_rows = extract_score_rows(extract)
    return {
        "validation_errors": validation_errors,
        "teams": teams,
        "score_rows": score_rows,
    }
