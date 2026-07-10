# PhantomBuster Provider Reference

Read this file whenever a GTM skill selects PhantomBuster as a provider, or when generating any PB script.

---

## Env Setup

PB credentials live in your project .env file. Set its path via `GTM_ENV_PATH` in `_shared/local.md` (default: `$HOME/.env.gtm`).

PB scripts load all three vars **in-script** (rather than export+inject) because they need session cookie and user agent alongside the API key. Use this helper:

```python
import os
from pathlib import Path

def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV_PATH       = Path(os.environ.get("GTM_ENV_PATH", str(Path.home() / ".env.gtm")))
env            = load_env(ENV_PATH)
API_KEY        = env["PHANTOMBUSTER_API_KEY"]
SESSION_COOKIE = env["LINKEDIN_SESSION_COOKIE"]
USER_AGENT     = env["LINKEDIN_USER_AGENT"]
```

---

## Agent IDs — GTM Use Cases

PhantomBuster agent IDs are account-specific. **Do not hardcode them.** Three options to resolve at runtime:

1. **`_shared/local.md`** — your personal config file (gitignored). See `_shared/local.example.md` for the template.
2. **PhantomBuster MCP** — query `PHANTOMBUSTER_GET_AGENTS_FETCH_ALL` and match by phantom script name.
3. **PB dashboard** — copy the ID from the URL when viewing the agent.

| Use Case | Phantom Script | Local Config Key |
|----------|---------------|-----------------|
| **Connect** — send LinkedIn connection requests | LinkedIn Auto Connect.js | `PB_AGENT_CONNECT` |
| **Message** — send LinkedIn messages / InMails | Sales Navigator Message Sender.js | `PB_AGENT_MESSAGE` |
| **Company enrichment** — SN account data (headcount, revenue, growth) | Sales Navigator Account Scraper.js | `PB_AGENT_SN_ACCOUNT` |
| **People search** — employees at a company | LinkedIn Company Employees Export.js | `PB_AGENT_EMPLOYEES` |
| **People search** — SN search export | Sales Navigator Search Export.js | `PB_AGENT_SN_SEARCH` |
| **Profile scraping** — full profile data | LinkedIn Profile Scraper.js | `PB_AGENT_PROFILE` |
| **Signal search** — job postings export | LinkedIn Search Export.js | `PB_AGENT_JOB_SEARCH` |
| **Warm-up** — like posts before outreach | LinkedIn Auto Liker.js | `PB_AGENT_LIKER` |
| **Warm-up** — comment on posts | LinkedIn Auto Commenter.js | `PB_AGENT_COMMENTER` |
| **Maintenance** — withdraw old invitations | LinkedIn Auto Invitation Withdrawer.js | `PB_AGENT_WITHDRAWER` |
| **Inbox** — scrape message threads | LinkedIn Inbox Scraper.js | `PB_AGENT_INBOX` |
| **Export** — export all connections | LinkedIn Connections Export.js | `PB_AGENT_CONNECTIONS` |

To resolve an agent ID inside a script:

```python
# Option 1: from _shared/local.md (parsed as KEY=VALUE)
agent_id = local_config["PB_AGENT_CONNECT"]

# Option 2: via PB API by phantom name
agents = pb_api("GET", "agents/fetch-all")
agent_id = next(a["id"] for a in agents if a["script"] == "LinkedIn Auto Connect.js")
```

---

## Core Helper

```python
import subprocess, json, time

def pb_api(method, path, body=None):
    cmd = ["curl", "-s"]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(body)]
    cmd += [f"https://api.phantombuster.com/api/v2/{path}", "-H", f"X-Phantombuster-Key-1: {API_KEY}"]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)
```

---

## Script Pattern — One Row Per Run

All PB scripts process exactly one row per execution. Generate using this template:

```python
#!/usr/bin/env python3
"""pb_<agent_name>.py — Process one row per run via <Agent Name>."""

import csv, json, os, subprocess, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CSV_PATH   = SCRIPT_DIR / "<data_file>.csv"
STATE_PATH = SCRIPT_DIR / "pb_<agent_name>_state.json"
ENV_PATH   = Path(os.environ.get("GTM_ENV_PATH", str(Path.home() / ".env.gtm")))
AGENT_ID   = "<agent_id_from_local_md_or_mcp>"
API_KEY    = ""  # loaded at runtime

def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def pb_api(method, path, body=None):
    cmd = ["curl", "-s"]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(body)]
    cmd += [f"https://api.phantombuster.com/api/v2/{path}", "-H", f"X-Phantombuster-Key-1: {API_KEY}"]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)

def main():
    global API_KEY
    e              = load_env(ENV_PATH)
    API_KEY        = e["PHANTOMBUSTER_API_KEY"]
    session_cookie = e["LINKEDIN_SESSION_COOKIE"]
    user_agent     = e["LINKEDIN_USER_AGENT"]

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"done": []}
    done  = set(state["done"])

    row = None
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = r["<key_column>"].strip()
            if key and key not in done:
                row = r; break

    if not row:
        print("✅ All rows processed.")
        return

    key = row["<key_column>"].strip()
    print(f"▶  {row.get('<name_column>', key)} — {key}")

    argument = json.dumps({
        "<param>": key,
        "sessionCookie": session_cookie,
        "userAgent": user_agent,
        # ... agent-specific fields (see argument templates below)
    })

    resp = pb_api("POST", "agents/launch", {"id": AGENT_ID, "argument": argument})
    container_id = resp.get("containerId")
    if not container_id:
        print(f"❌ Launch failed: {resp}"); return

    print(f"🚀 Container {container_id} — polling...")
    while True:
        status = pb_api("GET", f"containers/fetch?id={container_id}")["status"]
        if status != "running": break
        time.sleep(5)
    print(f"✅ {status}")

    log = pb_api("GET", f"agents/fetch-output?id={AGENT_ID}&containerId={container_id}").get("output", "")
    print(log[-2000:] if len(log) > 2000 else log)

    done.add(key)
    STATE_PATH.write_text(json.dumps({"done": sorted(done)}, indent=2))

if __name__ == "__main__":
    main()
```

**Critical:** `argument` must be `json.dumps(dict)` — a JSON-encoded string. Booleans and numbers must be real JSON types (`false` not `"false"`, `1` not `"1"`). Python's `json.dumps()` handles this correctly; never hand-write the string.

---

## Argument Templates Per Agent

### LinkedIn Auto Connect
```python
argument = json.dumps({
    "inputType": "profileUrl",
    "profileUrl": row["linkedin_profile_url"],
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "enableScraping": False,
    "numberOfAddsPerLaunch": 1,
    "dwellTime": True,
})
```

### Sales Navigator Message Sender
```python
argument = json.dumps({
    "queries": row["linkedin_profile_url"],  # PB auto-converts to SN URL
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "messageControl": "sendOnlyIfNoMessage",
    "sendInMail": True,
    "message": row["linkedinMessage"],
    "inMailSubject": row["inmailSubject"],
})
```

### LinkedIn Company Employees Export
```python
argument = json.dumps({
    "spreadsheetUrl": row["company_linkedin_url"],
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "numberOfCompaniesPerLaunch": 1,
    "numberOfResultsPerCompany": 6,
    "positionFilter": "Sales OR COO OR Operations OR Director",
})
```

### Sales Navigator Account Scraper
```python
argument = json.dumps({
    "spreadsheetUrl": row["company_sn_url"],
    "columnName": "companyUrl",
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "numberOfLinesPerLaunch": 1,
    "csvName": "sn_account_scrape",
})
```

### LinkedIn Profile Scraper
```python
argument = json.dumps({
    "spreadsheetUrl": row["linkedin_profile_url"],
    "columnName": "profileUrl",
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "numberOfAddsPerLaunch": 1,
    "enrichWithCompanyData": True,
})
```

### LinkedIn Job Export (Signal Search)
```python
argument = json.dumps({
    "category": "Jobs",
    "searchType": "linkedInSearchUrl",
    "linkedInSearchUrl": row["job_search_url"],
    "sessionCookie": session_cookie,
    "userAgent": user_agent,
    "connectionDegreesToScrape": ["2", "3+"],
    "numberOfResultsPerLaunch": 500,
    "removeDuplicateProfiles": True,
    "enrichLeadsWithAdditionalInformation": False,
})
```

---

## Running & Looping

After generating and testing a script:

```bash
# Test once
python3 "<script_path>"

# Loop (every 20 min during business hours)
# /loop 20m python3 "<script_path>"
# Cron equivalent: */20 10-18 * * *
```

**Rate limits to respect:**
| Agent | Safe Pace | Hard Limit |
|-------|-----------|------------|
| LinkedIn Auto Connect | 1–2/run, max ~14/day | 100/week per LinkedIn account |
| Sales Navigator Message Sender | 1–3/run | No hard limit (InMail credits apply) |
| Company Employees Export | 1–5 companies/run | No hard limit |
| Profile Scraper | 5–10 profiles/run | No hard limit |
| Auto Liker / Commenter | 2–5/run | No hard limit |
