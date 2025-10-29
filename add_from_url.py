"""Add people by auto-detecting name and firm from a public LinkedIn profile.

Usage:
    python add_from_url.py https://www.linkedin.com/in/username
    python add_from_url.py URL1 URL2 ...

Behavior:
    - Fetches public metadata for each URL using the compliant scraper.
    - Extracts name (required) and firm (optional, from company).
    - Inserts a row into `people` with the detected values.
    - Prints the created IDs or a clear SKIP reason.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from db import init_db
from models import add_person
from scraper_public import fetch_public_headline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add people from LinkedIn URLs with auto-detected fields")
    parser.add_argument("urls", nargs="+", help="One or more public LinkedIn profile URLs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    init_db()

    added = 0
    for url in args.urls:
        if not url.lower().startswith("http"):
            print(f"[SKIP] {url} → invalid_url")
            continue

        result = fetch_public_headline(url)
        error = result.get("error")
        name = (result.get("name_from_page") or "").strip() or None
        firm = (result.get("company") or "").strip() or None

        if error and not name:
            print(f"[SKIP] {url} → {error}")
            continue

        if not name:
            print(f"[SKIP] {url} → could_not_detect_name")
            continue

        try:
            person_id = add_person(name=name, firm=firm, profile_url=url)
        except Exception as exc:  # defensive
            print(f"[SKIP] {url} → db_error:{exc}")
            continue

        firm_label = firm or "-"
        print(f"[ADDED] id={person_id} name='{name}' firm='{firm_label}'")
        added += 1

    if added == 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

