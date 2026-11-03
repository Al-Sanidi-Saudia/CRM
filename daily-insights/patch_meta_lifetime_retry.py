"""Turns on retries for the Meta calls in the existing 'Get Meta Insights' flow (the lifetime insights step).

The three GetDetailsFromAdID actions had retryPolicy 'none', so one transient Meta error (code 2, subcode 1504044
"Unknown Error Occurred": "try again", per Meta's Ads Insights error codes) failed the whole run. They now retry
3 times, 15 seconds apart (inside the action's 2-minute timeout); a retry only happens on 408 / 429 / 5xx.

  python3 patch_meta_lifetime_retry.py            # show the current policies
  python3 patch_meta_lifetime_retry.py --apply
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

FLOW = "e30b9610-07c5-f111-aaaf-70a8a581e5c5"  # Get Meta Insights
CALLS = {"For_each_Campaigns": "Get_Insights_Campaigns", "For_each_AdSets": "Get_Insights_AdSets",
         "For_each_Ads": "Get_Insights_Ads"}
RETRY = {"type": "fixed", "count": 3, "interval": "PT15S"}


def main(apply):
    dv = Dataverse()
    cd = json.loads(dv.get(f"workflows({FLOW})?$select=clientdata")["clientdata"])
    actions = cd["properties"]["definition"]["actions"]
    for loop, call in CALLS.items():
        action = actions[loop]["actions"][call]
        action.pop("retryPolicy", None)  # a policy belongs under inputs
        print(f"{call}: {action['inputs'].get('retryPolicy')} -> {RETRY}")
        action["inputs"]["retryPolicy"] = RETRY
    if not apply:
        return
    dv.request("PATCH", f"workflows({FLOW})", {"statecode": 0, "statuscode": 1})
    try:
        dv.request("PATCH", f"workflows({FLOW})", {"clientdata": json.dumps(cd)})
    finally:
        dv.request("PATCH", f"workflows({FLOW})", {"statecode": 1, "statuscode": 2})
    print("updated, turned back on")


if __name__ == "__main__":
    main("--apply" in sys.argv)
