"""Homepage-name checks, offline. python3 test_company_name.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_name import name_from_html as n

assert n("<title>Fundwise.com | Estate planning for advisors</title>", "fundwise.com") == "Fundwise.com"
assert n('<meta property="og:site_name" content="Brightloop"><title>Accept EBT online</title>', "getbrightloop.com") == "Brightloop"
assert n('<meta content="Harbor Labs" name="application-name">', "harborlabs.com") == "Harbor Labs"   # attribute order
assert n("<title>Ve | Telehealth for weight loss</title>", "ve.co") == "Ve"
assert n("<title>Venue operations | Proven care</title>", "ve.co") is None                     # 've' inside words
assert n("<title>Construction Management Software</title>", "buildbook.com") is None            # slogan only
assert n("<title>Northwind Health Limited - Clinic software</title>", "northwind-health.com") == "Northwind Health Limited"
assert n("<title>Smith &amp; Sons | Plumbing</title>", "smithsons.com") == "Smith & Sons"    # entities
assert n("", "blocked.com") is None
assert n("<title>Brightloop: Payments for Retailers</title>", "getbrightloop.com") == "Brightloop"
assert n('<meta property="og:site_name" content="Atlas Education AU"><title>Atlas Education - School Management System</title>',
         "atlas.education") == "Atlas Education"
print("ok")
