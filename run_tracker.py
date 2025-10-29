"""Command-line entry point to refresh the LinkedIn watchlist."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from db import init_db
from diff_logic import detect_and_record_change
from models import list_people
from scraper_public import fetch_public_headline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the tracker run."""

    parser = argparse.ArgumentParser(description="Refresh LinkedIn public headlines")
    parser.add_argument(
        "firm_filter",
        nargs="?",
        default=None,
        help="Optional firm name to limit the refresh",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=5.0,
        help="Delay between profile fetches (seconds)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the tracker and print a summary of detected changes."""

    args = parse_args(argv)
    if args.delay_seconds < 0:
        print("Delay must be non-negative.", file=sys.stderr)
        return 1

    init_db()
    people = list_people(args.firm_filter)
    if not people:
        if args.firm_filter:
            print(f"No people found for firm '{args.firm_filter}'. Nothing to do.")
        else:
            print("No people found in the database. Use add_people.py to seed entries.")
        return 0

    total = len(people)
    changed_count = 0
    unchanged_count = 0
    skipped_count = 0

    delay = args.delay_seconds

    for index, person in enumerate(people):
        person_name = person["name"]
        firm_label = person["firm"] or "-"
        try:
            result = fetch_public_headline(person["profile_url"])
        except Exception as exc:  # pragma: no cover - defensive catch
            skipped_count += 1
            print(f"[SKIP] {person_name} ({firm_label}) → unexpected_error:{exc}")
            continue

        error = result.get("error")
        observed_title = result.get("title")
        observed_company = result.get("company")

        if error or (observed_title is None and observed_company is None):
            skipped_count += 1
            reason = error or "profile not public / no headline"
            print(f"[SKIP] {person_name} ({firm_label}) → {reason}")
        else:
            try:
                diff_result = detect_and_record_change(person, observed_title, observed_company)
            except Exception as exc:  # pragma: no cover - defensive catch
                skipped_count += 1
                print(f"[SKIP] {person_name} ({firm_label}) → diff_error:{exc}")
                continue

            print(diff_result["message"])
            if diff_result["changed"]:
                changed_count += 1
            else:
                unchanged_count += 1

        if index < total - 1 and delay:
            time.sleep(delay)

    print(
        f"Checked {total} people. {changed_count} changed. "
        f"{unchanged_count} unchanged. {skipped_count} skipped."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

