"""CLI utility to export the full change history to CSV."""

from __future__ import annotations

import argparse

from db import init_db
from models import export_full_history_to_csv


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Export change history to CSV")
    parser.add_argument("output", help="Path to the CSV file to create")
    return parser.parse_args()


def main() -> int:
    """Entry point for history export."""

    args = parse_args()
    init_db()
    export_full_history_to_csv(args.output)
    print(f"Exported full history to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

