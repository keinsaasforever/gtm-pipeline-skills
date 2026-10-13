"""ATS job feeds (--ats-jobs): detection, one parse per adapter, the lookback filter. No network. python3 test_ats_jobs.py"""
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
    '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>': ("greenhouse", "acme"),
    '<iframe src="https://job-boards.greenhouse.io/embed/job_board?for=acme&amp;b=x"></iframe>': ("greenhouse", "acme"),
    "<a href='https://jobs.ashbyhq.com/acme'>": ("ashby", "acme"),
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
for html, want in links.items():
    assert a.board_from_html(html) == want, (html, a.board_from_html(html))
for html in ('<a href="https://www.recruitee.com/?utm=powered">', '<a href="https://www.teamtailor.com/en">',
             '<a href="https://app.teamtailor.com/x">', '<a href="https://apply.workable.com/j/AB12">',
             '<a href="/karriere">Karriere</a>', "<p>boards.greenhouse.io/acme</p>"):  # vendor pages, own links, plain text
    assert a.board_from_html(html) is None, html

# detect(): homepage first, then /karriere, /jobs, /careers; a page that fails to load is skipped.
def serve(pages):
    def get(url):
        if url not in pages:
            raise OSError(f"404 {url}")
        return pages[url] if isinstance(pages[url], bytes) else pages[url].encode()
    a._get = get

serve({"https://acme.de": '<a href="/karriere">Karriere</a>',
       "https://acme.de/jobs": '<iframe src="https://acme.jobs.personio.de/"></iframe>'})
assert a.detect("acme.de") == ("personio", "acme.jobs.personio.de")
serve({"https://acme.de": "<p>no jobs</p>"})
assert a.detect("acme.de") is None

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
a.detect = lambda domain: ("recruitee", "acmesolar")
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
print("ok")
