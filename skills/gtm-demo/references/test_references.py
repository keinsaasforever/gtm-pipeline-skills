"""End-to-end check of the demo scripts on a two-card fixture: nickname greeting, the fit-length warning, per-card
contact_label, the fit box on signal cards, a deck with no address, and no zero signal count anywhere.
python3 test_references.py"""
import csv, json, os, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONPATH": str(HERE.parent.parent / "_shared")}
tmp = Path(tempfile.mkdtemp())
for d in ("context", "csv/intermediate", "csv/output"):
    (tmp / d).mkdir(parents=True)


def run(script, *args):
    out = subprocess.run([sys.executable, str(HERE / script), *args], cwd=tmp, env=ENV, capture_output=True, text=True)
    assert script == "qa_deck.py" or out.returncode == 0, out.stderr
    return out.stdout


def write_signals(fresh):
    sig = [{"date": (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d"), "summary": "Opened a cask programme.",
            "source_url": "https://acme-casks.com/news/new-cask-programme"}] if fresh else []
    with open(tmp / "csv/intermediate/signals.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company_domain", "scoredSignals"])
        w.writeheader()
        w.writerows([{"company_domain": "acme-casks.com", "scoredSignals": json.dumps(sig)},
                     {"company_domain": "stone-spirits.com", "scoredSignals": "[]"}])


(tmp / "context/deck.json").write_text(json.dumps({
    "lang": "en", "client_name": "Acme", "client_slug": "acme", "hero_headline": "Two US cask buyers",
    "hero_intro": "Two buyers with a ready draft each.", "stat4": {"n": "1", "label": "segment"},
    "segments": [{"key": "a", "title": "Bottlers", "intro": "US bottlers."}],
    "approach_signal": "A dated development.", "approach_icp": "What each company buys.",
    "method_note": "We found no fresh signal at these companies. Every contact was checked.",
    "footer_headline": "Next?", "footer_body": "Let's talk.", "footer_meta": "Prepared for Acme",
    "cta_label": "Book a time", "signoff": {"en": "Best,\nSam"}}))
people = [("Joshua", "Lane", "acme-casks.com", "Hi Josh,", "Spirits buyer"), ("Mia", "Stone", "stone-spirits.com", "Hi Mia,", "")]


def write_contacts(mia_has_address=True):
    with open(tmp / "csv/intermediate/contacts_enriched.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company_name", "company_domain", "segment", "full_name", "first_name", "last_name",
                                          "linkedin_profile_url", "email", "email_status", "country"])
        w.writeheader()
        for first, last, dom, _, _ in people:
            kept = first == "Mia" and mia_has_address
            w.writerow({"company_name": dom.split(".")[0].title(), "company_domain": dom, "segment": "a",
                        "full_name": f"{first} {last}", "first_name": first, "last_name": last,
                        "linkedin_profile_url": f"https://www.linkedin.com/in/{first.lower()}",
                        "email": "mia@stone-spirits.com" if kept else "", "email_status": "valid" if kept else "",
                        "country": "USA"})


write_contacts()


def write_messages(greeting_for_joshua):
    msgs = {f"https://www.linkedin.com/in/{first.lower()}": {
        "job_title": "Buyer", "why_they_fit": "Bottles single casks under its own label.", "lang": "en", "register": "",
        "cta_variant": "A", "contact_label": label,
        "li_p1": f"{greeting_for_joshua if first == 'Joshua' else hi}\nYou bottle single casks under your own label.",
        "li_p2": "We source Scotch casks for US bottlers. Shall I send you three current offers?",
        **({"email_subject": "Casks", "email_p1": "Hi Mia,\nYour own label bottles single casks.",
            "email_p2": "We source Scotch casks.", "email_p3": "Shall I send three offers?\nBest,\nSam"} if first == "Mia" else
           {"email_subject": "", "email_p1": "", "email_p2": "", "email_p3": ""})}
        for first, _, _, hi, label in people}
    (tmp / "csv/intermediate/messages.json").write_text(json.dumps(msgs))


write_messages("Hi Josh,")
assert "greeting" not in run("check_messages.py")          # a short form of the first name greets
write_messages("Hi Jo,")
assert "greeting 'Hi Jo,'" in run("check_messages.py")      # two letters are too short
write_messages("Hi Josh,")
assert "why_they_fit" not in run("check_messages.py")
msgs = json.loads((tmp / "csv/intermediate/messages.json").read_text())
msgs["https://www.linkedin.com/in/mia"]["why_they_fit"] = "Bottles single casks. " * 10
(tmp / "csv/intermediate/messages.json").write_text(json.dumps(msgs))
assert "why_they_fit 220 > ~200" in run("check_messages.py")  # deck copy over its target: a warning
write_messages("Hi Josh,")

write_signals(fresh=False)
run("build_output.py")
run("render_deck.py", "deck.html")
page = (tmp / "deck.html").read_text()
assert "buying signal" not in page and "0 with" not in page, "a zero signal count shows"
assert "no fresh signal" not in page and "Every contact was checked." in page
assert '<div class="clabel">Spirits buyer</div>' in page and '<div class="clabel">Decision-maker</div>' in page
assert ">named contacts<" in page
assert run("qa_deck.py", "deck.html").startswith("PASS")

write_signals(fresh=True)                                  # one signal renders as before
run("build_output.py")
run("render_deck.py", "deck.html")
page = (tmp / "deck.html").read_text()
assert ">1</div><div class=\"l\">with a fresh buying signal<" in page and "no fresh signal" in page
assert page.count('<div class="siglabel">Why they fit</div>') == 2   # the signal card keeps its fit box
assert run("qa_deck.py", "deck.html").startswith("PASS")

write_contacts(mia_has_address=False)                      # no card keeps an address: the deck still builds
run("build_output.py")
run("render_deck.py", "deck.html")
assert 'class="cmail"' not in (tmp / "deck.html").read_text()
assert run("qa_deck.py", "deck.html").startswith("PASS")
print("ok")
