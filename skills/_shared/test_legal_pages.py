"""Legal pages: the link in the company's languages, the officers blanked (2026-11-16). python3 test_legal_pages.py
Offline: no fetch. The Sales Agent's test_pure_helpers.test_legal_pages holds the full set for the twin."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from legal_pages import is_legal, languages, legal_link, redact, strip_fax, strip_officers

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
tkg = ("Geschäftsführer: Anna Beispiel\nTelefon: +49 4121 12345-0\nTelefax: +49 (0) 4121 / 12345-99\n\n"
       "Sicherheitsbeauftragter gemäß § 166 TKG:\nMax Muster\nTel.: +49 4121 12345-77\n\nRegistergericht: HRB 1")
out = strip_officers(tkg)                                                  # a telephony provider (2026-11-20)
assert "Muster" not in out and "12345-77" not in out and "Anna Beispiel" in out and "HRB 1" in out
out = strip_fax(tkg)
assert "12345-99" not in out and "Telefon: +49 4121 12345-0" in out and len(out) == len(tkg)
assert "05261" not in strip_fax("Fax-Nr.: 05261 999") and strip_fax("Faxgerät defekt") == "Faxgerät defekt"
ext = ("### **Betrieblicher Datenschutzbeauftragter gemäß §4f BDSG**\n\nMax Muster  \nKanzlei Recht Partnerschaft mbB "
       "Rechtsanwälte Steuerberater  \nWeg 5  \n20459 Hamburg\n\nTel. +49 40 300\n\n### **Handelsregister**\nHRB 1")
out = strip_officers(ext)                                         # an external officer's law firm (2026-11-20)
assert "Kanzlei" not in out and "Weg 5" not in out and "+49 40 300" not in out and "HRB 1" in out
# fetch_legal: no legal link on a cached homepage, /impressum lands back on the homepage, /impressum.html has it.
import legal_pages as lp
pages = {"https://acme.de": {"url": "https://acme.de", "final_url": "https://acme.de/", "text": "Willkommen", "links": []},
         "https://acme.de/impressum": {"url": "https://acme.de/impressum", "final_url": "https://acme.de/", "text": "Willkommen"},
         "https://acme.de/impressum.html": {"url": "https://acme.de/impressum.html", "final_url": "https://acme.de/impressum.html",
                                             "text": "Impressum\nAcme GmbH, Geschäftsführer: Max Muster"}}
lp._fetch = lambda urls, links=False: [dict(pages[urls[0]])] if urls[0] in pages else []
assert lp.fetch_legal("acme.de") == {"url": "https://acme.de/impressum.html", "text": pages["https://acme.de/impressum.html"]["text"]}
print("legal_pages: ok")
