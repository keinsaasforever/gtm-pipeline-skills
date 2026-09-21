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
print("ok")
