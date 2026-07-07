#!/usr/bin/env python3
"""Deterministic sanitizer for lead-facing GTM output.

Every session hand-scrubbed the same four things out of the client-facing deliverable:
provider/source labels, all-empty columns, undeliverable/identity-mismatched emails, and
stale/sourceless signals. This module makes that a single, reusable, no-LLM step so no skill
has to re-implement it. Intermediate CSVs keep everything (provenance, statuses); the
lead-facing view is what gets sanitized.

Use as a library (preferred, from a skill) or as a CLI:
    python3 sanitize.py --in csv/intermediate/leads.csv --out csv/output/leads.csv \
        --email-policy standard --max-signal-age-days 60

Library:
    from sanitize import sanitize_rows, EMAIL_POLICIES
    clean, report = sanitize_rows(rows, email_policy="standard", max_signal_age_days=60)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta

# ── Columns that are internal provenance / technical and must never reach a lead ──
# Matched case-insensitively, exact or as a prefix (e.g. "fe_", "_"). Extend per skill via arg.
INTERNAL_COLUMNS = {
    "source", "provider", "providers", "data_source", "finder_source",
    "fe_company_name", "fe_company_domain", "bc_company_name", "raw_status",
    "email_status", "phone_status",
    "seniority", "seniority_level", "request_id", "task_id", "credits",
    "domain_verified", "domain_match", "identity_match", "needs_review",
    "_needs_agent_processing", "overallsummary", "websitesignals", "websearchsignals",
    "parallelenrichment", "scoredsignals", "lastrun",
}
INTERNAL_PREFIXES = ("fe_", "bc_", "pipe0_", "_", "provider_", "raw_")

# ── Email deliverability policy ──
# Statuses are normalized to UPPER_SNAKE before comparison. The real anti-"made-up-address"
# guard is the domain-identity cross-check upstream (people-enrichment) — this is the last net.
EMAIL_POLICIES = {
    # keinsaas default: keep deliverable, high-probability, and catch-all (usually usable on
    # corporate domains); drop unknown/risky/invalid/undeliverable.
    "standard": {"DELIVERABLE", "VALID", "HIGH_PROBABILITY", "CATCH_ALL", "ACCEPT_ALL"},
    # strict: also drop catch-all.
    "strict": {"DELIVERABLE", "VALID", "HIGH_PROBABILITY"},
    # lenient: any non-empty email, whatever the status.
    "any": None,
}

DASH_RE = re.compile(r"\s*[—–]\s*")  # em/en dash → comma+space (keinsaas German rule)


def normalize_status(status: str) -> str:
    return re.sub(r"[\s-]+", "_", str(status or "").strip()).upper()


def email_ok(status: str, email: str, policy: str) -> bool:
    """True if this email may be shown to a lead under the policy."""
    if not str(email or "").strip() or "@" not in str(email):
        return False
    allowed = EMAIL_POLICIES.get(policy, EMAIL_POLICIES["standard"])
    if allowed is None:  # "any"
        return True
    return normalize_status(status) in allowed


def clean_text(text: str) -> str:
    """Collapse whitespace and replace em/en dashes (keinsaas style: dashes → comma)."""
    if text is None:
        return ""
    t = DASH_RE.sub(", ", str(text))
    return re.sub(r"[ \t]+", " ", t).strip()


def over_limit(text: str, limit: int) -> bool:
    return len(str(text or "")) > limit


def trim_to(text: str, limit: int) -> str:
    """Trim to <= limit at a sentence, else word, boundary (never mid-word)."""
    t = str(text or "").strip()
    if len(t) <= limit:
        return t
    window = t[:limit]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut >= limit * 0.6:
        return window[:cut + 1].strip()
    cut = window.rfind(" ")
    return (window[:cut] if cut > 0 else window).strip()


def _signal_is_valid(sig: dict, cutoff: datetime | None) -> bool:
    """A signal is lead-worthy only if it has a source URL, a parseable date, and (if a cutoff
    is given) is within the freshness window. Undated/sourceless signals are dropped."""
    if not isinstance(sig, dict):
        return False
    url = sig.get("source_url") or sig.get("source") or sig.get("url") or ""
    if not str(url).startswith("http"):
        return False
    raw_date = str(sig.get("date") or sig.get("published_at") or "").strip()
    dt = None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw_date[:len(fmt) + 2].strip(), fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return False
    if cutoff and dt < cutoff:
        return False
    return True


def clean_signals(value, cutoff: datetime | None):
    """Filter a JSON list (or JSON string) of signals down to valid, in-window ones.
    Returns (cleaned_list, n_dropped)."""
    sigs = value
    if isinstance(value, str):
        try:
            sigs = json.loads(value) if value.strip() else []
        except json.JSONDecodeError:
            return [], 0
    if not isinstance(sigs, list):
        return [], 0
    kept = [s for s in sigs if _signal_is_valid(s, cutoff)]
    return kept, len(sigs) - len(kept)


def is_internal_column(col: str, extra: set[str]) -> bool:
    c = col.strip().lower()
    if c in INTERNAL_COLUMNS or c in {e.lower() for e in extra}:
        return True
    return any(c.startswith(p) for p in INTERNAL_PREFIXES)


def sanitize_rows(
    rows: list[dict],
    *,
    email_policy: str = "standard",
    require_email: bool = True,
    drop_internal: bool = True,
    drop_empty: bool = True,
    extra_internal_columns: set[str] | None = None,
    message_fields: tuple[str, ...] = ("email_message", "linkedin_message", "email_subject"),
    email_limit: int = 500,
    li_limit: int = 400,
    signal_fields: tuple[str, ...] = ("scored_signals", "scoredSignals", "signal"),
    max_signal_age_days: int | None = 60,
    email_field: str = "email",
    status_field: str = "email_status",
    today: datetime | None = None,
):
    """Return (clean_rows, report). Deterministic, no LLM. See module docstring."""
    extra_internal_columns = extra_internal_columns or set()
    today = today or datetime.utcnow()
    cutoff = today - timedelta(days=max_signal_age_days) if max_signal_age_days else None
    report = {"rows_in": len(rows), "rows_dropped_bad_email": 0, "signals_dropped": 0,
              "messages_trimmed": 0, "columns_dropped": []}

    clean: list[dict] = []
    for r in rows:
        r = dict(r)
        # 1) bad emails
        if require_email and not email_ok(r.get(status_field, ""), r.get(email_field, ""), email_policy):
            report["rows_dropped_bad_email"] += 1
            continue
        # 2) stale / sourceless signals
        for sf in signal_fields:
            if sf in r and r[sf] not in (None, ""):
                kept, dropped = clean_signals(r[sf], cutoff)
                report["signals_dropped"] += dropped
                r[sf] = json.dumps(kept, ensure_ascii=False) if isinstance(r[sf], str) else kept
        # 3) message hygiene: em-dash scrub + length cap
        for mf in message_fields:
            if mf in r and r[mf]:
                cleaned = clean_text(r[mf])
                limit = li_limit if "linkedin" in mf else email_limit
                if "subject" not in mf and over_limit(cleaned, limit):
                    cleaned = trim_to(cleaned, limit)
                    report["messages_trimmed"] += 1
                r[mf] = cleaned
        clean.append(r)

    if not clean:
        return clean, report

    # 4) drop internal/provenance columns
    all_cols = list(dict.fromkeys(k for row in clean for k in row.keys()))
    keep_cols = all_cols
    if drop_internal:
        internal = [c for c in all_cols if is_internal_column(c, extra_internal_columns)]
        report["columns_dropped"] += internal
        keep_cols = [c for c in keep_cols if c not in internal]
    # 5) drop columns empty across ALL kept rows
    if drop_empty:
        empty = [c for c in keep_cols if all(not str(row.get(c, "")).strip() for row in clean)]
        report["columns_dropped"] += empty
        keep_cols = [c for c in keep_cols if c not in empty]

    clean = [{c: row.get(c, "") for c in keep_cols} for row in clean]
    report["rows_out"] = len(clean)
    report["columns_out"] = keep_cols
    return clean, report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--email-policy", choices=list(EMAIL_POLICIES), default="standard")
    p.add_argument("--no-require-email", action="store_true", help="Keep rows even without a usable email")
    p.add_argument("--max-signal-age-days", type=int, default=60)
    p.add_argument("--email-limit", type=int, default=500)
    p.add_argument("--li-limit", type=int, default=400)
    args = p.parse_args()

    with open(args.inp, newline="") as f:
        rows = list(csv.DictReader(f))
    clean, report = sanitize_rows(
        rows, email_policy=args.email_policy, require_email=not args.no_require_email,
        max_signal_age_days=args.max_signal_age_days,
        email_limit=args.email_limit, li_limit=args.li_limit,
    )
    if clean:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=report["columns_out"])
            w.writeheader(); w.writerows(clean)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Wrote {len(clean)} sanitized rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
