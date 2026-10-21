# Flowline — Sales Playbook

> Fictional example company. This is the format `gtm-pipeline:revenue-setup` writes to `context/playbook.md`, and the file the revenue-intelligence skills read (see `shared/revenue.md`).

```yaml
version: 3
method: meddpicc
quiet_after_days: 10

stages:
  - name: Discovery
    exit_criteria: "Buyer named a pain in their own words; second meeting booked"
    auto_advance: true
    locked: false
    required_fields: [pain, next_step]
  - name: Demo
    exit_criteria: "Demo held with the champion; success criteria agreed"
    auto_advance: true
    locked: false
    required_fields: [champion, metrics]
  - name: Proposal
    exit_criteria: "Economic buyer identified and met; pricing sent"
    auto_advance: false
    locked: false
    required_fields: [economic_buyer, decision_process]
  - name: Negotiation
    exit_criteria: "Paper process known; signature date named by the buyer"
    auto_advance: false
    locked: false
    required_fields: [paper_process, closedate]
  - name: Closed Won
    locked: true
  - name: Closed Lost
    locked: true

fields:
  - label: Next step
    crm_property: next_step
    standard: "Concrete action with an owner and a date, agreed in the call"
    write_mode: auto
  - label: Pain
    crm_property: pain
    standard: "Problem the buyer described in their own words, with its cost or impact if given"
    write_mode: auto
  - label: Metrics
    crm_property: success_metrics
    standard: "Number the buyer wants to move (hours saved, error rate), stated by the buyer"
    write_mode: propose
  - label: Champion
    crm_property: champion
    standard: "Person who said they will push this internally, or who arranged the next meeting with others"
    write_mode: propose
  - label: Economic buyer
    crm_property: economic_buyer
    standard: "Person who approves the budget, named by the buyer or present in a call"
    write_mode: propose
  - label: Decision process
    crm_property: decision_process
    standard: "Steps and people until signature, as described by the buyer"
    write_mode: propose
  - label: Competitor
    crm_property: competitor
    standard: "Tool or vendor the buyer is also evaluating, named in a call or mail"
    write_mode: auto
  - label: Close date
    crm_property: closedate
    standard: "Buyer named a target month or quarter for signature"
    write_mode: propose
  - label: Amount
    crm_property: amount
    standard: "Pricing we sent, or a budget the buyer stated"
    write_mode: never

create_rules:
  contacts: propose
  deals: never
  companies: propose

writing:
  language_default: de
  address: Du
  calendar_url: "https://cal.example.com/flowline/30min"
  rules:
    - "Under 150 words"
    - "Recap next steps as a bullet list with owner and date"
    - "End with one clear next step and the calendar link"
    - "Never name a competitor"
  style: "Conversational and direct. Refer to the buyer's own tools by name (HubSpot, SAP). No buzzwords."
  approved_claims:
    - "Customers reclaim 6–10 hours per ops person per week in the first month"
    - "80+ pre-built connectors, incl. Salesforce, HubSpot, SAP, Jira, Slack"

assets:
  - name: Security whitepaper
    location: "Drive: Sales/Collateral/Flowline-Security.pdf"
  - name: Battlecard — iPaaS competitors
    location: "Drive: Sales/Battlecards/iPaaS.md"

transcripts:
  source: "Google Meet transcripts in Drive folder 'Meet Recordings'"
  fallback: vexa
  bot_name: "Flowline Notetaker"
  consent_confirmed: true
  per_meeting_consent: false

change_log:
  destination: "slack:#deal-updates"
digest:
  destination: "slack:dm"
```
