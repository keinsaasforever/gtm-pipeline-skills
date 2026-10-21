---
name: revenue-setup
description: Set up the sales playbook that the revenue-intelligence skills use. Covers deal stages with exit criteria, CRM field standards and write modes (auto, propose, never), the qualification method, follow-up writing rules, where call transcripts are stored, and where change logs go. Reads the user's CRM to propose the mapping. Run once per team; re-run to change rules. Also triggers on "set up my playbook", "configure CRM updates", "which fields can you update", "set up meeting prep", "set up revenue intelligence".
---

# Revenue Setup

Build the **playbook**: the rules `meeting-prep`, `post-call`, `daily-plan`, `deal-review` and `live-assist` follow. It takes about 10 minutes. Draft from what you can read, then ask only what you can't infer.

**Read `references/revenue.md` (in this skill's folder; the canonical copy is `shared/revenue.md` in the plugin) before executing.**

---

## Step 1: Load what exists

- An existing playbook: Sales Agent `get_playbook`, or `context/playbook.md`. If found, show a summary and ask what to change. Edit only that.
- `context/profile.md`, `context/icp.md` and `context/personas/*.md` from `gtm-setup`, if present. Reuse offering, tone and personas; don't ask again.

## Step 2: Read the CRM (connector required for this step)

From the user's CRM, read:
1. **Pipelines and stages**: names, order, probability if set.
2. **Deal properties**: name, internal name, type and options for single/multi-select. Note custom properties that look like qualification fields (champion, economic buyer, pain, competitor, budget, MEDDPICC, BANT, next step).
3. **Activity types** in use: notes, tasks, meetings, emails.
4. **Ten recent closed deals** (won and lost), only to see which fields are actually filled. Don't copy their contents into the playbook.

If no CRM is connected, ask for the stage names and the 5 to 10 fields that matter, or skip CRM writing entirely (everything becomes `propose` in the reply).

## Step 3: Draft, then ask

Draft the playbook from Step 2. Mark everything you inferred `[INFERRED]`. Then ask these, one message, numbered:

1. **Stages:** "For each stage, what has to be true to move a deal *into* it?" Offer your drafted exit criteria, e.g. "Demo → a pain was identified and confirmed by the buyer".
2. **Automation:** "Which stages may I advance on my own when the criteria are met, and which are locked?" Default: none auto, Closed Won and Closed Lost locked.
3. **Fields:** for each mapped field, the plain-language standard plus a write mode. Show it as a table:

   | Field (CRM property) | Standard | Write mode |
   |---|---|---|
   | Close date (`closedate`) | The buyer named a target month or quarter | propose |
   | Next step (`next_step`) | Concrete action with owner and date, agreed in the call | auto |
   | Economic buyer (`economic_buyer`) | Person who signs, named by the buyer or present in a call | propose |

   Write modes: `auto`, `overwrite`, `propose` (default), `never`. Explain them in one line each.
4. **Records:** "May I create contacts for external attendees who aren't in the CRM yet? May I create deals?" Default: contacts yes (propose), deals no.
5. **Method:** "Which qualification method do you use: MEDDPICC, BANT, SPICED, your own, or none?"
6. **Follow-ups:** 2 to 3 example emails the user is happy with (or let them point to sent mails). Their calendar link. Rules such as "under 150 words", "always end with a calendar link", "never name a competitor", Du or Sie.
7. **Transcripts:** "Where are your call transcripts stored?" Use the options in `call-transcripts`. If the answer is "nowhere" or they want a recorder, offer Vexa and run the Consent step from `call-transcripts`.
8. **Change log and digests:** where they go (a team-chat channel or DM, a CRM note on the deal, or just the reply). Also: what counts as a quiet deal (default 10 days without a two-way touch).

Don't ask questions the CRM or existing context already answered. Show the inferred answer and let them correct it.

## Step 4: Save

- **Sales Agent connector:** `update_playbook` with the structure below.
- **Claude Code:** write `{client-slug}-gtm/context/playbook.md`, using `examples/sample-client-gtm/context/playbook.md` as the template.
- **Neither:** output the playbook as one Markdown block. Tell the user to save it as a doc named "Sales Playbook" (or as project instructions) so the other skills can find it.

Never store mail bodies, transcripts or contact data in the playbook. Store only rules, mappings and a short description of the writing style.

## Step 5: Show what happens next

One short paragraph with the three skills to try first: `meeting-prep` before the next call, `post-call` after it, `daily-plan` tomorrow morning. Plus the routines in `docs/ROUTINES.md` if they want it automatic.

---

## Playbook structure

```yaml
version: 1
method: meddpicc            # meddpicc | bant | spiced | custom | none
quiet_after_days: 10
stages:
  - name: Discovery
    exit_criteria: "Pain named by the buyer; next meeting booked"
    auto_advance: false
    locked: false
    required_fields: [pain, next_step]
fields:
  - label: Close date
    crm_property: closedate
    standard: "Buyer named a target month or quarter"
    write_mode: propose      # auto | overwrite | propose | never
create_rules:
  contacts: propose          # auto | propose | never
  deals: never
  companies: propose
writing:
  language_default: de
  address: Sie               # Du | Sie (German)
  calendar_url: ""
  rules: ["under 150 words", "end with a calendar link"]
  style: "Short sentences, concrete numbers, no buzzwords"
assets:                      # links only
  - name: Battlecard vs. competitors
    location: "Drive: Sales/Battlecards"
transcripts:
  source: "Google Meet transcripts in Drive folder 'Meet Recordings'"   # or notetaker name, "vexa", "paste"
  fallback: vexa             # vexa | paste
  bot_name: "Anna's Notetaker"
  consent_confirmed: true
  per_meeting_consent: false
change_log:
  destination: "slack:#deal-updates"   # or "crm_note", "reply"
digest:
  destination: "slack:dm"              # or "email_draft_to_self", "reply"
```
