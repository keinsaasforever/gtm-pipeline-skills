#!/usr/bin/env python3
"""
pb_email_finder.py — Priority-1 email enrichment via the PhantomBuster Email Finder.

The PhantomBuster "Email Finder" phantom (emailChooser=phantombuster) resolves a
professional email from first name + last name + company domain, using PB's built-in
email waterfall (BetterContact et al.) under the hood. It is a *data* phantom — no
LinkedIn session cookie required.

Unlike FullEnrich / BetterContact / Pipe0 (direct JSON POST), this phantom reads its
input from a Google Sheet tab (`spreadsheetUrl`). This engine therefore:
  1. stages the input contacts into a worksheet in a spreadsheet you already own,
  2. launches the phantom pointed at that tab,
  3. polls the container to completion,
  4. fetches the result object, maps emails back by (first, last, domain),
  5. writes email / email_status / email_source into an output CSV (all original
     columns preserved).

SKIP-IF-N/A CONTRACT (exit code 3): this engine is Priority 1 in the email waterfall,
but it is optional infrastructure. It exits 3 — a clean "not available, fall through to
the next provider" — when ANY prerequisite is missing:
  - PHANTOMBUSTER_API_KEY not set
  - gspread not importable / Google OAuth creds not found
  - no --staging-spreadsheet-id given
The caller (people-enrichment / demo) treats exit 3 as "skip, run FullEnrich next".
Exit 0 = ran (emails may or may not have been found). Exit 1 = hard error.

Domain-identity cross-check (conventions rule): a returned email whose domain does not
belong to the target company is DROPPED by default (not written), honouring the
people-enrichment MANDATORY cross-check. Use --keep-mismatch to override.

Usage:
    source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh"
    export $(grep -E '^PHANTOMBUSTER_API_KEY=' "$GTM_ENV_PATH" | xargs)
    python3 pb_email_finder.py \
        --input  csv/intermediate/contacts_filtered.csv \
        --output csv/intermediate/contacts_pb_email.csv \
        --staging-spreadsheet-id 1AbC...xyz

Column names default to the GTM people schema (snake_case) and are all overridable.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

# ── PhantomBuster config ───────────────────────────────────────────────────

# Account-specific; do NOT rely on this default. Resolve via PB_AGENT_EMAIL in the
# env / _shared/local.md, or by phantom name "Email Finder" through the PB API/MCP.
# The value below is the keinsaas account's Email Finder agent, kept as a fallback.
DEFAULT_PB_EMAIL_AGENT_ID = "4895754995515269"

PB_INITIAL_WAIT = 180   # phantom needs ~3 min before results appear
PB_POLL_INTERVAL = 10
PB_POLL_TIMEOUT = 600
PB_BATCH_SIZE = 50
PB_STAGING_TAB = "pb_email_staging"


def load_env_file(keys):
    """Fill os.environ for `keys` from the GTM .env (GTM_ENV_PATH) without overriding
    already-exported values or CLI flags. Loading in-script avoids the fragile
    `export $(grep|xargs)` idiom, which mangles values containing spaces — e.g. a
    Google cred path under `.../Sales Agent Projects (Remote)/...`. Mirrors the
    in-script load convention in _shared/phantombuster.md."""
    path = os.environ.get("GTM_ENV_PATH") or str(Path.home() / ".env.gtm")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                if k in keys and not os.environ.get(k):
                    os.environ[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass


def pb_api(method, path, body, api_key):
    """PhantomBuster v2 API wrapper (matches _shared/phantombuster.md core helper)."""
    url = f"https://api.phantombuster.com/api/v2/{path}"
    headers = {"X-Phantombuster-Key-1": api_key}
    if method == "POST":
        headers["Content-Type"] = "application/json"
        resp = requests.post(url, headers=headers, json=body, timeout=30)
    else:
        resp = requests.get(url, headers=headers, timeout=30)
    if not resp.text.strip():
        return {}
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text}


# ── Domain-identity cross-check ─────────────────────────────────────────────

_SLD_SUFFIXES = {"co", "com", "net", "org", "gov", "ac", "edu", "mil"}


def clean_domain(raw):
    d = (raw or "").strip()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.rstrip("/").lower()


def _extract_sld(domain):
    """Registrable-name label, ignoring TLD (handles multi-part like .co.uk)."""
    if not domain:
        return ""
    parts = domain.lower().split(".")
    if len(parts) < 2:
        return parts[0] if parts else ""
    if len(parts) >= 3 and parts[-2] in _SLD_SUFFIXES:
        return parts[-3]
    return parts[-2]


def email_domain_matches(email, company_domain):
    """Return match | subdomain | mismatch | "" — TLD-agnostic on the brand label."""
    if not email or "@" not in email:
        return ""
    e = email.split("@", 1)[1].strip().lower()
    c = clean_domain(company_domain)
    if not e or not c:
        return ""
    if e == c:
        return "match"
    if e.endswith("." + c):
        return "subdomain"
    e_sld, c_sld = _extract_sld(e), _extract_sld(c)
    if e_sld and c_sld and e_sld == c_sld:
        return "match"
    return "mismatch"


# ── Google Sheets staging (gspread, OAuth) ─────────────────────────────────

def get_gspread_client():
    """Return an authorized gspread client, or None if unavailable (→ skip)."""
    try:
        import gspread
    except ImportError:
        print("N/A: gspread not installed; skipping PB email finder", file=sys.stderr)
        return None
    cred = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "")
    token = os.getenv("GOOGLE_AUTHORIZED_USER_FILE", "")
    if not cred or not Path(cred).exists():
        print("N/A: GOOGLE_CLIENT_SECRET_FILE not set / not found; skipping PB email finder",
              file=sys.stderr)
        return None
    try:
        return gspread.oauth(
            credentials_filename=cred,
            authorized_user_filename=(token or None),
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
    except Exception as e:
        print(f"N/A: Google OAuth failed ({e}); skipping PB email finder", file=sys.stderr)
        return None


def ensure_staging_tab(sh):
    try:
        return sh.worksheet(PB_STAGING_TAB)
    except Exception:
        return sh.add_worksheet(title=PB_STAGING_TAB, rows=200, cols=6)


def write_staging_rows(ws, batch, cols):
    """Wipe the staging tab and write one batch as PB input rows."""
    ws.clear()
    header = ["firstName", "lastName", "companyName", "companyWebsite"]
    rows = [header]
    for c in batch:
        rows.append([
            str(c.get(cols["first"], "")).strip(),
            str(c.get(cols["last"], "")).strip(),
            str(c.get(cols["company"], "")).strip(),
            clean_domain(c.get(cols["domain"], "")),
        ])
    ws.update(values=rows, range_name="A1")


# ── PhantomBuster launch / poll / fetch ────────────────────────────────────

def launch_email_finder(spreadsheet_url, csv_name, line_count, agent_id, api_key):
    argument = json.dumps({
        "csvName": csv_name,
        "emailChooser": "phantombuster",
        "spreadsheetUrl": spreadsheet_url,
        "firstNameColumn": "firstName",
        "lastNameColumn": "lastName",
        "domainNameColumn": "companyWebsite",
        "companyNameColumn": "companyName",
        "customSpreadsheet": True,
        "numberOfLinesPerLaunch": line_count,
    })
    resp = pb_api("POST", "agents/launch", {"id": agent_id, "argument": argument}, api_key)
    return resp.get("containerId")


def wait_for_container(container_id, api_key):
    print(f"    container {container_id} — waiting {PB_INITIAL_WAIT}s before polling...")
    time.sleep(PB_INITIAL_WAIT)
    elapsed = 0
    status = None
    while elapsed < PB_POLL_TIMEOUT:
        resp = pb_api("GET", f"containers/fetch?id={container_id}", None, api_key)
        status = resp.get("status")
        if status and status != "running":
            return status
        time.sleep(PB_POLL_INTERVAL)
        elapsed += PB_POLL_INTERVAL
    return status


def _walk_for_emails(obj, hits):
    if isinstance(obj, dict):
        email = (obj.get("email") or obj.get("professionalEmail")
                 or obj.get("bestEmail") or obj.get("workEmail"))
        if email:
            hits.append({
                "firstName": (obj.get("firstName") or obj.get("first_name") or "").strip(),
                "lastName": (obj.get("lastName") or obj.get("last_name") or "").strip(),
                "domain": clean_domain(obj.get("companyWebsite") or obj.get("domain")
                                       or obj.get("companyDomain") or ""),
                "email": str(email).strip(),
            })
        for v in obj.values():
            _walk_for_emails(v, hits)
    elif isinstance(obj, list):
        for item in obj:
            _walk_for_emails(item, hits)


def fetch_email_results(container_id, agent_id, api_key):
    hits = []
    resp = pb_api("GET", f"containers/fetch-result-object?id={container_id}", None, api_key)
    raw = resp.get("resultObject")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            _walk_for_emails(parsed, hits)
        except (ValueError, TypeError) as e:
            print(f"    WARN: could not parse resultObject ({e}); trying output log")
    if hits:
        return hits
    # Fallback: scrape the console log for emails (loses name/domain mapping).
    log = pb_api("GET", f"agents/fetch-output?id={agent_id}&containerId={container_id}",
                 None, api_key).get("output", "")
    if log:
        pat = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
        for line in log.splitlines():
            for m in pat.findall(line):
                hits.append({"firstName": "", "lastName": "", "domain": "", "email": m.strip()})
    return hits


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # Self-load config from the GTM .env so the caller doesn't need the fragile
    # `export $(grep|xargs)` (which breaks on space-containing paths). Already-set
    # env vars and CLI flags still win.
    load_env_file({"PHANTOMBUSTER_API_KEY", "PB_AGENT_EMAIL", "PB_EMAIL_STAGING_SHEET_ID",
                   "GOOGLE_CLIENT_SECRET_FILE", "GOOGLE_AUTHORIZED_USER_FILE"})

    ap = argparse.ArgumentParser(description="Priority-1 email enrichment via PhantomBuster Email Finder")
    ap.add_argument("--input", required=True, help="Input contacts CSV")
    ap.add_argument("--output", required=True, help="Output CSV (original columns + email fields)")
    ap.add_argument("--staging-spreadsheet-id", default=os.getenv("PB_EMAIL_STAGING_SHEET_ID", ""),
                    help="Google Sheet ID to stage input rows (a `pb_email_staging` tab is created)")
    ap.add_argument("--agent-id", default=os.getenv("PB_AGENT_EMAIL", DEFAULT_PB_EMAIL_AGENT_ID),
                    help="PB Email Finder agent ID (default: PB_AGENT_EMAIL env or keinsaas fallback)")
    ap.add_argument("--first-col", default="first_name")
    ap.add_argument("--last-col", default="last_name")
    ap.add_argument("--company-col", default="company_name")
    ap.add_argument("--domain-col", default="company_domain")
    ap.add_argument("--email-col", default="email")
    ap.add_argument("--status-col", default="email_status")
    ap.add_argument("--source-col", default="email_source")
    ap.add_argument("--batch-size", type=int, default=PB_BATCH_SIZE)
    ap.add_argument("--keep-mismatch", action="store_true",
                    help="Keep emails whose domain does not match the company (default: drop)")
    args = ap.parse_args()

    cols = {"first": args.first_col, "last": args.last_col,
            "company": args.company_col, "domain": args.domain_col}

    api_key = os.getenv("PHANTOMBUSTER_API_KEY", "")
    if not api_key:
        print("N/A: PHANTOMBUSTER_API_KEY not set; skipping PB email finder", file=sys.stderr)
        return 3
    if not args.staging_spreadsheet_id:
        print("N/A: no --staging-spreadsheet-id (or PB_EMAIL_STAGING_SHEET_ID); "
              "skipping PB email finder", file=sys.stderr)
        return 3

    gc = get_gspread_client()
    if gc is None:
        return 3  # reason already printed; caller falls through to FullEnrich

    with open(args.input, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No input rows; nothing to do.")
        return 0

    # PB Email Finder needs first + last + domain. Rows missing any are left blank
    # (they fall through to the next provider in the waterfall).
    eligible = [r for r in rows
                if str(r.get(cols["first"], "")).strip()
                and str(r.get(cols["last"], "")).strip()
                and clean_domain(r.get(cols["domain"], ""))]
    print(f"PB Email Finder: {len(eligible)}/{len(rows)} rows eligible "
          f"(have name + domain)")
    if not eligible:
        _write_output(rows, args)
        return 0

    try:
        sh = gc.open_by_key(args.staging_spreadsheet_id)
    except Exception as e:
        print(f"N/A: cannot open staging spreadsheet ({e}); skipping PB email finder",
              file=sys.stderr)
        return 3
    staging_ws = ensure_staging_tab(sh)

    batches = [eligible[i:i + args.batch_size] for i in range(0, len(eligible), args.batch_size)]
    result_map = {}   # (first, last, domain) -> email
    name_map = {}     # (first, last) -> email  (fallback when domain differs)

    for bi, batch in enumerate(batches, 1):
        print(f"  [{bi}/{len(batches)}] staging {len(batch)} rows, launching agent...")
        try:
            write_staging_rows(staging_ws, batch, cols)
            url = (f"https://docs.google.com/spreadsheets/d/{args.staging_spreadsheet_id}"
                   f"/edit?gid={staging_ws.id}#gid={staging_ws.id}")
            csv_name = f"gtm_emails_{date.today().isoformat()}_b{bi}"
            container_id = launch_email_finder(url, csv_name, len(batch), args.agent_id, api_key)
            if not container_id:
                print(f"    WARN: launch failed for batch {bi}; skipping batch")
                continue
            status = wait_for_container(container_id, api_key)
            if status not in ("finished", "success"):
                print(f"    WARN: batch {bi} ended status={status}; fetching anyway")
            hits = fetch_email_results(container_id, args.agent_id, api_key)
            print(f"    [{bi}/{len(batches)}] {len(hits)} emails returned")
        except Exception as e:
            print(f"    WARN: batch {bi} failed ({e}); continuing")
            continue
        for h in hits:
            k = (h["firstName"].lower(), h["lastName"].lower(), clean_domain(h["domain"]))
            result_map[k] = h["email"]
            if h["firstName"] and h["lastName"]:
                name_map.setdefault((h["firstName"].lower(), h["lastName"].lower()), h["email"])

    found = match = subdomain = mismatch = 0
    for r in rows:
        if str(r.get(args.email_col, "")).strip():
            continue  # already has an email — don't overwrite
        first = str(r.get(cols["first"], "")).strip().lower()
        last = str(r.get(cols["last"], "")).strip().lower()
        dom = clean_domain(r.get(cols["domain"], ""))
        email = result_map.get((first, last, dom)) or name_map.get((first, last))
        if not email:
            continue
        flag = email_domain_matches(email, r.get(cols["domain"], ""))
        if flag == "mismatch" and not args.keep_mismatch:
            mismatch += 1
            continue  # drop wrong-company email; fall through to next provider
        r[args.email_col] = email
        r[args.status_col] = flag or "unknown"
        r[args.source_col] = "phantombuster"
        found += 1
        if flag == "match":
            match += 1
        elif flag == "subdomain":
            subdomain += 1

    _write_output(rows, args)
    print(f"\nPB Email Finder done: {found} emails written "
          f"(match={match}, subdomain={subdomain}, dropped_mismatch={mismatch}). "
          f"Remaining rows without an email fall through to FullEnrich.")
    return 0


def _write_output(rows, args):
    fieldnames = list(rows[0].keys())
    for c in (args.email_col, args.status_col, args.source_col):
        if c not in fieldnames:
            fieldnames.append(c)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"Wrote {len(rows)} rows → {args.output}")


if __name__ == "__main__":
    sys.exit(main())
