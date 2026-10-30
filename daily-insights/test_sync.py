"""Starts Sync Control requests the way the page does and waits for them (PLAN.md §3.5 step 7).

  python3 test_sync.py daymonth tiktok meta snap google     # one Day & Month to Date request per platform
  python3 test_sync.py alltime tiktok --data                 # All Time (Data and Insights) for TikTok

Requests are created with Triggered By = Schedule, so nobody gets an in-app notification for a test. Prints each
request's status, steps log and error when it finishes, then the row counts of the platform's insight tables.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

TYPES = {"daymonth": (100000002, "Day & Month to Date"), "alltime": (100000003, "All Time")}
STATUS = {100000000: "Requested", 100000001: "Running", 100000002: "Succeeded", 100000003: "Failed",
          100000004: "Skipped"}


def main(kind, platforms, include_data):
    dv = Dataverse()
    rows = dv.get("sanidi_integrationplatforms?$select=sanidi_platformkey,sanidi_name")["value"]
    ids = {r["sanidi_platformkey"]: (r["sanidi_integrationplatformid"], r["sanidi_name"]) for r in rows}
    sync_type, label = TYPES[kind]
    requests = {}
    for p in platforms:
        pid, name = ids[p]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _, uri = dv.request("POST", "sanidi_integrationsyncrequests", {
            "sanidi_name": f"{name} - {label} - test", "sanidi_Platform@odata.bind": f"/sanidi_integrationplatforms({pid})",
            "sanidi_synctype": sync_type, "sanidi_status": 100000000, "sanidi_startedon": now,
            "sanidi_triggeredby": 100000001, "sanidi_includedata": include_data})
        requests[p] = uri.split("(")[-1].rstrip(")")
        print(f"{name}: request {requests[p]}", flush=True)
    pending = dict(requests)
    while pending:
        time.sleep(60)
        for p, rid in list(pending.items()):
            r = dv.get(f"sanidi_integrationsyncrequests({rid})?$select=sanidi_status,sanidi_errormessage,"
                       "sanidi_stepslog,sanidi_startedon,sanidi_completedon")
            if r["sanidi_status"] in (100000000, 100000001):
                continue
            del pending[p]
            print(f"\n== {ids[p][1]}: {STATUS.get(r['sanidi_status'])} ({r['sanidi_startedon']} -> {r['sanidi_completedon']})")
            print(r.get("sanidi_stepslog") or "(no steps log)")
            if r.get("sanidi_errormessage"):
                print("ERROR:", r["sanidi_errormessage"][:3000])
            for logical, t in spec.tables().items():
                if t["platform"] == p:
                    n = dv.request("GET", f"{logical}s?$select=createdon&$count=true&$top=1",
                                   headers={"Prefer": "odata.maxpagesize=1"})[0].get("@odata.count")
                    print(f"   {logical}: {n} rows")
            sys.stdout.flush()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1:], "--data" in sys.argv)
