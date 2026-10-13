"""PB Email Finder: a failed phantom run exits 3, and the domain check honours the company's mail domains.
python3 test_pb_email_finder.py"""
import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pb_email_finder as pb

# The domain check: the website domain, plus the mail domains the company's own evidence ties to it (a supplier
# run, 2026-10-12: site on one domain, imprint info@ on another that redirects to the site).
m = pb.email_domain_matches
assert m("rc@site-alu.de", "site-alu.de") == "match"
assert m("rc@group-mail.de", "site-alu.de") == "mismatch"                      # the website alone drops it
assert m("rc@group-mail.de", "site-alu.de", "group-mail.de") == "match"        # the imprint's domain keeps it
assert m("rc@site-alu.de", "site-alu.de", "group-mail.de") == "match"          # the website still counts
assert m("rc@mx.group-mail.de", "https://www.site-alu.de/", "other.com group-mail.de") == "subdomain"
assert m("rc@group-mail.com", "site-alu.de", "group-mail.de") == "other_tld"   # dropped like a mismatch
assert m("rc@stranger.de", "site-alu.de", "group-mail.de") == "mismatch"
assert m("", "site-alu.de") == "" and m("rc@x.de", "", "") == ""

# A canned failed run, as the phantom logged it on 2026-10-12: exit code 1, 0 found.
FAILED_LOG = ("* Container 1 started\r\n[load_]🔄 Enriching 11 profiles\r\n[error]❌ You have no remaining emails.\r\n"
              "[info_]ℹ️ Found 0 emails out of 11 profiles.\r\n[load_]🔄 Saving data...\r\n"
              "[error]❌ Storage full: Please make some space by deleting Phantoms or files.\r\n"
              "* Process finished with an error (exit code: 1)")
FAILED = {"id": "1", "status": "finished", "exitCode": 1, "endType": "finished"}
CLEAN_LOG = "[info_]ℹ️ Found 0 emails out of 1 profiles.\r\n* Process finished successfully (exit code: 0)"
CLEAN = {"id": "1", "status": "finished", "exitCode": 0, "endType": "finished"}
assert pb.phantom_failure(FAILED, FAILED_LOG) == ("You have no remaining emails.; "
                                                  "Storage full: Please make some space by deleting Phantoms or files.")
assert pb.phantom_failure(CLEAN, CLEAN_LOG) == ""                                # found nothing, but ran fine
assert "exitCode=1" in pb.phantom_failure(FAILED, "")                            # exit code alone is enough
assert pb.phantom_failure({"status": "running"}, "")                             # still running at the poll cap


class Sheet:
    id = "sheet-1"

    def __init__(self):
        self.sheet1 = self

    def share(self, *a, **kw): pass
    def clear(self): pass
    def update(self, **kw): pass


class Drive:
    def __init__(self):
        self.trashed = []

    def create(self, title): return Sheet()
    def del_spreadsheet(self, sheet_id): self.trashed.append(sheet_id)


run = {}


def fake_api(method, path, body, api_key):
    if path == "agents/launch":
        return {"containerId": "c1"}
    if path.startswith("containers/fetch?"):
        return run["container"]
    if path.startswith("agents/fetch-output"):
        return {"output": run["log"]}
    return {"resultObject": None}


drive = Drive()
pb.get_gspread_client = lambda: drive
pb.pb_api = fake_api
pb.time.sleep = lambda s: None
os.environ["PHANTOMBUSTER_API_KEY"] = "test-key-not-used-by-the-stub"
tmp = Path(tempfile.mkdtemp())
with open(tmp / "in.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["first_name", "last_name", "company_name", "company_domain", "email"])
    w.writeheader()
    w.writerow({"first_name": "Eva", "last_name": "Echt", "company_name": "Acme", "company_domain": "acme.de", "email": ""})
sys.argv = ["pb_email_finder.py", "--input", str(tmp / "in.csv"), "--output", str(tmp / "out.csv")]

run.update(container=FAILED, log=FAILED_LOG)
assert pb.main() == 3 and not (tmp / "out.csv").exists()    # the waterfall moves on to the next provider
assert drive.trashed == ["sheet-1"]                          # the link-shared sheet with lead names goes

run.update(container=CLEAN, log=CLEAN_LOG)
assert pb.main() == 0 and (tmp / "out.csv").exists()        # a clean run that finds nothing still exits 0
print("ok")
