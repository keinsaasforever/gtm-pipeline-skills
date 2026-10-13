"""Freshness checks: the date reader, both evidence filters and the calendar-day window. python3 test_freshness.py"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signal_search import dates_in, filter_crawl_pages_by_freshness, filter_search_results_by_freshness, is_fresh

now = datetime.utcnow()
fresh, stale = now - timedelta(days=10), now - timedelta(days=90)
iso = lambda d: d.strftime("%Y-%m-%d")
de = lambda d: d.strftime("%d.%m.%Y")

assert [d.date() for d in dates_in("am 29.07.2026, 29. Juli 2026, July 29, 2026 und 2026-07-29")] == [datetime(2026, 7, 29).date()] * 4
assert dates_in("Sept. 3, 2026") == [datetime(2026, 9, 3)] and dates_in("3. März 2026") == [datetime(2026, 3, 3)]
assert dates_in("bis 2040, seit 1996, Juli 2028") == []  # a year or a month alone is not a date
assert dates_in("09/24/2026") == [datetime(2026, 9, 24)]  # US form: 24 can't be a month

# The source's own date beats the provider's stamp, which is often the crawl date.
old_story = {"url": "appointment", "title": "ACME appoints Jane Doe as Head of Digitalisation | ACME",
             "publish_date": iso(fresh),
             "excerpts": ["# ACME appoints Jane Doe as Head of Digitalisation 01/09/2025 Picture: ACME",
                          f"More news: Air {fresh:%d/%m/%Y} ACME gets development contract"]}
fresh_text = {"url": "fresh-text", "title": "ACME opens a plant", "publish_date": iso(stale),
              "excerpts": [f"ACME opens a plant. Pressemitteilung vom {de(fresh)}"]}
results = [
    old_story, fresh_text,
    {"url": "a", "publish_date": iso(fresh)},                          # dated by the provider, fresh
    {"url": "b", "publish_date": iso(stale)},                          # dated by the provider, stale
    {"url": "e", "title": "Acme Building SE", "excerpts": ["Hochbau aus einer Hand"]},  # undated directory page
]
kept, dropped = filter_search_results_by_freshness(results, 2)
assert [r["url"] for r in kept] == ["fresh-text", "a"] and dropped == {"stale": 2, "undated": 1}, (kept, dropped)

# Crawled pages: a stale page, an old page re-stamped by a site rebuild and an undated page are all dropped.
pages = [
    {"metadata": {"article:published_time": iso(fresh)}, "markdown": ""},
    {"metadata": {"article:published_time": iso(stale), "last_modified": iso(fresh)}, "markdown": ""},
    {"metadata": {}, "markdown": f"Stand {de(stale)}"},
    {"metadata": {}, "markdown": "Karriere: Anlagenmechaniker gesucht"},
]
assert filter_crawl_pages_by_freshness(pages, 2) == pages[:1]  # stale and undated pages used to be kept

# The window counts calendar days: a date exactly 60 days back is in, whatever the time of day.
day = lambda n: datetime.combine((now - timedelta(days=n)).date(), datetime.min.time())
assert is_fresh([day(59)], 2) and is_fresh([day(60)], 2) and not is_fresh([day(61)], 2)
print("ok")
