"""Data access layer for the LinkedIn watcher tool."""

from __future__ import annotations

import csv
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from db import get_conn


def add_person(name: str, firm: str | None, profile_url: str) -> int:
    """Insert a new person into the watchlist and return their ID."""

    firm_value = firm if firm is not None and firm.strip() else None
    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO people (name, firm, profile_url, last_title, last_company, last_seen)
            VALUES (?, ?, ?, NULL, NULL, NULL)
            """,
            (name.strip(), firm_value, profile_url.strip()),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_person_by_id(person_id: int) -> sqlite3.Row | None:
    """Retrieve a person record by primary key."""

    conn = get_conn()
    try:
        cursor = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def list_people(firm_filter: str | None = None) -> list[sqlite3.Row]:
    """Return all tracked people, optionally filtered by firm."""

    conn = get_conn()
    try:
        if firm_filter:
            cursor = conn.execute(
                """
                SELECT * FROM people
                WHERE firm = ?
                ORDER BY firm ASC, name ASC
                """,
                (firm_filter,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM people
                ORDER BY firm ASC, name ASC
                """
            )
        return list(cursor.fetchall())
    finally:
        conn.close()


def update_person_snapshot(
    person_id: int, new_title: str | None, new_company: str | None
) -> None:
    """Update the stored snapshot for a person and mark the last seen date."""

    today_iso = dt.date.today().isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE people
            SET last_title = ?, last_company = ?, last_seen = ?
            WHERE id = ?
            """,
            (new_title, new_company, today_iso, person_id),
        )
        conn.commit()
    finally:
        conn.close()


def log_change(
    person_id: int,
    old_title: str | None,
    new_title: str | None,
    old_company: str | None,
    new_company: str | None,
    change_type: str,
) -> None:
    """Record a detected change for a person in the history table."""

    timestamp = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO history (
                person_id, timestamp, old_title, new_title, old_company, new_company, change_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (person_id, timestamp, old_title, new_title, old_company, new_company, change_type),
        )
        conn.commit()
    finally:
        conn.close()


def get_history_for_person(person_id: int) -> list[sqlite3.Row]:
    """Return the change history for a specific person ordered newest-first."""

    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM history
            WHERE person_id = ?
            ORDER BY timestamp DESC
            """,
            (person_id,),
        )
        return list(cursor.fetchall())
    finally:
        conn.close()


def export_full_history_to_csv(csv_path: str | Path) -> None:
    """Export all change history records to a CSV file."""

    path = Path(csv_path)
    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            SELECT
                h.timestamp,
                p.name,
                p.firm,
                h.old_title,
                h.new_title,
                h.old_company,
                h.new_company,
                h.change_type
            FROM history h
            JOIN people p ON p.id = h.person_id
            ORDER BY h.timestamp ASC
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "timestamp",
                "name",
                "firm",
                "old_title",
                "new_title",
                "old_company",
                "new_company",
                "change_type",
            ]
        )
        writer.writerows(rows)


def get_all_people_as_dicts() -> list[dict[str, Any]]:
    """Return all people as dictionaries for easy serialization."""

    people_rows = list_people()
    result: list[dict[str, Any]] = []
    for row in people_rows:
        result.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "firm": row["firm"],
                "profile_url": row["profile_url"],
                "last_title": row["last_title"],
                "last_company": row["last_company"],
                "last_seen": row["last_seen"],
            }
        )
    return result


def update_person_firm_by_id(person_id: int, firm: str | None) -> None:
    """Update the firm for a person by ID.

    Passing an empty or whitespace-only string will clear the firm (set to NULL).
    """

    normalized_firm = firm.strip() if isinstance(firm, str) else None
    if not normalized_firm:
        normalized_firm = None

    conn = get_conn()
    try:
        conn.execute("UPDATE people SET firm = ? WHERE id = ?", (normalized_firm, person_id))
        conn.commit()
    finally:
        conn.close()


def update_person_firm_by_url(profile_url: str, firm: str | None) -> int:
    """Update the firm for person(s) matching a profile URL.

    Returns the count of rows updated. If duplicates exist, all matches are updated.
    """

    normalized_firm = firm.strip() if isinstance(firm, str) else None
    if not normalized_firm:
        normalized_firm = None

    conn = get_conn()
    try:
        cursor = conn.execute(
            "UPDATE people SET firm = ? WHERE profile_url = ?", (normalized_firm, profile_url)
        )
        conn.commit()
        return cursor.rowcount if cursor.rowcount is not None else 0
    finally:
        conn.close()


def get_latest_title_change_for_person(person_id: int) -> sqlite3.Row | None:
    """Return the most recent title-change history row for a person, if any.

    This considers entries where change_type indicates a title change occurred:
    TITLE_CHANGE or TITLE_AND_COMPANY_CHANGE.
    """

    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            SELECT old_title, new_title, timestamp, change_type
            FROM history
            WHERE person_id = ? AND change_type IN ('TITLE_CHANGE','TITLE_AND_COMPANY_CHANGE')
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (person_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()

