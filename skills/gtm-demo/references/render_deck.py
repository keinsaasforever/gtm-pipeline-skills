"""Render the keinsaas demo deck from ../deck_template.html + context/deck.json + csv/intermediate/deck_data.json
+ csv/output/contacts_enriched.csv (embedded for the download button). python3 render_deck.py <out.html>"""
import html, json, os, re, sys
from common import deck_config

TPL = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "deck_template.html"), encoding="utf-8").read()
cfg, data = deck_config(), json.load(open("csv/intermediate/deck_data.json", encoding="utf-8"))
csv_text = open("csv/output/contacts_enriched.csv", encoding="utf-8", newline="").read()
LABELS = {
    "de": dict(signal="Kaufsignal", fit="Warum es passt", contact="Entscheider", subject="Betreff", draft="Nachrichtenentwurf",
               verified="verifiziert", likely="wahrscheinlich gültig", on_request="E-Mail auf Anfrage",
               cta_a="CTA A · Frage", cta_b="CTA B · Angebot", sig_first="Signal zuerst", icp="ICP-Fit", segment="Segment",
               meta="{n} Unternehmen · {s} mit aktuellem Kaufsignal · {m} mit E-Mail", tag_sig="Signal",
               stat1="Entscheider", stat2="mit aktuellem Kaufsignal", stat3="geprüfte E-Mail-Adressen",
               download="CSV herunterladen", expand="Alle aufklappen", collapse="Alle zuklappen",
               months=["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]),
    "en": dict(signal="Buying signal", fit="Why they fit", contact="Decision-maker", subject="Subject", draft="Draft message",
               verified="verified", likely="likely valid", on_request="Email on request",
               cta_a="CTA A · Question", cta_b="CTA B · Offer", sig_first="Signal first", icp="ICP fit", segment="Segment",
               meta="{n} companies · {s} with a fresh buying signal · {m} with email", tag_sig="Signal",
               stat1="decision-makers", stat2="with a fresh buying signal", stat3="checked email addresses",
               download="Download CSV", expand="Expand all", collapse="Collapse all",
               months=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]),
}
L = LABELS[cfg["lang"]]
BADGE = {"valid": ("est-ok", L["verified"]), "valid-risky": ("est-ok", L["likely"])}
e = lambda s: html.escape(str(s or ""), quote=True)
para = lambda s: e(s).replace("\n", "<br>")


def fmt_date(d):
    y, m, dd = map(int, d[:10].split("-"))
    return f"{dd}. {L['months'][m - 1]} {y}" if cfg["lang"] == "de" else f"{L['months'][m - 1]} {dd}, {y}"


def card(r):
    sig = r["group"] == "signal"
    tag = f'<span class="tag tag-sig">{L["tag_sig"]}</span>' if sig else f'<span class="tag tag-icp">{L["icp"]}</span>'
    if sig:
        box = (f'<div class="signal sig-hot"><div class="siglabel">{L["signal"]}</div><div class="sigtext">{e(r["signal_text"])}</div>'
               f'<a class="sigsrc" href="{e(r["signal_source_url"])}" target="_blank" rel="noopener">&#8599; {e(r["signal_source_label"])} · {fmt_date(r["signal_date"])}</a></div>')
    else:
        box = f'<div class="signal sig-fit"><div class="siglabel">{L["fit"]}</div><div class="sigtext">{e(r["why_they_fit"])}</div></div>'
    if r["email"]:
        cls, label = BADGE[r["email_status"]]  # KeyError = a build bug: an unchecked address reached the deck
        mail = f'<span class="cmail">{e(r["email"])}</span> <span class="est {cls}">{label}</span>'
    else:
        mail = f'<span class="est est-warn">{L["on_request"]}</span>'
    contact = (f'<div class="contact"><div class="clabel">{L["contact"]}</div><div class="cname"><strong>{e(r["full_name"])}</strong>'
               f'<span class="ctitle"> · {e(r["job_title"])}</span></div><div class="clinks"><a href="{e(r["linkedin_url"])}" target="_blank" rel="noopener">LinkedIn</a> · {mail}</div></div>')
    email_block = ""
    if r["email"]:
        email_block = (f'<div class="msg-sub"><span class="ml">{L["subject"]}</span> {e(r["email_subject"])}</div><div class="msg-body">'
                       + "".join(f'<p class="mp">{para(r[k])}</p>' for k in ("email_p1", "email_p2", "email_p3") if r.get(k)) + "</div>")
    li_cls = "msg-sub li" if email_block else "msg-sub"
    li_block = (f'<div class="{li_cls}"><span class="ml">LinkedIn</span></div><div class="msg-body">'
                + "".join(f'<p class="mp">{para(r[k])}</p>' for k in ("li_p1", "li_p2") if r.get(k)) + "</div>")
    cta = L["cta_a"] if r["cta_variant"] == "A" else L["cta_b"]
    return (f'<details class="lead"><summary class="lead-top"><img class="fav" src="https://www.google.com/s2/favicons?domain={e(r["company_domain"])}&sz=64" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
            f'<div class="lead-id"><div class="lead-name">{e(r["company_name"])}</div><a class="lead-domain" href="https://{e(r["company_domain"])}" target="_blank" rel="noopener">{e(r["company_domain"])}</a></div>'
            f'<div class="lead-tags">{tag}<span class="tag">{e(r["location"])}</span><span class="tag tag-lang">{e(r["lang"])}</span></div><span class="chev" aria-hidden="true">&#9662;</span></summary>'
            f'<div class="lead-body">{box}{contact}<div class="msg"><div class="msglabel">{L["draft"]} <span class="cta-chip">{cta}</span></div>{email_block}{li_block}</div></div></details>')


sections = []
for n, seg in enumerate([s for s in cfg["segments"] if any(r["segment"] == s["key"] for r in data)], 1):
    rows = [r for r in data if r["segment"] == seg["key"]]
    sig = sorted([r for r in rows if r["group"] == "signal"], key=lambda r: r["signal_date"], reverse=True)
    icp = [r for r in rows if r["group"] != "signal"]
    meta = L["meta"].format(n=len(rows), s=len(sig), m=sum(bool(r["email"]) for r in rows))
    body = [f'<section class="seg"><div class="seg-head"><div class="seg-kicker">{L["segment"]} {n}</div><h2>{e(seg["title"])}</h2><p>{e(seg["intro"])}</p><div class="seg-meta">{meta}</div></div>']
    if sig:
        body.append(f'<div class="approach sig"><h3>{L["sig_first"]}</h3><p>{e(cfg["approach_signal"])}</p></div>')
        body += [card(r) for r in sig]
    if icp:
        body.append(f'<div class="approach icp"><h3>{L["icp"]}</h3><p>{e(cfg["approach_icp"])}</p></div>')
        body += [card(r) for r in icp]
    body.append("</section>")
    sections.append("\n".join(body))

start = TPL.index("  <!-- ============================================================\n       SEGMENT")
end = TPL.index('  <p class="note">')
page = TPL[:start] + "\n".join(sections) + "\n\n" + TPL[end:]
tokens = {
    "LANG": cfg["lang"], "CLIENT_NAME": cfg["client_name"], "HERO_HEADLINE": cfg["hero_headline"], "HERO_INTRO": cfg["hero_intro"],
    "STAT1_N": str(len(data)), "STAT1_LABEL": L["stat1"],
    "STAT2_N": str(sum(r["group"] == "signal" for r in data)), "STAT2_LABEL": L["stat2"],
    "STAT3_N": str(sum(bool(r["email"]) for r in data)), "STAT3_LABEL": L["stat3"],
    "STAT4_N": cfg["stat4"]["n"], "STAT4_LABEL": cfg["stat4"]["label"],
    "LBL_DOWNLOAD": L["download"], "LBL_EXPAND": L["expand"], "LBL_COLLAPSE": L["collapse"],
    "METHOD_NOTE": cfg["method_note"], "FOOTER_HEADLINE": cfg["footer_headline"], "FOOTER_BODY": cfg["footer_body"],
    "CTA_LABEL": cfg["cta_label"], "FOOTER_META": cfg["footer_meta"], "CSV_FILENAME": f'{cfg["client_slug"]}_prospects.csv',
    "CALENDAR_URL": "https://calendar.google.com/calendar/appointments/schedules/AcZssZ3kHmy2kw6fePg6tqmkoaFnj8AKGN2Baq3rRyfo4ItozAv2BfXF3Gh2-oMjYDxWIc7P_hEfMZTi",
}
page = re.sub(r"<!--.*?-->\n?", "", page, flags=re.S)  # template authoring notes stay out of the deliverable
page = page.replace('"{{CSV_DATA}}"', json.dumps(csv_text, ensure_ascii=False).replace("</", "<\\/"))
for k, v in tokens.items():
    page = page.replace("{{" + k + "}}", v if k == "CALENDAR_URL" else e(v))
open(sys.argv[1], "w", encoding="utf-8").write(page)
print(f"wrote {sys.argv[1]}: {len(data)} cards; unfilled tokens: {sorted(set(re.findall(r'{{[A-Z0-9_]+}}', page)))}")
