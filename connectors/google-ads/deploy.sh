#!/usr/bin/env bash
# Creates (or updates) the Google Ads custom connector inside the
# "AlSanidi | Marketing" solution using the Power Platform CLI (pac).
#
# Usage:
#   ./deploy.sh <environment-url> [solution-unique-name] [connector-id]
#
#   environment-url       e.g. https://operations-alsenidiuat.crm4.dynamics.com
#   solution-unique-name  unique (not display) name of "AlSanidi | Marketing" (default: AlSanidiMarketing)
#   connector-id          pass to update an existing connector instead of creating one
set -euo pipefail

ENV_URL="${1:?environment URL required}"
SOLUTION="${2:-AlSanidiMarketing}"
CONNECTOR_ID="${3:-}"

DIR="$(cd "$(dirname "$0")" && pwd)"

# Sign in only if there is no auth profile yet (opens a browser).
pac org who >/dev/null 2>&1 || pac auth create --environment "$ENV_URL"

ARGS=(--api-definition-file "$DIR/apiDefinition.swagger.json"
      --api-properties-file "$DIR/apiProperties.json"
      --script-file "$DIR/script.csx"
      --solution-unique-name "$SOLUTION"
      --environment "$ENV_URL")
if [[ -n "$CONNECTOR_ID" ]]; then
  pac connector update --connector-id "$CONNECTOR_ID" "${ARGS[@]}"
else
  pac connector create "${ARGS[@]}"
fi

echo "Done. The connector needs no sign-in: create a connection and run 'Get access token'."
