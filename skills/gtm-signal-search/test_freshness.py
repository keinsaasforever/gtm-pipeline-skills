"""Freshness + source checks, from the cases of the perma-trade run (2026-09-18). python3 test_freshness.py"""
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
assert dates_in("09/02/2026") == [datetime(2026, 9, 2)]                       # TRUMPF en_US: 2 Sept, not 9 Feb
assert dates_in("07.09.2026Diehl Aviation") == [datetime(2026, 9, 7)]         # no space after the year

# The source's own date beats the provider's stamp (Sphere run, 2026-09-24).
old_story = {"url": "hensoldt", "title": "HENSOLDT appoints Sven Heursch as Head of Digitalisation | HENSOLDT",
             "publish_date": iso(fresh),  # the crawl date, not the article's
             "excerpts": ["# HENSOLDT appoints Sven Heursch as Head of Digitalisation 01/09/2025 Picture: HENSOLDT",
                          f"More news: Air {fresh:%d/%m/%Y} HENSOLDT gets development contract"]}
sidebar = {"url": "multivac", "title": "Broader basis with new four-man team at the top",
           "publish_date": iso(fresh),
           "excerpts": [f"Breaking news Posted on: {fresh:%B %d, %Y} ...... ...... ...... ...... ...... ...... ...... "
                        "...... ...... ...... ...... Broader basis with new four-man team at the top. From 1 January 2023 on"]}
date_line = {"url": "einhell", "title": "COMPACT SERIES: The Next Generation",
             "excerpts": [f"Go back {de(fresh)} 00:00 COMPACT SERIES: The Next Generation. Related: {de(stale)} story"]}
fresh_text = {"url": "fresh-text", "title": "ACME opens a plant", "publish_date": iso(stale),
              "excerpts": [f"ACME opens a plant. Pressemitteilung vom {de(fresh)}"]}
no_text_date = {"url": "no-text-date", "title": "ACME opens a plant", "publish_date": iso(fresh), "excerpts": ["ACME opens a plant."]}
kept, dropped = filter_search_results_by_freshness([old_story, sidebar, date_line, fresh_text, no_text_date], 2)
assert [r["url"] for r in kept] == ["einhell", "fresh-text", "no-text-date"] and dropped == {"stale": 2, "undated": 0}, (kept, dropped)

results = [
    {"url": "a", "publish_date": iso(fresh)},                          # dated by the provider, fresh
    {"url": "b", "publish_date": iso(stale)},                          # dated by the provider, stale
    {"url": "c", "excerpts": [f"Pressemitteilung vom {de(fresh)}"]},   # undated, fresh date in text (ENGIE, PORR)
    {"url": "d", "excerpts": [f"announced on {stale:%B %d, %Y}"]},    # undated, only stale dates (wn.com HOCHTIEF)
    {"url": "e", "title": "ZECH Building SE", "excerpts": ["Hochbau aus einer Hand"]},  # undated directory page
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

assert is_article_url("https://www.engie-deutschland.de/en/press/heating-transition-municipal-scale-engie-deutschland-take-over")
assert is_article_url("https://www.porr.de/en/news-press/press-releases/detail/porr-baut-fuer-x-fab-chipfabrik-in-erfurt-1")
assert is_article_url("https://www.linkedin.com/posts/klueh1911_legionellen-activity-123")
for url in ("https://linkedin.com/company/klueh1911", "https://www.linkedin.com/in/someone",
            "https://www.porr.de/en/news-press/press-releases", "https://www.klueh.de/en", "https://www.klueh.de/en/news/press-and-media"):
    assert not is_article_url(url), url
assert not _signal_is_valid({"source_url": "https://linkedin.com/company/klueh1911", "date": iso(fresh)}, now - timedelta(days=60))
assert _signal_is_valid({"source_url": "https://www.porr.de/de/presse/porr-baut-x-fab", "date": iso(fresh)}, now - timedelta(days=60))

# Firecrawl fallback pass: no second web search, the crawled pages still go through the cutoff.
import json, tempfile
from pathlib import Path
import signal_search as ss

tmp = Path(tempfile.mkdtemp())
(tmp / "context").mkdir()
for name in ("icp.md", "offering.md"):
    (tmp / "context" / name).write_text("x")
(tmp / "context" / "signal_criteria.md").write_text(
    "# Signal criteria — perma-trade\n\n## Include\n- Won a hospital project\n- Opened a branch\n\n## Not a signal\n- Heat-pump market news")
ctx = ss.ClientContext.load(tmp)
assert ctx.signal_hint == "Won a hospital project; Opened a branch", ctx.signal_hint  # was the seller's title

(tmp / "pages").mkdir()
(tmp / "pages" / "acme.de.json").write_text(json.dumps(pages))
ss.parallel_web_search = lambda *a, **k: (_ for _ in ()).throw(AssertionError("web search on a crawl-only pass"))
cfg = ss.RunConfig(use_firecrawl=False, use_parallel_enrichment=False, lookback_months=2, llm_backend="agent",
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
print("ok")
