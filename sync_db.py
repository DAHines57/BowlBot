"""CLI: load sheet data into PostgreSQL. Requires DATABASE_URL and sheet env vars."""
import argparse
import logging
import sys

from db.sync import sync_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync bowling sheet data into PostgreSQL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows per season without writing to the database",
    )
    parser.add_argument(
        "--season",
        metavar="N",
        help="Only sync one season (e.g. 13 or 'Season 13')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        result = sync_database(dry_run=args.dry_run, season_filter=args.season)
    except Exception as exc:
        logging.error("%s", exc)
        return 1

    mode = "dry-run" if result["dry_run"] else "sync"
    print(
        f"{mode}: {result['rows']} rows, {result['seasons']} season(s), "
        f"{result['seconds']:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
