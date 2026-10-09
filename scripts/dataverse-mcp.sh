#!/usr/bin/env bash
# Starts the Dataverse MCP server, first creating the Dataverse CLI auth
# profile from DATAVERSE_* environment variables if it doesn't exist yet.
# stdout is reserved for the MCP protocol, so all setup output goes to stderr.
set -euo pipefail

export DATAVERSE_TELEMETRY_OPT_OUT=1
PKG="@microsoft/dataverse"
PROFILE="crm-claude"

# Tolerate values stored with JSON-style quotes or a trailing comma.
clean() { local v="${1:-}"; v="${v%,}"; v="${v#\"}"; v="${v%\"}"; printf '%s' "$v"; }

URL="$(clean "${DATAVERSE_URL:-https://operations-alsenidiuat.crm4.dynamics.com}")"
URL="${URL%/}"
TENANT="$(clean "${DATAVERSE_TENANT_ID:-}")"
CLIENT_ID="$(clean "${DATAVERSE_CLIENT_ID:-}")"
SECRET="$(clean "${DATAVERSE_CLIENT_SECRET:-}")"

if ! npx -y "$PKG" auth list 2>/dev/null | grep -q "$PROFILE"; then
  if [[ -z "$TENANT" || -z "$CLIENT_ID" || -z "$SECRET" ]]; then
    echo "dataverse-mcp: DATAVERSE_TENANT_ID, DATAVERSE_CLIENT_ID and DATAVERSE_CLIENT_SECRET must be set" >&2
    exit 1
  fi
  npx -y "$PKG" auth create --name "$PROFILE" --environment "$URL" \
    --applicationId "$CLIENT_ID" --clientSecret "$SECRET" --tenant "$TENANT" \
    --accept-cleartext-caching >&2
fi

exec npx -y "$PKG" --log-level Error mcp "$URL"
