"""Freshness + source checks, from the cases of a construction-supplier run (2026-09-18). python3 test_freshness.py"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gtm-pipeline", "_shared"))
from sanitize import _signal_is_valid, is_article_url
from signal_search import dates_in, filter_crawl_pages_by_freshness, filter_search_results_by_freshness

now = datetime.utcnow()
fresh, stale = now - timedelta(days=10), now - timedelta(days=90)
iso = lambda d: d.strftime("%Y-%m-%d")
de = lambda d: d.strftime("%d.%m.%Y")

assert [d.date() for d in dates_in("am 29.07.2026, 29. Juli 2026, July 29, 2026 und 2026-07-29")] == [datetime(2026, 7, 29).date()] * 4
assert dates_in("Sept. 3, 2026") == [datetime(2026, 9, 3)] and dates_in("3. März 2026") == [datetime(2026, 3, 3)]
assert dates_in("bis 2040, seit 1996, Juli 2028") == []  # a year or a month alone is not a date
assert dates_in("09/24/2026") == [datetime(2026, 9, 24)]                      # US form: 24 can't be a month
assert dates_in("01/09/2025") == [datetime(2025, 9, 1)]                       # ambiguous, both past: the later reading
assert dates_in("09/02/2026") == [datetime(2026, 9, 2)]                       # a machine maker's en_US page: 2 Sept, not 9 Feb
assert dates_in("07.09.2026Acme Aviation") == [datetime(2026, 9, 7)]         # no space after the year

# The source's own date beats the provider's stamp (a machinery run, 2026-09-24).
old_story = {"url": "appointment", "title": "ACME appoints Jane Doe as Head of Digitalisation | ACME",
             "publish_date": iso(fresh),  # the crawl date, not the article's
             "excerpts": ["# ACME appoints Jane Doe as Head of Digitalisation 01/09/2025 Picture: ACME",
                          f"More news: Air {fresh:%d/%m/%Y} ACME gets development contract"]}
sidebar = {"url": "sidebar", "title": "Broader basis with new four-man team at the top",
           "publish_date": iso(fresh),
           "excerpts": [f"Breaking news Posted on: {fresh:%B %d, %Y} ...... ...... ...... ...... ...... ...... ...... "
                        "...... ...... ...... ...... Broader basis with new four-man team at the top. From 1 January 2023 on"]}
date_line = {"url": "dateline", "title": "PRO LINE: The Next Generation",
             "excerpts": [f"Go back {de(fresh)} 00:00 PRO LINE: The Next Generation. Related: {de(stale)} story"]}
fresh_text = {"url": "fresh-text", "title": "ACME opens a plant", "publish_date": iso(stale),
              "excerpts": [f"ACME opens a plant. Pressemitteilung vom {de(fresh)}"]}
no_text_date = {"url": "no-text-date", "title": "ACME opens a plant", "publish_date": iso(fresh), "excerpts": ["ACME opens a plant."]}
kept, dropped = filter_search_results_by_freshness([old_story, sidebar, date_line, fresh_text, no_text_date], 2)
assert [r["url"] for r in kept] == ["dateline", "fresh-text", "no-text-date"] and dropped == {"stale": 2, "undated": 0}, (kept, dropped)

results = [
    {"url": "a", "publish_date": iso(fresh)},                          # dated by the provider, fresh
    {"url": "b", "publish_date": iso(stale)},                          # dated by the provider, stale
    {"url": "c", "excerpts": [f"Pressemitteilung vom {de(fresh)}"]},   # undated, fresh date in text (two builders' press pages)
    {"url": "d", "excerpts": [f"announced on {stale:%B %d, %Y}"]},    # undated, only stale dates (a news aggregator)
    {"url": "e", "title": "Acme Building SE", "excerpts": ["Hochbau aus einer Hand"]},  # undated directory page
]
kept, dropped = filter_search_results_by_freshness(results, 2)
assert [r["url"] for r in kept] == ["a", "c"] and dropped == {"stale": 2, "undated": 1}, (kept, dropped)

pages = [
    {"metadata": {"article:published_time": iso(fresh)}, "markdown": ""},
    {"metadata": {"article:published_time": iso(stale), "last_modified": iso(fresh)}, "markdown": ""},
    {"metadata": {}, "markdown": f"Stand {de(stale)}"},
    {"metadata": {}, "markdown": "Karriere: Anlagenmechaniker SHK gesucht"},
]
assert len(filter_crawl_pages_by_freshness(pages, 2)) == 1  # stale and undated pages used to be kept

assert is_article_url("https://www.acme-energie.de/en/press/heating-transition-municipal-scale-acme-energie-take-over")
assert is_article_url("https://www.bau-ag.de/en/news-press/press-releases/detail/bau-ag-baut-chipfabrik-in-erfurt-1")
assert is_article_url("https://www.linkedin.com/posts/acme-service_legionellen-activity-123")
for url in ("https://linkedin.com/company/acme-service", "https://www.linkedin.com/in/someone",
            "https://www.bau-ag.de/en/news-press/press-releases", "https://www.acme-service.de/en", "https://www.acme-service.de/en/news/press-and-media"):
    assert not is_article_url(url), url
assert not _signal_is_valid({"source_url": "https://linkedin.com/company/acme-service", "date": iso(fresh)}, now - timedelta(days=60))
assert _signal_is_valid({"source_url": "https://www.bau-ag.de/de/presse/bau-ag-baut-chipfabrik", "date": iso(fresh)}, now - timedelta(days=60))

# Firecrawl fallback pass: no second web search, the crawled pages still go through the cutoff.
import json, tempfile
from pathlib import Path
import signal_search as ss

tmp = Path(tempfile.mkdtemp())
(tmp / "context").mkdir()
for name in ("icp.md", "offering.md"):
    (tmp / "context" / name).write_text("x")
(tmp / "context" / "signal_criteria.md").write_text(
    "# Signal criteria — Acme\n\n## Include\n- Won a hospital project\n- Opened a branch\n\n## Not a signal\n- Heat-pump market news")
ctx = ss.ClientContext.load(tmp)
bullets = ss.objective_bullets(ctx.signal_criteria)
assert bullets == "- Won a hospital project\n- Opened a branch", bullets  # no seller title, no exclude half

(tmp / "pages").mkdir()
(tmp / "pages" / "acme.de.json").write_text(json.dumps(pages))
ss.parallel_web_search = lambda *a, **k: (_ for _ in ()).throw(AssertionError("web search on a crawl-only pass"))
cfg = ss.RunConfig(site_search=None, use_parallel_enrichment=False, lookback_months=2, llm_backend="agent",
                   claude_extract_model="", claude_scoring_model="", extract_model="", scoring_model="",
                   gemini_extract_model="", gemini_scoring_model="", parallel_key="", firecrawl_key=None,
                   openrouter_key="", gemini_key=None, context=ctx, raw_evidence_dir=tmp / "raw",
                   firecrawl_pages_dir=tmp / "pages", crawl_only=True)
ss.process_company({"company_name": "Acme", "company_website": "https://acme.de"}, cfg)
raw = json.loads((tmp / "raw" / "acme.de.json").read_text())
assert raw["web_search_results"] == [] and len(raw["website_urls_crawled"]) == 4 and len(raw["website_pages"]) == 1, raw

# Firecrawl matches excludePaths anywhere in the path: a whole segment is excluded, a news slug is not.
import re
excluded = lambda path: any(re.search(p, path) for p in ss.FIRECRAWL_EXCLUDE_PATHS)
for path in ("/karriere", "/de/jobs/", "/impressum.html", "/llms.txt", "/.well-known/x", "/shop/cart"):
    assert excluded(path), path
for path in ("/news/200-neue-jobs-in-erfurt", "/aktuelles/workshop-trinkwasser", "/referenzen/data-center-frankfurt",
             "/presse/restore-programm"):
    assert not excluded(path), path

# keep_site_hits: shared filter for all three site-search providers.
hits = [
    "https://acme.de/news/a", "https://acme.de/karriere/job-1", "https://acme.de/jobs/job-2",
    "https://acme.de/press/report.pdf", "https://acme.de/news/a",  # duplicate
    "https://acme.de/news/b", "https://acme.de/news/c", "https://acme.de/news/d", "https://acme.de/news/e",
]
kept = ss.keep_site_hits(hits)
assert kept == ["https://acme.de/news/a", "https://acme.de/news/b", "https://acme.de/news/c",
                "https://acme.de/news/d", "https://acme.de/news/e"], kept  # karriere/jobs/.pdf/dup dropped, capped at 5, order kept

# Tavily's published_date is RFC 2822; convert to ISO, or None if unparseable.
assert ss._rfc2822_to_iso("Thu, 24 Sep 2026 19:00:00 GMT") == "2026-09-24"
assert ss._rfc2822_to_iso("") is None
assert ss._rfc2822_to_iso("not a date") is None
print("ok")
