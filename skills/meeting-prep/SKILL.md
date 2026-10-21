---
name: meeting-prep
description: Prepare a one-page brief for an upcoming sales meeting. Pulls the meeting from the calendar, then the matching deal and contacts from the CRM, recent emails, past call transcripts, account news and buying signals, and gaps against the qualification method. Also sends a notetaker if the user wants the call recorded. Also triggers on "prep my next call", "brief me for my 2pm", "what should I know before meeting X", "prepare for the call with ACME".
---

# Meeting Prep

A one-page brief before a sales meeting: who, where the deal stands, what was promised, what changed, what to ask.

**Read `references/revenue.md` (in this skill's folder; the canonical copy is `shared/revenue.md` in the plugin) before executing.**

---

## Step 1: Pick the meeting

- **Named meeting:** find it in the calendar by title, company or time.
- **"Next call" or nothing named:** take the next meeting today with at least one **external** attendee (email domain ≠ the user's).
- **Routine run:** every external meeting starting in the next 4 hours that has no brief yet. Use the run-once marker `meeting-prep:{calendar_event_id}`.

Get the title, time, link, attendees with emails, the description and attachments.

## Step 2: Match the deal

Follow `revenue.md` §3. If there is no deal (a first meeting), the brief is account research plus attendees, with no deal section.

## Step 3: Gather (read only, in parallel where the host allows)

| Source | What to take | Limit |
|---|---|---|
| CRM | Deal stage, amount, close date, qualification fields with last-modified dates, open tasks, last 5 notes, contacts on the deal with roles | 1 deal + its contacts |
| Mail | Threads with attendee domains: open questions, promised material, objections | Last 10 threads, 90 days |
| Transcripts | Via `call-transcripts`: commitments (both sides), objections, pains, competitors, decision process | Last 3 calls with this account |
| Web | Company news since the last touch (funding, hires, leadership change, launches, layoffs); for attendees, only role and tenure | 5 items, each with link and date |
| Sales Agent connector | `research_account(domain)` if available: signals with scores and fit. Say before calling it that it uses credits, unless the playbook pre-approves it. | 1 call |
| Docs | Playbook assets (battlecard, case study) relevant to the industry or competitor mentioned | Links only |

## Step 4: Find the gaps

Compare the qualification fields with the playbook's method and with the **exit criteria of the next stage**. List what's missing, each with how to close it in this meeting. Example: "No economic buyer → ask who signs off on budgets over €20k."

Also flag:
- commitments **we** made that are overdue;
- the buyer's open questions with no answer yet;
- a close date earlier than the stage makes plausible.

## Step 5: Write the brief

```
# {Company} — {meeting title} — {day, time}
Goal for this meeting: {one sentence, from stage + gaps}

## Who
- {Name}, {title} — {role in deal: champion/EB/user/unknown}; last spoke {date}; cares about {…} ({source})

## Where it stands
Stage {stage} since {date} · {amount} · close {date} ({confirmed|inferred})
{2–3 sentences: what happened since the last call}

## Open commitments
- Ours: {…} — due {date} — {status}
- Theirs: {…}

## What changed
- {news/signal} — {date} — {link}

## Gaps → questions to ask
1. {question} (closes: {field/criterion})
…(3–5)

## Watch out
- {objection/competitor/risk with source}

Sources: {list}
```

Keep it to one screen. Unknowns are written as "unknown", never guessed.

## Step 6: Offer to record

If the playbook's transcript source is `vexa`, or the user has no transcript source, and the meeting has a Meet, Teams or Zoom link: offer to send the notetaker via `call-transcripts`. Follow its Consent rules. In a routine, schedule the bot only if the playbook has `consent_confirmed: true`.

## Delivery

- **Interactive:** the brief in the reply.
- **Routine:** to the playbook's `digest.destination` (team-chat DM or a mail draft to self). Mark the run-once item done.
- Never send the brief to external attendees.

End with the Run Summary from `revenue.md` §8.
