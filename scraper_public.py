"""LinkedIn public profile scraper.

WARNING:
    - This code only attempts to access publicly visible LinkedIn profile data.
    - It must NOT attempt to log in, reuse authenticated cookies, solve CAPTCHAs,
      rotate proxies, or evade rate limits.
    - LinkedIn's terms of service may restrict automated scraping. Consult legal
      and compliance stakeholders before use.
    - Use strictly for a small internal watchlist with a legitimate business
      purpose (e.g., monitoring general partner stability during diligence).
    - If a profile is not publicly visible, this module will report that and
      return no headline data.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup
import time
import json


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def fetch_public_headline(profile_url: str) -> Dict[str, Optional[str]]:
    """Fetch the public headline information from a LinkedIn profile.

    Parameters
    ----------
    profile_url:
        The publicly accessible LinkedIn profile URL.

    Returns
    -------
    dict
        A dictionary containing parsed headline components or error details.
    """

    headers = {
        "User-Agent": USER_AGENT,
        # Be explicit to receive the standard public HTML rendition
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close",
    }
    # Gentle retry once for transient 5xx errors; no evasion
    for attempt in range(2):
        try:
            response = requests.get(profile_url, headers=headers, timeout=15)
        except requests.RequestException as exc:  # pragma: no cover - network failure path
            return {
                "name_from_page": None,
                "title": None,
                "company": None,
                "error": f"network_error:{exc.__class__.__name__}",
            }
        if response.status_code == 200:
            break
        if attempt == 0 and response.status_code in {500, 502, 503, 504}:
            time.sleep(1.0)
            continue
        return {
            "name_from_page": None,
            "title": None,
            "company": None,
            "error": f"bad_status:{response.status_code}",
        }

    soup = BeautifulSoup(response.text, "html.parser")

    def split_headline_text(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        t = text.strip()
        # Trim common suffixes
        for suffix in ("| LinkedIn", "| LinkedIn Profile", "| Professional Profile | LinkedIn"):
            if t.endswith(suffix):
                t = t[: -len(suffix)].strip()
        # Prefer hyphen delimiter, then fall back to pipe
        parts = [p.strip() for p in t.split(" - ") if p.strip()]
        if len(parts) <= 1 and "|" in t:
            parts = [p.strip() for p in t.split("|") if p.strip()]
        name: Optional[str] = None
        title: Optional[str] = None
        company: Optional[str] = None
        if parts:
            name = parts[0]
        if len(parts) == 2:
            # Sometimes the second part contains "Title at Company"
            p = parts[1]
            if " at " in p:
                before, after = p.split(" at ", 1)
                title = before.strip() or None
                company = after.strip() or None
            else:
                title = p
        elif len(parts) >= 3:
            title = " - ".join(parts[1:-1]) or None
            company = parts[-1]
        return name or None, title or None, company or None

    name_from_page: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None

    # Primary: og:title
    meta_tag = soup.find("meta", attrs={"property": "og:title"})
    if meta_tag and meta_tag.get("content"):
        name_from_page, title, company = split_headline_text(meta_tag["content"]) 

    # Fallback: twitter:title (often mirrors page title)
    if not title:
        tw_title = soup.find("meta", attrs={"name": "twitter:title"}) or soup.find(
            "meta", attrs={"property": "twitter:title"}
        )
        if tw_title and tw_title.get("content"):
            n2, t2, c2 = split_headline_text(tw_title["content"]) 
            name_from_page = name_from_page or n2
            title = title or t2
            company = company or c2

    # Fallback: og:description / meta description (if contains expected pattern)
    if not title and not company:
        desc_tag = soup.find("meta", attrs={"property": "og:description"}) or soup.find(
            "meta", attrs={"name": "description"}
        )
        if desc_tag and desc_tag.get("content") and " - " in desc_tag["content"]:
            n2, t2, c2 = split_headline_text(desc_tag["content"])
            name_from_page = name_from_page or n2
            title = title or t2
            company = company or c2

    # Fallback: twitter:description
    if not title and not company:
        tw_desc = soup.find("meta", attrs={"name": "twitter:description"}) or soup.find(
            "meta", attrs={"property": "twitter:description"}
        )
        if tw_desc and tw_desc.get("content"):
            n2, t2, c2 = split_headline_text(tw_desc["content"]) 
            name_from_page = name_from_page or n2
            title = title or t2
            company = company or c2

    # Fallback: JSON-LD Person schema if present
    if not title and not company:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.text)
            except Exception:
                continue
            # LinkedIn may embed dictionaries or lists
            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if not isinstance(obj, dict):
                    continue
                if obj.get("@type") == "Person":
                    if not name_from_page and isinstance(obj.get("name"), str):
                        name_from_page = obj["name"].strip() or name_from_page
                    if isinstance(obj.get("jobTitle"), str):
                        title = title or (obj["jobTitle"].strip() or None)
                    works_for = obj.get("worksFor")
                    if isinstance(works_for, dict) and isinstance(works_for.get("name"), str):
                        company = company or (works_for["name"].strip() or None)
            if title or company:
                break

    # Fallback: <title> element text
    if not title and not company:
        if soup.title and soup.title.string:
            n2, t2, c2 = split_headline_text(soup.title.string)
            name_from_page = name_from_page or n2
            title = title or t2
            company = company or c2

    if not any([name_from_page, title, company]):
        return {
            "name_from_page": None,
            "title": None,
            "company": None,
            "error": "no_public_headline",
        }

    return {
        "name_from_page": name_from_page,
        "title": title,
        "company": company,
        "error": None,
    }

