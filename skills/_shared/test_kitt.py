"""Kitt gate checks: only `valid` ships, nothing walks to another provider. python3 test_kitt.py"""
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitt
from sanitize import email_ok

assert kitt.http_verdict(200, "") == "ok"
assert kitt.http_verdict(401, "bad key") == "stop"
assert kitt.http_verdict(402, "insufficient funds") == "stop"   # out of funds, not a throttle
assert kitt.http_verdict(402, "rate limit exceeded") == "retry"
assert kitt.http_verdict(418, "The free tier API is busy right now") == "retry"
assert kitt.http_verdict(422, "bad domain") == "fail"

assert kitt.email_of({"email": "no-results-found"}) is None  # a miss is a STRING, not a null
assert kitt.email_of({"email": "a@b.de"}) == "a@b.de" and kitt.email_of(None) is None
assert kitt.clean_domain("https://www.Acme.de/impressum?x=1") == "acme.de"

# valid and valid-risky survive sanitize's standard policy; strict drops risky (catch-all).
assert email_ok("valid", "a@b.de", "standard") and email_ok("valid-risky", "a@b.de", "standard")
assert not email_ok("valid-risky", "a@b.de", "strict")
for verdict in ("unknown", "invalid", kitt.UNVERIFIED):
    assert not email_ok(verdict, "a@b.de", "standard"), verdict


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code, self._payload = status, payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


VERDICTS = {                       # what the stub Kitt says about each address
    "lena@fresh.de": "valid",
    "tom@risky.de": "valid-risky",
    "eva@gone.de": "invalid",
}


def fake_post(url, json=None, headers=None, timeout=None):
    if url.endswith("/job/find_email"):
        hit = json["domain"] == "found.de"
        return FakeResponse({"email": "neu@found.de" if hit else "no-results-found",
                             "validity": "valid"})
    address = json["email"]
    if address == "silent@nocheck.de":
        raise kitt.requests.RequestException("timeout")   # fails open → unverified
    return FakeResponse({"validity": VERDICTS[address]})


kitt.requests.post = fake_post
os.environ["KITT_API_KEY"] = "test-key-not-used-by-the-stub"

tmp = Path(tempfile.mkdtemp())
src, out = tmp / "in.csv", tmp / "out.csv"
rows_in = [
    # no address yet → Kitt find (first in line, and nothing walks on after a miss)
    {"full_name": "Nina Neu", "company_domain": "found.de", "email": "", "email_source": ""},
    {"full_name": "Miss Miss", "company_domain": "leer.de", "email": "", "email_source": ""},
    {"full_name": "No Domain", "company_domain": "", "email": "", "email_source": ""},
    # another provider's finds → the gate checks each one
    {"full_name": "Lena Klar", "company_domain": "fresh.de", "email": "lena@fresh.de",
     "email_source": "fullenrich"},
    {"full_name": "Tom Riskant", "company_domain": "risky.de", "email": "tom@risky.de",
     "email_source": "fullenrich"},
    {"full_name": "Eva Weg", "company_domain": "gone.de", "email": "eva@gone.de",
     "email_source": "phantombuster"},
    {"full_name": "Sam Still", "company_domain": "nocheck.de", "email": "silent@nocheck.de",
     "email_source": "pipe0"},
]
with open(src, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows_in[0]))
    writer.writeheader()
    writer.writerows(rows_in)

sys.argv = ["kitt.py", "--input", str(src), "--output", str(out)]
kitt.main()
rows = {r["full_name"]: r for r in csv.DictReader(open(out))}

assert rows["Nina Neu"]["email"] == "neu@found.de", rows["Nina Neu"]
assert rows["Nina Neu"]["email_status"] == "valid" and rows["Nina Neu"]["email_source"] == "kitt"
assert rows["Miss Miss"]["email"] == "" and rows["No Domain"]["email"] == ""  # miss, no walk-on
assert rows["Lena Klar"]["email"] == "lena@fresh.de" and rows["Lena Klar"]["email_status"] == "valid"
assert rows["Lena Klar"]["email_source"] == "fullenrich"      # the gate keeps the provenance
assert rows["Tom Riskant"]["email"] == "tom@risky.de" and rows["Tom Riskant"]["email_status"] == "valid-risky"
for name, verdict in (("Eva Weg", "invalid"),
                      ("Sam Still", kitt.UNVERIFIED)):
    assert rows[name]["email"] == "", (name, rows[name])      # address pulled
    assert rows[name]["email_status"] == verdict, rows[name]
    assert rows[name]["full_name"] and rows[name]["company_domain"]  # contact itself stays

# The documented second pass: `--no-find` gates the fallback's finds and leaves Kitt's alone.
sys.argv = ["kitt.py", "--no-find", "--input", str(out), "--output", str(tmp / "gated.csv")]
kitt.main()
rows = {r["full_name"]: r for r in csv.DictReader(open(tmp / "gated.csv"))}
assert rows["Nina Neu"]["email"] == "neu@found.de" and rows["Nina Neu"]["email_status"] == "valid", rows
assert rows["Lena Klar"]["email"] == "lena@fresh.de", rows["Lena Klar"]   # re-checked, still valid

# A contacts CSV with no email column at all (straight from a finder): the finds must still land.
src2, out2 = tmp / "in2.csv", tmp / "out2.csv"
with open(src2, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["full_name", "company_domain"])
    writer.writeheader()
    writer.writerows([{"full_name": "Miss Miss", "company_domain": "leer.de"},
                      {"full_name": "Nina Neu", "company_domain": "found.de"}])
sys.argv = ["kitt.py", "--input", str(src2), "--output", str(out2)]
kitt.main()
rows = {r["full_name"]: r for r in csv.DictReader(open(out2))}
assert rows["Nina Neu"]["email"] == "neu@found.de", rows   # row 0 missed, the column still exists

print("ok")
