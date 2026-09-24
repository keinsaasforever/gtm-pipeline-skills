"""gtm-demo Step 7c self-QA on the rendered deck. python3 qa_deck.py <deck.html> (from {client-slug}-gtm/).
Prints PASS or every failed check; exits 1 on failure."""
import csv, html, io, json, re, sys
from common import KEPT, deck_config

cfg = deck_config()
page = open(sys.argv[1], encoding="utf-8").read()
data = json.load(open("csv/intermediate/deck_data.json", encoding="utf-8"))
report = json.load(open("csv/intermediate/sanitize_report.json", encoding="utf-8"))
fails = []
check = lambda ok, msg: ok or fails.append(msg)
MONTHS = ("Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|January|February|March|"
          "May|June|July|October|December")
DATE = re.compile(rf"\b20\d\d-\d\d-\d\d\b|\b\d{{1,2}}[./]\d{{1,2}}[./]20\d\d\b|\b\d{{1,2}}\.? ({MONTHS}) 20\d\d|({MONTHS}) (\d{{1,2}}, )?20\d\d")

cards = re.findall(r'<details class="lead">(.*?)</details>', page, re.S)
check(len(cards) == len(data), f"cards {len(cards)} != deck_data rows {len(data)}")
check(not re.findall(r"\{\{[A-Z0-9_]+\}\}", page), "unfilled {{TOKEN}} placeholders")
visible = html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", page, flags=re.S))
check(not re.search("[–—]", visible), "en/em dash in visible text")
vendor = re.search(r"\b(kitt|trykitt|fullenrich|bettercontact|phantombuster|pipe0|parallel\.ai|firecrawl|apollo|crustdata|amplemarket|clay)\b", visible, re.I)
check(not vendor, f"provider name visible: {vendor and vendor.group()}")
by_dom = {d["company_domain"]: d for d in data}
mails = []
for c in cards:
    d = by_dom[re.search(r'class="lead-domain" href="https://([^"]+)"', c).group(1)]
    name, sig = d["company_name"], "sig-hot" in c
    check(sig == (d["group"] == "signal"), f"{name}: signal box vs data")
    if sig:
        src = re.search(r'class="sigsrc" href="(https?://[^"]+)"[^>]*>(.*?)</a>', c, re.S)
        check(src and re.search(r"20\d\d", src.group(2)), f"{name}: signal without live link + date")
    else:
        check(not DATE.search(html.unescape(re.sub(r"<[^>]+>", " ", c))), f"{name}: a date on an ICP-fit card")
    if 'class="cmail"' in c:
        check(d["email_status"] in KEPT and "est est-ok" in c, f"{name}: address without a kept verdict / est-ok badge")
        check(c.count('<span class="ml">LinkedIn</span>') == 1 and len(re.findall(r'<div class="msg-sub"><span class="ml">', c)) == 1,
              f"{name}: needs exactly one email + one LinkedIn draft")
        mails.append(d["email"].lower())
    else:
        check(not d["email"] and "est est-warn" in c and c.count('<span class="ml">') == 1, f"{name}: no-address card must be LinkedIn-only")
check(len(mails) == len(set(mails)), "one address on two cards")
check(not report.get("emails_wrong_person"), f"wrong-person addresses: {report.get('emails_wrong_person')}")
if report.get("emails_name_mismatch"):
    print("REVIEW by hand (name mismatch):", report["emails_name_mismatch"])
if cfg["lang"] == "de":  # the deck's own copy is Du-form; drafts follow their own register
    own = visible
    parts = {p for d in data for k in ("email_subject", "email_p1", "email_p2", "email_p3", "li_p1", "li_p2",
             "why_they_fit", "signal_text") for p in (d.get(k) or "").split("\n") if p}
    for part in sorted(parts, key=len, reverse=True):  # longest first: one draft's CTA can sit inside another's line
        own = own.replace(part, " ")
    formal = re.findall(r".{0,30}\b(?:Sie|Ihnen|Ihre?[mnrs]?)\b.{0,20}", own)
    check(not formal, f"formal address in deck copy: {formal[:3]}")
hero = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
check(hero and len(html.unescape(re.sub(r"<[^>]+>", "", hero.group(1))).split()) <= 7, "hero headline > 7 words")
check(cfg["hero_intro"].count(". ") <= 1, "hero intro > 2 sentences")
check('id="dl"' in page and 'id="toggle"' in page and 'class="cta-btn' in page, "plumbing missing (dl / toggle / cta-btn)")
m = re.search(r'const CSV = ("(?:[^"\\]|\\.)*");', page, re.S)
check(m is not None, "embedded CSV missing")
if m:
    rows = list(csv.DictReader(io.StringIO(json.loads(m.group(1)))))
    check(len(rows) == len(cards), f"embedded CSV rows {len(rows)} != cards {len(cards)}")
    check(rows == list(csv.DictReader(open("csv/output/contacts_enriched.csv", newline="", encoding="utf-8"))), "embedded CSV != csv/output file")
print("PASS" if not fails else "FAIL\n  " + "\n  ".join(fails))
sys.exit(1 if fails else 0)
