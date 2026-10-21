"""Updates the dispatcher flow definition in place (keeps the flow on).

Adds: no retries on the child-flow calls, and an in-app notification to the person who pressed the
button when the sync succeeds or fails. Usage: python3 update_dispatcher.py <dir containing dv.py>
"""
import sys, json; sys.path.insert(0, sys.argv[1])
import dv

FLOW_ID = '4974c02e-4ac5-f111-aaad-70a8a581e673'
DV = {"apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "connectionName": "shared_commondataserviceforapps"}
REQ_ID = "@triggerOutputs()?['body/sanidi_integrationsyncrequestid']"
SYNC_LABEL = "@{outputs('Get_platform')?['body/sanidi_name']} @{if(equals(triggerOutputs()?['body/sanidi_synctype'], 100000000), 'data', 'insights')} sync"
LOCAL_NOW = "@{convertTimeZone(utcNow(), 'UTC', 'Arab Standard Time', 'dd MMM yyyy, HH:mm')}"

def dv_action(op, params, run_after):
    return {"type": "OpenApiConnection", "runAfter": run_after,
            "inputs": {"host": {**DV, "operationId": op}, "parameters": params,
                       "authentication": "@parameters('$authentication')"}}

def update_request(fields, run_after):
    params = {"entityName": "sanidi_integrationsyncrequests", "recordId": REQ_ID}
    params.update({"item/" + k: v for k, v in fields.items()})
    return dv_action("UpdateOnlyRecord", params, run_after)

def notify(title, body, icon, run_after):
    # appnotification: icontype 100000001 Success / 100000002 Failure; toasttype 200000000 Timed.
    return dv_action("CreateRecord", {
        "entityName": "appnotifications",
        "item/title": title,
        "item/body": body,
        "item/icontype": icon,
        "item/toasttype": 200000000,
        "item/ttlinseconds": 1209600,
        "item/ownerid@odata.bind": "/systemusers(@{triggerOutputs()?['body/_createdby_value']})",
    }, run_after)

def child(flow_id):
    return {"type": "Workflow", "runAfter": {},
            "inputs": {"host": {"workflowReferenceName": flow_id}, "retryPolicy": {"type": "none"}}}

CASES = {
    "meta-100000000":   ("Run_Get_Meta_Campaigns", "8b6d991c-d3c0-f111-aaaf-70a8a581e673"),
    "meta-100000001":   ("Run_Get_Meta_Insights", "e30b9610-07c5-f111-aaaf-70a8a581e5c5"),
    "snap-100000000":   ("Run_Get_Snap_Campaigns", "f0adc814-8c13-5fe3-8ba7-9ad697ea4ea2"),
    "snap-100000001":   ("Run_Get_Snap_Insights", "028e8be8-505f-5f70-acc7-85653b1f859f"),
    "google-100000000": ("Run_Get_Google_Ads_Campaigns", "b10505e5-822c-5641-8499-e8324198b469"),
    "google-100000001": ("Run_Get_Google_Ads_Insights", "59399b2c-080a-50b0-afcf-b803145237cf"),
    "tiktok-100000000": ("Run_Get_TikTok_Campaigns", "de45712c-6cd1-59ff-8546-26bb91f692f4"),
    "tiktok-100000001": ("Run_Get_TikTok_Insights", "4bcc7027-25a2-51c9-adc4-9c4b5c5ca128"),
}

NO_FLOW_MSG = "No flow is set up for this platform and sync type."
FAILED_MSG = ("@{if(empty(variables('NoFlowMessage')), concat(variables('FlowName'), ' failed: ', "
              "coalesce(first(body('Failed_steps'))?['error']?['message'], 'see the flow run history in Power Automate for details.')), "
              "variables('NoFlowMessage'))}")

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
        "No_flow_message": {
            "type": "InitializeVariable", "runAfter": {"Flow_name": ["Succeeded"]},
            "inputs": {"variables": [{"name": "NoFlowMessage", "type": "string", "value": ""}]}
        },
        "Mark_running": update_request({"sanidi_status": 100000001, "sanidi_startedon": "@utcNow()"},
                                       {"No_flow_message": ["Succeeded"]}),
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
                    # Record why, then fail this block on purpose (a Terminate would end the run before
                    # the request is marked failed and the requester notified).
                    "default": {"actions": {
                        "Set_no_flow_message": {"type": "SetVariable", "runAfter": {},
                            "inputs": {"name": "NoFlowMessage", "value": NO_FLOW_MSG}},
                        "No_flow_set_up": {"type": "Compose", "runAfter": {"Set_no_flow_message": ["Succeeded"]},
                            "inputs": "@int('no-flow-set-up')"}}}
                }
            }
        },
        "Mark_succeeded": update_request({"sanidi_status": 100000002, "sanidi_completedon": "@utcNow()"},
                                         {"Try": ["Succeeded"]}),
        "Notify_succeeded": notify(SYNC_LABEL + " succeeded",
                                   "@{variables('FlowName')} finished at " + LOCAL_NOW + ".",
                                   100000001, {"Mark_succeeded": ["Succeeded"]}),
        "Failed_steps": {
            "type": "Query", "runAfter": {"Try": ["Failed", "TimedOut", "Skipped"]},
            "inputs": {"from": "@result('Run_the_matching_flow')", "where": "@equals(item()?['status'], 'Failed')"}
        },
        "Mark_failed": update_request({"sanidi_status": 100000003, "sanidi_completedon": "@utcNow()",
                                       "sanidi_errormessage": FAILED_MSG},
                                      {"Failed_steps": ["Succeeded", "Failed"]}),
        "Notify_failed": notify(SYNC_LABEL + " failed", FAILED_MSG, 100000002, {"Mark_failed": ["Succeeded"]}),
    },
    "outputs": {}
}

if __name__ == '__main__':
    st, b, _ = dv.call('GET', f'workflows({FLOW_ID})?$select=clientdata', solution=None)
    cd = json.loads(b['clientdata'])
    with open(sys.argv[1] + '/backup/dispatcher-before-v2.json', 'w') as f:
        json.dump(cd, f)
    cd['properties']['definition'] = definition
    st, b, _ = dv.call('PATCH', f'workflows({FLOW_ID})', {"clientdata": json.dumps(cd)}, solution=None)
    print('update dispatcher', st, '' if st < 300 else b)
