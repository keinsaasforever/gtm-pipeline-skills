---
name: deal-review
description: Review one deal or a whole pipeline for risk. Computes momentum (engagement, progression, recency), labels each deal healthy, moderate or slipping with source-backed reasons (missing stakeholders, unresolved objections, slipping close dates, weak next steps, one-sided threads, meeting cadence, competitor mentions) and gives one concrete action per deal. Can create proposed CRM tasks. Also triggers on "review my pipeline", "which deals are at risk", "deal health for ACME", "forecast check", "what's slipping".
---

# Deal Review

Health check for deals, with evidence for every flag and one next action each.

**Read `references/revenue.md` (in this skill's folder; the canonical copy is `shared/revenue.md` in the plugin) before executing.**

---

## Scope

- **One deal:** the named deal.
- **Pipeline:** the user's open deals, optionally filtered by stage, owner, close quarter or amount. Cap 25 deals per run; more → take the nearest close dates first and say what was left out.

## Step 1: Gather per deal (read only)

- **CRM:** stage and the date it entered the stage, amount, close date and its change history (how often it slipped), next step plus its date, qualification fields, contacts on the deal with roles, activities in the last 60 days.
- **Mail:** for each thread with the deal's domains, the inbound/outbound counts and the last reply date for each direction.
- **Transcripts:** the last 3 calls via `call-transcripts`, or the `post-call` notes if present (cheaper). Look for objections, competitors, commitments, and stakeholders named but absent.

## Step 2: Score momentum (0 to 100)

| Component | Weight | Measure |
|---|---|---|
| Engagement | 40 | Two-way touches in the last 14 days (calls, buyer replies); inbound/outbound ratio; number of distinct buyer people engaged |
| Progression | 35 | Days in the current stage vs. the user's median for that stage; close-date slips; exit criteria met for the next stage |
| Recency | 25 | Days since the last buyer-initiated touch vs. `quiet_after_days` |

- **Labels:** ≥ 70 healthy · 40 to 69 moderate · < 40 slipping.
- Show the score's main driver in words. The number alone is not the output.
- With fewer than 2 activities in 60 days, the label is "not enough data", not "slipping".

## Step 3: Risk flags (each with evidence)

- **Missing stakeholders:** the method's roles not covered (economic buyer, champion, decision maker). Stakeholders named in calls but never met.
- **Unresolved objections:** raised in a call or mail and not answered since.
- **Close date risk:** slipped twice or more; or closing in 30 days or less while the stage is two or more steps from closing.
- **Weak next step:** empty, no date, date in the past, or no owner on the buyer side.
- **One-sided:** three or more of our touches without a buyer reply.
- **Cadence drop:** the meeting interval has more than doubled compared with the deal's own average.
- **Competition:** a competitor named in the last 30 days.
- **Single-threaded:** one buyer contact only, at a stage past discovery.

## Step 4: One action per deal

Choose the action with the highest expected effect:
- add a stakeholder: who, and a suggested intro ask to the champion;
- answer the objection: playbook answer and asset;
- re-confirm the timeline: question to ask;
- a nudge: hand over to `daily-plan` or a follow-up draft;
- or "qualify out": suggest it when momentum stays under 25 for 30 days and the buyer hasn't replied twice.

If the Sales Agent connector is present, `find_stakeholders(domain, roles)` can suggest people for a missing role. Their emails stay out of the chat, so show names and titles only. `research_account(domain)` can check for new signals that justify reopening a quiet deal. Both use credits; ask first.

## Step 5: Output

```
# Pipeline review — {date} — {n} deals — {healthy}/{moderate}/{slipping}

| Deal | Stage | Amount | Close | Momentum | Main risk | Action |
|---|---|---|---|---|---|---|
| ACME | Proposal | 24k | 31 Oct | 38 slipping | no economic buyer; 2 slips | ask champion for intro to CFO this week |

## Details (slipping and moderate deals)
### ACME — 38 (engagement 12/40, progression 14/35, recency 12/25)
- No economic buyer: MEDDPICC "E" unknown; CFO named in call 14 Oct [22:10] but never met
- Close date moved twice (30 Sep → 15 Oct → 31 Oct)
→ Action: …
```

## Optional writes

- Offer to create one CRM task per action (`propose` unless the playbook allows `auto` for tasks), dated today or tomorrow.
- Never change stage, amount or close date from this skill. It reviews; `post-call` updates.

End with the Run Summary from `revenue.md` §8.
