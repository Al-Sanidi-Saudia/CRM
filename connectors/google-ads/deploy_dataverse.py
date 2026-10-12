"""Creates or updates the Google Ads connector and its environment variables in the
AlSanidi | Marketing solution through the Dataverse Web API (no pac needed).

  python3 deploy_dataverse.py env-vars            # show what would be created
  python3 deploy_dataverse.py env-vars --apply    # create the environment variables
  python3 deploy_dataverse.py connector --apply   # create or update the connector

Environment variables (String). Their values are kept out of the solution so secrets are not exported:
  sanidi_GoogleAdsClientId, sanidi_GoogleAdsClientSecret, sanidi_GoogleAdsRefreshToken
      initial values copied from the legacy "Google Ads Sync" flow (never printed)
  sanidi_GoogleAdsDeveloperToken      set by you in make.powerapps.com
  sanidi_GoogleAdsLoginCustomerId     manager (MCC) ID; empty when not needed
Existing and reused: sanidi_GoogleAdsCustomerId, sanidi_GoogleAdsLastSyncStatus.
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

SOLUTION = "AlSanidiMarketing"
CONNECTOR_NAME = "sanidi_googleads"
LEGACY_FLOW_ID = "f1593d4c-4bc2-f111-aaaf-70a8a581e673"  # Google Ads Sync - Campaigns, Ad Groups, Ads & Insights

ENV_VARS = [
    ("sanidi_GoogleAdsClientId", "Google Ads Client ID",
     "Google Cloud OAuth client ID used by the Google Ads flows to get an access token.", "Init_varClientId"),
    ("sanidi_GoogleAdsClientSecret", "Google Ads Client Secret",
     "Google Cloud OAuth client secret used by the Google Ads flows to get an access token. Do not share.",
     "Init_varClientSecret"),
    ("sanidi_GoogleAdsRefreshToken", "Google Ads Refresh Token",
     "Google OAuth refresh token (adwords scope) used by the Google Ads flows to get an access token. "
     "Do not share.", "Init_varRefreshToken"),
    ("sanidi_GoogleAdsDeveloperToken", "Google Ads Developer Token",
     "Google Ads API developer token (Google Ads > Tools > API Center), sent on every Google Ads call.", None),
    ("sanidi_GoogleAdsLoginCustomerId", "Google Ads Login Customer ID",
     "Manager (MCC) account ID, without dashes, when the Ads account is reached through a manager. "
     "Leave empty otherwise.", None),
]


def legacy_values(dv):
    flow = dv.get(f"workflows({LEGACY_FLOW_ID})?$select=clientdata")
    actions = json.loads(flow["clientdata"])["properties"]["definition"]["actions"]
    out = {}
    for action_name in [a for *_, a in ENV_VARS if a]:
        value = actions[action_name]["inputs"]["variables"][0].get("value", "")
        out[action_name] = value.strip() if isinstance(value, str) and not value.startswith("@") else ""
    return out


def env_vars(dv, apply):
    values = legacy_values(dv)
    for schema, display, description, source in ENV_VARS:
        existing = dv.first("environmentvariabledefinitions?$select=environmentvariabledefinitionid"
                            f"&$filter=schemaname eq '{schema}'")
        value = values.get(source, "") if source else ""
        state = "exists" if existing else "create"
        print(f"{schema}: definition {state}; value "
              f"{'copied from legacy flow (' + str(len(value)) + ' chars)' if value else 'empty'}")
        if not apply:
            continue
        if existing:
            def_id = existing["environmentvariabledefinitionid"]
        else:
            _, entity = dv.request("POST", "environmentvariabledefinitions", {
                "schemaname": schema, "displayname": display, "description": description,
                "type": 100000000,  # String
            }, solution=SOLUTION)
            def_id = entity.split("(")[-1].rstrip(")")
        if value and not dv.first("environmentvariablevalues?$select=environmentvariablevalueid"
                                  f"&$filter=_environmentvariabledefinitionid_value eq {def_id}"):
            # No solution header: the value stays in this environment and is not exported with the solution.
            dv.request("POST", "environmentvariablevalues", {
                "schemaname": schema + "_value", "value": value,
                "EnvironmentVariableDefinitionId@odata.bind": f"/environmentvariabledefinitions({def_id})",
            })
            print(f"  value set")


def connector(dv, apply):
    swagger = (HERE / "apiDefinition.swagger.json").read_text()
    script = (HERE / "script.csx").read_text()
    props = json.loads((HERE / "apiProperties.json").read_text())["properties"]
    operations = [o["operationId"] for p in json.loads(swagger)["paths"].values() for o in p.values()]
    body = {
        "name": CONNECTOR_NAME,
        "displayname": "Google Ads",
        "description": json.loads(swagger)["info"]["description"],
        "connectortype": 1,
        "openapidefinition": swagger,
        "connectionparameters": json.dumps(props["connectionParameters"]),
        "policytemplateinstances": json.dumps(props.get("policyTemplateInstances", [])),
        "iconbrandcolor": props["iconBrandColor"],
        "customcodeblobcontent": script,
        "scriptoperations": json.dumps(operations),
    }
    existing = dv.first(f"connectors?$select=connectorid,connectorinternalid&$filter=name eq '{CONNECTOR_NAME}'")
    print(f"{CONNECTOR_NAME}: {'update ' + existing['connectorid'] if existing else 'create'}; "
          f"{len(operations)} operations, script {len(script)} chars")
    if not apply:
        return
    if existing:
        dv.request("PATCH", f"connectors({existing['connectorid']})", body, solution=SOLUTION)
        connector_id = existing["connectorid"]
    else:
        connector_id = str(uuid.uuid4())
        dv.request("POST", "connectors", {"connectorid": connector_id, **body}, solution=SOLUTION)
    row = dv.get(f"connectors({connector_id})?$select=name,displayname,connectorinternalid,scriptoperations")
    print(f"  connector {row['name']} / {row['displayname']} / internal id {row['connectorinternalid']}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("env-vars", "connector"):
        raise SystemExit(__doc__)
    {"env-vars": env_vars, "connector": connector}[sys.argv[1]](Dataverse(), "--apply" in sys.argv)
