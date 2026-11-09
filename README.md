<div align="center">

<a href="#readme"><img src=".github/assets/banner.svg" alt="MCPLedger: know every MCP server and agent skill your team runs" width="100%"></a>

<h3>Inventory, allowlist and drift alerts for the MCP servers and agent skills on your team's machines.</h3>

<p>
  <a href="https://github.com/mujtabajalil/mcpledger/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/mujtabajalil/mcpledger/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Server: AGPL-3.0" src="https://img.shields.io/badge/server-AGPL--3.0-16343d?style=flat"></a>
  <a href="cli/LICENSE"><img alt="CLI: Apache-2.0" src="https://img.shields.io/badge/CLI-Apache--2.0-0f6a72?style=flat"></a>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-0f6a72?style=flat&logo=python&logoColor=white">
  <img alt="Zero runtime dependencies" src="https://img.shields.io/badge/CLI%20dependencies-0-2c7a4b?style=flat">
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-2c7a4b?style=flat"></a>
</p>

<p>
  <a href="#quick-start"><b>Quick start</b></a> &nbsp;·&nbsp;
  <a href="#how-it-works"><b>How it works</b></a> &nbsp;·&nbsp;
  <a href="docs/self-hosting.md"><b>Self-hosting</b></a> &nbsp;·&nbsp;
  <a href="#editions"><b>Editions</b></a> &nbsp;·&nbsp;
  <a href="CONTRIBUTING.md"><b>Contributing</b></a>
</p>

</div>

<br>

Every developer on your team now runs AI tools that load **MCP servers** and **agent skills** straight from npm, PyPI, Docker Hub and random URLs. Those are code and prompts with access to your laptops, repos and credentials, and nobody reviews them. One unpinned package or one quietly edited tool description is enough to turn a trusted server into an exfiltration channel.

MCPLedger gives you the missing ledger: **see** what's installed on every machine, **approve** the exact versions you reviewed, get **alerted** the moment one changes, and **block** the ones you don't trust, in CI as well as on laptops.

<p align="center">
  <img src=".github/assets/dashboard.webp" alt="MCPLedger overview: KPI cards for items needing review, changed since approval, approved share and machines reporting, a components-by-AI-tool chart, and the high-risk items waiting for review" width="100%">
</p>

## Highlights

<table>
<tr>
<td width="33%" valign="top">

**🔎 Full inventory**<br>
Reads the MCP configs and skill folders of 11 AI tools on every machine. Each component gets a stable identity, so the same server in Cursor and Claude Code is one row.

</td>
<td width="33%" valign="top">

**📌 Version pinning**<br>
Approving pins a fingerprint of the exact launch config, tool list or skill files. Anything else shows as **Changed** until a human looks at it.

</td>
<td width="33%" valign="top">

**🪤 Rug-pull detection**<br>
`--introspect` starts each server and records its tools. Same package, same URL, new hidden instruction in a tool description? You see the diff.

</td>
</tr>
<tr>
<td valign="top">

**🧪 Static checks**<br>
Hidden `<IMPORTANT>` tags, invisible Unicode, "don't tell the user", exfiltration targets, `curl | sh`, reverse shells, privileged Docker, inline secrets.

</td>
<td valign="top">

**🚦 CI gate & auto-fix**<br>
`mcpledger check` fails the build on blocked components. `mcpledger fix` removes them from configs and quarantines skills, with backups.

</td>
<td valign="top">

**🔐 Secrets stay home**<br>
Only env var and header **names** leave the machine. Slack alerts, a full audit log and offline license keys for air-gapped installs.

</td>
</tr>
</table>

## Quick start

### Scan your own machine (no account, no server)

```bash
pipx install "git+https://github.com/mujtabajalil/mcpledger#subdirectory=cli"
mcpledger scan --local -v
```

<details open>
<summary><b>Example output</b></summary>

```text
MCP servers (3)
  [clean] linear  claude-code · user
  [low] postmark  claude-code · user
      SG001 Unpinned package version  config
  [medium] github  cursor · user
      SG002 Static secret stored in config  config

Agent skills (1)
  [high] deploy-helper  claude-code · user  2 files
      SG102 Asks the agent to hide actions from the user  file:SKILL.md
      SG201 Downloads and executes remote code  file:scripts/prep.sh:2
      SG209 Skill ships executable scripts  files

5 finding(s), worst: high
```

</details>

### Run the team server (Docker, about five minutes)

```bash
git clone https://github.com/mujtabajalil/mcpledger && cd mcpledger
docker compose up --build -d        # Postgres 16 + MCPLedger on http://localhost:8080
```

Create the first account (it becomes the owner), copy the enrollment token from **Settings**, then on each laptop:

```bash
mcpledger enroll <token> --server http://your-host:8080 --email you@company.com
mcpledger scan --introspect         # report, and record each server's tools
mcpledger schedule --every 6        # keep reporting in the background
```

Production setup (TLS, migrations, backups): [docs/self-hosting.md](docs/self-hosting.md).

## See it catch things

<table>
<tr>
<td width="50%" valign="top">
<img src=".github/assets/rug-pull.webp" alt="postmark-mcp marked Changed: the diff shows a new hidden instruction to BCC every email to an outside address">
<p align="center"><sub><b>A rug pull.</b> Same npm package, new tool description that BCCs every email to an outside address. The version is held until someone approves or blocks it.</sub></p>
</td>
<td width="50%" valign="top">
<img src=".github/assets/malicious-skill.webp" alt="deploy-helper skill with high-risk findings: it hides a step from the user and pipes a remote script into the shell">
<p align="center"><sub><b>A malicious skill.</b> Tells the agent to hide a step from the user, pipes a remote script into <code>sh</code> and uploads <code>~/.aws/credentials</code>.</sub></p>
</td>
</tr>
</table>

<p align="center">
  <img src=".github/assets/inventory.webp" alt="Inventory of nine components with status, risk, machine count and the AI tools each is used in" width="100%">
</p>

## How it works

```mermaid
flowchart LR
    subgraph dev["Developer laptops & CI"]
        cli["<b>mcpledger</b> CLI<br/>scan · check · fix"]
    end
    subgraph srv["MCPLedger server (one container)"]
        api["FastAPI<br/>/api/*"]
        web["Angular dashboard"]
    end
    db[("Postgres")]
    slack["Slack"]

    cli -- "inventory + fingerprints<br/>(HTTPS, device key)" --> api
    api -- "verdicts: allow / warn / block" --> cli
    web --- api
    api --> db
    api -- "drift & new-component alerts" --> slack
```

**Fingerprints.** Each MCP server gets a stable **identity** (npm/PyPI package, Docker image, URL or local path) and per-version **fingerprints**:

| Hash | Covers | Catches |
|---|---|---|
| **Launch hash** | command, args (incl. version), URL, env var and header **names** | version bumps, config edits |
| **Tools hash** | every tool's name, description and input schema (needs `--introspect`) | **rug pulls**: same package or URL, changed tool descriptions |
| **Skill hash** | SHA-256 of every file in the skill folder | edited prompts and scripts |

Approving pins a fingerprint. Anything that doesn't match an approved one shows as **Changed**, and in enforce mode fails `mcpledger check`.

**Static checks** live in [`cli/src/mcpledger/rules.py`](cli/src/mcpledger/rules.py) and are shared by the CLI and the server, so a finding on a laptop and in the dashboard always agree.

### Supported AI tools

| Tool | MCP configs read | Skill folders read |
|---|---|---|
| **Claude Code** | `~/.claude.json` (incl. per-project), `~/.claude/settings.json`, `.mcp.json` | `~/.claude/skills`, `.claude/skills`, plugins |
| **Claude Desktop** | `claude_desktop_config.json` | |
| **Cursor** | `~/.cursor/mcp.json`, `.cursor/mcp.json`, user settings | `~/.cursor/skills`, `.cursor/skills` |
| **VS Code** <sub>(+ Insiders, VSCodium)</sub> | user `mcp.json` and `settings.json`, `.vscode/mcp.json` | |
| **Codex** | `~/.codex/config.toml`, `.codex/config.toml` | `~/.codex/skills`, `.codex/skills` |
| **Gemini CLI** | `~/.gemini/settings.json`, `.gemini/settings.json` | `~/.gemini/skills` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json`, `.windsurf/mcp.json` | |
| **Cline**, **Roo Code** | extension settings in VS Code and Cursor | |
| **Zed** | `settings.json` (`context_servers`) | |
| **Amazon Q** | `~/.aws/amazonq/mcp.json` | |
| **Any agent** | | `~/.agents/skills`, `.agents/skills` |

Missing one? Adding a location is a few lines in [`discovery.py`](cli/src/mcpledger/discovery.py); see [CONTRIBUTING.md](CONTRIBUTING.md).

### What leaves the machine

| ✅ Sent | 🚫 Never sent |
|---|---|
| Server names, commands, arguments, URLs | Values of environment variables or headers |
| Env var and header **names**, plus a flag when a literal secret is present | Your source code |
| Tool names, descriptions and schemas (only with `--introspect`) | Anything from servers you didn't configure |
| Skill files under 64 KB (hashes only with `--hashes-only`) | Files outside skill folders |
| Hostname, OS, username, CLI version | |

Run `mcpledger scan --json` to see exactly what a report contains before you enroll.

## CLI reference

| Command | What it does |
|---|---|
| `scan` | Finds MCP servers and skills, runs static checks, reports to your team and prints each item's verdict. `--local` skips the server. |
| `check` | Same, but exits `1` if anything is blocked (`--strict`: also on unapproved). Without enrollment it fails on local findings at or above `--fail-on` (default `high`). |
| `fix` | Dry run of removing blocked servers from JSON configs and quarantining blocked skills. `--yes` applies it, with backups in `~/.mcpledger/quarantine/`. |
| `enroll`, `status`, `schedule` | Join a team, show enrollment, and run background scans (launchd on macOS, a printed cron or schtasks line elsewhere). |

**In CI**, set `MCPLEDGER_SERVER` and `MCPLEDGER_DEVICE_KEY`, then:

```yaml
- run: pipx install "git+https://github.com/mujtabajalil/mcpledger#subdirectory=cli"
- run: mcpledger check --project .
```

## Editions

MCPLedger is **open core**. The self-hosted Community edition is free with no device limit.

| | **Community** <br><sub>self-hosted</sub> | **Business** <br><sub>self-hosted license key</sub> | **Cloud Free / Team** <br><sub>hosted, coming soon</sub> |
|---|:---:|:---:|:---:|
| Price | **Free** | $199/month or yearly key | Free (3 machines) / $29/month (25) |
| Machines | Unlimited | Unlimited or license limit | 3 / 25 |
| Inventory, findings, approvals, drift alerts | ✅ | ✅ | ✅ |
| `check` / `fix` in CI and on laptops | ✅ | ✅ | ✅ |
| Slack alerts | ✅ | ✅ | Team only |
| Audit-log CSV export | | ✅ | |
| SSO, longer retention | | Planned | |

License keys are verified offline, so air-gapped installs work. An expired key falls back to Community without losing data.

## Develop

Requires Python 3.10+ (server), Python 3.9+ (CLI) and Node 22.

```bash
make setup      # venv + npm install
make dev-api    # API on :8000 (SQLite, tables auto-created)
make dev-web    # dashboard on :4200 (proxies /api)
make seed       # demo team: demo@mcpledger.dev / demo-password-123
make test       # CLI + API tests
make e2e        # real CLI against the running API
```

<details>
<summary><b>Server configuration</b></summary>
<br>

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./mcpledger.db` | `postgresql+psycopg://user:pass@host/db` in production |
| `PUBLIC_URL` | `http://localhost:8000` | used in links, enroll commands and Slack messages |
| `ALLOWED_ORIGINS` | localhost | CSRF guard for cookie-authenticated writes |
| `MCPLEDGER_ENV` | `development` | `production` hides `/api/docs` and stops auto-creating tables |
| `SECURE_COOKIES` | `0` | `1` in production (set by the Dockerfile) |
| `SIGNUPS_OPEN` | `1` | `0` = invite-only |
| `DEPLOYMENT_MODE` | `self_hosted` | `cloud` on the hosted service (Paddle plans and limits) |
| `MCPLEDGER_LICENSE_KEY` | empty | self-hosted Business license key |
| `TRUSTED_PROXY_HOPS` | `1` | proxies in front of the app, used for client IPs in rate limits and the audit log |
| `PADDLE_ENV`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_TEAM`, `PADDLE_PRICE_BUSINESS` | empty | billing; checkout is hidden until set |

Cloud plans live in `server/app/config.py` (`PLANS`); editions and license checks in `server/app/editions.py` and `server/app/licensing.py`.

</details>

<details>
<summary><b>Deploy to Google Cloud Run</b></summary>
<br>

```bash
export PROJECT_ID=your-project REGION=us-central1
./deploy/gcp/bootstrap.sh                                 # once: Cloud SQL, secrets, service accounts
./deploy/gcp/deploy.sh                                    # test, build, migrate, deploy to Cloud Run
PUBLIC_URL=https://<printed-url> ./deploy/gcp/deploy.sh   # redeploy with the real URL
```

</details>

<details>
<summary><b>Repository layout</b></summary>
<br>

```text
cli/         mcpledger CLI + shared detection rules        Apache-2.0
server/      FastAPI app, models, Alembic migrations, tests AGPL-3.0
server/ee/   Business features                              MCPLedger Enterprise License
web/         Angular 20 dashboard                           AGPL-3.0
deploy/gcp/  bootstrap.sh, deploy.sh, cloudbuild.yaml
docs/        self-hosting guide
scripts/     e2e.sh
```

</details>

## Roadmap

- [ ] Publish the CLI to PyPI (`pipx install mcpledger`)
- [ ] Hosted cloud at mcpledger.dev
- [ ] SSO / SAML (Business)
- [ ] Email notifications and data-retention jobs
- [ ] MDM-friendly installers (`.pkg`, `.msi`)
- [ ] Run external scanners (e.g. Snyk Agent Scan) from the CLI

Ideas and votes welcome in [issues](https://github.com/mujtabajalil/mcpledger/issues).

## Contributing

Bug reports, new AI-tool config locations, detection rules and docs fixes are the most useful contributions. Start with [CONTRIBUTING.md](CONTRIBUTING.md); first-time contributors sign the [CLA](CLA.md) once, by commenting on their pull request.

Found a vulnerability? Please report it privately, as described in [SECURITY.md](SECURITY.md).

## License

| Path | License |
|---|---|
| `cli/` | [Apache-2.0](cli/LICENSE) |
| `server/`, `web/` (except `server/ee/`) | [AGPL-3.0](LICENSE) |
| `server/ee/` | [MCPLedger Enterprise License](server/ee/LICENSE): source-available, production use needs a Business plan or license key |

<br>

<p align="center">
  <img src="web/public/favicon.svg" width="28" alt=""><br>
  <sub>Built for teams who want to say yes to AI tools without saying yes to everything.</sub>
</p>
