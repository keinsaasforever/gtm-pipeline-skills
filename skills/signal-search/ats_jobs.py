#!/usr/bin/env python3
"""
Public ATS job feeds: dated hiring signals for signal_search.py --ats-jobs. Free, stdlib only.

detect(domain) reads the ATS and board token off the company's own site: the homepage, the careers
pages it links to, and the jobs pages those link to. It reads them plainly first; when that finds no
ATS and a TinyFish key is given, it renders them (free), which catches pages built by JavaScript and
iframes injected by an ATS widget. The token always comes from a link on the employer's own site,
never a guess from the domain: a guessed token can belong to another company with the same name.
Without an ATS, detect returns the rendered careers pages for the caller to scrape.
jobs(ats, board) returns [{title, url, published, text}]: url is the public posting page, published
is YYYY-MM-DD ("" when the feed has no date). arbeitsagentur(name, days) returns the same for a German
employer's postings on the Federal Employment Agency's job board. wants_job_signals(criteria) says
whether a client's signal criteria ask for hiring.

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
Rendering: TinyFish fetch, POST api.fetch.tinyfish.ai with links + iframe_links  docs.tinyfish.ai/fetch-api/reference
Arbeitsagentur: rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs, X-API-Key jobboerse-jobsuche
                (the public clientId)  jobsuche.api.bund.dev
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

TIMEOUT = 20
TINYFISH_FETCH_URL = "https://api.fetch.tinyfish.ai/"
CAREERS_PATHS = ("/karriere", "/jobs", "/careers")  # tried when the homepage links no careers page
MAX_PAGES = 8  # pages read per company and per reader: the homepage plus careers and jobs pages
# A careers link names careers in its host, path or anchor text ("Anfrage stellen" is not a job).
CAREERS_WORDS = re.compile(r"\bkarriere|\bcareers?\b|\bjobs?\b|/stellen\b|\bstellen(?:angebot|markt|anzeige)"
                           r"|(?:offene|freie)\s+stellen|arbeiten\s+bei|join\s+us", re.I)
MAX_POSTINGS = 1000  # ponytail: paginated feeds stop at 1000 postings; raise it for a bigger board
ARBEITSAGENTUR_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
# Legal forms dropped before two employer names are compared ("Acme Elektro GmbH & Co. KG").
_LEGAL_FORMS = re.compile(r"\b(?:gmbh|mbh|ag|kgaa|kg|se|ug|ohg|gbr|e\s?k|e\s?v|co|inh|haftungsbeschränkt)\b")
# Signal criteria that ask for hiring turn the job feeds on (signal_search.py, unless --no-ats-jobs).
HIRING_WORDS = re.compile(r"\bhiring\b|\bhires?\b|recruit|\bjob\s*(?:ads?|postings?|openings?|offers?)\b|\bvacanc"
                          r"|open\s+(?:roles|positions)|stellen(?:anzeige|angebot|ausschreibung|markt)|(?:offene|neue)\s+stellen"
                          r"|\bstell(?:t|en)\s+\w*\s*ein\b|einstellung|personalbedarf|personalsuche", re.I)

_TOKEN = r"([A-Za-z0-9_-]+)"
# (ats, pattern after "//"), tried in order on every href/src; group 1 is the board token or host.
ATS_LINKS = (
    # An EU board (job-boards.eu.greenhouse.io) reads through the same API (checked live, 2026-10-13).
    ("greenhouse", r"(?:job-boards(?:\.eu)?|boards)\.greenhouse\.io/embed/[^?]*\?(?:[^#]*&)?for=" + _TOKEN),
    ("greenhouse", r"(?:job-boards(?:\.eu)?|boards)\.greenhouse\.io/" + _TOKEN),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)"),  # a board name can carry a dot: /acme.io
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


def _open(url: str, headers: dict | None = None) -> tuple[str, bytes]:
    """(final URL after redirects, body)."""
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})}), timeout=TIMEOUT) as resp:
        return resp.geturl(), resp.read()


def _get(url: str) -> bytes:
    return _open(url)[1]


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


def board_from_links(links: list[str]) -> tuple[str, str] | None:
    """The first ATS board among absolute link and iframe URLs."""
    for link in links:
        for ats, pattern in ATS_LINKS:
            m = re.match(r"(?:https?:)?//" + pattern, link, re.I)
            if m and m.group(1).split(".")[0].lower() not in NOT_BOARDS:
                return ats, m.group(1)
    return None


def parse_html(url: str, html: str) -> dict:
    """A plainly read page: its anchors as (absolute URL, text) and every href/src (links, iframes, scripts)."""
    anchors = [(urljoin(url, unescape(h)), re.sub(r"<[^>]+>", " ", t))
               for h, t in re.findall(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", html, re.I | re.S)]
    srcs = [urljoin(url, unescape(x)) for x in re.findall(r"""(?:href|src)\s*=\s*["']([^"']+)""", html, re.I)]
    return {"url": url, "title": "", "text": "", "anchors": anchors, "srcs": srcs}


def careers_links(page: dict, sites: set[str]) -> list[str]:
    """Links to careers pages: on the company's own site or a subdomain, or on a host that itself names
    careers (acme-karriere.de); never a job portal's page about the company."""
    out = []
    for url, text in page["anchors"]:
        u = urlparse(url.split("#")[0])
        host = (u.hostname or "").removeprefix("www.")
        own = any(host == site or host.endswith("." + site) for site in sites)
        if u.scheme in ("http", "https") and not u.path.lower().endswith(".pdf") \
                and (own or CAREERS_WORDS.search(host)) and CAREERS_WORDS.search(f"{host}{u.path} {text}"):
            out.append(u.geturl())
    return list(dict.fromkeys(out))


def _read_plain(urls: list[str]) -> list[dict]:
    pages = []
    for url in urls:
        try:
            final, body = _open(url)
        except Exception:  # a page that fails to load is skipped
            continue
        pages.append(parse_html(final, body.decode("utf-8", "replace")))
    return pages


def _read_rendered(urls: list[str], key: str) -> list[dict]:
    """Pages rendered in a browser by TinyFish fetch (free, at most 10 URLs a call). links holds every
    <a href>, iframe_links the iframes, including ones a script injected; both come back absolute."""
    body = {"urls": urls[:10], "format": "markdown", "links": True, "iframe_links": True, "per_url_timeout_ms": 45000}
    req = Request(TINYFISH_FETCH_URL, data=json.dumps(body).encode(),
                  headers={"X-API-Key": key, "Content-Type": "application/json"})
    with urlopen(req, timeout=120) as resp:
        results = json.loads(resp.read()).get("results") or []
    return [{"url": r.get("final_url") or r.get("url"), "title": r.get("title") or "", "text": r.get("text") or "",
             "anchors": [(link, "") for link in r.get("links") or []],
             "srcs": (r.get("links") or []) + (r.get("iframe_links") or [])} for r in results]


def _walk(domain: str, read) -> tuple[tuple[str, str] | None, list[dict]]:
    """Breadth-first from the homepage over careers links, three levels deep (homepage, careers page,
    jobs page), at most MAX_PAGES pages: the first ATS board linked, else the careers pages read."""
    home = f"https://{domain}"
    sites, seen, careers, level = {domain.removeprefix("www.")}, {home}, [], [home]
    for depth in range(3):
        following = []
        for page in read(level) if level else []:
            found = board_from_links(page["srcs"])
            if found:
                return found, []
            u = urlparse(page["url"])
            sites.add((u.hostname or "").removeprefix("www."))  # where a redirect or careers domain lands
            if depth and CAREERS_WORDS.search(u.netloc + u.path):  # not a soft 404 back to the homepage
                careers.append(page)
            for url in careers_links(page, sites):
                if url not in seen and len(seen) < MAX_PAGES:
                    seen.add(url); following.append(url)
        if depth == 0 and not following:
            following = [home + path for path in CAREERS_PATHS]; seen.update(following)
        level = following
    return None, careers


def detect(domain: str, tinyfish_key: str | None = None) -> tuple[tuple[str, str] | None, list[dict]]:
    """((ats, board) or None, careers pages). Read plainly first; rendered with TinyFish only when that
    finds no ATS and a key is given. The careers pages (rendered markdown, at most 3) come back only
    when no ATS was found, for the caller to scrape."""
    found, _ = _walk(domain, _read_plain)
    if found or not tinyfish_key:
        return found, []
    found, careers = _walk(domain, lambda urls: _read_rendered(urls, tinyfish_key))
    return found, [{"markdown": p["text"], "metadata": {"title": p["title"], "sourceURL": p["url"]}}
                   for p in careers if p["text"]][:3]


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


def company_key(name: str | None) -> str:
    """An employer name without legal form, case and punctuation, for an exact comparison."""
    words = re.sub(r"[^\w\s]", " ", (name or "").lower())
    return " ".join(_LEGAL_FORMS.sub(" ", words).split())


def arbeitsagentur(company_name: str, days: int) -> list[dict]:
    """Postings on the Arbeitsagentur job board whose employer is the company itself: one search call,
    no detail calls. The search also returns other employers (a sister company at the same address) and
    staffing agencies; zeitarbeit=false drops the agencies, the exact name match the rest.
    veroeffentlichtseit (0-100 days) filters by the latest republish date, so an ad first posted months
    ago comes back; published is datumErsteVeroeffentlichung, the first publication, which the live
    response carries though the OpenAPI spec does not list it (checked 2026-10-13)."""
    query = urlencode({"was": company_name, "veroeffentlichtseit": min(days, 100), "size": 25, "zeitarbeit": "false"})
    data = json.loads(_open(f"{ARBEITSAGENTUR_URL}?{query}", {"X-API-Key": "jobboerse-jobsuche"})[1])
    key, out = company_key(company_name), []
    for j in data.get("ergebnisliste") or []:
        if company_key(j.get("firma")) != key or not j.get("referenznummer"):
            continue
        place = ((j.get("stellenlokationen") or [{}])[0].get("adresse") or {}).get("ort") or ""
        out.append(_job(j.get("stellenangebotsTitel"), f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{j['referenznummer']}",
                        j.get("datumErsteVeroeffentlichung"), ", ".join(x for x in (j.get("firma"), place) if x)))
    return out


def wants_job_signals(signal_criteria: str) -> bool:
    """Whether the include half of signal_criteria.md asks for hiring; the "Not a signal:" half doesn't count."""
    include = re.split(r"(?im)^[#*_\s]*(?:not a signal|not signals|exclude)", signal_criteria or "")[0]
    return bool(HIRING_WORDS.search(include))

