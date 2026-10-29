"""Updates the dispatcher flow "Sync Control - Run Sync Request" in place (v3, Daily & Monthly Insights).

  python3 update_dispatcher.py            # write dispatcher.json for review
  python3 update_dispatcher.py --apply    # update the flow (saved in the patch), then turn it off and on so its
                                          # trigger re-registers

v2: no retries on the child-flow calls; an in-app notification to the person who pressed the button.
v3 (daily-insights/PLAN.md §3.3, §5):
- Sync types Day & Month to Date, All Time, Scheduled Daily (05:00) and Scheduled Intraday run the platform's
  "<Platform> - Run Sync" flow, which reports each step; its log is saved in Steps Log.
- Scheduled requests (Triggered By = Schedule) wait while another sync of the same platform is running (up to an
  hour, then they are marked Skipped). Notifications go only to the person who pressed a button.
- Data (and the legacy Insights type) still run the platform's own flows, as before.
Uses the service principal from scripts/dataverse-mcp.sh (DATAVERSE_* variables).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
sys.path.insert(0, str(HERE.parent.parent / "daily-insights"))

FLOW_ID = '4974c02e-4ac5-f111-aaad-70a8a581e673'
DV = {"apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "connectionName": "shared_commondataserviceforapps"}
REQ_ID = "@triggerOutputs()?['body/sanidi_integrationsyncrequestid']"
SYNC_TYPE = "triggerOutputs()?['body/sanidi_synctype']"
TYPE_LABELS = {100000000: "data", 100000001: "insights", 100000002: "day & month to date", 100000003: "all time",
               100000004: "scheduled daily", 100000005: "scheduled intraday"}
RUN_TYPES = {100000002: "daymonth", 100000003: "alltime", 100000004: "daily", 100000005: "intraday"}
SCHEDULED = "equals(triggerOutputs()?['body/sanidi_triggeredby'], 100000001)"
STATUS = {"requested": 100000000, "running": 100000001, "succeeded": 100000002, "failed": 100000003,
          "skipped": 100000004}
SYNC_LABEL = ("@{outputs('Get_platform')?['body/sanidi_name']} @{outputs('Sync_type_labels')?[string(" + SYNC_TYPE
              + ")]} sync")
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
    # Only for a button press: a scheduled request has no person to notify (decision 22).
    # appnotification: icontype 100000001 Success / 100000002 Failure; toasttype 200000000 Timed.
    return {"type": "If", "runAfter": run_after,
            "expression": {"and": [{"not": {"equals": [f"@{SCHEDULED}", True]}}]},
            "actions": {"Send_notification": dv_action("CreateRecord", {
                "entityName": "appnotifications",
                "item/title": title,
                "item/body": body,
                "item/icontype": icon,
                "item/toasttype": 200000000,
                "item/ttlinseconds": 1209600,
                "item/ownerid@odata.bind": "/systemusers(@{triggerOutputs()?['body/_createdby_value']})",
            }, {})}, "else": {"actions": {}}}


def child(flow_id, body=None):
    inputs = {"host": {"workflowReferenceName": flow_id}, "retryPolicy": {"type": "none"}}
    if body is not None:
        inputs["body"] = body
    return {"type": "Workflow", "runAfter": {}, "inputs": inputs}


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


def run_sync_cases():
    """platform-new -> its Run Sync flow, with the request's run type and options."""
    from deploy_flows import flow_id, name_run
    cases = {}
    for key in ("meta", "snap", "google", "tiktok"):
        name = f"Run_{key}_sync"
        cases[f"{key}-new"] = {
            name: child(flow_id(name_run(key)), {
                "run_type": "@outputs('Run_types')?[string(" + SYNC_TYPE + ")]",
                "include_data": "@equals(triggerOutputs()?['body/sanidi_includedata'], true)",
                "weekly": "@equals(triggerOutputs()?['body/sanidi_weeklyrun'], true)",
                "full_load_from": "@{coalesce(outputs('Get_platform')?['body/sanidi_fullloadfrom'], '')}",
            }),
            f"Keep_log_{key}": {"type": "SetVariable", "runAfter": {name: ["Succeeded"]},
                                "inputs": {"name": "RunLog", "value": f"@{{body('{name}')?['log']}}"}},
            # A step that failed fails this block, so the request is marked Failed with the log.
            f"Check_{key}": {"type": "Compose", "runAfter": {f"Keep_log_{key}": ["Succeeded"]},
                             "inputs": f"@if(equals(body('{name}')?['status'], 'Failed'), int('A step failed'), 'ok')"},
        }
    return cases


NO_FLOW_MSG = "No flow is set up for this platform and sync type."
FAILED_MSG = ("@{if(not(empty(variables('RunLog'))), concat(variables('FlowName'), ' finished with failed steps:', "
              "decodeUriComponent('%0A'), take(variables('RunLog'), 3000)), if(empty(variables('NoFlowMessage')), "
              "concat(variables('FlowName'), ' failed: ', coalesce(first(body('Failed_steps'))?['error']?['message'], "
              "'see the flow run history in Power Automate for details.')), variables('NoFlowMessage')))}")


def definition():
    old_cases = {"Case_" + key.replace("-", "_"): {"case": key, "actions": {name: child(fid)}}
                 for key, (name, fid) in CASES.items()}
    new_cases = {f"Case_{key.replace('-', '_')}": {"case": key, "actions": actions}
                 for key, actions in run_sync_cases().items()}
    others_running = ("sanidi_integrationsyncrequests", "_sanidi_platform_value eq @{triggerOutputs()?['body/_sanidi_platform_value']} "
                      f"and sanidi_status eq {STATUS['running']} and sanidi_integrationsyncrequestid ne "
                      "@{triggerOutputs()?['body/sanidi_integrationsyncrequestid']}")
    return {
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
                "$select": "sanidi_name,sanidi_platformkey,sanidi_dataflows,sanidi_insightsflowname,sanidi_fullloadfrom"}, {}),
            "Sync_type_labels": {"type": "Compose", "runAfter": {"Get_platform": ["Succeeded"]},
                                 "inputs": {str(k): v for k, v in TYPE_LABELS.items()}},
            "Run_types": {"type": "Compose", "runAfter": {"Sync_type_labels": ["Succeeded"]},
                          "inputs": {str(k): v for k, v in RUN_TYPES.items()}},
            "Flow_name": {
                "type": "InitializeVariable", "runAfter": {"Run_types": ["Succeeded"]},
                "inputs": {"variables": [{"name": "FlowName", "type": "string",
                    "value": "@{if(greaterOrEquals(" + SYNC_TYPE + ", 100000002), concat(outputs('Get_platform')?['body/sanidi_name'], ' - Run Sync'), "
                             "if(equals(" + SYNC_TYPE + ", 100000000), coalesce(first(json(coalesce(outputs('Get_platform')?['body/sanidi_dataflows'], '[]')))?['name'], 'The data flow'), "
                             "coalesce(outputs('Get_platform')?['body/sanidi_insightsflowname'], 'The insights flow')))}"}]}
            },
            "No_flow_message": {
                "type": "InitializeVariable", "runAfter": {"Flow_name": ["Succeeded"]},
                "inputs": {"variables": [{"name": "NoFlowMessage", "type": "string", "value": ""}]}
            },
            "Run_log": {
                "type": "InitializeVariable", "runAfter": {"No_flow_message": ["Succeeded"]},
                "inputs": {"variables": [{"name": "RunLog", "type": "string", "value": ""}]}
            },
            "Busy_checks": {
                "type": "InitializeVariable", "runAfter": {"Run_log": ["Succeeded"]},
                "inputs": {"variables": [{"name": "OthersRunning", "type": "integer", "value": 0}]}
            },
            # One sync per platform at a time: a scheduled request waits for the platform's running one.
            "If_scheduled": {
                "type": "If", "runAfter": {"Busy_checks": ["Succeeded"]},
                "expression": {"and": [{"equals": [f"@{SCHEDULED}", True]}]},
                "actions": {
                    "Wait_for_other_syncs": {
                        "type": "Until", "runAfter": {},
                        "expression": "@equals(variables('OthersRunning'), 0)",
                        "limit": {"count": 31, "timeout": "PT70M"},
                        "actions": {
                            "Other_running_requests": dv_action("ListRecords", {
                                "entityName": others_running[0], "$select": "sanidi_integrationsyncrequestid",
                                "$filter": others_running[1], "$top": 1}, {}),
                            "Count_running": {"type": "SetVariable", "runAfter": {"Other_running_requests": ["Succeeded"]},
                                              "inputs": {"name": "OthersRunning",
                                                         "value": "@length(outputs('Other_running_requests')?['body/value'])"}},
                            "If_busy": {"type": "If", "runAfter": {"Count_running": ["Succeeded"]},
                                        "expression": {"and": [{"greater": ["@variables('OthersRunning')", 0]}]},
                                        "actions": {"Wait_2_minutes": {"type": "Wait", "runAfter": {},
                                                    "inputs": {"interval": {"count": 2, "unit": "Minute"}}}},
                                        "else": {"actions": {}}},
                        }},
                    "If_still_busy": {
                        "type": "If", "runAfter": {"Wait_for_other_syncs": ["Succeeded", "Failed", "TimedOut"]},
                        "expression": {"and": [{"greater": ["@variables('OthersRunning')", 0]}]},
                        "actions": {
                            "Mark_skipped": update_request({
                                "sanidi_status": STATUS["skipped"], "sanidi_completedon": "@utcNow()",
                                "sanidi_errormessage": "Skipped: another sync of this platform was still running after "
                                                       "an hour. The next scheduled run covers the same periods."}, {}),
                            "Stop_skipped": {"type": "Terminate", "runAfter": {"Mark_skipped": ["Succeeded"]},
                                             "inputs": {"runStatus": "Succeeded"}},
                        }, "else": {"actions": {}}},
                },
                "else": {"actions": {}},
            },
            "Mark_running": update_request({"sanidi_status": STATUS["running"], "sanidi_startedon": "@utcNow()"},
                                           {"If_scheduled": ["Succeeded"]}),
            "Try": {
                "type": "Scope", "runAfter": {"Mark_running": ["Succeeded"]},
                "actions": {
                    "Run_the_matching_flow": {
                        "type": "Switch", "runAfter": {},
                        "expression": "@concat(outputs('Get_platform')?['body/sanidi_platformkey'], '-', if(greaterOrEquals("
                                      + SYNC_TYPE + ", 100000002), 'new', string(" + SYNC_TYPE + ")))",
                        "cases": {**old_cases, **new_cases},
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
            "Mark_succeeded": update_request({"sanidi_status": STATUS["succeeded"], "sanidi_completedon": "@utcNow()",
                                              "sanidi_stepslog": "@{variables('RunLog')}"}, {"Try": ["Succeeded"]}),
            "Notify_succeeded": notify(SYNC_LABEL + " succeeded",
                                       "@{variables('FlowName')} finished at " + LOCAL_NOW + ".",
                                       100000001, {"Mark_succeeded": ["Succeeded"]}),
            "Failed_steps": {
                "type": "Query", "runAfter": {"Try": ["Failed", "TimedOut", "Skipped"]},
                "inputs": {"from": "@result('Run_the_matching_flow')", "where": "@equals(item()?['status'], 'Failed')"}
            },
            "Mark_failed": update_request({"sanidi_status": STATUS["failed"], "sanidi_completedon": "@utcNow()",
                                           "sanidi_errormessage": FAILED_MSG, "sanidi_stepslog": "@{variables('RunLog')}"},
                                          {"Failed_steps": ["Succeeded", "Failed"]}),
            "Notify_failed": notify(SYNC_LABEL + " failed", FAILED_MSG, 100000002, {"Mark_failed": ["Succeeded"]}),
        },
        "outputs": {}
    }


def main(apply):
    d = definition()
    (HERE / "dispatcher.json").write_text(json.dumps(d, indent=1) + "\n")
    print(f"dispatcher v3: {len(json.dumps(d)) // 1024} KB, cases: "
          f"{len(d['actions']['Try']['actions']['Run_the_matching_flow']['cases'])} -> dispatcher.json")
    if not apply:
        return
    from dv import Dataverse
    import spec
    dv = Dataverse()
    flow = dv.get(f"workflows({FLOW_ID})?$select=clientdata,statecode")
    cd = json.loads(flow["clientdata"])
    (HERE / "backup").mkdir(exist_ok=True)
    (HERE / "backup" / "dispatcher-before-v3.json").write_text(json.dumps(cd))
    cd["properties"]["definition"] = d
    was_on = flow["statecode"] == 1
    if was_on:
        dv.request("PATCH", f"workflows({FLOW_ID})", {"statecode": 0, "statuscode": 1})
    try:
        dv.request("PATCH", f"workflows({FLOW_ID})", {"clientdata": json.dumps(cd)}, solution=spec.SOLUTION)
        print("updated the dispatcher")
    finally:
        if was_on:
            dv.request("PATCH", f"workflows({FLOW_ID})", {"statecode": 1, "statuscode": 2})
            print("turned it back on")


if __name__ == '__main__':
    main("--apply" in sys.argv)
