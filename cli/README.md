# mcpledger

Inventory, allowlist and drift alerts for the MCP servers and agent skills on your team's machines.

```bash
pipx install mcpledger        # or: uv tool install mcpledger
mcpledger scan --local -v     # see what's on this machine, no account needed
```

## With a team

```bash
mcpledger enroll <token> --server https://app.mcpledger.dev --email you@company.com
mcpledger scan --introspect   # report to your team, record each server's tools
mcpledger schedule --every 6  # keep reporting in the background
```

| command | what it does |
|---|---|
| `scan` | Finds MCP servers and skills, runs static checks, reports to your team and prints each item's verdict. |
| `check` | Same, but exits `1` if anything is blocked (`--strict`: also on unapproved). Use it in CI or a git hook. Without enrollment it fails on local findings at or above `--fail-on` (default `high`). |
| `fix` | Dry run of removing blocked servers from JSON configs and quarantining blocked skills. `--yes` applies it, with backups in `~/.mcpledger/quarantine/`. |
| `status`, `schedule`, `enroll` | Enrollment and background scans (launchd on macOS, a printed cron or schtasks line elsewhere). |

`--introspect` starts each configured server the same way your editor does and asks for `tools/list`. That is what detects a server that changes its tool descriptions after you approved it.

## What it reads

User and project MCP configs for Claude Code (`~/.claude.json`, `.mcp.json`), Claude Desktop, Cursor, VS Code (`mcp.json` and settings), Windsurf, Codex (`config.toml`), Gemini CLI, Cline, Roo Code, Zed and Amazon Q. It also reads skill folders (`SKILL.md`) under `~/.claude/skills`, Claude plugins, `~/.codex/skills`, `~/.cursor/skills`, `~/.agents/skills` and the same folders in the current project.

**Secret values are never sent.** Only env var and header names are sent, plus a flag when a literal secret sits in a config file. Skill file contents are sent so reviewers can see diffs; pass `--hashes-only` to send hashes only.

CI: set `MCPLEDGER_SERVER` and `MCPLEDGER_DEVICE_KEY`, then run `mcpledger check --project .`.

No runtime dependencies. Python 3.9+.
