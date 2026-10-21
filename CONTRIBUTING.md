# Contributing

Thanks for your interest in improving the GTM pipeline skills. This guide covers how to contribute.

---

## How to Contribute

1. **Fork** the repo
2. **Create a branch** from `main` for your change
3. **Make your changes** — follow the conventions below
4. **Test** with `./install.sh` and invoke the skill you modified
5. **Submit a PR** to `main`

PRs are reviewed before merging. The `stable` branch is the maintainer's production copy — don't target it.

---

## What You Can Contribute

- **Skill improvements:** Better instructions, clearer steps, edge case handling
- **New provider support:** Add a data provider to an existing skill's provider table
- **Bug fixes:** Incorrect field names, broken references, missing steps
- **Documentation:** Architecture docs, examples, README improvements
- **New skills:** Propose via an issue first — discuss scope before building

---

## Conventions

### Skill Files

- Each skill lives in `skills/{name}/SKILL.md` (lowercase, hyphens)
- Follow the YAML frontmatter format. `name` must equal the folder name; the plugin adds the `gtm-pipeline:` prefix:
  ```yaml
  ---
  name: {skill-name}
  description: What it does and when to use it. Trigger phrases at the end. Max 1024 characters.
  ---
  ```
- Reference shared files with `${CLAUDE_PLUGIN_ROOT}/shared/conventions.md`
- Use snake_case for all CSV field names (see `shared/conventions.md` for canonical names)

### No Personal Data

Never commit:
- API keys, session cookies, or secrets
- Absolute paths (use `${CLAUDE_PLUGIN_ROOT}/...` for plugin files, `$HOME` for user files)
- Client names, domains, or real contact data
- Your name or identifying information

If a skill needs user-specific config, use an environment variable in `~/.env.gtm` and document it in `.env.example`.

### Scope

Email and phone enrichment, LinkedIn automation and sending (email or LinkedIn) run in keinsaas Sales Agent, not in this plugin. Don't add them to a skill.

### Shared Files

- `shared/conventions.md` — field naming, terminology, directory structure
- `shared/revenue.md` — rules for the revenue-intelligence skills. After editing, run `scripts/sync-shared.sh`.

### Examples

If your change affects the expected project structure, update `examples/sample-client-gtm/` to match.

---

## Testing Your Changes

```bash
# Validate the plugin
claude plugin validate --strict .
scripts/sync-shared.sh --check

# Load your checkout for one session (or ./install.sh to install it)
claude --plugin-dir .

# Invoke the skill you changed
/gtm-pipeline:{skill-name}
```

Verify:
- The skill runs without referencing missing files
- Field names match `shared/conventions.md`
- No hardcoded paths, IDs, or personal data
- Existing skills that reference your changed skill still work

---

## Reporting Issues

Open an issue with:
- Which skill is affected
- What you expected vs. what happened
- Your provider setup (which API keys you have configured)

---

## Code of Conduct

Be constructive. This project exists to make GTM pipelines accessible — contributions that support that goal are welcome.
