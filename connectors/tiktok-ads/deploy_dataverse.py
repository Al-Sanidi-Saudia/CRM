"""Creates or updates the TikTok connector and its environment variables in the AlSanidi | Marketing
solution through the Dataverse Web API (no pac needed).

  python3 deploy_dataverse.py env-vars            # show what would be created
  python3 deploy_dataverse.py env-vars --apply    # create the environment variables (no values)
  python3 deploy_dataverse.py connector --apply   # create or update the connector
  python3 deploy_dataverse.py token --auth-code <code> [--apply]
      exchanges an authorization code for the long-term access token (App ID / App Secret are read from
      their environment variables) and writes TikTok Ads Access Token and TikTok Ads Advertiser IDs

Environment variables (String). Their values are kept out of the solution so secrets are not exported:
  sanidi_TikTokAdsAppId, sanidi_TikTokAdsAppSecret, sanidi_TikTokAdsAccessToken, sanidi_TikTokAdsAdvertiserIds
The legacy sync's sanidi_TikTokAccessToken / sanidi_TikTokAdvertiserIds are not touched.
"""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

SOLUTION = "AlSanidiMarketing"
CONNECTOR_NAME = "sanidi_tiktok"

ENV_VARS = [
    ("sanidi_TikTokAdsAppId", "TikTok Ads App ID",
     "App ID of the TikTok for Business developer app used by the TikTok flows."),
    ("sanidi_TikTokAdsAppSecret", "TikTok Ads App Secret",
     "Secret of the TikTok for Business developer app. Only needed to get or check the access token. Do not share."),
    ("sanidi_TikTokAdsAccessToken", "TikTok Ads Access Token",
     "Long-term TikTok API for Business access token, sent on every TikTok call by the TikTok flows. Do not share."),
    ("sanidi_TikTokAdsAdvertiserIds", "TikTok Ads Advertiser IDs",
     "Comma-separated TikTok advertiser (ad account) IDs synced by the Get TikTok Campaigns and Get TikTok "
     "Insights flows."),
]


def definition_id(dv, schema):
    row = dv.first("environmentvariabledefinitions?$select=environmentvariabledefinitionid"
                   f"&$filter=schemaname eq '{schema}'")
    return row["environmentvariabledefinitionid"] if row else None


def env_vars(dv, apply):
    for schema, display, description in ENV_VARS:
        existing = definition_id(dv, schema)
        print(f"{schema}: definition {'exists' if existing else 'create'}")
        if apply and not existing:
            dv.request("POST", "environmentvariabledefinitions", {
                "schemaname": schema, "displayname": display, "description": description,
                "type": 100000000,  # String
            }, solution=SOLUTION)
            print("  created")


def get_value(dv, schema):
    def_id = definition_id(dv, schema)
    row = def_id and dv.first("environmentvariablevalues?$select=value"
                              f"&$filter=_environmentvariabledefinitionid_value eq {def_id}")
    return (row or {}).get("value") or ""


def set_value(dv, schema, value):
    """Sets the current value. No solution header: the value stays in this environment."""
    def_id = definition_id(dv, schema)
    if not def_id:
        raise SystemExit(f"{schema} does not exist; run env-vars --apply first")
    row = dv.first("environmentvariablevalues?$select=environmentvariablevalueid"
                   f"&$filter=_environmentvariabledefinitionid_value eq {def_id}")
    if row:
        dv.request("PATCH", f"environmentvariablevalues({row['environmentvariablevalueid']})", {"value": value})
    else:
        dv.request("POST", "environmentvariablevalues", {
            "schemaname": schema + "_value", "value": value,
            "EnvironmentVariableDefinitionId@odata.bind": f"/environmentvariabledefinitions({def_id})",
        })


def token(dv, apply, auth_code):
    app_id, secret = get_value(dv, "sanidi_TikTokAdsAppId"), get_value(dv, "sanidi_TikTokAdsAppSecret")
    if not (app_id and secret and auth_code):
        raise SystemExit("Set TikTok Ads App ID and TikTok Ads App Secret first, and pass --auth-code <code>.")
    print("will exchange the auth code (TikTok /oauth2/access_token/) and store the token and advertiser IDs")
    if not apply:
        return
    req = urllib.request.Request(
        "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
        data=json.dumps({"app_id": app_id, "secret": secret, "auth_code": auth_code}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("code") != 0 or not (body.get("data") or {}).get("access_token"):
        raise SystemExit(f"TikTok refused the code: {body.get('code')} {body.get('message')}")
    data = body["data"]
    ids = ",".join(str(i) for i in data.get("advertiser_ids") or [])
    set_value(dv, "sanidi_TikTokAdsAccessToken", data["access_token"])
    set_value(dv, "sanidi_TikTokAdsAdvertiserIds", ids)
    print(f"stored the access token ({len(data['access_token'])} chars) and advertiser IDs: {ids}")


def connector(dv, apply):
    swagger = (HERE / "apiDefinition.swagger.json").read_text()
    script = (HERE / "script.csx").read_text()
    props = json.loads((HERE / "apiProperties.json").read_text())["properties"]
    operations = [o["operationId"] for p in json.loads(swagger)["paths"].values() for o in p.values()]
    body = {
        "name": CONNECTOR_NAME,
        "displayname": "TikTok",
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
    if len(sys.argv) < 2 or sys.argv[1] not in ("env-vars", "connector", "token"):
        raise SystemExit(__doc__)
    apply = "--apply" in sys.argv
    dv = Dataverse()
    if sys.argv[1] == "token":
        code = sys.argv[sys.argv.index("--auth-code") + 1] if "--auth-code" in sys.argv else ""
        token(dv, apply, code)
    else:
        {"env-vars": env_vars, "connector": connector}[sys.argv[1]](dv, apply)
