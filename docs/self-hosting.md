# Self-hosting MCPLedger

The Community edition is free, has no device limit, and includes inventory, findings, approvals, drift alerts, Slack alerts, the audit log viewer and the CLI's `check`/`fix`. A Business license key adds audit-log export now, and SSO and longer retention when they ship.

## Quick start (Docker, about five minutes)

```bash
git clone https://github.com/mujtabajalil/mcpledger && cd mcpledger
docker compose up --build -d          # Postgres 16 + MCPLedger on http://localhost:8080
```

Open http://localhost:8080, create the first account (it becomes the owner), then on each laptop:

```bash
pipx install "git+https://github.com/mujtabajalil/mcpledger#subdirectory=cli"
mcpledger enroll <token from Settings> --server http://your-host:8080
mcpledger scan --introspect
```

## Production checklist

| Setting | Value |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host/db` (Postgres 14+) |
| `PUBLIC_URL` and `ALLOWED_ORIGINS` | your HTTPS URL, e.g. `https://mcpledger.internal.example.com` |
| `SECURE_COOKIES` | `1` (the image sets it; set `0` only for plain-HTTP testing) |
| `SIGNUPS_OPEN` | `0` after the first owner signs up; invite everyone else |
| `TRUSTED_PROXY_HOPS` | `1` behind one reverse proxy, `2` behind a load balancer plus a proxy |
| `MCPLEDGER_LICENSE_KEY` | your Business license key, if you have one |

Run migrations on every upgrade before starting the new version:

```bash
docker run --rm -e DATABASE_URL=… <image> alembic upgrade head
```

Put it behind your usual TLS reverse proxy (nginx, Caddy, Traefik or a cloud load balancer). Back up the Postgres database daily; it holds everything.

## Business license

Set `MCPLEDGER_LICENSE_KEY` and restart. Settings > Plan shows the customer name, device limit and expiry. Keys are checked offline, so air-gapped installs work. An expired key falls back to the Community edition without losing data. To get one, open an issue titled "Business license" at https://github.com/mujtabajalil/mcpledger/issues.
