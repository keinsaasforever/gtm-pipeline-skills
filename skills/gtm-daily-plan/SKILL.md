---
name: gtm-pipeline:daily-plan
description: The rep's morning plan in one message. Today's external meetings with a 3-line prep each, overdue commitments from CRM tasks and from call transcripts, deals going quiet or without a next step, calls still waiting for a follow-up, all ranked into the 5 to 10 actions that matter today. Runs on demand or as a weekday-morning routine. Also triggers on "what should I do today", "plan my day", "morning briefing", "which deals need attention".
---

# Daily Plan

A ranked to-do list for today, built from the calendar, the CRM, the inbox and recent calls.

**Read `~/.claude/skills/gtm-pipeline/_shared/revenue.md` before executing.**

---

## Step 1: Collect (read only)

| Source | What |
|---|---|
| Calendar | Today's meetings with an external attendee: time, company, link |
| CRM | Open deals owned by the user: stage, amount, close date, next step plus its date, last activity date. Open tasks due today or overdue. |
| Mail | Unanswered inbound mails from deal contacts (last 7 days). Our sent mails with no reply in more than 5 days. |
| Transcripts | Commitments we made in calls in the last 14 days (via `post-call` notes on deals, or `call-transcripts` if no notes exist) that have no matching task or sent mail |
| Ledger / CRM notes | Calls from the last 48 h without a `post-call` marker (follow-up not done) |

Cap: the user's own deals only, at most 50 open deals. With more, take the 50 with the nearest close date and say so.

## Step 2: Score each candidate action

| Signal | Points |
|---|---|
| Meeting today | 100 (always listed, ordered by time) |
| Inbound mail from a buyer unanswered for more than 24 h | 80 |
| Overdue commitment we made | 70 + 5 per day overdue |
| Call in the last 48 h without a follow-up | 65 |
| Deal past its close date, or closing in 14 days or less with no next step | 60 |
| Quiet deal (no two-way touch for `quiet_after_days` or longer) | 40 + amount weight |
| Task due today | 30 |

Amount weight: 0 to 20, relative to the user's median open deal. Merge actions on the same deal into one line.

## Step 3: Write the plan

```
# {Weekday, date} — {n} meetings, {n} actions

## Meetings
- 10:00 ACME — Discovery #2 — goal: identify the economic buyer · gap: no budget owner · [prep]
…

## Do today (ranked)
1. Reply to Jane Doe (ACME) — asked for the security whitepaper on Mon — [thread]
2. Send the pricing we promised Globex on 14 Oct (3 days overdue) — [draft?]
3. Follow up on the call with Initech yesterday — no follow-up yet → run post-call
…(max 10)

## Going quiet
- Umbrella Corp — 12 days no reply — last: proposal sent 9 Oct → suggested nudge: {1 line}

Sources: calendar, CRM ({n} deals), mail ({n} threads), calls ({n})
```

- `[prep]` means run `meeting-prep` for that meeting (a routine does it automatically for meetings in the next 4 h).
- Offer to create drafts for the top follow-ups. Create them only on a yes, or if the routine is configured to (drafts only, never sent).

## Delivery

- **Interactive:** in the reply.
- **Routine:** to `digest.destination`.
- **Run once per day:** marker `daily-plan:{date}`.

End with the Run Summary from `revenue.md` §8.
