"""Check csv/intermediate/messages.json against the message rules before building anything.
python3 check_messages.py   (from {client-slug}-gtm/) — prints CLEAN or the list of problems."""
import re
from collections import Counter
from common import contacts, deck_config, has_address, messages

cfg, msgs, errs, hooks = deck_config(), messages(), [], []
INFORMAL = re.compile(r"\b(du|dich|dir|dein\w*|euch|euer\w*)\b", re.I)
FORMAL = re.compile(r"(?<=[a-zäöüß,] )(Sie|Ihnen|Ihre?[mnrs]?)\b")  # mid-sentence only: a capital at sentence start can be "they"
BANNED = re.compile(r"linkedin|phantom|fullenrich|pipe0|bettercontact|kitt|firecrawl|gefunden|revolution|gamechanger", re.I)
for c in contacts():
    key, who = c["linkedin_profile_url"], c["company_name"]
    m = msgs.get(key)
    if not m:
        errs.append(f"{who}: no message"); continue
    lang, reg = m["lang"].lower(), m.get("register", "")
    text = " ".join(str(v) for k, v in m.items() if k not in ("why_they_fit", "job_title"))
    names = {c["last_name"].strip(), c["first_name"].strip()}
    for k in ("li_p1", "email_p1"):
        if m.get(k):
            first = m[k].split("\n", 1)[0]
            if not first.endswith(",") or not any(n and n in first for n in names): errs.append(f"{who}: {k} greeting '{first}'")
    if re.search("[–—]", text): errs.append(f"{who}: dash")
    if "!" in text: errs.append(f"{who}: exclamation")
    if BANNED.search(text): errs.append(f"{who}: banned word {BANNED.search(text).group()}")
    if lang == "de" and reg == "sie" and INFORMAL.search(text): errs.append(f"{who}: informal '{INFORMAL.search(text).group()}' in a Sie draft")
    if lang == "de" and reg == "du" and FORMAL.search(text): errs.append(f"{who}: formal '{FORMAL.search(text).group()}' in a Du draft")
    li = len(m["li_p1"]) + 1 + len(m["li_p2"])
    if li > 400: errs.append(f"{who}: LinkedIn {li} > 400")
    if (m["cta_variant"] == "A") != m["li_p2"].rstrip().endswith("?"): errs.append(f"{who}: LinkedIn CTA form != {m['cta_variant']}")
    li_hook = m["li_p1"].split("\n", 1)[-1]
    hooks.append(("li", li_hook))
    if has_address(c):
        if not all(m.get(k) for k in ("email_subject", "email_p1", "email_p2", "email_p3")): errs.append(f"{who}: email draft missing"); continue
        signoff = cfg["signoff"][lang]
        if not m["email_p3"].endswith("\n" + signoff): errs.append(f"{who}: sign-off != {signoff!r}")
        if len(m["email_subject"]) > 60: errs.append(f"{who}: subject > 60")
        hook, cta = m["email_p1"].split("\n", 1)[-1], m["email_p3"][: -len("\n" + signoff)]
        body = len(hook) + 1 + len(m["email_p2"]) + 1 + len(cta)
        if not 320 <= body <= 450: errs.append(f"{who}: email body {body} not in 320-450")
        if li >= len(m["email_p1"]) + len(m["email_p2"]) + len(m["email_p3"]): errs.append(f"{who}: LinkedIn not shorter than email")
        if hook.strip() == li_hook.strip(): errs.append(f"{who}: LinkedIn hook copies the email hook")
        if (m["cta_variant"] == "A") != cta.rstrip().endswith("?"): errs.append(f"{who}: email CTA form != {m['cta_variant']}")
        hooks.append(("email", hook))
    elif m.get("email_subject") or m.get("email_p1"):
        errs.append(f"{who}: email draft on a card without a kept address")
for ch in ("email", "li"):
    for p, n in Counter(" ".join(h.split()[:3]) for c_, h in hooks if c_ == ch).items():
        if n > 2: errs.append(f"{ch} opening '{p}' used {n}x")
print("CLEAN" if not errs else "ERRORS:\n  " + "\n  ".join(errs))
