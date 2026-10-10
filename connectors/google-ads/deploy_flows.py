"""Builds the three Google Ads sync flows (same structure as the Snap ones) and creates them, turned off,
in the AlSanidi | Marketing solution.

  Get Google Ads Campaigns       instant (manual): token -> client accounts -> campaigns -> upsert
  Get Google Ads Ad Groups       when a Google Ads Campaign is added or modified -> ad groups -> upsert
  Get Google Ads Advertisements  when a Google Ads Ad Group is added or modified -> ads -> upsert

  python3 deploy_flows.py              # write flows/*.json for review
  python3 deploy_flows.py --apply      # also create/update the connection reference and the flows (off)

Every flow starts with the connector's "Get access token" (client ID / secret / refresh token from
environment variables) and passes the token and the developer token to the Google Ads actions.
Choices are mapped with a Choice_maps compose generated from spec.py (Google value -> option value).
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from deploy_tables import SOLUTION  # noqa: E402

GADS_API = "shared_sanidi-5fgoogle-20ads-5f43b530b23a0dc933"
DV_API = "shared_commondataserviceforapps"
GADS_CONN = "shared_sanidi-5fgoogle-20ads-5f43b530b23a0dc933-1"
GADS_REF = "sanidi_googleads_connref"
DV_REF = "sanidi_sharedcommondataserviceforapps_79822"  # existing Dataverse reference used by Snap/Meta
NS = uuid.UUID("0b9a3d7e-2f41-4c55-9c1e-7a8b6d5e4f32")

ENV = {  # parameter name in the flow -> env var schema name
    "client_id": "sanidi_GoogleAdsClientId",
    "client_secret": "sanidi_GoogleAdsClientSecret",
    "refresh_token": "sanidi_GoogleAdsRefreshToken",
    "developer_token": "sanidi_GoogleAdsDeveloperToken",
    "login_customer_id": "sanidi_GoogleAdsLoginCustomerId",
    "customer_id": "sanidi_GoogleAdsCustomerId",
}
ENV_DISPLAY = {
    "sanidi_GoogleAdsClientId": "Google Ads Client ID", "sanidi_GoogleAdsClientSecret": "Google Ads Client Secret",
    "sanidi_GoogleAdsRefreshToken": "Google Ads Refresh Token",
    "sanidi_GoogleAdsDeveloperToken": "Google Ads Developer Token",
    "sanidi_GoogleAdsLoginCustomerId": "Google Ads Login Customer ID",
    "sanidi_GoogleAdsCustomerId": "Google Ads Customer ID",
}


def p(key):
    schema = ENV[key]
    return f"parameters('{ENV_DISPLAY[schema]} ({schema})')"


def gads(op, params, run_after):
    return {"runAfter": run_after, "type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{GADS_API}", "operationId": op,
                 "connectionName": GADS_CONN}}}


def dataverse(op, params, run_after=None):
    a = {"type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DV_API}", "operationId": op,
                 "connectionName": DV_API}}}
    if run_after is not None:
        a["runAfter"] = run_after
    return a


def tokens():
    login = (f"@if(empty(trim(coalesce({p('login_customer_id')}, ''))), "
             f"replace({p('customer_id')}, '-', ''), replace({p('login_customer_id')}, '-', ''))")
    return {"access-token": "@body('Get_access_token')?['access_token']",
            "developer-token": f"@{p('developer_token')}", "login-customer-id": login}


def choice_maps(table):
    maps = {}
    for col, _, _, kind, src in spec.TABLES[table]["columns"]:
        if kind in ("enum", "enums"):
            maps[spec.PREFIX + col] = {o["label"]: o["value"] for o in spec.enum_options(src)}
    return {"runAfter": {}, "type": "Compose", "inputs": maps,
            "description": "Google Ads value -> Dataverse option value for every choice column"}


def row_mapping(table, row, extra):
    """item/<column> parameters for Create/Update, plus the Select/Query actions multi-selects need."""
    t = spec.TABLES[table]
    params, pre = {}, {}
    prev = None
    for col, _, _, kind, _ in t["columns"]:
        field = spec.PREFIX + col
        value = f"{row}?['{col}']"
        if kind == "enum":
            params["item/" + field] = f"@outputs('Choice_maps')?['{field}']?[string({value})]"
        elif kind == "enums":
            sel, qry = f"Known_{col}_values", f"Known_{col}"
            pre[sel] = {"type": "Select", "inputs": {
                "from": f"@coalesce({value}, json('[]'))",
                "select": f"@outputs('Choice_maps')?['{field}']?[item()]"}}
            pre[qry] = {"type": "Query", "inputs": {"from": f"@body('{sel}')", "where": "@not(equals(item(), null))"}}
            params["item/" + field] = f"@if(empty(body('{qry}')), null, join(body('{qry}'), ','))"
        elif col == "adname":
            params["item/" + field] = (
                f"@coalesce({value}, if(empty({row}?['headlines']), null, "
                f"first(split({row}?['headlines'], decodeUriComponent('%0A')))), concat('Ad ', {row}?['adid']))")
        else:
            params["item/" + field] = f"@{value}"
    # chain the multi-select helpers one after another
    for name in pre:
        pre[name]["runAfter"] = {prev: ["Succeeded"]} if prev else {}
        prev = name
    params.update(extra)
    return params, pre, prev


def upsert_loop(table, loop_name, items_expr, row_name, extra, run_after):
    t = spec.TABLES[table]
    entity_set = spec.PREFIX + table + "s"
    row = f"items('{loop_name}')"
    params, pre, last_pre = row_mapping(table, row, extra)
    find = f"Find_existing_{row_name}"
    actions = dict(pre)
    actions[find] = dataverse("ListRecords", {
        "entityName": entity_set, "$select": f"{spec.PREFIX}{table}id",
        "$filter": f"{spec.PREFIX}{t['googleid']} eq '@{{{row}?['{t['googleid']}']}}'", "$top": 1},
        {last_pre: ["Succeeded"]} if last_pre else {})
    actions[f"If_{row_name}_exists"] = {
        "type": "If", "runAfter": {find: ["Succeeded"]},
        "expression": {"and": [{"greater": [f"@length(outputs('{find}')?['body/value'])", 0]}]},
        "actions": {f"Update_{row_name}": dataverse("UpdateOnlyRecord", {
            "entityName": entity_set,
            "recordId": f"@first(outputs('{find}')?['body/value'])?['{spec.PREFIX}{table}id']", **params})},
        "else": {"actions": {f"Add_{row_name}": dataverse("CreateRecord", {"entityName": entity_set, **params})}},
    }
    return {loop_name: {"type": "Foreach", "foreach": items_expr, "runAfter": run_after, "actions": actions}}


def env_parameters():
    return {f"{ENV_DISPLAY[s]} ({s})": {"defaultValue": "", "type": "String", "metadata": {"schemaName": s}}
            for s in ENV.values()}


def get_token(run_after):
    return gads("GetAccessToken", {
        "body/client_id": f"@{p('client_id')}", "body/client_secret": f"@{p('client_secret')}",
        "body/refresh_token": f"@{p('refresh_token')}"}, run_after)


def definition(triggers, actions):
    return {"properties": {
        "connectionReferences": {
            GADS_CONN: {"api": {"name": GADS_API, "logicalName": "sanidi_googleads"},
                        "connection": {"connectionReferenceLogicalName": GADS_REF}, "runtimeSource": "embedded"},
            DV_API: {"api": {"name": DV_API},
                     "connection": {"connectionReferenceLogicalName": DV_REF}, "runtimeSource": "embedded"},
        },
        "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/"
                       "workflowdefinition.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {"$authentication": {"defaultValue": {}, "type": "SecureObject"},
                           "$connections": {"defaultValue": {}, "type": "Object"}, **env_parameters()},
            "triggers": triggers, "actions": actions},
        "templateName": ""},
        "schemaVersion": "1.0.0.0"}


def currency_bind(expr):
    return {"item/transactioncurrencyid@odata.bind": f"/transactioncurrencies(@{{{expr}}})"}


def flow_campaigns():
    t = tokens()
    actions = {
        "Choice_maps": choice_maps("googleadscampaign"),
        "Get_access_token": get_token({"Choice_maps": ["Succeeded"]}),
        "Base_currency": dataverse("ListRecords", {
            "entityName": "organizations", "$select": "_basecurrencyid_value", "$top": 1},
            {"Get_access_token": ["Succeeded"]}),
        "List_client_accounts": gads("ListClientAccounts", {
            "customer_id": f"@replace({p('customer_id')}, '-', '')", **t},
            {"Base_currency": ["Succeeded"]}),
        "For_each_account": {
            "type": "Foreach", "runAfter": {"List_client_accounts": ["Succeeded"]},
            "foreach": "@outputs('List_client_accounts')?['body/rows']",
            "actions": {
                "Account_currency": dataverse("ListRecords", {
                    "entityName": "transactioncurrencies", "$select": "transactioncurrencyid",
                    "$filter": "isocurrencycode eq '@{items('For_each_account')?['currency_code']}'", "$top": 1}, {}),
                "List_campaigns": gads("ListCampaigns", {
                    "customer_id": "@items('For_each_account')?['customer_id']", **t,
                    "status": "ALL", "include_metrics": True}, {"Account_currency": ["Succeeded"]}),
                **upsert_loop(
                    "googleadscampaign", "For_each_campaign", "@outputs('List_campaigns')?['body/rows']",
                    "campaign",
                    currency_bind("coalesce(first(outputs('Account_currency')?['body/value'])?['transactioncurrencyid'], "
                                  "first(outputs('Base_currency')?['body/value'])?['_basecurrencyid_value'])"),
                    {"List_campaigns": ["Succeeded"]}),
            }},
    }
    triggers = {"manual": {"type": "Request", "kind": "Button",
                           "inputs": {"schema": {"type": "object", "properties": {}, "required": []}}}}
    return definition(triggers, actions)


def flow_children(table, parent, list_op, filter_param, filter_col, loop, row_name):
    parent_logical = spec.PREFIX + parent
    trigger_name = f"When_a_{spec.TABLES[parent]['display'].replace(' ', '_')}_is_added_or_modified"
    t = tokens()
    login = t.pop("login-customer-id")
    actions = {
        "Choice_maps": choice_maps(table),
        "Get_access_token": get_token({"Choice_maps": ["Succeeded"]}),
        f"List_{row_name}s": gads(list_op, {
            "customer_id": "@triggerOutputs()?['body/sanidi_customerid']", **t, "login-customer-id": login,
            filter_param: f"@triggerOutputs()?['body/{filter_col}']", "status": "ALL", "include_metrics": True},
            {"Get_access_token": ["Succeeded"]}),
        **upsert_loop(
            table, loop, f"@coalesce(outputs('List_{row_name}s')?['body/rows'], json('[]'))", row_name,
            {f"item/{parent_logical}@odata.bind": f"/{parent_logical}s(@{{triggerOutputs()?['body/{parent_logical}id']}})",
             **currency_bind("triggerOutputs()?['body/_transactioncurrencyid_value']")},
            {f"List_{row_name}s": ["Succeeded"]}),
    }
    triggers = {trigger_name: {"type": "OpenApiConnectionWebhook", "inputs": {
        "parameters": {"subscriptionRequest/message": 4, "subscriptionRequest/entityname": parent_logical,
                       "subscriptionRequest/scope": 4},
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DV_API}", "operationId": "SubscribeWebhookTrigger",
                 "connectionName": DV_API}}}}
    return definition(triggers, actions)


FLOWS = {
    "Get Google Ads Campaigns": (flow_campaigns, "Instant: syncs all Google Ads campaigns (all client accounts of "
                                 "the Google Ads Customer ID) into Google Ads Campaign records."),
    "Get Google Ads Ad Groups": (lambda: flow_children(
        "googleadsadgroup", "googleadscampaign", "ListAdGroups", "campaign_id", "sanidi_campaignid",
        "For_each_ad_group", "ad_group"),
        "When a Google Ads Campaign is added or modified: syncs its ad groups into Google Ads Ad Group records."),
    "Get Google Ads Advertisements": (lambda: flow_children(
        "googleadsadvertisement", "googleadsadgroup", "ListAds", "ad_group_id", "sanidi_adgroupid",
        "For_each_ad", "ad"),
        "When a Google Ads Ad Group is added or modified: syncs its ads into Google Ads Advertisement records."),
}


def main(apply):
    out = HERE / "flows"
    out.mkdir(exist_ok=True)
    built = {}
    for name, (build, description) in FLOWS.items():
        clientdata = build()
        built[name] = (clientdata, description)
        path = out / (name.lower().replace(" ", "-") + ".json")
        path.write_text(json.dumps(clientdata, indent=2) + "\n")
        actions = clientdata["properties"]["definition"]["actions"]
        print(f"{name}: {len(json.dumps(clientdata))} chars, top-level actions: {', '.join(actions)} -> {path.name}")
    if not apply:
        return
    from dv import Dataverse
    dv = Dataverse()
    if not dv.first(f"connectionreferences?$select=connectionreferenceid&$filter=connectionreferencelogicalname eq '{GADS_REF}'"):
        dv.request("POST", "connectionreferences", {
            "connectionreferencelogicalname": GADS_REF, "connectionreferencedisplayname": "Google Ads AlSanidiMarketing",
            "connectorid": f"/providers/Microsoft.PowerApps/apis/{GADS_API}"}, solution=SOLUTION)
        print(f"created connection reference {GADS_REF}")
    for name, (clientdata, description) in built.items():
        existing = dv.first(f"workflows?$select=workflowid,statecode&$filter=name eq '{name}' and category eq 5")
        body = {"name": name, "description": description, "clientdata": json.dumps(clientdata)}
        if existing:
            dv.request("PATCH", f"workflows({existing['workflowid']})", body, solution=SOLUTION)
            print(f"updated {name} ({existing['workflowid']})")
        else:
            wid = str(uuid.uuid5(NS, name))
            dv.request("POST", "workflows", {"workflowid": wid, "category": 5, "type": 1, "primaryentity": "none",
                                             **body}, solution=SOLUTION)
            print(f"created {name} ({wid}), turned off")


if __name__ == "__main__":
    main("--apply" in sys.argv)
