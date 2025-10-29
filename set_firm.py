"""CLI to set or clear the firm for a tracked person.

Usage examples:
    python set_firm.py --id 1 --firm "CenterOak Partners"
    python set_firm.py --url https://www.linkedin.com/in/username --firm "Firm X"
    python set_firm.py --id 1 --clear
"""

from __future__ import annotations

import argparse
import sys

from db import init_db
from models import update_person_firm_by_id, update_person_firm_by_url


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set or clear firm for a tracked person")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, help="Person ID to update")
    group.add_argument("--url", type=str, help="Profile URL to update (all matches)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--firm", type=str, help="Firm name to set")
    action.add_argument("--clear", action="store_true", help="Clear firm (set to NULL)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    init_db()

    firm_value = None if args.clear else args.firm

    if args.id is not None:
        try:
            update_person_firm_by_id(args.id, firm_value)
        except Exception as exc:
            print(f"Update failed: {exc}", file=sys.stderr)
            return 1
        print("Updated 1 record by id.")
        return 0

    # Update by URL (may affect multiple rows if duplicates exist)
    try:
        updated = update_person_firm_by_url(args.url, firm_value)  # type: ignore[arg-type]
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    print(f"Updated {updated} record(s) by URL.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

