#!/usr/bin/env bash
# Creates (or updates) the Google Ads custom connector inside the
# "AlSanidi | Marketing" solution using the Power Platform CLI (pac).
#
# Usage:
#   GOOGLE_CLIENT_ID=... GOOGLE_ADS_DEVELOPER_TOKEN=... ./deploy.sh <environment-url> [solution-unique-name] [connector-id]
#
#   environment-url       e.g. https://operations-alsenidiuat.crm4.dynamics.com
#   solution-unique-name  unique (not display) name of "AlSanidi | Marketing" (default: AlSanidiMarketing)
#   connector-id          pass to update an existing connector instead of creating one
set -euo pipefail

ENV_URL="${1:?environment URL required}"
SOLUTION="${2:-AlSanidiMarketing}"
CONNECTOR_ID="${3:-}"
: "${GOOGLE_CLIENT_ID:?set GOOGLE_CLIENT_ID to the Google OAuth client ID}"
: "${GOOGLE_ADS_DEVELOPER_TOKEN:?set GOOGLE_ADS_DEVELOPER_TOKEN to the Google Ads developer token}"

DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT  # the script copy holds the developer token

sed "s|REPLACE_WITH_GOOGLE_CLIENT_ID|${GOOGLE_CLIENT_ID}|" "$DIR/apiProperties.json" > "$WORK/apiProperties.json"
sed "s|REPLACE_WITH_DEVELOPER_TOKEN|${GOOGLE_ADS_DEVELOPER_TOKEN}|" "$DIR/script.csx" > "$WORK/script.csx"

# Sign in only if there is no auth profile yet (opens a browser).
pac org who >/dev/null 2>&1 || pac auth create --environment "$ENV_URL"

ARGS=(--api-definition-file "$DIR/apiDefinition.swagger.json"
      --api-properties-file "$WORK/apiProperties.json"
      --script-file "$WORK/script.csx"
      --solution-unique-name "$SOLUTION"
      --environment "$ENV_URL")
if [[ -n "$CONNECTOR_ID" ]]; then
  pac connector update --connector-id "$CONNECTOR_ID" "${ARGS[@]}"
else
  pac connector create "${ARGS[@]}"
fi

echo "Done. Next: open the connector in make.powerapps.com, paste the Google client secret"
echo "on the Security tab, Update connector, then add the shown Redirect URL to the Google OAuth client."
