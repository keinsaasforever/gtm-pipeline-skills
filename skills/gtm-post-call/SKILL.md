---
name: gtm-pipeline:post-call
description: After a sales call, extract what was agreed and learned from the transcript, update the CRM under the playbook's write rules (auto fields written, the rest proposed), create next-step tasks, draft the follow-up email as a draft in the user's mail, and post a change log. Works on transcripts from any notetaker, Meet, Teams or Zoom, Vexa, or pasted notes. Runs on demand or as an hourly sweep. Also triggers on "process my last call", "update the CRM from the call with X", "write the follow-up", "what did we agree with ACME".
---

# Post-Call

Turn a finished call into CRM updates, tasks and a follow-up draft, with evidence for every change.

**Read `~/.claude/skills/gtm-pipeline/_shared/revenue.md` before executing.**

---

## Step 1: Pick the call(s)

- **Named call:** get it via `call-transcripts`.
- **"My last call":** the most recent external meeting that has ended and has a transcript.
- **Sweep (routine):** all external meetings that ended in the last 24 h. Skip each one already processed (run-once, `revenue.md` §6, marker `post-call:{source}:{external_id}`). Skip calls whose transcript isn't available yet; the next sweep picks them up.

Claim each item before working on it, so parallel runs don't double up.

## Step 2: Match the deal

Follow `revenue.md` §3.
- If the match is ambiguous, an interactive run asks; a routine run puts the call in the digest as "needs a deal" and writes nothing.
- If there is no deal and `create_rules.deals` is not `auto`, propose one, don't create it.

## Step 3: Extract

Read the transcript once and extract into this structure. Each item carries `confirmed | inferred`, the speaker, a timestamp and a quote of 25 words or fewer.

- **Playbook fields:** every `fields[]` entry, judged against its `standard`. If the standard isn't met, the value is "unknown", even if something related was said.
- **Next steps:** action, owner (us or them, by name), due date.
- **Commitments** both sides made, including material we promised to send.
- **Pains, objections and competitors** mentioned, plus questions we could not answer.
- **Stakeholders** named but not present: name, role, and their part in the decision.
- **Stage:** does the deal now meet the exit criteria of the next stage? Which criteria are met and which are missing?

Unknown speaker segments (`call-transcripts`) are never attributed to the buyer. A commitment from an unknown speaker is `inferred`.

## Step 4: CRM changes

Build the change table first:

| Record | Field | Current (last changed) | Proposed | Evidence | Mode | Action |
|---|---|---|---|---|---|---|
| Deal ACME | Next step | "Send pricing" (2026-10-02) | "Security review with IT, Thu 23 Oct" | [14:02] J. Doe: "…" | auto | write |
| Deal ACME | Close date | 2026-12-31 | 2027-01-31 | [31:40] "realistically January" | propose | ask |

Apply the rules from `revenue.md` §5:
- `auto` and `overwrite` fields: write if the rules hold.
- `propose`: interactive runs ask for approval as one batch (the user may approve some and reject others); routine runs put them in the digest.
- Stage moves: only when the stage is in `auto_advance`, every required field holds confirmed evidence, and the stage is not locked. Otherwise propose.
- **Tasks:** one CRM task per next step owned by us, with its due date. Check for an existing open task with the same intent first.
- **New contacts** for external attendees not in the CRM, per `create_rules.contacts`. Use name, title and email from the calendar invite only; no enrichment.
- **Call note** on the deal: a summary of 5 to 8 bullets with key quotes, ending with the run-once marker `[post-call:{source}:{external_id}]`. Never paste the full transcript.

At most 25 writes. If more are needed, stop and list the rest.

## Step 5: Follow-up draft

Write the email the rep would send today:
- **To:** the external attendees. Cc stays empty unless the buyer asked to include someone.
- **Language and address** from the call language and the playbook (`writing.language_default`, `address`).
- **Structure:** thanks plus one specific reference to the conversation; recap of agreed next steps with owners and dates; the material we promised (link from the playbook assets or Docs; if not found, write `[ATTACH: …]`); one clear next step with the calendar link if one is set.
- **Follow** the `writing.rules` and `writing.style`. No new claims beyond the playbook's approved claims and what was said in the call.
- **Save it as a draft** in the user's mail, as a reply in the existing thread with the attendees if one exists. **Never send.**
- **No mail connector:** put the draft in the reply.

## Step 6: Change log and digest

- **Change log** (what was written): goes to `change_log.destination`. Format: `{Deal} — {field}: {old} → {new} ({evidence time})`, one line each, plus a link to the draft.
- **Digest** (routine runs): proposals awaiting approval, calls with no deal match, calls without transcripts yet. Goes to `digest.destination`.
- **Ledger:** mark each item done with a one-line result.

End with the Run Summary from `revenue.md` §8.

---

## Quality checks before writing anything

- Is the deal right? Attendee domain matches the deal's company.
- Is every confirmed value backed by a buyer quote, not our rep's statement? A rep saying "so you're looking at January?" is not a confirmation; the buyer's "yes, January" is.
- Is any proposed value older than the CRM's current value? Then drop it.
- Does the draft promise anything not agreed in the call?
