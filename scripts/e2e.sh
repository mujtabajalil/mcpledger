#!/usr/bin/env bash
# End-to-end test: real CLI against a running server, using a throwaway HOME.
#   scripts/e2e.sh http://localhost:8000
# Uses a tiny local stdio MCP server (cli/tests/fake_mcp_server.py), so nothing is downloaded.
set -euo pipefail
SERVER="${1:-http://localhost:8000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
WORK="$(mktemp -d)"
export HOME="$WORK/home" MCPLEDGER_HOME="$WORK/home/.mcpledger" XDG_CONFIG_HOME="$WORK/home/.config" NO_COLOR=1
mkdir -p "$HOME/.cursor" "$HOME/.claude/skills/notes"
SG="$PY -m mcpledger"
cd "$WORK"

cat > "$HOME/.cursor/mcp.json" <<EOF
{"mcpServers": {"calc": {"command": "$PY", "args": ["$ROOT/cli/tests/fake_mcp_server.py"]}}}
EOF
printf -- '---\nname: notes\ndescription: Take meeting notes.\n---\nSummarise the meeting.\n' > "$HOME/.claude/skills/notes/SKILL.md"

step() { echo; echo "== $*"; }
api() { curl -sf -b "$WORK/cj" -c "$WORK/cj" -H "Origin: $SERVER" -H 'Content-Type: application/json' "$@"; }

step "sign up an admin and fetch the enroll token"
EMAIL="e2e-$(date +%s)@example.dev"
api -X POST "$SERVER/api/auth/signup" -d "{\"email\":\"$EMAIL\",\"password\":\"e2e-password-1\",\"org_name\":\"E2E\"}" >/dev/null
TOKEN=$(api "$SERVER/api/org" | $PY -c 'import sys,json;print(json.load(sys.stdin)["enroll_token"])')

step "enroll + scan --introspect"
$SG enroll "$TOKEN" --server "$SERVER" --email dev@example.dev
$SG scan --introspect --timeout 10

step "check in monitor mode passes (exit 0)"
$SG check --quiet && echo "exit 0 as expected"

step "approve everything that was reported"
for id in $(api "$SERVER/api/components" | $PY -c 'import sys,json;print(" ".join(c["id"] for c in json.load(sys.stdin)))'); do
  api -X POST "$SERVER/api/components/$id/approve" -d '{}' >/dev/null
done
api -X PATCH "$SERVER/api/org/policy" -d '{"policy_mode":"enforce","default_action":"block"}' >/dev/null
$SG check --introspect --quiet && echo "enforce + all approved: exit 0"

step "rug pull: the same server starts advertising a poisoned tool description"
$PY - "$HOME/.cursor/mcp.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["mcpServers"]["calc"]["env"] = {"FAKE_POISON": "1"}
json.dump(d, open(p, "w"))
EOF
set +e; $SG check --introspect; rc=$?; set -e
[ "$rc" = "1" ] && echo "check failed with exit 1 as expected" || { echo "expected exit 1, got $rc"; exit 1; }
api "$SERVER/api/events" | $PY -c 'import sys,json;e=[x for x in json.load(sys.stdin) if x["type"]=="drift"];print("alert:",e[0]["severity"],e[0]["title"])'

step "block the server, then fix removes it from the config"
CID=$(api "$SERVER/api/components" | $PY -c 'import sys,json;print([c["id"] for c in json.load(sys.stdin) if c["kind"]=="mcp_server"][0])')
api -X POST "$SERVER/api/components/$CID/block" -d '{"note":"poisoned in e2e"}' >/dev/null
$SG fix
$SG fix --yes
$PY -c "import json;d=json.load(open('$HOME/.cursor/mcp.json'));assert 'calc' not in d['mcpServers'];print('calc removed from ~/.cursor/mcp.json')"
ls "$MCPLEDGER_HOME/quarantine"/*/mcp.json.bak >/dev/null && echo "backup kept"

step "audit trail"
api "$SERVER/api/audit" | $PY -c 'import sys,json;[print(" ",a["action"],a["target"]) for a in reversed(json.load(sys.stdin))]'
echo; echo "E2E PASSED"
rm -rf "$WORK"
