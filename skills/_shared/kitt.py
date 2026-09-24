#!/usr/bin/env python3
"""Kitt (trykitt.ai): first email finder, and the verifier gate on every other provider's find.

Ported from the live dashboard chain (`scaleway-jobs/_shared/enrich_providers.py`,
`handoff/KITT_EMAIL_PLAN.md`) with the demo rules Paul set on 2026-09-23:

  - Kitt runs FIRST. A contact Kitt cannot resolve is NOT walked on to the next
    provider — a demo spends no credits chasing one address (the live chain does walk).
  - Every address another provider found is checked by Kitt before it ships. Kitt's own
    finds come back verified and are not checked again.
  - `valid` and `valid-risky` ship (Paul, 2026-09-24: risky is Kitt's catch-all verdict, and
    corporate DACH mail servers are mostly catch-all). `unknown` and `invalid` lose the
    address, and so does an address Kitt never answered for (`unverified`). The live chain
    also accepts unknown and learns its bounce rate later.
  - Losing the address never deletes the contact: the row keeps its name and LinkedIn URL,
    the deck shows the `est-warn` "on request" badge and drops the email draft.

The verdict lands in the status column, which is what `sanitize.py` filters on: its
`standard` policy keeps VALID / VALID_RISKY and drops UNKNOWN / INVALID / UNVERIFIED, so
the lead-facing CSV and deck come out clean with no extra wiring.

    source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
    export $(grep -E '^KITT_API_KEY=' "$GTM_ENV_PATH" | xargs) && \
    python3 ~/.claude/skills/gtm-pipeline/_shared/kitt.py \
      --input  csv/intermediate/contacts_enriched.csv \
      --output csv/intermediate/contacts_kitt.csv

Cost: $0.005 per email found, misses free; checks ~$0.0015 each (on us, never billed on).
"""
import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

KITT_BASE = "https://api.trykitt.ai"
CONCURRENCY = int(os.environ.get("KITT_CONCURRENCY", "15"))
CALL_TIMEOUT_S = 180
STAGE_TIMEOUT_S = int(os.environ.get("KITT_STAGE_TIMEOUT_S", "600"))
VALIDITIES = ("valid", "valid-risky", "unknown", "invalid")
SHIPPABLE = ("valid", "valid-risky")  # demo policy; valid-risky = catch-all domain
UNVERIFIED = "unverified"  # Kitt gave no verdict — in no sanitize policy, so it drops


def clean_domain(raw):
    s = (raw or "").strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    if s.startswith("www."):
        s = s[4:]
    return s.split("/")[0].split("?")[0].split("#")[0].rstrip("/.")


def http_verdict(status, body):
    """What to do with one Kitt HTTP answer: ok | retry | stop | fail.

    A 402 is BOTH "rate limited" and "out of funds" — only the body tells them apart, and
    the funds wording is undocumented. 418 is the free tier's throttle ("The free tier API
    is busy right now", 2026-09-21 probe). Out of funds or a bad key stops the whole run:
    every later call would fail the same way."""
    if status == 200:
        return "ok"
    text = (body or "").lower()
    if status == 401 or (status == 402 and any(
            word in text for word in ("fund", "credit", "balance", "insufficient"))):
        return "stop"
    if status in (402, 418):
        return "retry"
    return "fail"


def email_of(response):
    """The found address, or None. A miss is HTTP 200 with the STRING "no-results-found"
    in `email`, not a null — test for the @."""
    email = str((response or {}).get("email") or "").strip()
    return email if "@" in email else None


def _run(jobs, deadline, log):
    """{key: (path, body)} → {key: response} for the calls Kitt answered.

    Bounded at CONCURRENCY and by `deadline`: every call's timeout is cut to the time left,
    so nothing outlives the stage cap. Fails OPEN — a key missing from the result is simply
    unanswered, and the caller treats it as unverified, never as a rejection."""
    api_key = os.environ.get("KITT_API_KEY")
    if not api_key:
        sys.exit("KITT_API_KEY not set — source resolve_env.sh and export it (see conventions)")
    stopped, gave_up = [], []

    def one(item):
        key, (path, body) = item
        backoff, tries = 5.0, 0
        while not stopped and deadline - time.time() > 1:
            try:
                r = requests.post(
                    f"{KITT_BASE}{path}", json=body, headers={"x-api-key": api_key},
                    timeout=(min(10, deadline - time.time()),
                             min(CALL_TIMEOUT_S, deadline - time.time())),
                )
            except requests.RequestException:
                return key, None
            verdict = http_verdict(r.status_code, r.text)
            if verdict == "ok":
                try:
                    return key, r.json()
                except ValueError:
                    return key, None
            if verdict == "stop":
                stopped.append(f"HTTP {r.status_code}: {r.text[:200]}")
                return key, None
            if verdict == "fail":
                return key, None
            tries += 1
            if tries >= 3:
                gave_up.append(f"HTTP {r.status_code}: {r.text[:200]}")
                return key, None
            time.sleep(max(0.0, min(backoff, deadline - time.time())))
            backoff = min(backoff * 2, 60.0)
        return key, None

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        answers = {k: v for k, v in pool.map(one, jobs.items()) if isinstance(v, dict)}
    if stopped:
        log(f"🔴 KITT STOPPED ({stopped[0]}) — top up / check KITT_API_KEY")
    if gave_up:
        log(f"Kitt: {len(gave_up)} calls still throttled after 3 tries ({gave_up[0]})")
    return answers


def find_emails(contacts, deadline, log):
    """[{key, full_name, domain}] → {key: (email, validity)}. A Kitt find is already
    verified — the finder returns the first permutation its own verifier accepts."""
    usable = {c["key"]: c for c in contacts if c["full_name"] and clean_domain(c["domain"])}
    if not usable:
        return {}
    answers = _run({k: ("/job/find_email", {
        "fullName": c["full_name"], "domain": clean_domain(c["domain"]),
        "realtime": True, "customData": k,
    }) for k, c in usable.items()}, deadline, log)
    out = {}
    for key, response in answers.items():
        email = email_of(response)
        if email:
            out[key] = (email, str(response.get("validity") or "").lower())
    log(f"Kitt found {len(out)}/{len(usable)} emails ({len(usable) - len(answers)} unanswered)")
    return out


def verify(addresses, deadline, log):
    """[address] → {address: validity}. One check per distinct address (a repeat costs
    nothing extra). An address missing from the result was never checked."""
    addresses = sorted({a for a in addresses if a})
    if not addresses:
        return {}
    answers = _run({a: ("/job/verify_email", {"email": a, "realtime": True})
                    for a in addresses}, deadline, log)
    out = {a: str(r.get("validity") or "").lower() for a, r in answers.items()
           if str(r.get("validity") or "").lower() in VALIDITIES}
    log(f"Kitt checked {len(out)}/{len(addresses)} addresses"
        + (f", {len(addresses) - len(out)} got no verdict (kept as unverified)"
           if len(out) < len(addresses) else ""))
    return out


def full_name_of(row, args):
    name = (row.get(args.name_col) or "").strip()
    if not name:
        name = " ".join(p for p in ((row.get("first_name") or "").strip(),
                                    (row.get("last_name") or "").strip()) if p)
    return name


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--name-col", default="full_name")
    p.add_argument("--domain-col", default="company_domain")
    p.add_argument("--email-col", default="email")
    p.add_argument("--status-col", default="email_status")
    p.add_argument("--source-col", default="email_source")
    p.add_argument("--no-find", action="store_true",
                   help="only check the addresses already in the CSV, find nothing new")
    p.add_argument("--keep-rejected", action="store_true",
                   help="leave a rejected address in the column (it still won't ship: the "
                        "verdict in the status column is what sanitize.py drops on)")
    args = p.parse_args()

    log = lambda msg: print(msg, flush=True)
    rows = list(csv.DictReader(open(args.input, newline="", encoding="utf-8")))
    if not rows:
        sys.exit(f"no rows in {args.input}")
    for i, row in enumerate(rows):
        row.setdefault(args.email_col, "")   # the header comes from rows[0]: no column, no finds
        row.setdefault(args.status_col, "")
        row.setdefault(args.source_col, "")
        row["_key"] = str(i)

    deadline = time.time() + STAGE_TIMEOUT_S
    # 1. Kitt first, for every contact without an address. No other provider follows.
    found = {} if args.no_find else find_emails(
        [{"key": r["_key"], "full_name": full_name_of(r, args),
          "domain": r.get(args.domain_col)} for r in rows
         if not (r.get(args.email_col) or "").strip()], deadline, log)
    for row in rows:
        if row["_key"] in found:
            row[args.email_col], row[args.status_col] = found[row["_key"]]
            row[args.source_col] = "kitt"

    # 2. The gate: every address from another provider, checked once. Kitt's own finds —
    # this run's or an earlier pass's (the `--no-find` gate after a fallback) — keep their verdict.
    gated = {row["_key"] for row in rows
             if (row.get(args.email_col) or "").strip()
             and row["_key"] not in found
             and (row.get(args.source_col) or "").strip().lower() != "kitt"}
    verdicts = verify([row[args.email_col].strip().lower() for row in rows if row["_key"] in gated],
                      deadline, log)

    counts = {"shipped": 0, "no_email": 0}
    rejected = []
    for row in rows:
        email = (row.get(args.email_col) or "").strip()
        if not email:
            row[args.status_col] = row[args.status_col] or ""
            counts["no_email"] += 1
            continue
        if row["_key"] in gated:
            row[args.status_col] = verdicts.get(email.lower(), UNVERIFIED)
        verdict = (row[args.status_col] or UNVERIFIED).lower()
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict in SHIPPABLE:
            counts["shipped"] += 1
        else:
            rejected.append((row, email, verdict))
            if not args.keep_rejected:
                row[args.email_col] = ""

    fields = [f for f in rows[0] if f != "_key"]
    for col in (args.status_col, args.source_col):
        if col not in fields:
            fields.append(col)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    log(f"\n{args.output}: {counts['shipped']}/{len(rows)} rows ship a verified address")
    for row, email, verdict in rejected:
        log(f"  ✗ {verdict:<11} {email:<38} {full_name_of(row, args)} "
            f"({(row.get(args.domain_col) or '').strip()})")
    if counts["no_email"]:
        log(f"  · {counts['no_email']} rows have no address at all")
    log("Rejected rows keep the contact: LinkedIn draft only, est-warn badge.")


if __name__ == "__main__":
    main()
