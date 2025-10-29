"""Interactive CLI utility to seed new people into the watchlist."""

from __future__ import annotations

import sys

from db import init_db
from models import add_person


def _prompt_required(prompt: str) -> str:
    """Prompt until the user provides a non-empty response."""

    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field is required. Please enter a value.")


def _prompt_profile_url() -> str:
    """Prompt for a LinkedIn profile URL with basic validation."""

    while True:
        url = input("LinkedIn profile URL: ").strip()
        if not url:
            print("Profile URL cannot be empty.")
            continue
        if not url.lower().startswith("http"):
            print("Profile URL must start with 'http'. Please try again.")
            continue
        return url


def main() -> int:
    """Run the interactive prompt for adding people."""

    init_db()
    print("Add people to the LinkedIn watchlist. Press Ctrl+C to exit at any prompt.")

    try:
        while True:
            name = _prompt_required("Name: ")
            firm = input("Firm (optional): ").strip() or None
            profile_url = _prompt_profile_url()

            person_id = add_person(name=name, firm=firm, profile_url=profile_url)
            print(f"Added '{name}' with ID {person_id}.")

            while True:
                another = input("Add another? (y/n): ").strip().lower()
                if another in {"y", "yes"}:
                    break
                if another in {"n", "no"}:
                    print("Done.")
                    return 0
                print("Please respond with 'y' or 'n'.")
    except KeyboardInterrupt:
        print("\nCancelled. Goodbye.")
        return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

