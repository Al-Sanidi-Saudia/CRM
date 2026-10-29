"""Limits the triggers of the 9 child data flows to the platform ID column of their parent table (PLAN.md §3.2,
decision 33), so lifetime insights updates on the parent rows no longer start a data re-sync.

  python3 deploy_triggers.py                      # dry run
  python3 deploy_triggers.py --apply [--only=tiktok,google]

The data flows write the parent's platform ID on every update; the insights flows never do. Dataverse fires a
filtered trigger when a filtering column is part of the update, even with an unchanged value, so a data sync still
cascades exactly as before. Each flow is turned off, saved in the patch and turned back on; turning a flow on needs
its connections to be usable by this app user.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

# flow -> (platform, filtering column on the parent table that triggers it)
FLOWS = {
    "947c3f10-d3c0-f111-aaaf-70a8a581e673": ("meta", "Get Meta AdSets", "sanidi_campaignid"),
    "957c3f10-d3c0-f111-aaaf-70a8a581e673": ("meta", "Get Meta Advertisements", "sanidi_adsetid"),
    "ddb71436-2f06-50ad-b721-146978286924": ("snap", "Get Snap Ad Squads", "sanidi_campaignid"),
    "9c0d86ce-7ccd-5b1e-bb13-55921b643dad": ("snap", "Get Snap Advertisements", "sanidi_adsquadid"),
    "3574fbc1-642c-5d29-8757-9521a4b03c8e": ("google", "Get Google Ads Ad Groups", "sanidi_campaignid"),
    "511feda4-57bc-5009-bf26-21dd79bb8fe9": ("google", "Get Google Ads Advertisements", "sanidi_adgroupid"),
    "5f9e257b-5d19-5fe5-9a1e-974434268472": ("google", "Get Google Ads Asset Groups", "sanidi_campaignid"),
    "49f87836-4262-5c77-b470-5c90c1054813": ("tiktok", "Get TikTok Ad Groups", "sanidi_campaignid"),
    "1c99d003-a774-5c45-94a8-73e1048fd19c": ("tiktok", "Get TikTok Advertisements", "sanidi_adgroupid"),
}


def main(apply, only):
    dv = Dataverse()
    backup = HERE / "backup"
    backup.mkdir(exist_ok=True)
    for wid, (platform, name, column) in FLOWS.items():
        if only and platform not in only:
            continue
        flow = dv.get(f"workflows({wid})?$select=name,clientdata,statecode")
        cd = json.loads(flow["clientdata"])
        trigger = next(iter(cd["properties"]["definition"]["triggers"].values()))
        params = trigger["inputs"]["parameters"]
        current = params.get("subscriptionRequest/filteringattributes")
        print(f"{name}: filtering columns {current!r} -> {column!r}")
        if not apply or current == column:
            continue
        (backup / f"{wid}.json").write_text(json.dumps(cd))
        params["subscriptionRequest/filteringattributes"] = column
        was_on = flow["statecode"] == 1
        if was_on:
            dv.request("PATCH", f"workflows({wid})", {"statecode": 0, "statuscode": 1})
        try:
            dv.request("PATCH", f"workflows({wid})", {"clientdata": json.dumps(cd)}, solution=spec.SOLUTION)
        finally:
            if was_on:
                # Never leave a data flow off: turn it back on even when the save failed.
                dv.request("PATCH", f"workflows({wid})", {"statecode": 1, "statuscode": 2})
        print("  saved" + (", turned back on" if was_on else ""))


if __name__ == "__main__":
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    main("--apply" in sys.argv, only)
