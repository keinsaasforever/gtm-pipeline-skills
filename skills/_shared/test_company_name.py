"""Homepage-name checks, offline. python3 test_company_name.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_name import name_from_html as n

assert n("<title>Wealth.com | Estate planning for advisors</title>", "wealth.com") == "Wealth.com"
assert n('<meta property="og:site_name" content="Forage"><title>Accept EBT online</title>', "joinforage.com") == "Forage"
assert n('<meta content="Cover Genius" name="application-name">', "covergenius.com") == "Cover Genius"   # attribute order
assert n("<title>Ro | Telehealth for weight loss</title>", "ro.co") == "Ro"
assert n("<title>Provider operations | Proven care</title>", "ro.co") is None                   # 'ro' inside words
assert n("<title>Construction Management Software</title>", "projectsimpel.com") is None        # slogan only
assert n("<title>Global Health Limited - Clinic software</title>", "global-health.com") == "Global Health Limited"
assert n("<title>AT&amp;T | Phones and internet</title>", "att.com") == "AT&T"            # entities
assert n("", "blocked.com") is None
assert n("<title>Forage: SNAP EBT Payments for Retailers</title>", "joinforage.com") == "Forage"
assert n('<meta property="og:site_name" content="Compass Education AU"><title>Compass Education - School Management System</title>',
         "compass.education") == "Compass Education"
print("ok")
