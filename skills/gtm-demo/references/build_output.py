"""contacts_enriched + signals + messages.json → sanitize.py → csv/output/{contacts_enriched,messages}.csv
+ csv/intermediate/deck_data.json + sanitize_report.json. python3 build_output.py (from {client-slug}-gtm/)"""
import csv, json
from common import contacts, deck_config, has_address, messages, signals
from sanitize import sanitize_rows

cfg, msgs, sigs = deck_config(), messages(), signals()
titles = {s["key"]: s["title"] for s in cfg["segments"]}
rows, deck = [], []
for c in contacts():
    m, sig, kept = msgs[c["linkedin_profile_url"]], sigs.get(c["company_domain"]), has_address(c)
    email = c["email"].strip() if kept else ""
    rows.append({"company_name": c["company_name"], "company_domain": c["company_domain"], "segment": titles[c["segment"]],
        "full_name": c["full_name"], "job_title": m["job_title"], "linkedin_url": c["linkedin_profile_url"],
        "email": email, "email_status": c["email_status"] if kept else "",
        "scored_signals": json.dumps([sig] if sig else [], ensure_ascii=False), "why_they_fit": m["why_they_fit"],
        "email_subject": m["email_subject"] if kept else "",
        "email_message": "\n".join(m[k] for k in ("email_p1", "email_p2", "email_p3")) if kept else "",
        "linkedin_message": m["li_p1"] + "\n" + m["li_p2"]})
    deck.append({"group": "signal" if sig else "icp", "segment": c["segment"], "full_name": c["full_name"],
        "job_title": m["job_title"], "company_name": c["company_name"], "company_domain": c["company_domain"],
        "location": c["country"], "linkedin_url": c["linkedin_profile_url"], "email": email,
        "email_status": c["email_status"] if kept else "", "why_they_fit": m["why_they_fit"],
        "signal_text": (sig or {}).get("summary", ""), "signal_date": (sig or {}).get("date", ""),
        "signal_source_url": (sig or {}).get("source_url", ""),
        "signal_source_label": (sig or {}).get("source_url", "").split("/")[2].removeprefix("www.") if sig else "",
        "cta_variant": m["cta_variant"], "lang": m["lang"].upper(), "email_subject": m["email_subject"] if kept else "",
        **{k: (m[k] if kept else "") for k in ("email_p1", "email_p2", "email_p3")}, "li_p1": m["li_p1"], "li_p2": m["li_p2"]})
# email_limit covers greeting + sign-off; the body itself is held to 450 by check_messages.py
clean, report = sanitize_rows(rows, email_policy="standard", require_email=False, max_signal_age_days=60, email_limit=520)
out = []
for r in clean:
    sig = (json.loads(r.pop("scored_signals", "[]") or "[]") or [{}])[0]
    r.update(signal=sig.get("summary", ""), signal_date=sig.get("date", ""), signal_source=sig.get("source_url", ""))
    out.append(r)
blanked = {r["linkedin_url"] for r in out if not r["email"]}
for d in deck:  # the deck shows exactly what survived sanitize
    if d["linkedin_url"] in blanked and d["email"]:
        d.update(email="", email_status="", email_subject="", email_p1="", email_p2="", email_p3="")
cols = ["company_name", "company_domain", "segment", "full_name", "job_title", "linkedin_url", "email", "signal", "signal_date",
        "signal_source", "why_they_fit", "email_subject", "email_message", "linkedin_message"]
with open("csv/output/contacts_enriched.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n"); w.writeheader(); w.writerows(out)
with open("csv/output/messages.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["company_name", "full_name", "email_subject", "email_message", "linkedin_message"], extrasaction="ignore")
    w.writeheader(); w.writerows(out)
json.dump(deck, open("csv/intermediate/deck_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
report.pop("columns_out", None)
json.dump(report, open("csv/intermediate/sanitize_report.json", "w", encoding="utf-8"), ensure_ascii=False)
print(json.dumps(report, ensure_ascii=False))
print(len(out), "rows;", sum(bool(r["email"]) for r in out), "addresses;", sum(bool(r["signal"]) for r in out), "signals")
