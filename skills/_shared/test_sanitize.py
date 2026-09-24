"""Wrong-person + keep-the-contact checks (Neocom demo, 2026-09-23). python3 test_sanitize.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitize import email_owner_score, sanitize_rows, wrong_person_emails

assert email_owner_score("Karl Horst", "khorst@bau-ko.de") == 2
assert email_owner_score("Bernd Baum", "khorst@bau-ko.de") == 0
assert email_owner_score("Sven Weißer", "sweisser@jagd-shop.de") == 2      # ß folds to ss
assert email_owner_score("Christoph Brenner", "christoph.brenner@bergsport.eu") == 2
assert email_owner_score("Jane Doe", "jd@acme.de") == 1                        # initials
assert email_owner_score("Jane Doe", "info@acme.de") is None                   # role mailbox
assert email_owner_score("", "jane@acme.de") is None

rows = [
    {"full_name": "Karl Horst", "email": "khorst@bau-ko.de", "email_status": "valid"},
    {"full_name": "Bernd Baum", "email": "khorst@bau-ko.de", "email_status": "valid"},
    {"full_name": "Ida Unklar", "email": "office2@acme.de", "email_status": "valid"},
    {"full_name": "Udo Unklar", "email": "office2@acme.de", "email_status": "valid"},
    {"full_name": "Lea Lone", "email": "buchhaltung@acme.de", "email_status": "valid"},
    {"full_name": "Eva Echt", "email": "eva.echt@acme.de", "email_status": "valid"},
]
found = wrong_person_emails(rows, "email", ("full_name",))
assert set(found["blank"]) == {1, 2, 3}, found          # Horst keeps his own, the unclear pair loses it
assert "Karl Horst" in found["blank"][1]
assert "owner unclear" in found["blank"][2]
assert found["mismatched"] == ["Lea Lone <buchhaltung@acme.de>"]  # reported only, never dropped

# require_email=False: the contact survives, the address does not — that is the est-warn card.
rows = [
    {"full_name": "Eva Echt", "email": "eva.echt@acme.de", "email_status": "valid"},
    {"full_name": "Tom Riskant", "email": "tom@risky.de", "email_status": "valid-risky"},
    {"full_name": "Sam Still", "email": "sam@nocheck.de", "email_status": "unverified"},
    {"full_name": "Bernd Baum", "email": "eva.echt@acme.de", "email_status": "valid"},
]
clean, report = sanitize_rows(rows, require_email=False, drop_empty=False)
assert len(clean) == 4, clean                                  # nobody is dropped
assert clean[0]["email"] == "eva.echt@acme.de"
assert clean[1]["email"] == "tom@risky.de", clean               # valid-risky ships (catch-all)
assert [r["email"] for r in clean[2:]] == ["", ""], clean       # unverified, not-yours
assert report["emails_blanked"] == 1 and len(report["emails_wrong_person"]) == 1, report

clean, report = sanitize_rows(rows, require_email=True)         # the old behaviour still drops
assert [r["full_name"] for r in clean] == ["Eva Echt", "Tom Riskant"], clean
assert report["rows_dropped_bad_email"] == 2, report

print("ok")
