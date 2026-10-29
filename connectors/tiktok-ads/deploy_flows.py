"""Builds the four TikTok sync flows (same structure as the Snap / Google Ads ones) and creates them, turned off,
in the AlSanidi | Marketing solution.

  Get TikTok Campaigns       instant (manual): each advertiser ID -> advertiser info -> campaigns -> upsert
  Get TikTok Ad Groups       when a TikTok Campaign is added or modified -> its ad groups -> upsert
  Get TikTok Advertisements  when a TikTok Ad Group is added or modified -> its ads -> upsert
  Get TikTok Insights        instant (manual): all-time insights for the three tables, insight columns only

  python3 deploy_flows.py              # write flows/*.json for review
  python3 deploy_flows.py --apply      # create flows that don't exist yet (turned off)
  python3 deploy_flows.py --apply --update-existing   # also replace existing flows' definitions
  python3 deploy_flows.py --apply --update-existing "--only=Get TikTok Insights"   # one flow
  (an update keeps the flow's connection references and its on/off state)

Every flow reads the TikTok Ads Access Token / Advertiser IDs environment variables and passes the token to the
TikTok actions. Deleted items are synced too (include_deleted). Choices are mapped with a Choice_maps compose
generated from spec.py (TikTok value -> option value). The instant flows end with Respond to a Power App or flow
so Sync Control can run them as child flows.
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from deploy_tables import SOLUTION  # noqa: E402

TT_API = "shared_sanidi-5ftiktok-5f43b530b23a0dc933"
DV_API = "shared_commondataserviceforapps"
TT_REF = "sanidi_sharedsanidi5ftiktok5f43b530b23a0dc933_3e7c1"
DV_REF = "sanidi_sharedcommondataserviceforapps_79822"  # existing Dataverse reference used by Snap/Meta/Google
NS = uuid.UUID("5c2e8a41-7d3b-4f96-a1e0-9b8c7d6e5f40")

ENV = {"access_token": "sanidi_TikTokAdsAccessToken", "advertiser_ids": "sanidi_TikTokAdsAdvertiserIds"}
ENV_DISPLAY = {"sanidi_TikTokAdsAccessToken": "TikTok Ads Access Token",
               "sanidi_TikTokAdsAdvertiserIds": "TikTok Ads Advertiser IDs"}


def p(key):
    schema = ENV[key]
    return f"parameters('{ENV_DISPLAY[schema]} ({schema})')"


TOKEN = {"Access-Token": f"@trim({p('access_token')})"}


def tiktok(op, params, run_after):
    return {"runAfter": run_after, "type": "OpenApiConnection", "inputs": {
        "parameters": {**TOKEN, **params},
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{TT_API}", "operationId": op,
                 "connectionName": TT_API}}}


def dataverse(op, params, run_after=None, paginate=False):
    a = {"type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DV_API}", "operationId": op,
                 "connectionName": DV_API}}}
    if run_after is not None:
        a["runAfter"] = run_after
    if paginate:
        a["runtimeConfiguration"] = {"paginationPolicy": {"minimumItemCount": 100000}}
    return a


def choice_maps(table):
    level = spec.TABLES[table]["level"]
    maps = {}
    for col, _, _, kind, src in spec.TABLES[table]["columns"]:
        if kind in ("enum", "enums"):
            maps[spec.PREFIX + col] = {o["label"]: o["value"] for o in spec.enum_options(level, src)}
    return {"runAfter": {}, "type": "Compose", "inputs": maps,
            "description": "TikTok value -> Dataverse option value for every choice column"}


def data_columns(table):
    """Columns the data flows write: everything except the insight columns."""
    return [c for c in spec.TABLES[table]["columns"] if not c[2].startswith("insights") and c[0] != "insightslastsyncedon"]


def row_mapping(table, row, extra):
    """item/<column> parameters for Create/Update, plus the Select/Query actions multi-selects need."""
    params, pre, prev = {}, {}, None
    for col, _, _, kind, _ in data_columns(table):
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
        elif col == spec.TABLES[table]["primary"]:
            # TikTok names can be empty (e.g. Promote items): fall back to the ID.
            tid = spec.TABLES[table]["tiktokid"]
            params["item/" + field] = f"@coalesce({value}, concat('{spec.TABLES[table]['display']} ', {row}?['{tid}']))"
        else:
            params["item/" + field] = f"@{value}"
    for name in pre:  # chain the multi-select helpers one after another
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
        "$filter": f"{spec.PREFIX}{t['tiktokid']} eq '@{{{row}?['{t['tiktokid']}']}}'", "$top": 1},
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


def definition(triggers, actions):
    return {"properties": {
        "connectionReferences": {
            TT_API: {"api": {"name": TT_API, "logicalName": "sanidi_tiktok"},
                     "connection": {"connectionReferenceLogicalName": TT_REF}, "runtimeSource": "embedded"},
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


MANUAL = {"manual": {"type": "Request", "kind": "Button",
                     "inputs": {"schema": {"type": "object", "properties": {}, "required": []}}}}


def respond(run_after):
    return {"runAfter": {run_after: ["Succeeded"]}, "type": "Response", "kind": "PowerApp",
            "inputs": {"statusCode": 200, "body": {}, "schema": {"type": "object", "properties": {}}}}


def advertiser_ids(run_after):
    """The advertiser IDs environment variable as a clean array (spaces and empty entries removed)."""
    return {
        "Advertiser_ID_list": {
            "type": "Select", "runAfter": run_after,
            "inputs": {"from": f"@split(coalesce({p('advertiser_ids')}, ''), ',')", "select": "@trim(item())"}},
        "Advertiser_IDs": {
            "type": "Query", "runAfter": {"Advertiser_ID_list": ["Succeeded"]},
            "inputs": {"from": "@body('Advertiser_ID_list')", "where": "@not(empty(item()))"}},
    }


def currency_bind(expr):
    return {"item/transactioncurrencyid@odata.bind": f"/transactioncurrencies(@{{{expr}}})"}


def flow_campaigns():
    actions = {
        "Choice_maps": choice_maps("tiktokcampaign"),
        "Base_currency": dataverse("ListRecords", {
            "entityName": "organizations", "$select": "_basecurrencyid_value", "$top": 1},
            {"Choice_maps": ["Succeeded"]}),
        **advertiser_ids({"Base_currency": ["Succeeded"]}),
        "For_each_advertiser": {
            "type": "Foreach", "runAfter": {"Advertiser_IDs": ["Succeeded"]},
            "foreach": "@body('Advertiser_IDs')",
            "runtimeConfiguration": {"concurrency": {"repetitions": 1}},
            "actions": {
                "Get_advertiser_info": tiktok("GetAdvertiserInfo", {
                    "advertiser_id": "@items('For_each_advertiser')"}, {}),
                "Advertiser_currency": dataverse("ListRecords", {
                    "entityName": "transactioncurrencies", "$select": "transactioncurrencyid",
                    "$filter": "isocurrencycode eq '@{outputs('Get_advertiser_info')?['body/currency']}'", "$top": 1},
                    {"Get_advertiser_info": ["Succeeded"]}),
                "List_campaigns": tiktok("ListCampaigns", {
                    "advertiser_id": "@items('For_each_advertiser')", "include_deleted": True},
                    {"Advertiser_currency": ["Succeeded"]}),
                **upsert_loop(
                    "tiktokcampaign", "For_each_campaign", "@coalesce(outputs('List_campaigns')?['body/rows'], json('[]'))",
                    "campaign",
                    currency_bind("coalesce(first(outputs('Advertiser_currency')?['body/value'])?['transactioncurrencyid'], "
                                  "first(outputs('Base_currency')?['body/value'])?['_basecurrencyid_value'])"),
                    {"List_campaigns": ["Succeeded"]}),
            }},
        "Respond_to_a_Power_App_or_flow": respond("For_each_advertiser"),
    }
    return definition(MANUAL, actions)


def flow_children(table, parent, list_op, filter_param, filter_col, loop, row_name):
    parent_logical = spec.PREFIX + parent
    trigger_name = f"When_a_{spec.TABLES[parent]['display'].replace(' ', '_')}_is_added_or_modified"
    actions = {
        "Choice_maps": choice_maps(table),
        f"List_{row_name}s": tiktok(list_op, {
            "advertiser_id": "@triggerOutputs()?['body/sanidi_advertiserid']",
            filter_param: f"@triggerOutputs()?['body/{filter_col}']", "include_deleted": True},
            {"Choice_maps": ["Succeeded"]}),
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


# Insights flow: (connector level, table, name used in action names)
INSIGHT_LEVELS = [
    ("campaign", "tiktokcampaign", "Campaigns"),
    ("adgroup", "tiktokadgroup", "AdGroups"),
    ("ad", "tiktokadvertisement", "Ads"),
]


def flow_insights():
    """Instant: all-time insights for every TikTok record, written to the insight columns only."""
    actions = {}
    prev = None
    for _, _, name in INSIGHT_LEVELS:
        actions[f"Init_{name}_insights"] = {
            "type": "InitializeVariable", "runAfter": {prev: ["Succeeded"]} if prev else {},
            "inputs": {"variables": [{"name": f"{name}Insights", "type": "array", "value": []}]}}
        prev = f"Init_{name}_insights"
    actions["Init_merge"] = {"type": "InitializeVariable", "runAfter": {prev: ["Succeeded"]},
                             "inputs": {"variables": [{"name": "Merge", "type": "array", "value": []}]}}
    actions.update(advertiser_ids({"Init_merge": ["Succeeded"]}))
    # One lifetime report per level and advertiser.
    per_advertiser, prev = {}, None
    for level, _, name in INSIGHT_LEVELS:
        get = f"Get_{name}_insights"
        per_advertiser[get] = tiktok("GetLifetimeInsights", {
            "advertiser_id": "@items('For_each_advertiser')", "level": level},
            {prev: ["Succeeded"]} if prev else {})
        per_advertiser[f"Merge_{name}"] = {
            "type": "SetVariable", "runAfter": {get: ["Succeeded"]},
            "inputs": {"name": "Merge", "value": f"@union(variables('{name}Insights'), "
                                                f"coalesce(outputs('{get}')?['body/rows'], json('[]')))"}}
        per_advertiser[f"Store_{name}"] = {
            "type": "SetVariable", "runAfter": {f"Merge_{name}": ["Succeeded"]},
            "inputs": {"name": f"{name}Insights", "value": "@variables('Merge')"}}
        prev = f"Store_{name}"
    actions["For_each_advertiser"] = {
        "type": "Foreach", "runAfter": {"Advertiser_IDs": ["Succeeded"]},
        "foreach": "@body('Advertiser_IDs')", "actions": per_advertiser,
        "runtimeConfiguration": {"concurrency": {"repetitions": 1}}}
    prev = "For_each_advertiser"
    # Like Get Google Ads Insights: list the records, then update each one's insight columns.
    metric_cols = [c[0] for c in spec.synced_metrics()] + ["insightslastsyncedon"]
    for _, table, name in INSIGHT_LEVELS:
        tbl = spec.TABLES[table]
        entity_set = spec.PREFIX + table + "s"
        tid = tbl["tiktokid"]
        pk = f"{spec.PREFIX}{table}id"
        lst, loop, flt = f"List_TikTok_{name}", f"For_each_{name}", f"Insights_{name}"
        actions[lst] = dataverse("ListRecords", {
            "entityName": entity_set, "$select": f"{pk},{spec.PREFIX}{tid}",
            "$filter": f"{spec.PREFIX}{tid} ne null"}, {prev: ["Succeeded"]}, paginate=True)
        rec = f"items('{loop}')"
        params = {"entityName": entity_set, "recordId": f"@{rec}?['{pk}']",
                  **{f"item/{spec.PREFIX}{c}": f"@first(body('{flt}'))?['{c}']" for c in metric_cols}}
        actions[loop] = {
            "type": "Foreach", "runAfter": {lst: ["Succeeded"]},
            "foreach": f"@outputs('{lst}')?['body/value']",
            "runtimeConfiguration": {"concurrency": {"repetitions": 10}},
            "actions": {
                flt: {"type": "Query", "runAfter": {},
                      "inputs": {"from": f"@variables('{name}Insights')",
                                 "where": f"@equals(item()?['{tid}'], {rec}?['{spec.PREFIX}{tid}'])"}},
                f"If_{name}_has_insights": {
                    "type": "If", "runAfter": {flt: ["Succeeded"]},
                    "expression": {"and": [{"greater": [f"@length(body('{flt}'))", 0]}]},
                    "actions": {f"Update_{name}_insights": dataverse("UpdateOnlyRecord", params)},
                    "else": {"actions": {}}},
            }}
        prev = loop
    actions["Respond_to_a_Power_App_or_flow"] = respond(prev)
    return definition(MANUAL, actions)


FLOWS = {
    "Get TikTok Campaigns": (flow_campaigns, "Instant: syncs all TikTok campaigns (including deleted) of every "
                             "advertiser in TikTok Ads Advertiser IDs into TikTok Campaign records."),
    "Get TikTok Ad Groups": (lambda: flow_children(
        "tiktokadgroup", "tiktokcampaign", "ListAdGroups", "campaign_id", "sanidi_campaignid",
        "For_each_ad_group", "ad_group"),
        "When a TikTok Campaign is added or modified: syncs its ad groups (including deleted) into TikTok Ad Group "
        "records."),
    "Get TikTok Advertisements": (lambda: flow_children(
        "tiktokadvertisement", "tiktokadgroup", "ListAds", "adgroup_id", "sanidi_adgroupid",
        "For_each_ad", "ad"),
        "When a TikTok Ad Group is added or modified: syncs its ads (including deleted) into TikTok Advertisement "
        "records."),
    "Get TikTok Insights": (flow_insights,
        "Manual: refreshes all-time TikTok insights (lifetime, no date breakdown) for every TikTok Campaign, Ad Group "
        "and Advertisement and writes the insight columns only."),
}


def main(apply, update_existing=False, only=None):
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
    if not dv.first(f"connectionreferences?$select=connectionreferenceid&$filter=connectionreferencelogicalname eq '{TT_REF}'"):
        dv.request("POST", "connectionreferences", {
            "connectionreferencelogicalname": TT_REF, "connectionreferencedisplayname": "TikTok AlSanidiMarketing",
            "connectorid": f"/providers/Microsoft.PowerApps/apis/{TT_API}"}, solution=SOLUTION)
        print(f"created connection reference {TT_REF}")
    for name, (clientdata, description) in built.items():
        if only and name not in only:
            continue
        existing = dv.first(f"workflows?$select=workflowid,statecode,clientdata&$filter=name eq '{name}' and category eq 5")
        body = {"name": name, "description": description, "clientdata": json.dumps(clientdata)}
        if existing and not update_existing:
            print(f"{name}: exists, left unchanged")
        elif existing:
            # Keep the connection references picked in the designer; replace only the definition.
            current = json.loads(existing["clientdata"])
            refs = current["properties"]["connectionReferences"]
            key_for_api = {v["api"]["name"]: k for k, v in refs.items()}
            text = json.dumps(clientdata["properties"]["definition"])
            for api in (TT_API, DV_API):
                if api in key_for_api:
                    text = text.replace(f'"connectionName": "{api}"', f'"connectionName": "{key_for_api[api]}"')
            clientdata["properties"]["definition"] = json.loads(text)
            clientdata["properties"]["connectionReferences"] = refs
            body["clientdata"] = json.dumps(clientdata)
            wid, was_on = existing["workflowid"], existing["statecode"] == 1
            if was_on:
                dv.request("PATCH", f"workflows({wid})", {"statecode": 0, "statuscode": 1})
            try:
                dv.request("PATCH", f"workflows({wid})", body, solution=SOLUTION)
            finally:
                # Never leave a flow switched off: turn it back on even when the save failed.
                if was_on:
                    dv.request("PATCH", f"workflows({wid})", {"statecode": 1, "statuscode": 2})
            print(f"updated {name} ({wid}){', turned back on' if was_on else ''}")
        else:
            wid = str(uuid.uuid5(NS, name))
            dv.request("POST", "workflows", {"workflowid": wid, "category": 5, "type": 1, "primaryentity": "none",
                                             **body}, solution=SOLUTION)
            print(f"created {name} ({wid}), turned off")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    main("--apply" in sys.argv, "--update-existing" in sys.argv, only or None)
