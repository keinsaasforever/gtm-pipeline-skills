# _shared/local.md — Personal Configuration

Copy this file to `_shared/local.md` and fill in your values.
This file is gitignored — your keys and agent IDs stay on your machine.

---

## Environment

```
GTM_ENV_PATH=/Users/YOUR_USERNAME/.env.gtm
```

Set this to the path of your `.env` file containing API keys.
Default if not set: `~/.env.gtm`

---

## PhantomBuster Agent IDs

Find these in your PhantomBuster dashboard (agent URL contains the ID),
or run `/gtm-pipeline:setup` and it will look them up via the PB MCP automatically.

| Config Key | Agent ID | Agent Script Name |
|------------|----------|------------------|
| PB_AGENT_CONNECT | | LinkedIn Auto Connect |
| PB_AGENT_MESSAGE | | LinkedIn Message Sender / SN Message Sender |
| PB_AGENT_SN_ACCOUNT | | Sales Navigator Account Scraper |
| PB_AGENT_EMPLOYEES | | LinkedIn Company Employee Finder |
| PB_AGENT_SN_SEARCH | | Sales Navigator Search Export |
| PB_AGENT_EMAIL | | Email Finder (Priority 1 email enrichment) |
| PB_AGENT_PROFILE | | LinkedIn Profile Scraper |
| PB_AGENT_JOB_SEARCH | | LinkedIn Search Export (jobs mode) |
| PB_AGENT_LIKER | | LinkedIn Auto Liker |
| PB_AGENT_COMMENTER | | LinkedIn Auto Commenter |
| PB_AGENT_WITHDRAWER | | LinkedIn Invitation Auto Withdraw |
| PB_AGENT_INBOX | | LinkedIn Inbox Scraper |
| PB_AGENT_CONNECTIONS | | LinkedIn Connections Export |

You don't need all of these. Fill in only the ones you plan to use.

---

## PhantomBuster Email Finder staging (Google OAuth)

The Email Finder phantom (`PB_AGENT_EMAIL`) reads its input from a Google Sheet.
`_shared/pb_email_finder.py` **creates a fresh blank sheet for every run** (so different
projects/runs never share rows), link-shares it so PB can read it, then trashes it.
It just needs Google OAuth — **no pre-existing sheet ID.** Add to your `.env`:

```
GOOGLE_CLIENT_SECRET_FILE=/path/to/google_client_secret.json
GOOGLE_AUTHORIZED_USER_FILE=/path/to/authorized_user.json   # token; created on first OAuth
```

If either of these (or `PHANTOMBUSTER_API_KEY`) is absent, the email finder exits 3 and
the waterfall simply starts at FullEnrich instead — PB is never required.

The OAuth token needs the `spreadsheets` + `drive` scopes (to create and trash the
staging sheet). You can reuse a token from another project that already has them.

---

## Notes

- Skills that use PhantomBuster read agent IDs from this file
- If an ID is missing, the skill falls back to looking it up via the PhantomBuster MCP
- You can also look up IDs dynamically: ask Claude to run `PHANTOMBUSTER_GET_AGENTS_FETCH_ALL`
