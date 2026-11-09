# MCPLedger

Know every MCP server and agent skill your developers' AI tools can load. Approve exact versions, get told the moment one changes, and block the ones you don't trust.

- **`mcpledger` CLI** (Python, zero dependencies) reads the MCP configs and skill folders of Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Codex, Gemini CLI, Cline, Roo Code, Zed and Amazon Q. It can also start each server and record the tools it advertises (`--introspect`).
- **API** (FastAPI + Postgres) keeps the team inventory, pins approved fingerprints, raises drift alerts, sends Slack messages, keeps an audit log, and handles Paddle billing.
- **Dashboard** (Angular 20) for reviewing, approving and blocking.

## Editions

MCPLedger is open core. Self-host it free, or use the hosted service.

| | Community (self-hosted) | Cloud Free | Cloud Team | Cloud Business / self-hosted Business |
|---|---|---|---|---|
| Price | Free | Free | $29/month | $199/month, or a yearly license key |
| Machines | Unlimited | 3 | 25 | Unlimited (or the license's limit) |
| Inventory, findings, approvals, drift alerts, `check`/`fix` | Yes | Yes | Yes | Yes |
| Slack alerts | Yes | No | Yes | Yes |
| Audit-log CSV export | No | No | No | Yes |
| SSO, longer retention | No | No | No | When shipped |

Self-hosting guide: [docs/self-hosting.md](docs/self-hosting.md).

## License

- `cli/`: [Apache-2.0](cli/LICENSE)
- `server/` and `web/`, except `server/ee/`: [AGPL-3.0](LICENSE)
- `server/ee/`: [MCPLedger Enterprise License](server/ee/LICENSE). Source-available; production use needs a Business plan or license key.

Contributions need a one-time CLA signature ([CONTRIBUTING.md](CONTRIBUTING.md)). Security reports: [SECURITY.md](SECURITY.md).

```
developer laptop / CI                         Cloud Run (one container)              Cloud SQL
┌──────────────────────┐   HTTPS + device key  ┌──────────────────────────────┐      ┌──────────┐
│ mcpledger scan       │ ────────────────────▶ │ FastAPI  /api/*              │ ───▶ │ Postgres │
│ mcpledger check (CI) │ ◀──── verdicts ─────── │ Angular  / (static)          │      └──────────┘
│ mcpledger fix        │                        │ Slack webhook, Paddle webhook│
└──────────────────────┘                        └──────────────────────────────┘
```

## How approval works

Each MCP server gets a stable **identity** (npm/PyPI package, Docker image, URL or local path) and per-version **fingerprints**:

| hash | covers | catches |
|---|---|---|
| launch hash | command, args (incl. version), URL, env var and header **names** | version bumps, config edits |
| tools hash | every tool's name, description and input schema (needs `--introspect`) | **rug pulls**: same package or URL, changed tool descriptions |

Skills are fingerprinted over every file's SHA-256. Approving pins a fingerprint. Anything that doesn't match an approved one shows as **Changed**. In enforce mode that fails `mcpledger check`.

Secret values never leave the machine. The CLI sends env var names and a flag saying a literal secret exists, nothing more. Skill file contents are uploaded so reviewers can diff them; `--hashes-only` turns that off.

Static checks (shared by the CLI and the server, in `cli/src/mcpledger/rules.py`) flag hidden instructions, invisible Unicode, "don't tell the user" phrasing, hard-coded exfiltration destinations, credential-file references, `curl | sh`, reverse shells, privileged Docker, plain-HTTP remotes, unpinned packages and static secrets.

## Run it locally

Requires Python 3.10+ (server), Python 3.9+ (CLI) and Node 22.

```bash
make setup          # venv + npm install
make dev-api        # API on :8000 (SQLite, tables auto-created)
make dev-web        # dashboard on :4200 (proxies /api)
make seed           # demo team: demo@mcpledger.dev / demo-password-123
make test           # CLI + API tests
make e2e            # real CLI against the running API
```

Production-like with Docker: `docker compose up --build`, then open http://localhost:8080.

Try the CLI on your own machine without a server: `pip install ./cli && mcpledger scan --local -v`

## Deploy to Google Cloud

```bash
export PROJECT_ID=your-project REGION=us-central1
./deploy/gcp/bootstrap.sh                                 # once: Cloud SQL, secrets, service accounts
./deploy/gcp/deploy.sh                                    # test, build, migrate, deploy to Cloud Run
PUBLIC_URL=https://<printed-url> ./deploy/gcp/deploy.sh   # redeploy with the real URL
```

The full plan (domains, Paddle, monitoring, costs, rollout) is in the deployment plan document.

## Configuration (server)

| variable | default | notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./mcpledger.db` | `postgresql+psycopg://user:pass@/db?host=/cloudsql/PROJECT:REGION:INSTANCE` on Cloud Run |
| `PUBLIC_URL` | `http://localhost:8000` | used in links, enroll commands and Slack messages |
| `ALLOWED_ORIGINS` | localhost | CSRF guard for cookie-authenticated writes |
| `MCPLEDGER_ENV` | `development` | `production` hides `/api/docs` and stops auto-creating tables |
| `SECURE_COOKIES` | `0` | `1` in production (set by the Dockerfile) |
| `SIGNUPS_OPEN` | `1` | `0` = invite-only |
| `DEPLOYMENT_MODE` | `self_hosted` | `cloud` on the hosted service (Paddle plans and limits) |
| `MCPLEDGER_LICENSE_KEY` | empty | self-hosted Business license key |
| `TRUSTED_PROXY_HOPS` | `1` | proxies in front of the app, used for client IPs in rate limits and the audit log |
| `PADDLE_ENV`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_TEAM`, `PADDLE_PRICE_BUSINESS` | empty | billing; checkout is hidden until set |

Cloud plans live in `server/app/config.py` (`PLANS`); editions and license checks in `server/app/editions.py` and `server/app/licensing.py`. Issue license keys with `server/scripts/issue_license.py` (needs the private signing key, which is never committed).

## Layout

```
cli/        mcpledger CLI + shared detection rules (published to PyPI)
server/     FastAPI app, SQLAlchemy models, Alembic migrations, tests, demo seed
server/ee/  paid features (MCPLedger Enterprise License)
web/        Angular dashboard
deploy/gcp/ bootstrap.sh, deploy.sh, cloudbuild.yaml
scripts/    e2e.sh
```

## Not built yet

SSO/SAML (planned for the Business edition), email notifications, data-retention jobs, an MDM-friendly installer (`.pkg`/`.msi`), and running external scanners (e.g. Snyk Agent Scan) from the CLI.
