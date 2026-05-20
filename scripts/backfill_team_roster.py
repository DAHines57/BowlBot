"""Backfill team_roster_members from existing player_week rows.

Run after `alembic upgrade head` on local or production:

  python scripts/backfill_team_roster.py
  python scripts/backfill_team_roster.py --season 13
  python scripts/backfill_team_roster.py --clear   # replace existing memberships
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from db.models import Season
from db.roster_members import backfill_all_seasons, backfill_season_roster
from db.session import get_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Only backfill this season number (default: all seasons)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing memberships for target season(s) before backfill",
    )
    args = parser.parse_args()

    with get_session() as session:
        if args.season is not None:
            season = session.scalar(select(Season).where(Season.number == args.season))
            if season is None:
                print(f"Season {args.season} not found.", file=sys.stderr)
                return 1
            n = backfill_season_roster(
                session, season.id, clear_existing=args.clear
            )
            session.commit()
            print(f"Season {args.season}: {n} roster membership(s) upserted.")
        else:
            n = backfill_all_seasons(session, clear_existing=args.clear)
            session.commit()
            print(f"All seasons: {n} roster membership(s) upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
