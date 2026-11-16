"""Legal pages: the link in the company's languages, the officers blanked (2026-11-16). python3 test_legal_pages.py
Offline: no fetch. The Sales Agent's test_pure_helpers.test_legal_pages holds the full set for the twin."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from legal_pages import is_legal, languages, legal_link, redact, strip_officers

assert languages("DE", "acme.com") == ["de", "en"] and languages(None, "acme.fr") == ["fr", "en"]
assert legal_link(["https://x.com/en/departments/legal-department", "https://x.com/en/legal-notice"], "x.com", "DE") \
    == "https://x.com/en/legal-notice"                                         # a product page is no legal page
assert legal_link(["https://x.co.uk/terms-and-conditions", "https://x.co.uk/privacy-policy"], "x.co.uk") \
    == "https://x.co.uk/terms-and-conditions"                                  # the UK names the operator there
assert legal_link(["https://x.fr/cgv", "https://x.fr/mentions_legales.html"], "x.fr") == "https://x.fr/mentions_legales.html"
assert legal_link(["https://x.com/custom-imprinting"], "x.com", "US") is None
assert is_legal("https://x.de/datenschutz", "") and not is_legal("https://x.com/", "inhabergeführtes Unternehmen")

page = ("Geschäftsführer: Anna Beispiel\n\n## Externer Datenschutzbeauftragter\n\nMax Mustermann\nWeg 5\n32657 Lemgo\n\n"
        "Tel.: +49 5261 123\ninfo@dsb-firma.example\n\nRegistergericht: Amtsgericht Lemgo HRB 12345\nFax: 05261 999")
out = strip_officers(page)
assert "Mustermann" not in out and "Weg 5" not in out and "dsb-firma" not in out          # the officer's block
assert "Anna Beispiel" in out and "HRB 12345" in out and len(out) == len(page)            # the company stays
assert "Bob" not in strip_officers("CISO: Bob Secure\nVorstand: Carl Chef") and "Carl Chef" in strip_officers(
    "CISO: Bob Secure\nVorstand: Carl Chef")
assert "DPD und DHL" in strip_officers("Versand mit DPD und DHL.")                         # DPD is a parcel service
p = {"text": "Datenschutzbeauftragter: Max Muster\nmax@dsb-firma.example", "links": [
    "mailto:max@dsb-firma.example", "mailto:datenschutz@acme.example", "mailto:info@acme.example"]}
assert redact(p) and p["links"] == ["mailto:info@acme.example"]
print("legal_pages: ok")
