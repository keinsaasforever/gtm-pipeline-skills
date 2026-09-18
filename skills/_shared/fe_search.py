#!/usr/bin/env python3
"""FullEnrich Search API v2: company search, then people at those companies joined on company id.

Both endpoints are synchronous and bill 0.25 credits per row RETURNED (a row the workspace already
exported is free to fetch again). So the row cap is the cost ceiling, and a crashed run can be
re-run without paying twice. `--dry-run` validates the filters and prints the first request plus the
ceiling. It makes no network call and needs no key.

    # companies -> csv/input/companies_raw.csv (+ raw JSON in csv/intermediate/)
    python3 fe_search.py companies --client-dir acme-gtm --filters company_filters.json --max 40 [--dry-run]

    # people at those companies -> csv/intermediate/contacts_found.csv
    python3 fe_search.py people --client-dir acme-gtm --filters people_filters.json --per-company 2 [--dry-run]

The filters file is the request body without offset/limit/search_after (the script owns those) and,
for `people`, without current_company_ids (injected per company from the companies CSV).

Keys:  source resolve_env.sh, then export FULLENRICH_API_KEY (conventions.md -> Environment Variables).
Docs:  https://docs.fullenrich.com/api/v2/company/search/post
       https://docs.fullenrich.com/api/v2/people/search/post
       https://docs.fullenrich.com/api/v2/general/enums   (fe_industries.txt is vendored from here)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = "https://app.fullenrich.com/api/v2"
CREDITS_PER_ROW = 0.25
PAGE_MAX = 100
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Exact request keys from the v2 OpenAPI spec. Whether FE rejects or silently drops an unknown key is
# unverified, so we refuse one here instead of finding out on a billed, unfiltered search.
COMPANY_KEYS = {
    "names", "domains", "professional_network_ids", "professional_network_urls", "keywords",
    "specialties", "technologies", "industries", "types", "headquarters_locations",
    "founded_years", "headcounts", "company_ids",
}
PEOPLE_KEYS = {
    "current_company_names", "current_company_domains", "current_company_professional_network_ids",
    "current_company_professional_network_urls", "current_company_specialties",
    "current_company_industries", "current_company_technologies", "past_company_names",
    "past_company_domains", "current_company_types", "current_company_headquarters",
    "current_company_headcounts", "current_company_founded_years", "person_ids", "person_names",
    "person_professional_network_ids", "person_professional_network_urls", "person_locations",
    "person_languages", "person_skills", "current_position_seniority_level",
    "current_position_job_functions", "current_position_sub_functions", "current_position_titles",
    "past_position_titles", "current_position_years_in", "current_company_years_at",
    "person_universities", "current_company_days_since_last_job_change",
}
INDUSTRIES = {l.strip().lower() for l in Path(__file__).with_name("fe_industries.txt").read_text().splitlines() if l.strip()}
TYPES = {"partnership", "nonprofit", "educational", "privately held", "public company", "self-owned",
         "self-employed", "government agency"}
ENUMS = {  # filter key -> accepted values, lower-cased (FE matching is never case-sensitive)
    "industries": INDUSTRIES,
    "current_company_industries": INDUSTRIES,
    "types": TYPES,
    "current_company_types": TYPES,
    "current_position_seniority_level": {"owner", "founder", "c-level", "partner", "vp", "head",
                                         "director", "manager", "senior"},
}


def validate(filters: dict, allowed: set[str]) -> None:
    errors = []
    for key, items in filters.items():
        if key not in allowed:
            errors.append(f"unknown filter key '{key}'")
            continue
        if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
            errors.append(f"'{key}' must be a non-empty list of objects")
            continue
        for bad in [i.get("value") for i in items if key in ENUMS and str(i.get("value", "")).lower() not in ENUMS[key]]:
            errors.append(f"'{key}': '{bad}' is not an accepted value (see fe_industries.txt / enums doc)")
    if errors:
        sys.exit("Filter validation failed:\n  " + "\n  ".join(errors))


def post(path: str, body: dict) -> dict:
    key = os.environ.get("FULLENRICH_API_KEY") or sys.exit("FULLENRICH_API_KEY not set")
    # curl, not urllib: FullEnrich is Cloudflare-fronted and blocks Python's TLS signature (conventions #8).
    cmd = ["curl", "-s", "-w", "\n__HTTP__%{http_code}", "-X", "POST", BASE + path,
           "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json",
           "-H", f"User-Agent: {UA}", "-d", json.dumps(body)]
    for _ in range(3):
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
        text, _, code = out.rpartition("\n__HTTP__")
        if code == "429":  # 60 calls/min workspace limit
            time.sleep(61)
            continue
        if not code.startswith("2"):
            sys.exit(f"FullEnrich {path} -> HTTP {code}: {text[:400]}")
        return json.loads(text)
    sys.exit(f"FullEnrich {path}: still rate-limited after 3 attempts")


def blank0(n) -> str:
    return "" if not n else str(n)  # FE returns 0 for unknown year_founded / headcount


def company_row(c: dict) -> dict:
    hq = (c.get("locations") or {}).get("headquarters") or {}
    return {
        "company_name": c.get("name", ""),
        "company_domain": c.get("domain", ""),
        "company_website": c.get("website", ""),
        "company_linkedin_url": ((c.get("social_profiles") or {}).get("professional_network") or {}).get("url", ""),
        "company_industry": (c.get("industry") or {}).get("main_industry", ""),
        "company_hq_location": ", ".join(x for x in (hq.get("city"), hq.get("region"), hq.get("country")) if x),
        "company_hq_country": hq.get("country", ""),
        "company_employee_count": blank0(c.get("headcount")),
        "company_employee_range": c.get("headcount_range", ""),
        "company_type": c.get("company_type", ""),
        "year_founded": blank0(c.get("year_founded")),
        "company_description": c.get("description", ""),
        "company_specialities": "; ".join(c.get("specialties") or []),
        "company_technologies": "; ".join(t.get("name", "") for t in c.get("technologies") or []),
        "fe_company_id": c.get("id", ""),
        "source": "fullenrich_company_search",
    }


def person_row(p: dict, company: dict) -> dict:
    cur = (p.get("employment") or {}).get("current") or {}
    loc = p.get("location") or {}
    return {
        **{k: company.get(k, "") for k in ("company_name", "company_domain", "company_linkedin_url", "company_industry",
                                           "company_hq_location", "company_employee_count", "company_employee_range")},
        "first_name": p.get("first_name", ""),
        "last_name": p.get("last_name", ""),
        "full_name": p.get("full_name", ""),
        "job_title": cur.get("title", ""),
        "seniority": cur.get("seniority", ""),
        "headline": p.get("headline", ""),
        "linkedin_profile_url": ((p.get("social_profiles") or {}).get("professional_network") or {}).get("url", ""),
        "location": ", ".join(x for x in (loc.get("city"), loc.get("country")) if x),
        "fe_company_id": company.get("fe_company_id", ""),
        "fe_person_id": p.get("id", ""),
        "source": "fullenrich_finder",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["company_name"])
        w.writeheader()
        w.writerows(rows)


def run_companies(a) -> None:
    filters = json.loads(Path(a.filters).read_text())
    if not filters:
        sys.exit("Refusing an empty company search: it is a billed dump of the whole index.")
    validate(filters, COMPANY_KEYS)
    first = {**filters, "limit": min(PAGE_MAX, a.max)}
    print(json.dumps(first, indent=2, ensure_ascii=False))
    print(f"Ceiling: {a.max} companies x {CREDITS_PER_ROW} = {a.max * CREDITS_PER_ROW:.2f} credits")
    if a.dry_run:
        return
    got, credits, total = [], 0.0, None
    while len(got) < a.max:
        # offset caps at 10,000 rows (2,500 credits), far past any run we'd pay for.
        body = {**filters, "limit": min(PAGE_MAX, a.max - len(got)), "offset": len(got)}
        resp = post("/company/search", body)
        page, meta = resp.get("companies") or [], resp.get("metadata") or {}
        got += page
        credits += meta.get("credits") or 0
        total = meta.get("total", total)
        if len(page) < body["limit"]:
            break
    d = Path(a.client_dir)
    (d / "csv/intermediate").mkdir(parents=True, exist_ok=True)
    (d / "csv/intermediate/fe_company_search_raw.json").write_text(json.dumps(got, indent=1, ensure_ascii=False))
    write_csv(d / (a.out or "csv/input/companies_raw.csv"), [company_row(c) for c in got])
    print(f"Matches in index: {total} | returned: {len(got)} | credits charged: {credits}")


def run_people(a) -> None:
    filters = json.loads(Path(a.filters).read_text())
    if "current_company_ids" in filters:
        sys.exit("Leave current_company_ids out of the filters file; it is injected per company.")
    validate(filters, PEOPLE_KEYS)
    d = Path(a.client_dir)
    companies = [r for r in csv.DictReader((d / a.companies).open()) if r.get("fe_company_id")]
    if not companies:
        sys.exit(f"No rows with fe_company_id in {a.companies}; run `companies` first.")
    ceiling = len(companies) * a.per_company * CREDITS_PER_ROW
    print(json.dumps(people_body(filters, companies[0]["fe_company_id"], a.per_company), indent=2, ensure_ascii=False))
    print(f"Ceiling: {len(companies)} companies x {a.per_company} people x {CREDITS_PER_ROW} = {ceiling:.2f} credits")
    if a.dry_run:
        return
    rows, raw, credits, foreign = [], [], 0.0, 0
    for c in companies:
        resp = post("/people/search", people_body(filters, c["fe_company_id"], a.per_company))
        credits += (resp.get("metadata") or {}).get("credits") or 0
        for p in resp.get("people") or []:
            raw.append(p)
            # Identity check: a person counts only if FE's own current-company id is the one we asked for.
            if (((p.get("employment") or {}).get("current") or {}).get("company") or {}).get("id") == c["fe_company_id"]:
                rows.append(person_row(p, c))
            else:
                foreign += 1
        time.sleep(1)  # stay under 60 calls/min
    write_csv(d / "csv/intermediate/contacts_found.csv", rows)  # creates csv/intermediate/ first
    (d / "csv/intermediate/fe_people_search_raw.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    hit = len({r["fe_company_id"] for r in rows})
    print(f"Companies with contacts: {hit}/{len(companies)} | contacts: {len(rows)} | "
          f"dropped (different current company): {foreign} | credits charged: {credits}")


def people_body(filters: dict, company_id: str, limit: int) -> dict:
    return {**filters, "current_company_ids": [{"value": company_id, "exact_match": True}], "limit": limit}


def self_test() -> None:
    c = {"id": "abc", "name": "Acme", "domain": "acme.de", "headcount": 0, "headcount_range": "11-50",
         "year_founded": 0, "industry": {"main_industry": "Telephone Call Centers"},
         "locations": {"headquarters": {"city": "Berlin", "country": "Germany"}},
         "social_profiles": {"professional_network": {"url": "https://www.linkedin.com/company/acme"}},
         "specialties": ["a", "b"], "technologies": [{"name": "HubSpot"}]}
    r = company_row(c)
    assert r["company_employee_count"] == "" and r["year_founded"] == "", "0 must map to unknown"
    assert r["company_hq_location"] == "Berlin, Germany" and r["company_linkedin_url"].endswith("/acme")
    assert r["company_specialities"] == "a; b" and r["company_technologies"] == "HubSpot"
    p = {"id": "p1", "full_name": "Ada L", "employment": {"current": {"title": "COO", "company": {"id": "abc"}}},
         "social_profiles": {"professional_network": {"url": "https://www.linkedin.com/in/ada"}}}
    pr = person_row(p, r)
    assert pr["job_title"] == "COO" and pr["company_name"] == "Acme" and pr["fe_company_id"] == "abc"
    assert people_body({"x": 1}, "abc", 2)["current_company_ids"][0]["value"] == "abc"
    validate({"industries": [{"value": "telephone call centers"}], "headcounts": [{"min": 10, "max": 200}]}, COMPANY_KEYS)
    for bad in ({"industry": [{"value": "Software Development"}]}, {"industries": [{"value": "Call Centers"}]},
                {"current_company_linkedin_urls": [{"value": "x"}]}):
        try:
            validate(bad, COMPANY_KEYS | PEOPLE_KEYS)
        except SystemExit:
            continue
        raise AssertionError(f"should have rejected {bad}")
    print("self-test ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("companies", "people"):
        s = sub.add_parser(name)
        s.add_argument("--client-dir", required=True)
        s.add_argument("--filters", required=True, help="JSON request body without pagination keys")
        s.add_argument("--dry-run", action="store_true")
    sub.choices["companies"].add_argument("--max", type=int, required=True, help="row cap = cost ceiling / 0.25")
    sub.choices["companies"].add_argument("--out", help="default csv/input/companies_raw.csv")
    sub.choices["people"].add_argument("--per-company", type=int, default=2)
    sub.choices["people"].add_argument("--companies", default="csv/input/companies_raw.csv")
    sub.add_parser("self-test")
    a = ap.parse_args()
    {"companies": run_companies, "people": run_people, "self-test": lambda _: self_test()}[a.cmd](a)


if __name__ == "__main__":
    main()
