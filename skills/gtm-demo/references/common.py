"""Shared loaders for the demo reference scripts. Run every script from {client-slug}-gtm/."""
import csv, json, os, sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/gtm-pipeline/_shared"))
KEPT = ("valid", "valid-risky")  # Kitt verdicts that ship (gtm-demo Step 5)


def deck_config():
    return json.load(open("context/deck.json", encoding="utf-8"))


def contacts():
    return list(csv.DictReader(open("csv/intermediate/contacts_enriched.csv", encoding="utf-8")))


def messages():
    return json.load(open("csv/intermediate/messages.json", encoding="utf-8"))


def signals():
    """{company_domain: first kept signal or None} from signal-search's signals.csv."""
    out = {}
    for r in csv.DictReader(open("csv/intermediate/signals.csv", encoding="utf-8")):
        kept = json.loads(r.get("scoredSignals") or "[]")
        out[r["company_domain"]] = kept[0] if kept else None
    return out


def has_address(c):
    return bool((c.get("email") or "").strip()) and c.get("email_status") in KEPT
