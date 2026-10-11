import sys, json; sys.path.insert(0, sys.argv[1])
import dv

DV = {"apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "connectionName": "shared_commondataserviceforapps"}
REQ_ID = "@triggerOutputs()?['body/sanidi_integrationsyncrequestid']"

def dv_action(op, params, run_after):
    return {"type": "OpenApiConnection", "runAfter": run_after,
            "inputs": {"host": {**DV, "operationId": op}, "parameters": params,
                       "authentication": "@parameters('$authentication')"}}

def update_request(fields, run_after):
    params = {"entityName": "sanidi_integrationsyncrequests", "recordId": REQ_ID}
    params.update({"item/" + k: v for k, v in fields.items()})
    return dv_action("UpdateOnlyRecord", params, run_after)

def child(flow_id):
    return {"type": "Workflow", "runAfter": {}, "inputs": {"host": {"workflowReferenceName": flow_id}}}

# platform key - sync type (100000000 Data, 100000001 Insights) -> flow started
CASES = {
    "meta-100000000":   ("Run_Get_Meta_Campaigns", "8b6d991c-d3c0-f111-aaaf-70a8a581e673"),
    "meta-100000001":   ("Run_Get_Meta_Insights", "e30b9610-07c5-f111-aaaf-70a8a581e5c5"),
    "snap-100000000":   ("Run_Get_Snap_Campaigns", "f0adc814-8c13-5fe3-8ba7-9ad697ea4ea2"),
    "snap-100000001":   ("Run_Get_Snap_Insights", "028e8be8-505f-5f70-acc7-85653b1f859f"),
    "google-100000000": ("Run_Get_Google_Ads_Campaigns", "b10505e5-822c-5641-8499-e8324198b469"),
    "google-100000001": ("Run_Get_Google_Ads_Insights", "59399b2c-080a-50b0-afcf-b803145237cf"),
}

definition = {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {"$authentication": {"defaultValue": {}, "type": "SecureObject"},
                   "$connections": {"defaultValue": {}, "type": "Object"}},
    "triggers": {
        "When_a_sync_request_is_added": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {"host": {**DV, "operationId": "SubscribeWebhookTrigger"},
                       "parameters": {"subscriptionRequest/message": 1,
                                      "subscriptionRequest/entityname": "sanidi_integrationsyncrequest",
                                      "subscriptionRequest/scope": 4},
                       "authentication": "@parameters('$authentication')"}
        }
    },
    "actions": {
        "Get_platform": dv_action("GetItem", {
            "entityName": "sanidi_integrationplatforms",
            "recordId": "@triggerOutputs()?['body/_sanidi_platform_value']",
            "$select": "sanidi_name,sanidi_platformkey,sanidi_dataflows,sanidi_insightsflowname"}, {}),
        "Flow_name": {
            "type": "InitializeVariable", "runAfter": {"Get_platform": ["Succeeded"]},
            "inputs": {"variables": [{"name": "FlowName", "type": "string",
                "value": "@{if(equals(triggerOutputs()?['body/sanidi_synctype'], 100000000), coalesce(first(json(coalesce(outputs('Get_platform')?['body/sanidi_dataflows'], '[]')))?['name'], 'The data flow'), coalesce(outputs('Get_platform')?['body/sanidi_insightsflowname'], 'The insights flow'))}"}]}
        },
        "Mark_running": update_request({"sanidi_status": 100000001, "sanidi_startedon": "@utcNow()"},
                                       {"Flow_name": ["Succeeded"]}),
        "Try": {
            "type": "Scope", "runAfter": {"Mark_running": ["Succeeded"]},
            "actions": {
                "Run_the_matching_flow": {
                    "type": "Switch", "runAfter": {},
                    "expression": "@concat(outputs('Get_platform')?['body/sanidi_platformkey'], '-', string(triggerOutputs()?['body/sanidi_synctype']))",
                    "cases": {
                        "Case_" + key.replace("-", "_"): {"case": key, "actions": {name: child(fid)}}
                        for key, (name, fid) in CASES.items()
                    },
                    "default": {"actions": {
                        "No_flow_set_up": {"type": "Terminate", "runAfter": {},
                            "inputs": {"runStatus": "Failed", "runError": {"code": "NoFlowSetUp",
                                "message": "No flow is set up for this platform and sync type."}}}}}
                }
            }
        },
        "Mark_succeeded": update_request({"sanidi_status": 100000002, "sanidi_completedon": "@utcNow()"},
                                         {"Try": ["Succeeded"]}),
        "Mark_failed": update_request({"sanidi_status": 100000003, "sanidi_completedon": "@utcNow()",
                                       "sanidi_errormessage": "@{variables('FlowName')} failed or was not set up. See the flow's run history in Power Automate for details."},
                                      {"Try": ["Failed", "TimedOut", "Skipped"]}),
    },
    "outputs": {}
}

clientdata = {"properties": {
    "connectionReferences": {"shared_commondataserviceforapps": {
        "runtimeSource": "embedded",
        "connection": {"connectionReferenceLogicalName": "sanidi_sharedcommondataserviceforapps_79822"},
        "api": {"name": "shared_commondataserviceforapps"}}},
    "definition": definition},
    "schemaVersion": "1.0.0.0"}

wf = {"name": "Sync Control - Run Sync Request", "category": 5, "type": 1, "primaryentity": "none",
      "description": "Runs the data or insights flow for each Integration Sync Request created from the Sync Control page, and records the outcome on the request.",
      "clientdata": json.dumps(clientdata)}
st, b, _ = dv.call('POST', 'workflows', wf)
print('create', st, b.get('workflowid') if isinstance(b, dict) else b)
if isinstance(b, dict):
    wid = b['workflowid']
    st2, b2, _ = dv.call('PATCH', f'workflows({wid})', {"statecode": 1, "statuscode": 2})
    print('activate', st2, '' if st2 < 300 else b2)
