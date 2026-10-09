#!/usr/bin/env bash
# Creates (or updates) the Snapchat Ads custom connector inside the
# "AlSanidi | Marketing" solution using the Power Platform CLI (pac).
#
# Usage:
#   SNAP_CLIENT_ID=... ./deploy.sh <environment-url> [solution-unique-name] [connector-id]
#
#   environment-url       e.g. https://alsanidi.crm4.dynamics.com
#   solution-unique-name  unique (not display) name of "AlSanidi | Marketing";
#                         find it with: pac solution list   (default: AlSanidiMarketing)
#   connector-id          pass to update an existing connector instead of creating one
set -euo pipefail

ENV_URL="${1:?environment URL required}"
SOLUTION="${2:-AlSanidiMarketing}"
CONNECTOR_ID="${3:-}"
: "${SNAP_CLIENT_ID:?set SNAP_CLIENT_ID to the Snap OAuth app client ID}"

DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$DIR/build_definition.py" >/dev/null
sed "s/REPLACE_WITH_SNAP_CLIENT_ID/${SNAP_CLIENT_ID}/" "$DIR/apiProperties.json" > "$WORK/apiProperties.json"

pac auth create --environment "$ENV_URL" >/dev/null 2>&1 || pac auth select --environment "$ENV_URL"

if [[ -n "$CONNECTOR_ID" ]]; then
  pac connector update \
    --connector-id "$CONNECTOR_ID" \
    --api-definition-file "$DIR/apiDefinition.swagger.json" \
    --api-properties-file "$WORK/apiProperties.json" \
    --solution-unique-name "$SOLUTION" \
    --environment "$ENV_URL"
else
  pac connector create \
    --api-definition-file "$DIR/apiDefinition.swagger.json" \
    --api-properties-file "$WORK/apiProperties.json" \
    --solution-unique-name "$SOLUTION" \
    --environment "$ENV_URL"
fi

echo "Done. Next: open the connector in make.powerapps.com, paste the Snap client secret"
echo "on the Security tab, Update connector, then register the shown Redirect URL in the Snap OAuth app."
