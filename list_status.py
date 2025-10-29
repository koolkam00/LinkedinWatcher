"""CLI utility to list the current snapshot for all tracked people."""

from __future__ import annotations

import argparse
from typing import List

from db import init_db
from models import list_people


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Show current LinkedIn snapshot data")
    parser.add_argument(
        "firm_filter",
        nargs="?",
        default=None,
        help="Optional firm to filter results",
    )
    return parser.parse_args()


def format_snapshot(title: str | None, company: str | None) -> str:
    """Create a human-readable snapshot string."""

    if title and company:
        return f"{title} @ {company}"
    if title:
        return title
    if company:
        return f"@ {company}"
    return "-"


def render_table(rows: List[List[str]]) -> None:
    """Render a table to stdout given rows including the header."""

    if not rows:
        return

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]

    for idx, row in enumerate(rows):
        padded = [row[i].ljust(widths[i]) for i in range(len(row))]
        print(" | ".join(padded))
        if idx == 0:
            print("-+-".join("-" * widths[i] for i in range(len(widths))))


def main() -> int:
    """Entry point for the status listing CLI."""

    args = parse_args()
    init_db()
    people = list_people(args.firm_filter)

    if not people:
        if args.firm_filter:
            print(f"No people found for firm '{args.firm_filter}'.")
        else:
            print("No people found. Use add_people.py to add entries first.")
        return 0

    header = ["ID", "Name", "Firm", "Title @ Company", "Last Seen"]
    rows: List[List[str]] = [header]

    for person in people:
        rows.append(
            [
                str(person["id"]),
                person["name"],
                person["firm"] or "-",
                format_snapshot(person["last_title"], person["last_company"]),
                person["last_seen"] or "-",
            ]
        )

    render_table(rows)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

