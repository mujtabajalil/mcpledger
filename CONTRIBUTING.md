# Contributing to MCPLedger

Thanks for helping. Bug reports, new client config locations, detection rules and docs fixes are the most useful contributions.

## Licenses in this repository

| Path | License | Why |
|---|---|---|
| `cli/` | Apache-2.0 | Use it anywhere, embed it, ship it in your own tools |
| `server/`, `web/` (except `server/ee/`) | AGPL-3.0 | Free to self-host and modify; hosted forks must share their changes |
| `server/ee/` | MCPLedger Enterprise License | Source-available; production use needs a Business subscription or license key |

## Contributor License Agreement

Before we can merge your first pull request, you sign the [CLA](CLA.md) once, by commenting on the pull request when the CLA bot asks. It keeps your copyright with you and gives MCPLedger the right to ship your contribution under both the open-source licenses above and the commercial license, which is what pays for the project.

## Development

```bash
make setup     # Python venv + npm install
make dev-api   # API on :8000 (SQLite)
make dev-web   # dashboard on :4200
make test      # CLI + API tests
make e2e       # real CLI against the running API
```

Good first contributions:

- **A new AI tool's config location:** add it to `user_config_files`, `project_config_files` or `skill_roots` in `cli/src/mcpledger/discovery.py`, with a fixture in `cli/tests/conftest.py`.
- **A detection rule:** add it to `cli/src/mcpledger/rules.py` with one test that fires and one benign example that doesn't. The server reuses the same rules.

Keep pull requests small, include tests, and run `make test` before pushing. For anything security-sensitive, read [SECURITY.md](SECURITY.md) first.
