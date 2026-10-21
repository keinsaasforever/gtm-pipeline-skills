---
name: call-transcripts
description: Find, fetch or record the transcript of a sales call, from wherever the user's meetings are transcribed (notetaker app, Google Meet, Microsoft Teams, Zoom, Drive folder) with Vexa as the fallback recorder. Can send a Vexa bot to an upcoming meeting. Used by post-call, meeting-prep, live-assist and deal-review. Also triggers on "get the transcript", "record my next call", "send a notetaker to", "where are my call notes", "transcribe this meeting".
---

# Call Transcripts

Get the transcript of a sales call, or arrange for one. This skill is the single place that knows where transcripts live. Other skills call it instead of searching on their own.

**Read `references/revenue.md` (in this skill's folder; the canonical copy is `shared/revenue.md` in the plugin) before executing.**

---

## Where transcripts come from (in this order)

### 1. The source the user told us

If the playbook has a `transcripts` section, use it exactly. Examples:
- "Fireflies";
- "Google Meet transcripts in Drive folder 'Meet Recordings'";
- "Teams transcripts in OneDrive";
- "we paste notes into the HubSpot deal";
- "Vexa".

If there is no playbook entry and this is the first run, **ask once**: "Where are your call transcripts stored? E.g. a notetaker app, Google Meet or Teams transcripts, Zoom cloud recordings, a Drive folder, or none." Save the answer with `revenue-setup`, or in `context/playbook.md` in Claude Code.

### 2. A connected notetaker or meeting tool

Use whichever the user has connected: Fireflies, Gong, Fathom, Otter, tl;dv, Avoma, Granola, Zoom, Teams or similar. Search by meeting time ±30 min and attendee email, falling back to meeting title.

### 3. Native transcripts from the meeting platform

| Platform | Where the transcript lands | How to find it |
|---|---|---|
| **Google Meet** | A Google Doc "<meeting title> – Transcript" (or Gemini "Notes by Gemini") in the organizer's Drive, usually folder *Meet Recordings*. It is also attached to the calendar event. | Calendar event → attachments; or Drive search for the meeting title + "Transcript" in the date range. |
| **Microsoft Teams** | The meeting's *Recap* tab; the file sits in the organizer's OneDrive (*Recordings*) or the channel's SharePoint as .vtt/.docx. | Teams or SharePoint connector; search by meeting title and date. |
| **Zoom** | Cloud recording → audio transcript (.vtt) when the host enabled it; or AI Companion meeting summary. | Zoom connector (recordings for the meeting ID). |

Native transcripts are only there if the host turned transcription on, and they appear minutes to an hour after the call. If the meeting is less than 60 min past and nothing is found, say so and offer to retry. In a routine, leave it for the next sweep.

### 4. Vexa (fallback recorder)

Vexa is an open-source meeting bot (Apache-2.0) that joins Google Meet, Teams and Zoom (web client) as a participant and transcribes. Use it when steps 1 to 3 give nothing, or when the playbook names it. It is also the only path to a **live** transcript (see `live-assist`).

**Access, in this order:**
1. **Vexa tools available as a connector or MCP server**: `request_meeting_bot`, `get_bot_status`, `get_meeting_transcript`, `list_meetings`, `stop_bot`. Use them.
   - Vexa's hosted MCP is `https://api.cloud.vexa.ai/mcp` and authenticates with an API key (`Authorization: Bearer <key>`).
   - Clients that only support OAuth connectors can't add it directly. In Claude Desktop or Code, use `npx mcp-remote https://api.cloud.vexa.ai/mcp --header "Authorization: Bearer ${VEXA_API_KEY}"`.
2. **Shell available (Claude Code):** call the REST API with `VEXA_API_KEY`, injected per conventions (never read the env file into context).
3. **Neither:** tell the user Vexa needs either the connector or an API key, and ask them to paste the transcript instead.

**REST reference** (hosted base `https://api.cloud.vexa.ai`; self-hosted default `http://localhost:18056`; header `X-API-Key`):

| Action | Call |
|---|---|
| Send a bot now | `POST /bots` `{"platform":"google_meet"\|"teams"\|"zoom", "native_meeting_id":"abc-defg-hij", "bot_name":"<Rep>'s Notetaker", "language":"de", "recording_enabled": false}`. Zoom needs the full `meeting_url`. Teams takes the numeric ID plus `passcode`, or the full `meeting_url`. 409 = a bot is already there. Set `recording_enabled: false` unless the user wants audio kept: the transcript is enough, and less stored data is better. |
| Schedule a bot for a calendar meeting | `POST /meetings` `{"title": "...", "meeting_url": "...", "scheduled_at": "<ISO time>"}`. The bot joins ~60 s before, never more than 10 min late. For whole calendars, Vexa can also follow an ICS feed (`PUT /user/calendar`). |
| Status | `GET /bots/status` |
| Transcript (during or after) | `GET /transcripts/{platform}/{native_meeting_id}` → `segments[]` with `speaker`, `text`, `start`, `end`, `completed`. Add `since_index` (MCP tool) to fetch only new segments. |
| Find past meetings | `GET /meetings?status=completed&limit=20` |
| Stop | `DELETE /bots/{platform}/{native_meeting_id}` |
| Webhook on meeting end | `PUT /user/webhook` `{"webhook_url": "...", "webhook_secret": "...", "webhook_events": {"meeting.completed": true}}`. The events field is a map, and an array is rejected. The HMAC is in `X-Webhook-Signature` (`sha256=` over `"<X-Webhook-Timestamp>." + body`). See `docs/ROUTINES.md` for wiring it to a scheduled task. |

Example (Claude Code):
```bash
source "${CLAUDE_PLUGIN_ROOT}/shared/resolve_env.sh"
while IFS= read -r line; do export "$line"; done < <(grep -E '^VEXA_API_KEY=' "$GTM_ENV_PATH") && \
curl -s -m 30 "${VEXA_API_URL:-https://api.cloud.vexa.ai}/transcripts/google_meet/abc-defg-hij" -H "X-API-Key: $VEXA_API_KEY"
```

**Known limits:**
- On Meet and Teams the bot waits in the lobby until someone admits it. A run can end as `awaiting_admission_timeout` or `awaiting_admission_rejected`; tell the user to admit "<bot_name>".
- About 5 % of segments have no speaker name under crosstalk. Attribute them as "unknown speaker". Never guess who said a commitment.
- Hosted Vexa publishes no data-residency, retention or DPA terms yet, and transcripts are not yet encrypted at rest. For EU customers who need that, recommend self-hosting Vexa or a notetaker they already have a DPA with. Say this once, when Vexa is first set up.

### 5. Nothing available

Ask the user to paste the transcript or their own notes. Post-call works on notes too; mark everything from notes as "rep notes", not as buyer quotes.

---

## Consent (required before any bot joins)

Before sending a Vexa bot (or any recorder) the first time for a user:
1. Ask the user to confirm that the attendees know the call is recorded and transcribed. In the EU and Germany that means telling them before the recording starts and stopping if anyone objects.
2. Name the bot visibly: `bot_name` = "<Rep first name>'s Notetaker" or the playbook's `bot_name`, never something disguised.
3. Offer a one-line notice for the invite or the start of the call, in the meeting's language. For example: "Zur Info: ein Notetaker schreibt mit, damit ich mich aufs Gespräch konzentrieren kann. Sag Bescheid, wenn das nicht passt."
4. Store the confirmation in the playbook (`transcripts.consent_confirmed: true`). Ask again if the playbook says per-meeting consent.

Never send a bot to meetings where the user is not an attendee.

---

## Sending bots to upcoming meetings ("record my calls")

1. Read the calendar for the requested window (default: today and tomorrow).
2. Keep meetings that have a Meet, Teams or Zoom link **and** at least one external attendee (domain ≠ the user's domain). Skip internal meetings unless the user asks.
3. Show the list and get one approval for the batch.
4. Schedule each with `POST /meetings` (or `request_meeting_bot` at start time if scheduling isn't available).
5. Report: scheduled meetings, skipped meetings and why, the bot name attendees will see.

---

## Output to the calling skill

Return a normalized transcript, never the raw provider payload:

```
meeting: {title} | {start time} | {platform} | {source: notetaker|native|vexa|notes} | {source link or id}
attendees: {name <email> (external|internal)}
segments:
  [mm:ss] {speaker or "unknown speaker"}: {text}
```

- Keep `{source}:{external_id}` for the run-once marker (`revenue.md` §6). Use the notetaker's call ID, the Drive file ID, or `vexa:{platform}:{native_meeting_id}:{start}`.
- If the transcript is longer than about 30k words, return the summary sections the caller asks for plus the segments around each relevant moment, not the whole text.
