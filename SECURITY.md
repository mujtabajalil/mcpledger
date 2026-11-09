# Security policy

MCPLedger is a security tool, so we treat reports about it with priority.

## Reporting a vulnerability

Email **security@mcpledger.dev** with steps to reproduce. Please don't open a public issue. You'll get a reply within 3 business days, and a fix or a plan within 30 days for confirmed issues. We credit reporters in release notes unless you'd rather we didn't.

In scope: the `mcpledger` CLI, the server and dashboard in this repository, and the hosted service at app.mcpledger.dev. Out of scope: denial of service by volume, findings that need a compromised developer machine, and social engineering.

## What the CLI sends

| Sent | Never sent |
|---|---|
| Names of MCP servers, commands and arguments, URLs | Values of environment variables or headers |
| Names of env vars and headers, plus a flag when a literal secret is present | Your source code |
| Tool names, descriptions and input schemas (only with `--introspect`) | Anything from servers you didn't configure |
| Skill files under 64 KB (hashes only with `--hashes-only`) | Files outside skill folders |
| Hostname, OS, username, CLI version | |

Run `mcpledger scan --json` to see exactly what a report contains before you enroll.

## Supported versions

Security fixes go into the latest release of the CLI and the server. Self-hosted installs should upgrade within 30 days of a security release.
