"""FE v2 work-email enrichment for Kitt's misses: python3 fe_enrich.py <in.csv> <out.csv>, run from {client-slug}-gtm/.
Only rows with no email AND no email_status (Kitt found nothing) are sent; an optional `email_domain` column
overrides the mail domain (bosch.com for bosch-pt.com, lht.dlh.de for lufthansa-technik.com).
Keeps all columns; adds email, email_status, email_source, email_domain_check. Drops wrong-company domains."""
import csv, json, os, subprocess, sys, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/gtm-pipeline/_shared"))
from pb_email_finder import email_domain_matches
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
def call(method, path, body=None):
    cmd = ["curl", "-s", "-X", method, f"https://app.fullenrich.com/api/v2{path}", "-A", UA,
           "-H", f"Authorization: Bearer {os.environ['FULLENRICH_API_KEY']}", "-H", "Content-Type: application/json"]
    if body is not None: cmd += ["-d", json.dumps(body)]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout)
src, dst = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(src)))
for c in ("email", "email_status", "email_source", "email_domain_check"):
    for r in rows: r.setdefault(c, "")
todo = [i for i, r in enumerate(rows) if not r["email"] and not r["email_status"]]
data = [{"first_name": rows[i]["first_name"], "last_name": rows[i]["last_name"], "domain": rows[i].get("email_domain") or rows[i]["company_domain"],
         "company_name": rows[i]["company_name"], "linkedin_url": rows[i]["linkedin_profile_url"],
         "enrich_fields": ["contact.work_emails"], "custom": {"row_id": str(i)}} for i in todo]
print("credits before:", call("GET", "/account/credits").get("balance"), "| sending", len(data))
results = []
for n, start in enumerate(range(0, len(data), 100)):  # FE bulk cap: 100 contacts per request
    sub = call("POST", "/contact/enrich/bulk", {"name": f"{os.path.basename(os.getcwd())} emails {os.path.basename(src)} {n}", "data": data[start:start + 100]})
    eid = sub.get("enrichment_id") or sys.exit(f"submit failed: {sub}")
    json.dump({"enrichment_id": eid}, open(f"csv/intermediate/request_ids_{os.path.basename(src)}_{n}.json", "w"))
    for _ in range(60):
        time.sleep(15)
        res = call("GET", f"/contact/enrich/bulk/{eid}")
        if res.get("status") not in ("CREATED", "IN_PROGRESS"): break
    json.dump(res, open(f"csv/intermediate/raw/fe_enrich_result_{os.path.basename(src)}_{n}.json", "w"), indent=1)
    print("chunk", n, "status:", res.get("status"))
    results += res.get("data", [])
found = dropped = 0
for e in results:
    r = rows[int(e["custom"]["row_id"])]
    best = (e.get("contact_info") or {}).get("most_probable_work_email") or {}
    email, status = best.get("email") or "", best.get("status") or ""
    if not email or status in ("INVALID", "INVALID_DOMAIN"): continue
    check = email_domain_matches(email, r.get("email_domain") or r["company_domain"])
    if check == "mismatch":
        dropped += 1; print(f"  DROP mismatch: {r['full_name']} @ {r['company_domain']} -> {email}"); continue
    r.update(email=email, email_status=status, email_source="fullenrich", email_domain_check=check); found += 1
with open(dst, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"found {found}/{len(data)}, dropped mismatches {dropped} | credits after:", call("GET", "/account/credits").get("balance"))
