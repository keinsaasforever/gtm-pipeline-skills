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
| PB_AGENT_PROFILE | | LinkedIn Profile Scraper |
| PB_AGENT_JOB_SEARCH | | LinkedIn Search Export (jobs mode) |
| PB_AGENT_LIKER | | LinkedIn Auto Liker |
| PB_AGENT_COMMENTER | | LinkedIn Auto Commenter |
| PB_AGENT_WITHDRAWER | | LinkedIn Invitation Auto Withdraw |
| PB_AGENT_INBOX | | LinkedIn Inbox Scraper |
| PB_AGENT_CONNECTIONS | | LinkedIn Connections Export |

You don't need all of these. Fill in only the ones you plan to use.

---

## Notes

- Skills that use PhantomBuster read agent IDs from this file
- If an ID is missing, the skill falls back to looking it up via the PhantomBuster MCP
- You can also look up IDs dynamically: ask Claude to run `PHANTOMBUSTER_GET_AGENTS_FETCH_ALL`
