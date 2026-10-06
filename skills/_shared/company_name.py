#!/usr/bin/env python3
"""Company display name from the company's own homepage, not from a finder's name field.

BetterContact sentence-cases every company name ("Cover genius", "Einhell germany ag") and builds
some from the domain ("Wealthcom" for wealth.com, "Yuno" for y.uno); 141 of 141 rows across four
demos, 2026-10-01. That name then becomes the search term in signal-search and pulls in a
different company (Wealthcome). FullEnrich returns LinkedIn display names and needs none of this.

    python3 company_name.py <in.csv> [<out.csv>]     # in place when out is omitted

Rewrites `company_name` for every row with a `company_domain`, using og:site_name,
application-name or a <title> segment that matches the domain. When the homepage blocks us or
offers only a slogan, the provider's name stays and the row is listed, so fix those by hand.
"""
import csv
import html
import re
import subprocess
import sys

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SEP = re.compile(r"\s*:\s+|\s+[|–—·•-]\s+")  # "Forage: SNAP…" has no space before the colon
META = re.compile(r"<meta\b[^>]*\b(?:property|name)\s*=\s*[\"'](?:og:site_name|application-name)[\"'][^>]*>", re.I)
CONTENT = re.compile(r"\bcontent\s*=\s*[\"']([^\"']+)[\"']", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _matches(name, root):
    """The name IS the domain's brand: equal, inside it (Forage / joinforage), or it plus a short suffix
    (Wealth.com / wealth, Global Health Limited / globalhealth). A bare substring is not enough:
    'ro' is inside every second word."""
    k = _key(name)
    return bool(k) and (k == root or (len(k) >= 3 and k in root) or (k.startswith(root) and len(k) <= len(root) + 8))


def name_from_html(page, domain):
    host = domain.lower().removeprefix("www.")
    roots = {_key(host.split(".")[0]), _key(host)}  # wealth, wealthcom; compasseducation for compass.education
    candidates = [CONTENT.search(m.group(0)) for m in META.finditer(page)]
    candidates = [html.unescape(c.group(1)).strip() for c in candidates if c]
    t = TITLE.search(page)
    if t:
        candidates += [s.strip() for s in SEP.split(html.unescape(" ".join(t.group(1).split())))]
    hits = [c for c in candidates if len(c) <= 40 and any(_matches(c, r) for r in roots)]
    return min(hits, key=len) if hits else None  # "Compass Education" over "Compass Education AU"


def fetch(domain):
    out = subprocess.run(["curl", "-sL", "-m", "20", "-A", UA, f"https://{domain}"], capture_output=True, timeout=30)
    return out.stdout[:300_000].decode("utf-8", "replace")


def main():
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    names, kept = {}, []
    for r in rows:
        d = (r.get("company_domain") or "").strip().lower()
        if d and d not in names:
            names[d] = name_from_html(fetch(d), d)
            if names[d] is None:
                kept.append(f"{d} (kept '{r.get('company_name', '')}')")
        if d and names[d]:
            r["company_name"] = names[d]
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{len(names) - len(kept)}/{len(names)} names from the homepage")
    for k in kept:
        print("  check by hand:", k)


if __name__ == "__main__":
    main()
