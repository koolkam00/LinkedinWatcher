"""Business logic for comparing stored and observed profile data."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from models import log_change, update_person_snapshot


def _normalize(value: str | None) -> str | None:
    """Return a stripped string or None if the value is empty."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _format_value(value: str | None) -> str:
    """Format a value for human-readable output."""

    return value if value is not None else "-"


def detect_and_record_change(
    person_row: sqlite3.Row,
    observed_title: str | None,
    observed_company: str | None,
) -> Dict[str, Any]:
    """Compare stored data with observed values and log changes as needed."""

    observed_title_norm = _normalize(observed_title)
    observed_company_norm = _normalize(observed_company)

    person_id = int(person_row["id"])
    person_name = person_row["name"]
    last_title = person_row["last_title"]
    last_company = person_row["last_company"]

    if last_title is None and last_company is None:
        log_change(
            person_id=person_id,
            old_title=None,
            new_title=observed_title_norm,
            old_company=None,
            new_company=observed_company_norm,
            change_type="INIT",
        )
        update_person_snapshot(person_id, observed_title_norm, observed_company_norm)
        message = (
            f"[INIT] {person_name}: title='{_format_value(observed_title_norm)}' "
            f"company='{_format_value(observed_company_norm)}'"
        )
        return {"person_id": person_id, "name": person_name, "changed": True, "message": message}

    title_changed = (
        observed_title_norm is not None and observed_title_norm != last_title
    )
    company_changed = (
        observed_company_norm is not None and observed_company_norm != last_company
    )

    if not title_changed and not company_changed:
        update_person_snapshot(person_id, last_title, last_company)
        message = f"[NO CHANGE] {person_name}"
        return {"person_id": person_id, "name": person_name, "changed": False, "message": message}

    if title_changed and company_changed:
        change_type = "TITLE_AND_COMPANY_CHANGE"
    elif title_changed:
        change_type = "TITLE_CHANGE"
    else:
        change_type = "COMPANY_CHANGE"

    log_change(
        person_id=person_id,
        old_title=last_title,
        new_title=observed_title_norm,
        old_company=last_company,
        new_company=observed_company_norm,
        change_type=change_type,
    )
    update_person_snapshot(person_id, observed_title_norm, observed_company_norm)

    lines = [f"[CHANGE] {person_name}:"]
    if title_changed:
        lines.append(
            "  Title:    '"
            + _format_value(last_title)
            + "' → '"
            + _format_value(observed_title_norm)
            + "'"
        )
    if company_changed:
        lines.append(
            "  Company:  '"
            + _format_value(last_company)
            + "' → '"
            + _format_value(observed_company_norm)
            + "'"
        )
    message = "\n".join(lines)
    return {"person_id": person_id, "name": person_name, "changed": True, "message": message}

