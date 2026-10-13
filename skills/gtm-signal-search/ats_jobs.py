#!/usr/bin/env python3
"""
Public ATS job feeds: dated hiring signals for signal_search.py --ats-jobs. Free, no key, stdlib only.

detect(domain) reads the ATS and board token off the company's own pages (the homepage, then
/karriere, /jobs, /careers). The token always comes from the employer's own careers link, never a
guess from the domain: a guessed token can belong to another company with the same name.
jobs(ats, board) returns [{title, url, published, text}]: url is the public posting page, published
is YYYY-MM-DD ("" when the feed has no date).

Public read routes (no key for any of them):
  Greenhouse       boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true  docs.greenhouse.io/job-board.html
  Ashby            api.ashbyhq.com/posting-api/job-board/{board}       developers.ashbyhq.com/docs/public-job-posting-api
  Lever            api.lever.co or api.eu.lever.co /v0/postings/{board}?mode=json  github.com/lever/postings-api
  Personio         {company}.jobs.personio.de|com/xml?language=de      developer.personio.de/v1.0/reference/get_xml
  Workable         www.workable.com/api/accounts/{board}?details=true  workable.readme.io/reference/jobs-1
  SmartRecruiters  api.smartrecruiters.com/v1/companies/{board}/postings  developers.smartrecruiters.com/docs/endpoints
  Recruitee        {board}.recruitee.com/api/feeds/offers.xml  (not the JSON /api/offers/, which needs a token from
                   2027-02-10; the XML feed stays open: docs.recruitee.com/reference/authentication-1)
  Teamtailor       {careers host}/jobs.rss                     support.teamtailor.com/en/articles/11171756
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from xml.etree import ElementTree

TIMEOUT = 20
CAREERS_PATHS = ("/karriere", "/jobs", "/careers")
MAX_POSTINGS = 1000  # ponytail: paginated feeds stop at 1000 postings; raise it for a bigger board

_TOKEN = r"([A-Za-z0-9_-]+)"
# (ats, pattern after "//"), tried in order on every href/src; group 1 is the board token or host.
ATS_LINKS = (
    ("greenhouse", r"(?:job-)?boards\.greenhouse\.io/embed/[^?]*\?(?:[^#]*&)?for=" + _TOKEN),
    ("greenhouse", r"(?:job-)?boards\.greenhouse\.io/" + _TOKEN),
    ("ashby", r"jobs\.ashbyhq\.com/" + _TOKEN),
    ("lever", r"jobs\.lever\.co/" + _TOKEN),
    ("lever-eu", r"jobs\.eu\.lever\.co/" + _TOKEN),
    ("personio", r"([A-Za-z0-9-]+\.jobs\.personio\.(?:de|com))\b"),
    ("workable", r"apply\.workable\.com/" + _TOKEN),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/" + _TOKEN),
    ("recruitee", r"([A-Za-z0-9-]+)\.recruitee\.com\b"),
    ("teamtailor", r"([A-Za-z0-9-]+\.teamtailor\.com)\b"),
)
# Vendor pages and app routes that look like a board token ("Powered by" links, embed scripts).
NOT_BOARDS = {"www", "app", "api", "embed", "j", "oneclick-ui", "support", "help", "docs"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.skip += 1
        elif tag in ("p", "div", "li", "h1", "h2", "h3", "br") and not self.skip:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self.skip:
            self.skip -= 1
        elif tag in ("p", "div", "li", "h1", "h2", "h3") and not self.skip:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def plain(raw: str | None) -> str:
    """Text of an HTML fragment. unescape first: Greenhouse sends its HTML entity-encoded."""
    parser = _Text(); parser.feed(unescape(raw or ""))
    text = re.sub(r"[ \t]+", " ", " ".join(parser.parts))
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def _get(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=TIMEOUT) as resp:
        return resp.read()


def _day(value) -> str:
    """YYYY-MM-DD from ISO 8601 (incl. "2026-09-08 14:39:12 UTC"), RFC 2822 or epoch milliseconds."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).strftime("%Y-%m-%d")
    value = (value or "").strip()
    if re.match(r"\d{4}-\d\d-\d\d", value):
        return value[:10]
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _job(title, url, published, html) -> dict:
    return {"title": (title or "").strip(), "url": url or "", "published": _day(published), "text": plain(html)}


def board_from_html(html: str) -> tuple[str, str] | None:
    """The first ATS board linked from a page's hrefs and srcs (links, iframes, embed scripts)."""
    for link in re.findall(r"""(?:href|src)\s*=\s*["']([^"']+)""", html, re.I):
        link = unescape(link)
        for ats, pattern in ATS_LINKS:
            m = re.match(r"(?:https?:)?//" + pattern, link, re.I)
            if m and m.group(1).split(".")[0].lower() not in NOT_BOARDS:
                return ats, m.group(1)
    return None


def detect(domain: str) -> tuple[str, str] | None:
    """(ats, board) from the company's own pages, None if none links an ATS. A page that fails to load is skipped."""
    for path in ("",) + CAREERS_PATHS:
        try:
            html = _get(f"https://{domain}{path}").decode("utf-8", "replace")
        except Exception:
            continue
        found = board_from_html(html)
        if found:
            return found
    return None


def greenhouse(board: str) -> list[dict]:
    data = json.loads(_get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"))
    # first_published is served (2026-10-13) but not in the docs, which list only updated_at; an edit
    # moves updated_at, so it is the fallback.
    return [_job(j.get("title"), j.get("absolute_url"), j.get("first_published") or j.get("updated_at"), j.get("content"))
            for j in data.get("jobs", [])]


def ashby(board: str) -> list[dict]:
    data = json.loads(_get(f"https://api.ashbyhq.com/posting-api/job-board/{board}"))
    return [_job(j.get("title"), j.get("jobUrl"), j.get("publishedAt"), j.get("descriptionHtml"))
            for j in data.get("jobs", []) if j.get("isListed", True)]


def lever(board: str, host: str = "api.lever.co") -> list[dict]:
    postings: list[dict] = []
    for skip in range(0, MAX_POSTINGS, 100):
        page = json.loads(_get(f"https://{host}/v0/postings/{board}?mode=json&skip={skip}&limit=100"))
        postings += page
        if len(page) < 100:
            break
    # createdAt (epoch ms) is served but missing from the docs' field table.
    return [_job(j.get("text"), j.get("hostedUrl"), j.get("createdAt"), j.get("description")) for j in postings]


def personio(host: str) -> list[dict]:
    root = ElementTree.fromstring(_get(f"https://{host}/xml?language=de"))
    out = []
    for p in root.iter("position"):
        text = "".join(f"<h3>{d.findtext('name') or ''}</h3>{d.findtext('value') or ''}" for d in p.iter("jobDescription"))
        url = f"https://{host}/job/{p.findtext('id')}" if p.findtext("id") else ""
        out.append(_job(p.findtext("name"), url, p.findtext("createdAt"), text))
    return out


def workable(board: str) -> list[dict]:
    data = json.loads(_get(f"https://www.workable.com/api/accounts/{board}?details=true"))
    return [_job(j.get("title"), j.get("url") or j.get("shortlink"), j.get("published_on"), j.get("description"))
            for j in data.get("jobs", [])]


def smartrecruiters(board: str) -> list[dict]:
    """The listing carries no description: title and date only."""
    base = f"https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=100&offset="
    pages = [json.loads(_get(base + "0"))]
    for offset in range(100, min(int(pages[0].get("totalFound") or 0), MAX_POSTINGS), 100):
        pages.append(json.loads(_get(base + str(offset))))
    return [_job(j.get("name"), f"https://jobs.smartrecruiters.com/{board}/{j['id']}" if j.get("id") else "",
                 j.get("releasedDate"), "")
            for page in pages for j in page.get("content", [])]


def recruitee(board: str) -> list[dict]:
    # This route serves the Careers Site API's offer fields (docs.recruitee.com/reference/offers:
    # published_at, careers_url, description, requirements) as <offers><offer>, not the <job>/<posted>
    # shape of Recruitee's job-board feed doc.
    root = ElementTree.fromstring(_get(f"https://{board}.recruitee.com/api/feeds/offers.xml"))
    return [_job(o.findtext("title"), o.findtext("careers_url"), o.findtext("published_at"),
                 (o.findtext("description") or "") + (o.findtext("requirements") or ""))
            for o in root.iter("offer")]


def teamtailor(host: str) -> list[dict]:
    items: list = []
    for offset in range(0, MAX_POSTINGS, 100):
        page = ElementTree.fromstring(_get(f"https://{host}/jobs.rss?offset={offset}&per_page=100")).findall(".//item")
        items += page
        if len(page) < 100:
            break
    return [_job(i.findtext("title"), i.findtext("link"), i.findtext("pubDate"), i.findtext("description")) for i in items]


ADAPTERS = {
    "greenhouse": greenhouse, "ashby": ashby, "lever": lever, "lever-eu": lambda b: lever(b, "api.eu.lever.co"),
    "personio": personio, "workable": workable, "smartrecruiters": smartrecruiters,
    "recruitee": recruitee, "teamtailor": teamtailor,
}


def jobs(ats: str, board: str) -> list[dict]:
    """The board's open postings. Raises on a fetch or parse error; the caller logs and skips."""
    return [j for j in ADAPTERS[ats](board) if j["title"] and j["url"]]

