"""Builds an unmanaged solution package that adds the "Get Snap Ad Squads" cloud flow to
the "AlSanidi | Marketing" solution.

Trigger: Dataverse "When a row is added, modified or deleted" (added or modified) on
Snap Campaign. For that campaign the flow reads its ad squads from the Snap connector,
maps choice labels to option values, and uses List rows on Ad Squad ID to update the
existing Snap Ad Squad row or add a new one, linked to the campaign. Ad squads that no
longer come back from Snap are left in place.

Run:
  python3 build_flow_solution.py --template <template export zip> [--out GetSnapAdSquadsFlow.zip]
  pac solution import --path GetSnapAdSquadsFlow.zip --environment <env>

The flow reuses the existing connection references sanidi_snapconnection (Snap) and
sanidi_sharedcommondataserviceforapps_79822 (Dataverse), so it can run straight after import.
"""
import argparse
import json
import re
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_table_solution import FIELDS  # noqa: E402
from table_builder import solution_xml  # noqa: E402

FLOW_NAME = "Get Snap Ad Squads"
FLOW_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "alsanidi/flows/get-snap-ad-squads"))
TABLE_SET = "sanidi_snapadsquads"
CAMPAIGN_SET = "sanidi_snapcampaigns"
SNAP_API = "shared_sanidi-5fsnap-5f43b530b23a0dc933"
SNAP_CONNREF = "sanidi_snapconnection"
DATAVERSE_API = "shared_commondataserviceforapps"
DATAVERSE_CONNREF = "sanidi_sharedcommondataserviceforapps_79822"
LOOKUP = "sanidi_snapcampaign"

# Where each column's value sits in a Snap ad squad object.
SOURCE = {
    "sanidi_adsquadname": ["name"],
    "sanidi_adsquadid": ["id"],
    "sanidi_campaignid": ["campaign_id"],
    "sanidi_type": ["type"],
    "sanidi_childadtype": ["child_ad_type"],
    "sanidi_storyadcreativetype": ["story_ad_creative_type"],
    "sanidi_forcedviewsetting": ["forced_view_setting"],
    "sanidi_status": ["status"],
    "sanidi_deliverystatus": ["delivery_status"],
    "sanidi_reachandfrequencystatus": ["reach_and_frequency_status"],
    "sanidi_targetingreachstatus": ["targeting_reach_status"],
    "sanidi_creationstate": ["creation_state"],
    "sanidi_deleted": ["deleted"],
    "sanidi_starttime": ["start_time"],
    "sanidi_endtime": ["end_time"],
    "sanidi_createdat": ["created_at"],
    "sanidi_updatedat": ["updated_at"],
    "sanidi_dailybudget": ["daily_budget_micro"],
    "sanidi_lifetimebudget": ["lifetime_budget_micro"],
    "sanidi_deliveryconstraint": ["delivery_constraint"],
    "sanidi_pacingtype": ["pacing_type"],
    "sanidi_bidstrategy": ["bid_strategy"],
    "sanidi_bid": ["bid_micro"],
    "sanidi_billingevent": ["billing_event"],
    "sanidi_roasvalue": ["roas_value_micro"],
    "sanidi_autobid": ["auto_bid"],
    "sanidi_targetbid": ["target_bid"],
    "sanidi_optimizationgoal": ["optimization_goal"],
    "sanidi_conversionwindow": ["conversion_window"],
    "sanidi_reachgoal": ["reach_goal"],
    "sanidi_impressiongoal": ["impression_goal"],
    "sanidi_placementconfig": ["placement_v2", "config"],
    "sanidi_platforms": ["placement_v2", "platforms"],
    "sanidi_snapchatpositions": ["placement_v2", "snapchat_positions"],
    "sanidi_includedcontenttypes": ["placement_v2", "inclusion", "content_types"],
    "sanidi_excludedcontenttypes": ["placement_v2", "exclusion", "content_types"],
    "sanidi_brandsafetyinventory": ["brand_safety_config", "inventory_option"],
    "sanidi_targeting": ["targeting"],
    "sanidi_separatedtypes": ["separated_types"],
    "sanidi_capandexclusionconfig": ["cap_and_exclusion_config"],
    "sanidi_adschedulingconfig": ["ad_scheduling_config"],
    "sanidi_pixelid": ["pixel_id"],
    "sanidi_eventsources": ["event_sources"],
    "sanidi_measurementproviders": ["measurement_provider_names"],
    "sanidi_skadnetworkstatus": ["skadnetwork_properties", "status"],
    "sanidi_ecidenrollmentstatus": ["skadnetwork_properties", "ecid_enrollment_status"],
    "sanidi_enableskoverlay": ["skadnetwork_properties", "enable_skoverlay"],
    "sanidi_createdbyappid": ["created_by_app_id"],
    "sanidi_createdbyuser": ["created_by_user"],
}
assert set(SOURCE) | {LOOKUP} == {f[0] for f in FIELDS}, "every table column needs a source"

# Snap's docs spell this value with a space.
EXTRA_LABELS = {"sanidi_deliverystatus": {"LEARNING PHASE": 26}}


def choice_maps():
    maps = {}
    for name, _, kind, extra, _ in FIELDS:
        if kind in ("choice", "multichoice"):
            labels = extra[1] if kind == "multichoice" else extra
            maps[name] = {label: i for i, label in enumerate(labels, start=1)}
            maps[name].update(EXTRA_LABELS.get(name, {}))
    return maps


def src(path):
    return "outputs('Ad_squad')" + "".join(f"?['{p}']" for p in path)


def known(name):
    return f"Known_{name.replace('sanidi_', '')}"


def value_expr(field):
    name, _, kind, _, _ = field
    s = src(SOURCE[name])
    if kind == "choice":
        return f"@outputs('Choice_maps')?['{name}']?[string({s})]"
    if kind == "multichoice":
        return f"@if(empty(body('{known(name)}')), null, join(body('{known(name)}'), ','))"
    if kind in ("money", "decimal"):
        return f"@if(equals({s}, null), null, div(float({s}), 1000000))"
    if kind == "multiline":
        return f"@if(equals({s}, null), null, string({s}))"
    if name == "sanidi_separatedtypes":     # array or string -> comma-joined text
        return (f"@if(empty({s}), null, replace(replace(replace(string({s}), '[', ''), ']', ''), "
                f"'\"', ''))")
    return f"@{s}"


def dataverse(operation, params):
    return {"type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE_API}",
                 "operationId": operation, "connectionName": DATAVERSE_API}}}


def definition():
    columns = {f"item/{f[0]}": value_expr(f) for f in FIELDS if f[0] != LOOKUP}
    columns[f"item/{LOOKUP}@odata.bind"] = f"/{CAMPAIGN_SET}(@{{triggerOutputs()?['body/sanidi_snapcampaignid']}})"

    actions = {"Ad_squad": {"type": "Compose", "inputs": "@items('For_each_ad_squad')?['adsquad']", "runAfter": {}}}
    previous = "Ad_squad"
    for name, _, kind, _, _ in FIELDS:
        if kind != "multichoice":
            continue
        values = f"{known(name)}_values"
        actions[values] = {"type": "Select", "runAfter": {previous: ["Succeeded"]},
                           "inputs": {"from": f"@coalesce({src(SOURCE[name])}, json('[]'))",
                                      "select": f"@outputs('Choice_maps')?['{name}']?[item()]"}}
        actions[known(name)] = {"type": "Query", "runAfter": {values: ["Succeeded"]},
                                "inputs": {"from": f"@body('{values}')", "where": "@not(equals(item(), null))"}}
        previous = known(name)
    actions["Find_existing_ad_squad"] = {
        **dataverse("ListRecords", {"entityName": TABLE_SET, "$select": "sanidi_snapadsquadid",
                                    "$filter": f"sanidi_adsquadid eq '@{{{src(['id'])}}}'", "$top": 1}),
        "runAfter": {previous: ["Succeeded"]}}
    actions["If_ad_squad_exists"] = {
        "type": "If", "runAfter": {"Find_existing_ad_squad": ["Succeeded"]},
        "expression": {"and": [{"greater": ["@length(outputs('Find_existing_ad_squad')?['body/value'])", 0]}]},
        "actions": {"Update_ad_squad": {**dataverse("UpdateOnlyRecord", {
            "entityName": TABLE_SET,
            "recordId": "@first(outputs('Find_existing_ad_squad')?['body/value'])?['sanidi_snapadsquadid']",
            **columns}), "runAfter": {}}},
        "else": {"actions": {"Add_ad_squad": {**dataverse("CreateRecord", {
            "entityName": TABLE_SET, **columns}), "runAfter": {}}}}}

    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        "triggers": {"When_a_Snap_Campaign_is_added_or_modified": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "parameters": {"subscriptionRequest/message": 4,
                               "subscriptionRequest/entityname": "sanidi_snapcampaign",
                               "subscriptionRequest/scope": 4},
                "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE_API}",
                         "connectionName": DATAVERSE_API, "operationId": "SubscribeWebhookTrigger"},
                "authentication": "@parameters('$authentication')"}}},
        "actions": {
            "Choice_maps": {"type": "Compose", "inputs": choice_maps(), "runAfter": {},
                            "description": "Snap value -> Dataverse option value for every choice column"},
            "List_ad_squads": {
                "type": "OpenApiConnection", "runAfter": {"Choice_maps": ["Succeeded"]},
                "inputs": {"parameters": {"campaign_id": "@triggerOutputs()?['body/sanidi_campaignid']"},
                           "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{SNAP_API}",
                                    "operationId": "ListAdSquadsByCampaign", "connectionName": SNAP_API}}},
            "For_each_ad_squad": {
                "type": "Foreach", "foreach": "@coalesce(outputs('List_ad_squads')?['body/adsquads'], json('[]'))",
                "runAfter": {"List_ad_squads": ["Succeeded"]}, "actions": actions},
        },
    }


def flow_json():
    return {"properties": {
        "connectionReferences": {
            SNAP_API: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": SNAP_CONNREF},
                       "api": {"name": SNAP_API, "logicalName": "sanidi_snap"}},
            DATAVERSE_API: {"runtimeSource": "embedded",
                            "connection": {"connectionReferenceLogicalName": DATAVERSE_CONNREF},
                            "api": {"name": DATAVERSE_API}}},
        "definition": definition(),
        "templateName": ""},
        "schemaVersion": "1.0.0.0"}


CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/octet-stream" /><Default Extension="json" ContentType="application/octet-stream" /></Types>"""


def build(template_zip, out):
    src_zip = zipfile.ZipFile(template_zip)
    c = src_zip.read("customizations.xml").decode("utf-8-sig")
    root_open = re.match(r".*?<ImportExportXml[^>]*>", c, re.S).group(0)
    json_file = f"/Workflows/GetSnapAdSquads-{FLOW_ID.upper()}.json"
    customizations = f"""{root_open}
  <Entities />
  <Roles />
  <Workflows>
    <Workflow WorkflowId="{{{FLOW_ID}}}" Name="{FLOW_NAME}">
      <JsonFileName>{json_file}</JsonFileName>
      <Type>1</Type>
      <Subprocess>0</Subprocess>
      <Category>5</Category>
      <Mode>0</Mode>
      <Scope>4</Scope>
      <OnDemand>0</OnDemand>
      <TriggerOnCreate>0</TriggerOnCreate>
      <TriggerOnDelete>0</TriggerOnDelete>
      <AsyncAutodelete>0</AsyncAutodelete>
      <SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>
      <StateCode>1</StateCode>
      <StatusCode>2</StatusCode>
      <RunAs>1</RunAs>
      <IsTransacted>1</IsTransacted>
      <IntroducedVersion>1.0.0</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <BusinessProcessType>0</BusinessProcessType>
      <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>
      <ModernFlowType>0</ModernFlowType>
      <PrimaryEntity>none</PrimaryEntity>
      <LocalizedNames>
        <LocalizedName languagecode="1033" description="{FLOW_NAME}" />
      </LocalizedNames>
    </Workflow>
  </Workflows>
  <FieldSecurityProfiles />
  <Templates />
  <EntityMaps />
  <EntityRelationships />
  <OrganizationSettings />
  <optionsets />
  <CustomControls />
  <EntityDataProviders />
  <Languages>
    <Language>1033</Language>
  </Languages>
</ImportExportXml>
"""
    solution = solution_xml(src_zip.read("solution.xml").decode("utf-8-sig"),
                            [f'<RootComponent type="29" id="{{{FLOW_ID}}}" behavior="0" />'])
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("solution.xml", solution)
        z.writestr("customizations.xml", customizations)
        z.writestr(json_file.lstrip("/"), json.dumps(flow_json(), indent=2))
    print(f"Wrote {out}: flow {FLOW_ID}, {len(FIELDS)} mapped columns")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export (any) for the package skeleton")
    ap.add_argument("--out", default="GetSnapAdSquadsFlow.zip")
    a = ap.parse_args()
    build(a.template, a.out)
