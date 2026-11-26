"""Legal pages (imprint, Impressum, mentions légales …): find a company's own,
and never keep its data-protection or information-security officer.

Twin of the Sales Agent's scaleway-jobs/_shared/legal_pages.py: the slug
lists, legal_link and strip_officers are the same code; change both.

Use it whenever a skill or a script reads an imprint (an address, the managing
directors, an office mailbox, a mail domain):

    python3 ~/.claude/skills/gtm-pipeline/_shared/legal_pages.py <domain> [<country>]

prints {"url", "text"} as JSON: the legal page the homepage links, found by
the slugs of the company's country's languages plus English, with every
officer's block blanked. In Python: `fetch_legal(domain, country)`, or
`legal_link(links, host, country)` and `redact(page)` on pages you fetched.
TinyFish fetch (free tier), TINYFISH_API_KEY from the environment. Never save
an imprint page you did not pass through redact(); fetch_legal also blanks its
fax numbers (strip_fax), so none is ever taken for a phone.

legal_link: the slugs below come from a survey of company sites in 27
languages (2026-11-16, each top slug seen on two or more real sites). The
country (an ISO code, else the domain's country code) gives the languages,
English always with them. A strong slug counts as a run of a path segment's
words ("impressum-datenschutz", "sayfa-kunye-2") or as the whole segment run
together ("mentionslegales"); a weak one (legal, disclaimer, terms, privacy)
only as a whole segment, so "/departments/legal-department" is no legal page.
Order: a strong slug of those languages, then a strong slug of any other
language, then a weak one of its languages (where the operator often stands
only in the terms or the privacy page: the UK, the Nordics, Czechia), the
shortest link first on a tie.

strip_officers: the block that names a data-protection or
information-security officer (27 languages), and such a mailbox, blanked; the
company itself and its managing directors stay.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote, urlparse


# lang: (strong, weak), most common first.
SLUGS = {
    "en": (["legal-notice", "legal-notices", "imprint", "company-information", "company-details",
            "company-registration-details", "site-notice"],
           ["legal", "legal-information", "legal-info", "legal-statement", "legal-statements", "legal-disclaimer",
            "legal-terms", "terms-and-conditions", "terms", "website-terms",
            "terms-of-use", "disclaimer", "privacy-policy"]),
    "de": (["impressum", "offenlegung", "anbieterkennzeichnung"],
           ["rechtliches", "rechtliche-hinweise", "rechtlicher-hinweis", "disclaimer", "haftungsausschluss", "agb",
            "nutzungsbedingungen"]),
    "fr": (["mentions-legales", "mention-legale", "informations-legales"],
           ["mentions", "cgu", "cgv", "conditions-generales", "legal", "politique-de-confidentialite"]),
    "it": (["note-legali", "nota-legale", "informazioni-legali", "dati-societari", "informazioni-societarie"],
           ["legal", "condizioni-di-utilizzo", "termini-e-condizioni", "disclaimer", "privacy"]),
    "es": (["aviso-legal", "avisos-legales", "avis-legal", "informacion-legal", "nota-legal"],
           ["legal", "terminos-y-condiciones", "condiciones-de-uso", "condiciones-generales", "politica-de-privacidad"]),
    "pt": (["aviso-legal", "avisos-legais", "informacao-legal", "informacoes-legais", "nota-legal"],
           ["termos-e-condicoes", "termos-de-utilizacao", "condicoes-gerais", "legal", "politica-de-privacidade"]),
    "nl": (["colofon", "bedrijfsgegevens", "wettelijke-vermeldingen", "juridische-informatie",
            "juridische-vermeldingen"],
           ["disclaimer", "juridisch", "legal", "algemene-voorwaarden", "privacy"]),
    "pl": (["nota-prawna", "informacje-prawne", "dane-rejestrowe", "dane-firmy"],
           ["regulamin", "rodo", "polityka-prywatnosci"]),
    "cs": (["pravni-upozorneni", "pravni-informace"],
           ["obchodni-podminky", "vseobecne-podminky", "ochrana-osobnich-udaju"]),
    "sk": (["pravne-informacie"],
           ["vseobecne-obchodne-podmienky", "obchodne-podmienky", "podmienky-pouzivania", "ochrana-osobnych-udajov"]),
    "hu": (["impresszum", "jogi-nyilatkozat"], ["aszf", "adatkezelesi-tajekoztato", "adatvedelem"]),
    "ro": (["informatii-legale", "mentiuni-legale"], ["termeni-si-conditii", "termeni-legali", "politica-gdpr"]),
    "bg": (["pravno-izvestie", "правно-известие", "informaciya-za-dostavchika"],
           ["obshti-usloviya", "obshti-uslovija", "общи-условия", "pravila-za-polzvane"]),
    "el": (["nomiki-simeiosi", "nomiki-simiosi", "νομικη-σημειωση", "legal-note"],
           ["oroi-xrisis", "oroi-proypotheseis-xrisis", "terms"]),
    "hr": (["impresum"], ["uvjeti-koristenja", "uvjeti-poslovanja", "opci-uvjeti-poslovanja", "politika-privatnosti"]),
    "sl": (["pravno-obvestilo", "impresum"], ["pravno", "splosni-pogoji", "pogoji-uporabe"]),
    "sr": (["impresum", "импресум", "pravna-obavestenja", "отисак"],
           ["politika-privatnosti", "uslovi-koriscenja", "zastita-privatnosti"]),
    "da": (["juridisk-information", "juridiske-oplysninger", "virksomhedsoplysninger"],
           ["handelsbetingelser", "privatlivspolitik", "persondatapolitik"]),
    "sv": (["juridisk-information"], ["integritetspolicy", "villkor", "anvandarvillkor", "integritet"]),
    "no": (["juridisk-informasjon", "selskapsinformasjon"], ["juridisk", "personvern", "personvernerklaering", "vilkar"]),
    "fi": (["oikeudellinen-huomautus", "oikeudelliset-tiedot"],
           ["kayttoehdot", "yritystiedot", "tietosuojaseloste", "tietosuoja"]),
    "et": (["oiguslik-teave"], ["kasutustingimused", "tingimused", "privaatsusteave"]),
    "lv": (["juridiska-informacija", "rekviziti"], ["lietosanas-noteikumi", "privatuma-politika"]),
    "lt": (["teisine-informacija", "rekvizitai"],
           ["naudojimo-salygos", "naudojimosi-salygos", "salygos-ir-taisykles", "privatumo-politika"]),
    "tr": (["kunye", "yasal-uyari", "ticaret-sicil-bilgileri", "bilgi-toplumu-hizmetleri"],
           ["yasal", "yasal-bilgiler", "kullanim-kosullari", "gizlilik-politikasi", "kvkk"]),
    "is": (["lagalegur-fyrirvari"], ["skilmalar", "personuverndarstefna"]),
}
# On company sites in every country (Shopify keeps English slugs everywhere).
EVERYWHERE = ["impressum", "imprint", "legal-notice", "legal-notices"]
# Country (ISO 3166-1 alpha-2, as accounts.country holds it, or a domain's
# country code) -> its languages, the main one first.
LANGS = {
    "DE": "de", "AT": "de", "LI": "de", "CH": "de fr it", "LU": "fr de", "GB": "en", "UK": "en", "IE": "en",
    "MT": "en", "US": "en", "CA": "en fr", "AU": "en", "FR": "fr", "BE": "nl fr de", "NL": "nl", "IT": "it de",
    "ES": "es", "PT": "pt", "PL": "pl", "CZ": "cs", "SK": "sk", "HU": "hu", "RO": "ro", "BG": "bg", "GR": "el",
    "CY": "el", "HR": "hr", "SI": "sl", "RS": "sr", "BA": "hr sr", "ME": "sr", "DK": "da", "SE": "sv", "NO": "no",
    "FI": "fi sv", "IS": "is", "EE": "et", "LV": "lv", "LT": "lt", "TR": "tr",
}
_EXT = re.compile(r"\.(?:html?|php\d?|aspx?|jsp|cfm)$")


def fold(text: str) -> str:
    """Lower case, accents off (é = e, ü = u, ή = η)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def languages(country: str | None, host: str | None = None) -> list[str]:
    """The company's languages, English last if not among them: its country's,
    else its domain's country code's, else English alone."""
    code = (country or "").strip().upper()
    if code not in LANGS:
        code = (host or "").rsplit(".", 1)[-1].upper()
    langs = LANGS.get(code, "").split()
    return langs + ([] if "en" in langs else ["en"])


def _segments(url: str) -> list[list[str]]:
    """The path's segments and its fragment ("#mentionslegales"), each as its
    words: percent-decoded, folded, "_" as "-", no file extension, no leading
    page id (PrestaShop's "/content/6-politica-de-privacidad")."""
    p = urlparse(url)
    out = []
    for raw in re.split(r"[/#]", f"{p.path}#{p.fragment}"):
        seg = _EXT.sub("", fold(unquote(raw)).replace("_", "-").replace(" ", "-")).strip("-")
        seg = re.sub(r"^\d+-+", "", seg)
        if seg:
            out.append(seg.split("-"))
    return out


def _strong(slug: str, segs: list[list[str]]) -> bool:
    words = slug.split("-")
    return any(seg[i:i + len(words)] == words for seg in segs for i in range(len(seg) - len(words) + 1)) \
        or any("".join(seg) == slug.replace("-", "") for seg in segs)


def rank(url: str, langs: list[str] | None) -> tuple | None:
    """(tier, language, slug), lower is better, or None: no legal page. Tier 0
    a strong slug of `langs`, 1 a strong slug of any other language (a legal
    notice beats a terms page), 2 a weak slug of `langs`. `langs` None: every
    language as its own (is_legal)."""
    segs = _segments(url)
    found = []
    for li, lang in enumerate(SLUGS if langs is None else langs):
        strong, weak = SLUGS[lang]
        found += [(0, li, si) for si, s in enumerate((EVERYWHERE if li == 0 else []) + strong) if _strong(s, segs)]
        found += [(2, li, si) for si, s in enumerate(weak) if any("-".join(seg) == s for seg in segs)]
    if langs is not None:
        found += [(1, li, si) for li, (lang, (strong, _)) in enumerate(SLUGS.items()) if lang not in langs
                  for si, s in enumerate(strong) if _strong(s, segs)]
    return min(found) if found else None


# The privacy pages, where the law has the officer named (GDPR Art. 13): legal
# pages for is_legal. legal_link takes one only as a weak slug of the company's
# languages (SLUGS), when no legal notice is linked: it names the controller.
PRIVACY = ["datenschutz", "datenschutzerklarung", "datenschutzerklaerung", "datenschutzhinweise", "privacy",
           "privacy-policy", "privacy-notice", "privacy-statement", "data-protection", "data-privacy",
           "confidentialite", "politique-de-confidentialite", "privacidad", "privacidade", "informativa-privacy",
           "privacyverklaring", "privacybeleid", "polityka-prywatnosci", "rodo", "gdpr", "dsgvo", "integritetspolicy",
           "privatlivspolitik", "personvern", "personvernerklaering", "tietosuoja", "tietosuojaseloste",
           "adatvedelem", "adatkezelesi-tajekoztato", "ochrana-osobnich-udaju", "ochrana-osobnych-udajov",
           "gizlilik-politikasi", "kvkk"]
# Words only a legal notice prints: the register, the VAT id, § 5 DDG (a
# one-pager's Impressum on its homepage). Never a lone "Inhaber" or
# "Geschäftsführer": an ordinary homepage says "inhabergeführt" too.
LEGAL_TEXT = re.compile(
    r"angaben\s+gem(?:a|ae|ä)(?:ss|ß)\s+§|§\s*5\s+(?:tmg|ddg)|registergericht|handelsregister|registernummer"
    r"|ust-?\s?id|umsatzsteuer-?\s?identifikations|registered\s+in\s+england|company\s+(?:number|no\.?)\s*:?\s*\d"
    r"|registered\s+office|\brcs\s+\w+|\bsiren\b|\bkvk\b|kamer\s+van\s+koophandel|partita\s+iva|registro\s+mercantil"
    r"|registro\s+delle\s+imprese|\bkrs\b|\bnip\b|\bcvr\b|y-tunnus|registrikood|\bmersis\b", re.I)


def is_legal(url: str | None, text: str | None) -> bool:
    """A legal page by its address (any language's slug, the terms and the
    privacy pages too) or by its text (LEGAL_TEXT)."""
    if url and (rank(url, None) is not None or any(_strong(s, _segments(url)) for s in PRIVACY)):
        return True
    return bool(text and LEGAL_TEXT.search(text))


def legal_link(links, host: str, country: str | None = None, *, own=lambda url: True,
               weak: bool = True) -> str | None:
    """The homepage link that best names the legal notice (module doc), among
    the links `own` accepts (the caller's same-site check). `weak` False: a
    legal notice only, never a terms or privacy page (the Impressum reader has
    its /impressum fallback)."""
    langs = languages(country, host)
    ranked = [(r, len(u), u) for u in links or () if own(u) and (r := rank(u, langs)) is not None
              and (weak or r[0] < 2)]
    return min(ranked)[2] if ranked else None


# --- the officers ---------------------------------------------------------------------------------
# What a page calls a data-protection or information-security officer, folded
# (fold1). A short abbreviation only as a label ("DSB:"): DPD is a parcel
# service, ISB a bank. Never the controller ("Verantwortlicher", "responsabile
# del trattamento"): that is the company.
OFFICER = re.compile(
    r"datenschutz-?\s?beauftragte\w*|beauftragte[rn]?\s+fur\s+(?:den\s+)?datenschutz|datenschutz-?\s?koordinator\w*"
    r"|datenschutz-?\s?berater\w*|informations-?\s?sicherheits-?\s?beauftragte\w*"
    r"|(?:it|cyber)-?\s?sicherheits-?\s?beauftragte\w*|beauftragte[rn]?\s+fur\s+informationssicherheit"
    r"|sicherheits-?\s?beauftragte\w*"  # the TKG's, on a telephony provider's Impressum (2026-11-20)
    r"|data\s+(?:protection|privacy)\s+(?:officer|lead|manager)|\bdpo\b|(?:chief\s+)?privacy\s+officer"
    r"|(?:chief\s+)?information\s+security\s+(?:officer|manager)|head\s+of\s+information\s+security|\bciso\b"
    r"|(?:cyber\s+|it\s+)?security\s+officer"
    r"|\b(?:dsb|isb|dpd|rpd|epd|iod|rssi|szzp|dap|fg)\s*:"
    r"|delegue\w*\s+a\s+la\s+protection\s+des\s+donnees|correspondant\s+informatique\s+et\s+libertes"
    r"|responsable\s+de\s+la\s+securite\s+des\s+systemes\s+d.information"
    r"|delegad[oa]\s+de\s+(?:proteccion\s+de\s+datos|privacidad)|responsable\s+de\s+seguridad\s+de\s+la\s+informacion"
    r"|responsabile\s+(?:della\s+)?protezione\s+(?:dei\s+)?dati|responsabile\s+della\s+sicurezza\s+(?:informatica|delle\s+informazioni)"
    r"|encarregad[oa]\s+(?:de|da|pela)\s+protec?cao\s+(?:de\s+|dos\s+)?dados"
    r"|responsavel\s+(?:pela\s+)?seguranca\s+da\s+informacao"
    r"|functionaris\s+(?:voor\s+de\s+)?gegevensbescherming|informatiebeveilig\w+"
    r"|inspektor\w*\s+ochrony\s+danych|administrator\w*\s+bezpieczenstwa\s+informacji"
    r"|poverenec\w*\s+pro\s+ochranu\s+(?:osobnich\s+)?udaju|manazer\w*\s+(?:kyberneticke|informacni)\s+bezpecnosti"
    r"|zodpovedn\w+\s+osob\w*\s*(?::|\(|pre\s+ochran|za\s+ochran)|manazer\w*\s+kybernetickej\s+bezpecnosti"
    r"|adatvedelmi\s+(?:tisztviselo|felelos)\w*|informaciobiztonsagi\s+felelos\w*"
    r"|informatikai\s+biztonsagi\s+(?:felelos|vezeto)\w*"
    r"|responsabil\w*\s+cu\s+protectia\s+datelor|manager\w*\s+(?:de\s+)?securitate\w*\s+a?\s*informatii\w*"
    r"|длъжностно\s+лице\s+по\s+защита\s+на\s+данните|отговорник\s+по\s+(?:защита\s+на\s+данните|информационна\s+сигурност)"
    r"|υπευθυνοσ\s+προστασιασ\s+(?:προσωπικων\s+)?δεδομενων|υπευθυνοσ\s+ασφαλειασ\s+πληροφοριων"
    r"|sluzbenik\w*\s+za\s+zastitu\s+(?:osobnih\s+)?podataka|lice\s+za\s+zastitu\s+podataka"
    r"|лице\s+за\s+заштиту\s+података|pooblascen\w*\s+(?:oseb\w*\s+)?za\s+varstvo"
    r"|odgovorna\s+oseba\s+za\s+upravljanje\s+informacijske\s+varnosti"
    r"|databeskyttelsesradgiver\w*|informationssikkerheds(?:chef|ansvarlig)\w*"
    r"|dataskyddsombud\w*|informationssakerhets(?:chef|ansvarig)\w*"
    r"|personvernombud\w*|informasjonssikkerhetssjef\w*"
    r"|tietosuojavastaava\w*|tietoturva(?:paallikko|johtaja|vastaava)\w*"
    r"|andmekaitsespetsialist\w*|infoturbejuht\w*"
    r"|datu\s+aizsardzibas\s+(?:specialist|amatperson)\w*|informacijas\s+drosibas\s+vaditaj\w*"
    r"|duomenu\s+apsaugos\s+pareig\w*|informacijos\s+(?:saugumo|saugos)\s+vadov\w*"
    r"|veri\s+koruma\s+gorevlisi|veri\s+sorumlusu\s+(?:temsilcisi|irtibat\s+kisisi)|kvkk\s+sorumlusu"
    r"|bilgi\s+guvenligi\s+(?:yoneticisi|sorumlusu|muduru)|siber\s+guvenlik\s+yoneticisi"
    r"|personuverndarfulltru\w*|oryggisstjor\w*")
# Mailboxes for the officers: a local part holding one of these words (a bare
# security@ is the vulnerability contact, no officer: it stays).
_BOX_WORD = re.compile(r"datenschutz|privacy|dataprotection|data-protection|tietosuoja|dataskydd|personvern|adatvedel"
                       r"|andmekaitse|protecciondedatos|privacidad|privacidade"
                       r"|(?:^|[._+-])(?:dpo|dsb|ciso|isb|iod|rpd|dpd|epd|rssi|gdpr|dsgvo|rgpd)(?:$|[._+-]|\d)", re.I)
# Where an officer's block ends, read on the folded line (fold1): the
# register, a tax number (not a firm of "Steuerberater": an external officer's own), the company's own officers, the content's
# responsible, the authority, the site's credits, the next legal topic.
_SECTION = re.compile(
    r"regist|\bhr[ab]\b|\bust\b|ust-|\bvat\b|\btax\b|steuer(?!berat)|company\s+(?:number|no)|\brcs\b|\bsiren|\bkvk\b"
    r"|\bp\.?\s?iva\b|\bcif\b|\bnif\b|\bkrs\b|\bnip\b|\bcvr\b|org\.?\s?nr|y-tunnus|registrikood|mersis|\bico\b"
    r"|gesch(?:a|ae)ftsf|geschaftsleitung|vertreten|vertretungsberechtigt|vorstand|inhaber|prokur|director|managing"
    r"|\bceo\b|gerant|amministrator|administrador|bestuurder|zarzad|haftung|liability|copyright|impressum|imprint"
    r"|streitbeilegung|streitschlichtung|\bodr\b|cookie|verantwortlich|responsible|redaktion|aufsicht|supervisory"
    r"|kammer|berufs|gestaltung|konzeption|webdesign|hosting|bildnachweis|quellen|datenschutzbehorde"
    r"|data\s+protection\s+authority|γεμη|αφμ|еик|пиб")
# A heading: markdown, or a line in bold only.
_HEADING = re.compile(r"^\s*(?:#|\*\*[^*]+\*\*:?\s*$)")
# A line of the officer's contact: its label, or only an address or a number.
_CONTACT = re.compile(r"^\W*(?:(?:datenschutz|privacy|data[\s-]?protection)[\w-]*[\s-]*)?"
                      r"(?:tel\w*|phone|fon|fax|telefax|mobil\w*|e-?mail\w*|mail\w*|adresse|address|anschrift"
                      r"|web\w*|www|internet)\b", re.I)
_PHONE_OR_MAIL = re.compile(r"^[\s>*-]*(?:(?:(?:datenschutz|privacy|data[\s-]?protection)[\w-]*[\s-]*)?"
                            r"(?:tel\w*|phone|fon|fax|telefax|mobil\w*|e-?mail\w*|mail\w*)\b"
                            r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+[\s.]*$|\+?[\d\s()/.–-]{7,}$)", re.I)
_BLOCK_LINES = 10
_INVISIBLE = {"­": "-", "​": "-", "‌": "-", "‍": "-", "⁠": "-"}


def fold1(text: str) -> str:
    """fold() one character for one, so a match's positions are the text's:
    a soft hyphen or a zero-width space reads as "-" ("Datenschutz­beauftragter"),
    the Turkish dotted and dotless i as "i", the final sigma as "σ"."""
    out = []
    for c in text:
        c = _INVISIBLE.get(c, c)
        low = "i" if c in "İı" else "σ" if c == "ς" else c.lower()
        out.append((unicodedata.normalize("NFKD", low)[:1] or c) if len(low) == 1 else c)
    return "".join(out)


def _emails(text: str) -> list[tuple[int, int, str]]:
    """(start, end, address) of every address in `text`, found from its "@"
    (linear: no pattern scans a long run of letters from every start)."""
    out, i = [], text.find("@")
    while i >= 0:
        a = i
        while a > 0 and (text[a - 1].isalnum() or text[a - 1] in "._+-"):
            a -= 1
        b = i + 1
        while b < len(text) and (text[b].isalnum() or text[b] in "-."):
            b += 1
        addr = text[a:b].rstrip(".")
        if a < i and "." in addr[i - a + 1:]:
            out.append((a, a + len(addr), addr))
        i = text.find("@", max(b, i + 1))
    return out


def _line(text: str, pos: int) -> str:
    """The next line with text after `pos`."""
    return text[pos:].lstrip("\n \t").split("\n", 1)[0]


def _name_like(line: str) -> bool:
    """A short line that reads as a name: no digits, no label, no part of the page."""
    words = line.strip(" \t*#>").split()
    return (0 < len(words) <= 6 and not re.search(r"[\d:@]", line) and not _HEADING.match(line.replace("**", ""))
            and not _SECTION.search(fold1(line)))


def _address_like(line: str) -> bool:
    """A name or an address line set as its own paragraph: short, no heading,
    no sentence, no part of the page."""
    line = line.strip()
    return (bool(line) and len(line) <= 60 and not line.startswith(("#", "**")) and not line.endswith((".", ":"))
            and not _SECTION.search(fold1(line)))


def strip_officers(text):
    """`text` with every officer's block blanked (spaces, line breaks kept, so
    lines and positions stay). By the line the officer's word stands on:
    - a table row ("| … |"): the row;
    - a cell of a row ("A | B (DSB) | C"): the cell;
    - a heading (markdown, bold, the word alone, a line ending in ":"): the
      line and the block below it, past blank lines into the next name,
      address, phone or mail paragraphs; a name right above the word alone
      with a contact line below ("**Name**" / "DSB" / "mail") too;
    - "DSB: Name", the word starting the line, "Name, DSB", "Name (DSB)": from
      the name or the word to the line's end and the lines below it;
    - a sentence ("… our DSB at dsb@…"): from the word to the line's end and
      the phone and mail lines right below.
    Lines below stop at a blank line (unless a heading's block), at
    _BLOCK_LINES, and at a line that opens another part of the page (_SECTION,
    a heading after the first line). Then every officer mailbox. Anything not
    a string comes back as it is."""
    if not isinstance(text, str) or not text:
        return text
    low, chars = fold1(text), list(text)

    def blank(a: int, b: int) -> None:
        for i in range(a, b):
            if chars[i] != "\n":
                chars[i] = " "

    for m in OFFICER.finditer(low):
        ls = text.rfind("\n", 0, m.start()) + 1
        le = text.find("\n", m.end())
        le = len(text) if le < 0 else le
        line, before, after = text[ls:le], text[ls:m.start()], text[m.end():le]
        if line.lstrip().startswith("|"):
            blank(ls, le)
            continue
        bare = before.strip(" \t*#>-•")
        rest = re.sub(r"^[\s:.,;)*\-–]*", "", after)
        name_before = bool(bare) and (not rest or after.lstrip().startswith(")")) \
            and bool(re.search(r"[,(–-]\s*$", before))
        start = m.start()
        if name_before:
            cut = max(before.rfind(s) for s in "|;•:")
            start = ls + cut + 1 if cut >= 0 else ls
        cell = [i for i in (text.find(s, m.end(), le) for s in "|•") if i >= 0]
        if cell or any(s in before for s in "|•"):
            blank(start if not any(s in before for s in "|•") or name_before
                  else ls + max(before.rfind(s) for s in "|•") + 1, min(cell) if cell else le)
            continue
        alone = not bare and not rest
        heading = alone or _HEADING.match(line) is not None or line.rstrip().endswith(":")
        mode = "heading" if heading else "value" if (not bare or name_before or after.lstrip().startswith(":")) \
            else "sentence"
        if alone and not line.lstrip().startswith("#") and _PHONE_OR_MAIL.match(_line(text, le)):
            above_end = ls - 1
            above_start = text.rfind("\n", 0, max(above_end, 0)) + 1
            if above_end > 0 and _name_like(text[above_start:above_end]):
                start = above_start  # a card: "**Name**" / the word / the mail
        end, pos, taken = le, le, 0
        while pos < len(text) and taken < _BLOCK_LINES:
            nxt = text.find("\n", pos + 1)
            nxt = len(text) if nxt < 0 else nxt
            nl = text[pos + 1:nxt]
            if not nl.strip():
                if mode == "heading" and (not taken or _PHONE_OR_MAIL.match(_line(text, nxt))
                                          or _address_like(_line(text, nxt))):
                    pos = nxt
                    continue
                break
            if mode == "sentence" and not _PHONE_OR_MAIL.match(nl):
                break
            if (_SECTION.search(fold1(nl)) and not _CONTACT.match(nl)) or (taken and _HEADING.match(nl)):
                break
            end, pos, taken = nxt, nxt, taken + 1
        blank(start, end)
    for a, b, addr in _emails("".join(chars)):
        if _BOX_WORD.search(addr.split("@")[0]):
            blank(a, b)
    return "".join(chars)


def _officer_link(url, gone: set) -> bool:
    if not isinstance(url, str) or not url.lower().startswith("mailto:"):
        return False
    addr = unquote(url[7:].split("?")[0]).strip().lower()
    return addr in gone or bool(_BOX_WORD.search(addr.split("@")[0]))


def redact(page: dict) -> bool:
    """A fetched page ({text, links, …}) with its officers blanked, in place:
    the text (strip_officers) and every mailto: link to an address the text no
    longer shows or to an officer mailbox. True when anything changed."""
    text, links = page.get("text"), page.get("links")
    clean = strip_officers(text)
    changed = clean != text
    if isinstance(text, str):
        page["text"] = clean
        gone = {a.lower() for _, _, a in _emails(text)} - {a.lower() for _, _, a in _emails(clean)}
    else:
        gone = set()
    if isinstance(links, list):
        kept = [u for u in links if not _officer_link(u, gone)]
        changed = changed or len(kept) != len(links)
        page["links"] = kept
    return changed


# --- fetching (this copy only) ---------------------------------------------------------------------
FETCH_URL = "https://api.fetch.tinyfish.ai"  # docs.tinyfish.ai/fetch-api/reference: up to 10 URLs a request


def _fetch(urls: list[str], links: bool = False) -> list[dict]:
    """TinyFish fetch → results [{url, final_url, text, links}], every legal
    page redacted before anyone sees it."""
    import json
    import os
    import urllib.request

    body = json.dumps({"urls": urls, "format": "markdown", "links": links}).encode()
    req = urllib.request.Request(FETCH_URL, data=body, method="POST", headers={
        "X-API-Key": os.environ["TINYFISH_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=150) as r:
        results = json.load(r).get("results") or []
    for page in results:
        if is_legal(page.get("url"), page.get("text")):
            redact(page)
            page["text"] = strip_fax(page.get("text"))
    return results


# A fax number after its label, in any spelling ("Fax:", "Telefax", "Fax-Nr."), also in a table ("| Fax: | …"). This copy only: the Sales Agent's
# list-enricher reads the fax off the page to mark it, but no demo or skill needs one (Paul, 2026-11-16).
_FAX = re.compile(r"\b(?:tele)?fax\b[\s.:|-]*(?:(?:nr|nummer|number|no)\b[\s.:|]*)?(\+?[\d\s()/.–-]*\d)", re.I)


def strip_fax(text):
    """`text` with every fax number blanked (spaces, so lines and positions stay); the label stays."""
    if not isinstance(text, str):
        return text
    return _FAX.sub(lambda m: m.group()[:m.start(1) - m.start()] + " " * len(m.group(1)), text)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def fetch_legal(domain: str, country: str | None = None) -> dict | None:
    """{"url", "text"} of the company's legal page, officers blanked, or None:
    the homepage's best legal link (legal_link, the site's own host only), else
    /impressum, then /impressum.html, for a German-speaking country. A fallback
    that lands back on the homepage is no legal page (a cached homepage of an
    older site build can lack the link: karrierehafen.de, 2026-11-18). The text
    is redacted even when is_legal does not know the page."""
    host = _host(f"https://{domain.strip().removeprefix('https://').removeprefix('http://')}")
    home = _fetch([f"https://{host}"], links=True)
    if not home:
        return None
    site = _host(home[0].get("final_url") or "") or host
    link = legal_link(home[0].get("links"), site, country,
                      own=lambda u: _host(u) == site or _host(u).endswith("." + site))
    tries = [link] if link else ([f"https://{site}/impressum", f"https://{site}/impressum.html"]
                                 if "de" in languages(country, host)[:1] else [])
    for url in tries:
        page = (_fetch([url]) or [None])[0]
        if not page or not (page.get("text") or "").strip():
            continue
        if not link and urlparse(page.get("final_url") or url).path.strip("/") == "":
            continue  # the fallback redirected to the homepage
        redact(page)
        return {"url": page.get("final_url") or url, "text": strip_fax(page["text"])}
    return None


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        sys.exit("usage: legal_pages.py <domain> [<country ISO code>]")
    print(json.dumps(fetch_legal(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), ensure_ascii=False))
