"""BC Lead Finder, run from {client-slug}-gtm/: python3 bc_search.py <name> <body.json>. Submits, polls, saves raw, prints compact rows."""
import json, os, subprocess, sys, time
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
KEY = os.environ["BETTERCONTACT_API_KEY"]
def call(method, path, body=None):
    cmd = ["curl", "-s", "-X", method, f"https://app.bettercontact.rocks/api/v2{path}", "-A", UA,
           "-H", f"X-API-Key: {KEY}", "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"non-JSON: {out[:500]}")
name, body_file = sys.argv[1], sys.argv[2]
os.makedirs("csv/intermediate/raw", exist_ok=True)
print("credits before:", call("GET", "/account").get("credits_left"))
sub = call("POST", "/lead_finder/async", json.load(open(body_file)))
rid = sub.get("request_id") or sys.exit(f"submit failed: {sub}")
json.dump({"name": name, "request_id": rid}, open(f"csv/intermediate/raw/bc_{name}_rid.json", "w"))
for _ in range(120):
    time.sleep(5)
    res = call("GET", f"/lead_finder/async/{rid}")
    if res.get("status") in ("terminated", "failed", "error"):
        break
json.dump(res, open(f"csv/intermediate/raw/bc_{name}.json", "w"), indent=1)
leads = res.get("leads") or []
print(f"{name}: status={res.get('status')} leads={len(leads)} credits_consumed={res.get('credits_consumed')} credits_left={res.get('credits_left')}")
for l in leads:
    print(f"  {l.get('contact_full_name','')[:26]:26} | {(l.get('contact_job_title') or '')[:48]:48} | {(l.get('company_name') or '')[:26]:26} | {l.get('company_domain')} | {l.get('contact_location_country')}")
