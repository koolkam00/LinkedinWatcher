"""Lightweight browser UI for the LinkedIn Watcher.

How to run:
    python web_app.py --host 127.0.0.1 --port 8000 --delay-seconds 5

Then open http://127.0.0.1:8000 in your browser.

Notes:
    - Uses only Python stdlib for the web server (wsgiref).
    - All scraping remains public-only and throttled; this UI simply orchestrates
      the existing modules.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
import threading
from typing import Callable, Iterable, Optional

from wsgiref.simple_server import make_server
import os
from urllib.parse import parse_qs

from db import init_db
from models import (
    add_person,
    export_full_history_to_csv,
    list_people,
    update_person_firm_by_id,
    get_latest_title_change_for_person,
)
from scraper_public import fetch_public_headline
from diff_logic import detect_and_record_change


HTML_HEADER = """<!doctype html><html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LinkedIn Watcher</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
    header { margin-bottom: 16px; }
    nav a { margin-right: 12px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background: #f6f6f6; }
    .btn { display: inline-block; padding: 6px 10px; border: 1px solid #999; border-radius: 4px; text-decoration: none; color: #000; background: #f3f3f3; }
    .btn:hover { background: #eaeaea; }
    form { margin: 0; }
    .flash { padding: 10px; border: 1px solid #ccc; background: #ffffe0; margin: 12px 0; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; }
    .grid { display: grid; grid-template-columns: 160px 1fr; gap: 8px; max-width: 720px; }
    input[type=text], input[type=url], select { padding: 6px; border: 1px solid #bbb; border-radius: 4px; width: 100%; }
  </style>
</head><body>
<header>
  <h1>LinkedIn Watcher</h1>
  <nav>
    <a href="/" class="btn">Home</a>
    <a href="/people" class="btn">People</a>
    <a href="/run" class="btn">Run Tracker</a>
    <a href="/bulk" class="btn">Bulk Upload</a>
    <a href="/history.csv" class="btn">Export History CSV</a>
  </nav>
</header>
"""

HTML_FOOTER = """
</body></html>
"""


class AppState:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds


def render_home(state: AppState) -> str:
    return (
        HTML_HEADER
        + f"""
        <section>
          <p>Welcome. Use this UI to manage your watchlist and run refreshes.</p>
          <ul>
            <li><a href="/people">Add or edit people</a></li>
            <li><a href="/run">Run tracker</a> (current delay: {state.delay_seconds:.1f}s)</li>
            <li><a href="/history.csv">Export full history CSV</a></li>
          </ul>
        </section>
        """
        + HTML_FOOTER
    )


def render_people(state: AppState, message: Optional[str] = None) -> str:
    rows = list_people()
    table_rows = []
    for p in rows:
        change = get_latest_title_change_for_person(int(p["id"]))
        if change and (change["old_title"] or change["new_title"]):
            recent_title_change = (
                f"'{change['old_title'] or '-'}' → '{change['new_title'] or '-'}'"
            )
        else:
            recent_title_change = "N/A"
        table_rows.append(
            f"<tr>"
            f"<td>{p['id']}</td>"
            f"<td>{p['name']}</td>"
            f"<td>{p['firm'] or '-'}</td>"
            f"<td>{(p['last_title'] or '-') }</td>"
            f"<td>{(p['last_company'] or '-') }</td>"
            f"<td>{(p['last_seen'] or '-') }</td>"
            f"<td>{recent_title_change}</td>"
            f"<td>"
            f"<form method=post action=/set_firm style='display:inline'>"
            f"<input type=hidden name=id value={p['id']} />"
            f"<input type=text name=firm placeholder=Firm value='{p['firm'] or ''}' />"
            f" <button class=btn type=submit>Save</button>"
            f" <button class=btn type=submit name=clear value=1>Clear</button>"
            f"</form>"
            f"</td>"
            f"</tr>"
        )

    flash_html = f"<div class=flash>{message}</div>" if message else ""
    return (
        HTML_HEADER
        + flash_html
        + """
        <section>
          <h2>People</h2>
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Firm</th><th>Last Title</th><th>Last Company</th><th>Last Seen</th><th>Recent Title Change</th><th>Actions</th></tr>
            </thead>
            <tbody>
        """
        + "".join(table_rows)
        + """
            </tbody>
          </table>
        </section>
        <section>
          <h3>Add Person</h3>
          <form method=post action=/add>
            <div class=grid>
              <label for=name>Name</label>
              <input id=name name=name type=text required placeholder="Jane Smith" />
              <label for=firm>Firm (optional)</label>
              <input id=firm name=firm type=text placeholder="CenterOak Partners" />
              <label for=url>LinkedIn Profile URL</label>
              <input id=url name=url type=url required placeholder="https://www.linkedin.com/in/username/" />
            </div>
            <p style="margin-top:10px"><button class=btn type=submit>Add</button></p>
          </form>
        </section>
        """
        + HTML_FOOTER
    )


def render_run_form(state: AppState, output: Optional[str] = None) -> str:
    flash_html = f"<div class=flash><div class=mono>{output}</div></div>" if output else ""
    return (
        HTML_HEADER
        + flash_html
        + f"""
        <section>
          <h2>Run Tracker</h2>
          <form method=post>
            <div class=grid>
              <label for=firm>Firm filter (exact, optional)</label>
              <input id=firm name=firm type=text />
              <label for=delay>Delay seconds</label>
              <input id=delay name=delay type=text value="{state.delay_seconds}" />
            </div>
            <p style="margin-top:10px"><button class=btn type=submit>Run</button></p>
          </form>
        </section>
        """
        + HTML_FOOTER
    )


def render_bulk_form(message: Optional[str] = None, output: Optional[str] = None) -> str:
    flash = []
    if message:
        flash.append(f"<div class=flash>{message}</div>")
    if output:
        flash.append(f"<div class=flash><div class=mono>{output}</div></div>")
    flash_html = "".join(flash)
    sample = "url,name,firm\nhttps://www.linkedin.com/in/username1/,Jane Smith,CenterOak Partners\nhttps://www.linkedin.com/in/username2/,,\n"
    return (
        HTML_HEADER
        + flash_html
        + f"""
        <section>
          <h2>Bulk Upload (CSV)</h2>
          <p>Upload a CSV exported from Excel. Columns supported (header optional): <strong>url</strong>, <em>name</em>, <em>firm</em>. Only <strong>url</strong> is required. Large uploads are processed in the background to avoid timeouts.</p>
          <form method="post" action="/bulk" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required />
            <button class="btn" type="submit">Upload & Add</button>
          </form>
          <details style="margin-top:10px"><summary>CSV example</summary>
            <pre class=mono>{sample}</pre>
          </details>
        </section>
        """
        + HTML_FOOTER
    )


def app(environ, start_response):  # type: ignore[no-untyped-def]
    # Keep a module-global state for delay seconds
    state: AppState = environ["app.state"]

    path = environ.get("PATH_INFO", "/") or "/"
    method = environ.get("REQUEST_METHOD", "GET").upper()

    def respond(
        status: str,
        body: str,
        content_type: str = "text/html; charset=utf-8",
        extra_headers: list[tuple[str, str]] | None = None,
    ):
        data = body.encode("utf-8")
        headers = [("Content-Type", content_type), ("Content-Length", str(len(data)))]
        if extra_headers:
            headers.extend(extra_headers)
        start_response(status, headers)
        return [data]

    # Routes
    if method == "GET" and path == "/":
        return respond("200 OK", render_home(state))

    if method == "GET" and path == "/people":
        return respond("200 OK", render_people(state))

    if method == "POST" and path == "/add":
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            size = 0
        body = environ["wsgi.input"].read(size).decode("utf-8")
        form = parse_qs(body)
        name = (form.get("name", [""])[0] or "").strip()
        firm = (form.get("firm", [""])[0] or "").strip() or None
        url = (form.get("url", [""])[0] or "").strip()
        if not name or not url.lower().startswith("http"):
            return respond("400 Bad Request", render_people(state, "Invalid name or URL."))
        add_person(name=name, firm=firm, profile_url=url)
        return respond(
            "303 See Other",
            "",
            content_type="text/plain; charset=utf-8",
            extra_headers=[("Location", "/")],
        )

    if method == "POST" and path == "/set_firm":
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            size = 0
        body = environ["wsgi.input"].read(size).decode("utf-8")
        form = parse_qs(body)
        pid = int((form.get("id", ["0"])[0] or "0"))
        clear = (form.get("clear", [""])[0] or "").strip() == "1"
        firm = None if clear else ((form.get("firm", [""])[0] or "").strip() or None)
        update_person_firm_by_id(pid, firm)
        return respond(
            "303 See Other",
            "",
            content_type="text/plain; charset=utf-8",
            extra_headers=[("Location", "/people")],
        )

    if path == "/run":
        if method == "GET":
            return respond("200 OK", render_run_form(state))
        # POST: run
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            size = 0
        body = environ["wsgi.input"].read(size).decode("utf-8")
        form = parse_qs(body)
        firm_filter = (form.get("firm", [""])[0] or "").strip() or None
        delay_str = (form.get("delay", [""])[0] or "").strip()
        try:
            if delay_str:
                state.delay_seconds = max(0.0, float(delay_str))
        except ValueError:
            pass

        # Perform run inline; for small lists this is acceptable
        people = list_people(firm_filter)
        if not people:
            return respond("200 OK", render_run_form(state, output="No people found for that filter."))

        msgs = []
        changed = unchanged = skipped = 0
        for idx, person in enumerate(people):
            person_name = person["name"]
            firm_label = person["firm"] or "-"
            try:
                result = fetch_public_headline(person["profile_url"])
            except Exception as exc:  # defensive
                skipped += 1
                msgs.append(f"[SKIP] {person_name} ({firm_label}) → unexpected_error:{exc}")
                continue

            error = result.get("error")
            observed_title = result.get("title")
            observed_company = result.get("company")

            if error or (observed_title is None and observed_company is None):
                skipped += 1
                reason = error or "profile not public / no headline"
                msgs.append(f"[SKIP] {person_name} ({firm_label}) → {reason}")
            else:
                try:
                    diff_result = detect_and_record_change(person, observed_title, observed_company)
                except Exception as exc:  # defensive
                    skipped += 1
                    msgs.append(f"[SKIP] {person_name} ({firm_label}) → diff_error:{exc}")
                    continue
                msgs.append(diff_result["message"])
                if diff_result["changed"]:
                    changed += 1
                else:
                    unchanged += 1

            if idx < len(people) - 1 and state.delay_seconds:
                time.sleep(state.delay_seconds)

        msgs.append(
            f"Checked {len(people)} people. {changed} changed. {unchanged} unchanged. {skipped} skipped."
        )
        return respond("200 OK", render_run_form(state, output="\n".join(msgs)))

    if path == "/bulk":
        if method == "GET":
            return respond("200 OK", render_bulk_form())
        # POST: process CSV upload
        # Minimal multipart/form-data parser (no cgi)
        content_type = environ.get("CONTENT_TYPE", "")
        if "multipart/form-data" not in content_type:
            return respond("400 Bad Request", render_bulk_form(message="Invalid content type."))
        boundary_key = "boundary="
        boundary_index = content_type.find(boundary_key)
        if boundary_index == -1:
            return respond("400 Bad Request", render_bulk_form(message="Missing multipart boundary."))
        boundary = content_type[boundary_index + len(boundary_key) :].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            size = 0
        raw_body = environ["wsgi.input"].read(size)
        delim = ("--" + boundary).encode()
        parts = raw_body.split(delim)
        file_bytes: bytes | None = None
        for part in parts:
            part = part.lstrip(b"\r\n")
            if not part or part.startswith(b"--"):
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers_blob = part[:header_end].decode("utf-8", errors="ignore")
            content = part[header_end + 4 :]
            # trim trailing CRLF if present
            if content.endswith(b"\r\n"):
                content = content[:-2]
            dispo_line = next((h for h in headers_blob.split("\r\n") if h.lower().startswith("content-disposition:")), "")
            if "name=\"file\"" in dispo_line:
                file_bytes = content
                break
        if file_bytes is None:
            return respond("400 Bad Request", render_bulk_form(message="No file part named 'file'."))
        try:
            text = file_bytes.decode("utf-8-sig", errors="replace")
        except Exception as exc:
            return respond("400 Bad Request", render_bulk_form(message=f"Failed to decode file: {exc}"))

        # Count rows quickly for user feedback
        try:
            total_rows = sum(1 for _ in csv.reader(io.StringIO(text)))
        except Exception:
            total_rows = 0

        def _background_process(csv_text: str) -> None:
            reader_local = csv.reader(io.StringIO(csv_text))
            rows_local = list(reader_local)
            if not rows_local:
                return
            header_local = [h.strip().lower() for h in rows_local[0]]
            has_header_local = (
                "url" in header_local or "name" in header_local or "firm" in header_local
            )
            start_idx_local = 1 if has_header_local else 0

            def get_cols_local(row):
                if has_header_local:
                    mapping = {
                        header_local[i]: (row[i].strip() if i < len(row) else "")
                        for i in range(len(header_local))
                    }
                    return mapping.get("url", ""), mapping.get("name", ""), mapping.get("firm", "")
                url = row[0].strip() if len(row) > 0 else ""
                name = row[1].strip() if len(row) > 1 else ""
                firm = row[2].strip() if len(row) > 2 else ""
                return url, name, firm

            for row in rows_local[start_idx_local:]:
                if not row or all((cell or "").strip() == "" for cell in row):
                    continue
                url, name, firm = get_cols_local(row)
                if not url.lower().startswith("http"):
                    continue
                # Avoid long request time: do not auto-detect here; rely on tracker run
                # If name missing, try a lightweight detect but without sleep
                if not name:
                    try:
                        res = fetch_public_headline(url)
                        if not res.get("error"):
                            name = (res.get("name_from_page") or "").strip() or name
                            if not firm:
                                firm = (res.get("company") or "").strip() or firm
                    except Exception:
                        pass
                if not name:
                    name = url  # fallback so record is created; user can edit later
                try:
                    add_person(name=name, firm=(firm or None), profile_url=url)
                except Exception:
                    continue

        threading.Thread(target=_background_process, args=(text,), daemon=True).start()
        queued_msg = (
            f"Upload received. Queued processing for approximately {max(0, total_rows - 1)} rows. "
            "You can navigate away; entries will appear on the People page as they are added."
        )
        return respond("200 OK", render_bulk_form(message=queued_msg))

    if method == "GET" and path == "/history.csv":
        # Stream CSV in-memory for simplicity
        # Build CSV using existing query logic
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "name",
            "firm",
            "old_title",
            "new_title",
            "old_company",
            "new_company",
            "change_type",
        ])
        # replicate export query
        from db import get_conn

        conn = get_conn()
        try:
            cur = conn.execute(
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
            for row in cur.fetchall():
                writer.writerow(row)
        finally:
            conn.close()

        data = output.getvalue().encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/csv; charset=utf-8"),
                ("Content-Length", str(len(data))),
                ("Content-Disposition", "attachment; filename=history.csv"),
            ],
        )
        return [data]

    # Fallback 404
    return respond("404 Not Found", HTML_HEADER + "<p>Not Found</p>" + HTML_FOOTER)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LinkedIn Watcher Web UI")
    default_port = int(os.environ.get("PORT", "8000"))
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=default_port, help="Bind port")
    parser.add_argument("--delay-seconds", type=float, default=5.0, help="Default delay between requests")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.delay_seconds < 0:
        print("Delay must be non-negative", file=sys.stderr)
        return 1
    init_db()
    state = AppState(delay_seconds=args.delay_seconds)

    with make_server(args.host, args.port, lambda env, sr: app({**env, "app.state": state}, sr)) as httpd:
        print(f"Serving on http://{args.host}:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

