"""Builds an unmanaged solution package that adds the "Get Snap Insights" instant (manual)
cloud flow to the "AlSanidi | Marketing" solution.

Modeled on "Get Meta Insights": for Snap Campaigns, then Snap Ad Squads, then Snap
Advertisements, it lists the active rows that have a Snap ID, fetches each one's all-time
(LIFETIME) stats from the Snap connector (10 at a time), and updates only the insight
columns on that row. Entity columns are not touched, so this refreshes the numbers
without a full Get Snap Campaigns cascade. The insight columns and the stats/mapping logic
are shared with the sync flows (../snap_insights.py).

Run:
  python3 build_flow_solution.py --template <template export zip> [--out GetSnapInsightsFlow.zip]
  pac solution import --path GetSnapInsightsFlow.zip --environment <env>
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flow_builder import (DATAVERSE_API, DATAVERSE_CONNREF, SNAP_API, SNAP_CONNREF,  # noqa: E402
                          dataverse, package_flow)
from snap_insights import stats_actions, stats_columns  # noqa: E402

FLOW_NAME = "Get Snap Insights"
FLOW_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "alsanidi/flows/get-snap-insights"))

# (suffix, entity set, primary key, Snap ID column, Snap stats operation, operation parameter)
LEVELS = [
    ("Campaigns", "sanidi_snapcampaigns", "sanidi_snapcampaignid", "sanidi_campaignid",
     "GetCampaignStats", "campaign_id"),
    ("AdSquads", "sanidi_snapadsquads", "sanidi_snapadsquadid", "sanidi_adsquadid",
     "GetAdSquadStats", "ad_squad_id"),
    ("Ads", "sanidi_snapadvertisements", "sanidi_snapadvertisementid", "sanidi_adid",
     "GetAdStats", "ad_id"),
]


def definition():
    actions, previous = {}, None
    for suffix, entity_set, pk, snap_id, operation, parameter in LEVELS:
        list_name, loop = f"List_Snap_{suffix}", f"For_each_{suffix}"
        actions[list_name] = {
            **dataverse("ListRecords", {"entityName": entity_set, "$select": f"{pk},{snap_id}",
                                        "$filter": f"{snap_id} ne null and statecode eq 0"}),
            "runAfter": {previous: ["Succeeded"]} if previous else {},
            "runtimeConfiguration": {"paginationPolicy": {"minimumItemCount": 100000}},
        }
        inner = stats_actions(SNAP_API, operation, parameter, f"@items('{loop}')?['{snap_id}']", {},
                              suffix=f"_{suffix}")
        inner[f"Update_{suffix}_Insights"] = {
            **dataverse("UpdateOnlyRecord", {"entityName": entity_set, "recordId": f"@items('{loop}')?['{pk}']",
                                             **stats_columns(suffix=f"_{suffix}")}),
            "runAfter": {f"Lifetime_stats_{suffix}": ["Succeeded"]},
        }
        actions[loop] = {
            "type": "Foreach", "foreach": f"@outputs('{list_name}')?['body/value']",
            "runAfter": {list_name: ["Succeeded"]},
            "runtimeConfiguration": {"concurrency": {"repetitions": 10}},
            "actions": inner,
        }
        previous = loop
    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/"
                   "workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        "triggers": {"manual": {"type": "Request", "kind": "Button", "inputs": {
            "schema": {"type": "object", "properties": {}, "required": []}}}},
        "actions": actions,
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export (any) for the package skeleton")
    ap.add_argument("--out", default="GetSnapInsightsFlow.zip")
    a = ap.parse_args()
    package_flow(FLOW_NAME, FLOW_ID, flow_json(), a.template, a.out)
    print(f"Wrote {a.out}: flow {FLOW_NAME} {FLOW_ID}")
