"""Job feeds: ATS detection, one parse per adapter, the lookback filter, the careers-page fallback, the
Arbeitsagentur name match and date rule, the hiring trigger. No network. python3 test_ats_jobs.py"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ats_jobs as a
import signal_search as ss

# Detection: the board token comes from the employer's own hrefs and iframe/script srcs.
links = {
    '<a href="https://boards.greenhouse.io/acme">Jobs</a>': ("greenhouse", "acme"),
    '<a href="https://job-boards.greenhouse.io/acme/jobs/123">Job</a>': ("greenhouse", "acme"),
    '<a href="https://job-boards.eu.greenhouse.io/acme">Jobs</a>': ("greenhouse", "acme"),
    '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>': ("greenhouse", "acme"),
    '<iframe src="https://job-boards.greenhouse.io/embed/job_board?for=acme&amp;b=x"></iframe>': ("greenhouse", "acme"),
    "<a href='https://jobs.ashbyhq.com/acme'>": ("ashby", "acme"),
    '<a href="https://jobs.ashbyhq.com/acme.io/123">': ("ashby", "acme.io"),
    '<a href="https://jobs.lever.co/acme/abc-123">': ("lever", "acme"),
    '<a href="https://jobs.eu.lever.co/acme">': ("lever-eu", "acme"),
    '<iframe src="https://acme-gmbh.jobs.personio.de/?display=de"></iframe>': ("personio", "acme-gmbh.jobs.personio.de"),
    '<a href="https://acme.jobs.personio.com/job/42">': ("personio", "acme.jobs.personio.com"),
    '<a href="https://apply.workable.com/acme/">': ("workable", "acme"),
    '<a href="https://careers.smartrecruiters.com/AcmeGroup">': ("smartrecruiters", "AcmeGroup"),
    '<a href="https://jobs.smartrecruiters.com/AcmeGroup/7444-engineer">': ("smartrecruiters", "AcmeGroup"),
    '<a href="https://acmesolar.recruitee.com/">': ("recruitee", "acmesolar"),
    '<a href="//acme.teamtailor.com/jobs">': ("teamtailor", "acme.teamtailor.com"),
}
board = lambda html: a.board_from_links(a.parse_html("https://acme.de/", html)["srcs"])
for html, want in links.items():
    assert board(html) == want, (html, board(html))
for html in ('<a href="https://www.recruitee.com/?utm=powered">', '<a href="https://www.teamtailor.com/en">',
             '<a href="https://app.teamtailor.com/x">', '<a href="https://apply.workable.com/j/AB12">',
             '<a href="/karriere">Karriere</a>', "<p>boards.greenhouse.io/acme</p>"):  # vendor pages, own links, plain text
    assert board(html) is None, html

# detect() follows careers links from the homepage, two clicks deep, onto a careers subdomain or a
# careers domain, never onto a job portal; /karriere, /jobs, /careers only when the homepage links none.
# A page that fails to load is skipped.
def serve(pages):
    def open_(url, headers=None):
        if url not in pages:
            raise OSError(f"404 {url}")
        return url, pages[url] if isinstance(pages[url], bytes) else pages[url].encode()
    a._open = open_

serve({"https://acme.de": '<a href="https://karriere.acme.de/">Arbeiten bei ACME</a><a href="/anfrage">PV Anfrage stellen</a>',
       "https://karriere.acme.de/": '<a href="/offene-stellen">Offene Stellen</a>',
       "https://karriere.acme.de/offene-stellen": '<iframe src="https://acme.jobs.personio.de/"></iframe>'})
assert a.detect("acme.de") == (("personio", "acme.jobs.personio.de"), [])
serve({"https://acme.de": '<a href="https://acme-jobs.de/">Team</a>',
       "https://acme-jobs.de/": '<a href="https://acme.recruitee.com/">Bewerben</a>'})
assert a.detect("acme.de") == (("recruitee", "acme"), [])
serve({"https://acme.de": '<a href="https://www.stepstone.de/cmp/acme/jobs">Jobs</a>',
       "https://www.stepstone.de/cmp/acme/jobs": '<a href="https://other.recruitee.com/">x</a>',
       "https://acme.de/jobs": '<iframe src="https://acme.jobs.personio.de/"></iframe>'})
assert a.detect("acme.de") == (("personio", "acme.jobs.personio.de"), [])  # the portal is skipped, /jobs is tried
serve({"https://acme.de": "<p>no jobs</p>"})
assert a.detect("acme.de") == (None, [])

# With a TinyFish key, a site the plain read found nothing on is rendered: links and iframe_links
# carry what JavaScript built. Without an ATS the rendered careers pages come back for scraping.
rendered = {
    "https://acme.de": {"url": "https://www.acme.de/", "title": "ACME", "text": "Home",
                        "anchors": [("https://www.acme.de/karriere", "")], "srcs": ["https://www.acme.de/karriere"]},
    "https://www.acme.de/karriere": {"url": "https://www.acme.de/karriere", "title": "Karriere", "text": "Elektriker gesucht",
                                     "anchors": [], "srcs": ["https://acme.teamtailor.com/jobs"]},
}
a._read_rendered = lambda urls, key: [rendered[u] for u in urls if u in rendered]
assert a.detect("acme.de") == (None, [])  # no key: no render
assert a.detect("acme.de", "key") == (("teamtailor", "acme.teamtailor.com"), [])
rendered["https://www.acme.de/karriere"]["srcs"] = []
assert a.detect("acme.de", "key") == (None, [{"markdown": "Elektriker gesucht",
                                              "metadata": {"title": "Karriere", "sourceURL": "https://www.acme.de/karriere"}}])

# One parse per adapter: public posting URL, YYYY-MM-DD date, plain text.
serve({
    "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true": json.dumps({"jobs": [
        {"title": "Data Engineer", "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
         "first_published": "2026-09-07T09:34:25-04:00", "updated_at": "2026-10-08T02:46:16-04:00",
         "content": "&lt;p&gt;Build &amp;amp; run pipelines&lt;/p&gt;"}]}),
    "https://api.ashbyhq.com/posting-api/job-board/acme": json.dumps({"jobs": [
        {"title": "AE", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "publishedAt": "2026-09-01T16:21:55.393+00:00",
         "descriptionHtml": "<p>Sell</p>", "isListed": True},
        {"title": "Hidden", "jobUrl": "https://jobs.ashbyhq.com/acme/2", "isListed": False}]}),
    "https://api.eu.lever.co/v0/postings/acme?mode=json&skip=0&limit=100": json.dumps([
        {"text": "SRE", "hostedUrl": "https://jobs.eu.lever.co/acme/1", "createdAt": 1788199939703,
         "description": "<div>On call</div>"}]),
    "https://acme.jobs.personio.de/xml?language=de": """<?xml version="1.0"?><workzag-jobs><position><id>42</id>
        <name>Elektriker (m/w/d)</name><createdAt>2026-09-08T12:14:07+0200</createdAt><jobDescriptions>
        <jobDescription><name>Aufgaben</name><value><![CDATA[<p>PV und Speicher</p>]]></value></jobDescription>
        </jobDescriptions></position></workzag-jobs>""",
    "https://www.workable.com/api/accounts/acme?details=true": json.dumps({"jobs": [
        {"title": "Ops", "url": "https://apply.workable.com/acme/j/AB12/", "shortlink": "https://apply.workable.com/j/AB12",
         "published_on": "2026-09-02", "description": "<p>Run ops</p>"}]}),
    "https://api.smartrecruiters.com/v1/companies/AcmeGroup/postings?limit=100&offset=0": json.dumps(
        {"totalFound": 1, "content": [{"id": "7444", "name": "Engineer", "releasedDate": "2026-09-03T10:00:00.000Z"}]}),
    "https://acmesolar.recruitee.com/api/feeds/offers.xml": """<?xml version="1.0"?><offers><offer><id>1</id>
        <title><![CDATA[Elektriker PV]]></title><description><![CDATA[<p>PV, Speicher</p>]]></description>
        <requirements><![CDATA[<p>Gesellenbrief</p>]]></requirements>
        <careers_url>https://acmesolar.recruitee.com/o/elektriker-pv</careers_url>
        <published_at>2026-09-08 14:39:12 UTC</published_at></offer></offers>""",
    "https://acme.teamtailor.com/jobs.rss?offset=0&per_page=100": """<?xml version="1.0"?><rss><channel><item>
        <title>Designer</title><link>https://acme.teamtailor.com/jobs/1-designer</link>
        <pubDate>Fri, 04 Sep 2026 10:00:00 +0200</pubDate><description>&lt;p&gt;Design&lt;/p&gt;</description>
        </item></channel></rss>""",
})
want = {
    ("greenhouse", "acme"): ("Data Engineer", "https://job-boards.greenhouse.io/acme/jobs/1", "2026-09-07", "Build & run pipelines"),
    ("ashby", "acme"): ("AE", "https://jobs.ashbyhq.com/acme/1", "2026-09-01", "Sell"),
    ("lever-eu", "acme"): ("SRE", "https://jobs.eu.lever.co/acme/1", "2026-08-31", "On call"),
    ("personio", "acme.jobs.personio.de"): ("Elektriker (m/w/d)", "https://acme.jobs.personio.de/job/42", "2026-09-08", "Aufgaben\nPV und Speicher"),
    ("workable", "acme"): ("Ops", "https://apply.workable.com/acme/j/AB12/", "2026-09-02", "Run ops"),
    ("smartrecruiters", "AcmeGroup"): ("Engineer", "https://jobs.smartrecruiters.com/AcmeGroup/7444", "2026-09-03", ""),
    ("recruitee", "acmesolar"): ("Elektriker PV", "https://acmesolar.recruitee.com/o/elektriker-pv", "2026-09-08", "PV, Speicher\nGesellenbrief"),
    ("teamtailor", "acme.teamtailor.com"): ("Designer", "https://acme.teamtailor.com/jobs/1-designer", "2026-09-04", "Design"),
}
for (ats, board), (title, url, published, text) in want.items():
    got = a.jobs(ats, board)
    assert [(j["title"], j["url"], j["published"], j["text"]) for j in got] == [(title, url, published, text)], (ats, got)

# Lookback: only postings published inside the window become pages, newest first, and they pass the
# same freshness gate as any website page. A failure is skipped, never raised.
day = lambda n: (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")
a.detect = lambda domain, key=None: (("recruitee", "acmesolar"), [])
a.jobs = lambda ats, board: [
    {"title": "Elektriker PV-Anlagen", "url": "u/new", "published": day(3), "text": "Seit 01.03.2015 bauen wir PV."},
    {"title": "Old", "url": "u/old", "published": day(90), "text": ""},
    {"title": "Undated", "url": "u/undated", "published": "", "text": ""},
    {"title": "Monteur", "url": "u/mid", "published": day(30), "text": ""},
]
pages = ss.ats_job_pages("acme.de", 2)
assert [p["metadata"]["sourceURL"] for p in pages] == ["u/new", "u/mid"], pages
assert ss.filter_crawl_pages_by_freshness(pages, 2) == pages  # an older date in the ad text doesn't override the posting date
a.jobs = lambda ats, board: (_ for _ in ()).throw(OSError("HTTP 404"))
assert ss.ats_job_pages("acme.de", 2) == []

# A careers page without a known ATS goes in as it is and passes only on a fresh date it prints itself.
careers = [{"markdown": f"Elektriker (m/w/d), veröffentlicht am {datetime.utcnow() - timedelta(days=5):%d.%m.%Y}",
            "metadata": {"title": "Karriere", "sourceURL": "https://acme.de/karriere"}},
           {"markdown": "Wir suchen immer gute Leute.", "metadata": {"title": "Jobs", "sourceURL": "https://acme.de/jobs"}}]
a.detect = lambda domain, key=None: (None, careers)
pages = ss.ats_job_pages("acme.de", 2, "key")
assert pages == careers and ss.filter_crawl_pages_by_freshness(pages, 2) == careers[:1]

# Arbeitsagentur: only the company's own postings (legal form, case and punctuation aside), dated by the
# first publication. The search returns a sister company at the same address and ads it republished.
assert a.company_key("ACME Elektro GmbH & Co. KG") == a.company_key("Acme-Elektro e.K.") == a.company_key("Acme Elektro")
assert a.company_key("Acmeenergie GmbH") != a.company_key("Acme Elektro")
ad = lambda firma, title, first, ref: {"firma": firma, "stellenangebotsTitel": title, "datumErsteVeroeffentlichung": first,
                                       "aenderungsdatum": day(1), "referenznummer": ref,
                                       "stellenlokationen": [{"adresse": {"ort": "Musterstadt"}}]}
query = "was=Acme+Elektro&veroeffentlichtseit=60&size=25&zeitarbeit=false"
serve({f"{a.ARBEITSAGENTUR_URL}?{query}": json.dumps({"ergebnisliste": [
    ad("Acme Elektro GmbH", "KNX-Programmierer (m/w/d)", day(36), "10001-1-S"),
    ad("Acmeenergie GmbH", "Elektroniker (m/w/d)", day(10), "10001-2-S"),
    ad("Acme Elektro GmbH", "Techniker E-Mobilität (m/w/d)", day(335), "10001-3-S")]})})
got = a.arbeitsagentur("Acme Elektro", 60)
assert [(j["title"], j["url"], j["text"]) for j in got] == [
    ("KNX-Programmierer (m/w/d)", "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1-S", "Acme Elektro GmbH, Musterstadt"),
    ("Techniker E-Mobilität (m/w/d)", "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-3-S", "Acme Elektro GmbH, Musterstadt")], got
a.detect = lambda domain, key=None: (None, [])
pages = ss.ats_job_pages("acme-elektro.de", 2, None, "Acme Elektro", german=True)
assert [p["metadata"]["sourceURL"] for p in pages] == ["https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1-S"], pages
assert ss.ats_job_pages("acme-elektro.com", 2, None, "Acme Elektro", german=False) == []  # Germany only

# The job feeds switch on when the include half of signal_criteria.md asks for hiring.
for criteria in ("- Hiring installers for PV", "- Stellenanzeigen für Elektriker", "- stellt Monteure ein",
                 "- Recruiting a Head of Operations", "- Neueinstellung im Vertrieb"):
    assert a.wants_job_signals(criteria), criteria
for criteria in ("- Opened a branch", "- Won a hospital project\n\n## Not a signal\n- Hiring news", "- Anfrage stellen"):
    assert not a.wants_job_signals(criteria), criteria
print("ok")
