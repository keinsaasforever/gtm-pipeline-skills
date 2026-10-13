"""The signal freshness window counts calendar days. python3 test_sanitize.py"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitize import sanitize_rows

today = datetime(2026, 10, 12, 18, 30)  # a run late in the day
for age, kept in ((59, 1), (60, 1), (61, 0)):
    sig = {"source_url": "https://acme.de/news/new-plant", "date": (today - timedelta(days=age)).strftime("%Y-%m-%d")}
    clean, _ = sanitize_rows([{"full_name": "Eva Echt", "email": "eva@acme.de", "email_status": "valid",
                               "scored_signals": [sig]}], drop_empty=False, max_signal_age_days=60, today=today)
    assert len(clean[0]["scored_signals"]) == kept, (age, clean)
print("ok")
