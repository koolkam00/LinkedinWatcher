# LinkedIn Watcher

Local tool and simple browser UI to track public headline changes (title/company) for specific LinkedIn profiles.

## Quick start

```bash
cd "/Users/andrewkam/Desktop/LinkedIn Watcher"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python db.py
python add_people.py
python run_tracker.py
```

## Browser UI

```bash
python web_app.py --host 127.0.0.1 --port 8000 --delay-seconds 5
```
Open http://127.0.0.1:8000

- People: list, add, set/clear firm
- Run Tracker: run refresh with optional firm filter and delay
- Export History CSV: download full audit trail

## Compliance
- Public-only: no login, no authenticated cookies, no CAPTCHA/proxy/rotation
- Throttled requests (default 5s delay; configurable)
- Non-public pages are skipped
