"""End-to-end check of the AutoNumbering plug-in against DATAVERSE_URL (UAT). Creates test campaigns and
advertisements, checks the numbers, then deletes them and puts the settings counters back as they were.

  python3 test_numbering.py

Not for Production: it takes campaign numbers while it runs (they are given back at the end).
"""
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

META, SNAP, TIKTOK, GOOGLE = 1, 5, 4, 6
YEAR = str((datetime.now(timezone.utc) + timedelta(hours=3)).year)
created = {"sanidi_advertisements": [], "sanidi_campaigns": []}
failures = []


def check(what, actual, expected):
    ok = actual == expected
    print(f"  {'ok  ' if ok else 'FAIL'} {what}: {actual!r}" + ("" if ok else f" (expected {expected!r})"))
    if not ok:
        failures.append(what)


def create(dv, entity_set, body):
    _, url = dv.request("POST", entity_set, body, idempotent=False)
    row_id = url.rsplit("(", 1)[1].rstrip(")")
    created[entity_set].append(row_id)
    return row_id


def campaign(dv, channels):
    body = {"sanidi_startdate": "2026-11-01", "sanidi_enddate": "2026-11-30", "sanidi_type": 1,
            "sanidi_description": "Auto numbering test"}
    if channels:
        body["sanidi_socialmediachannel"] = ",".join(map(str, channels))
    return create(dv, "sanidi_campaigns", body)


def advertisement(dv, campaign_id, channel):
    body = {"sanidi_channel": channel}
    if campaign_id:
        body["sanidi_Campaign@odata.bind"] = f"/sanidi_campaigns({campaign_id})"
    return create(dv, "sanidi_advertisements", body)


def get(dv, entity_set, row_id, cols):
    return dv.get(f"{entity_set}({row_id})?$select={','.join(cols)}")


def expect_error(what, fn, text):
    try:
        fn()
    except RuntimeError as e:
        check(what, text in str(e), True)
        return
    check(what, "saved", "blocked")


def main():
    dv = Dataverse()
    settings = dv.first("sanidi_autonumbersettings?$select=sanidi_autonumbersettingid,sanidi_currentyear,"
                        "sanidi_lastcampaignnumber&$filter=statecode eq 0&$orderby=createdon")
    original = None
    if settings:
        original = {"sanidi_currentyear": settings["sanidi_currentyear"],
                    "sanidi_lastcampaignnumber": settings["sanidi_lastcampaignnumber"]}
        dv.request("PATCH", f"sanidi_autonumbersettings({settings['sanidi_autonumbersettingid']})",
                   {"sanidi_currentyear": YEAR, "sanidi_lastcampaignnumber": 0})
    try:
        run(dv)
    finally:
        for entity_set in ("sanidi_advertisements", "sanidi_campaigns"):
            for row_id in created[entity_set]:
                dv.request("DELETE", f"{entity_set}({row_id})")
        settings = dv.first("sanidi_autonumbersettings?$select=sanidi_autonumbersettingid&$filter=statecode eq 0"
                            "&$orderby=createdon")
        restore = original or {"sanidi_currentyear": None, "sanidi_lastcampaignnumber": None}
        dv.request("PATCH", f"sanidi_autonumbersettings({settings['sanidi_autonumbersettingid']})", restore)
        print(f"cleaned up: {sum(len(v) for v in created.values())} test rows deleted, settings restored to {restore}")
    print("ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
    sys.exit(1 if failures else 0)


def run(dv):
    numbers = ["sanidi_name", "sanidi_metanumber", "sanidi_snapnumber", "sanidi_tiktoknumber",
               "sanidi_googleadsnumber"]
    first = f"MC-{YEAR}-01"
    print("campaign with Meta and Snap")
    c1 = campaign(dv, [META, SNAP])
    row = get(dv, "sanidi_campaigns", c1, numbers)
    check("name", row["sanidi_name"], first)
    check("Meta number", row["sanidi_metanumber"], first + "-M")
    check("Snap number", row["sanidi_snapnumber"], first + "-S")
    check("TikTok number", row["sanidi_tiktoknumber"], None)

    print("tick TikTok, untick Meta")
    dv.request("PATCH", f"sanidi_campaigns({c1})", {"sanidi_socialmediachannel": f"{SNAP},{TIKTOK}"})
    row = get(dv, "sanidi_campaigns", c1, numbers)
    check("TikTok number", row["sanidi_tiktoknumber"], first + "-T")
    check("Meta number kept", row["sanidi_metanumber"], first + "-M")

    print("advertisements")
    expect_error("Meta ad blocked while Meta is unticked", lambda: advertisement(dv, c1, META), "Meta channel")
    expect_error("Google Ads ad blocked (never ticked)", lambda: advertisement(dv, c1, GOOGLE), "Google Ads channel")
    expect_error("ad without campaign blocked", lambda: advertisement(dv, None, SNAP), "Select the campaign")
    dv.request("PATCH", f"sanidi_campaigns({c1})", {"sanidi_socialmediachannel": f"{META},{SNAP},{TIKTOK}"})
    check("Meta number unchanged after re-tick", get(dv, "sanidi_campaigns", c1, numbers)["sanidi_metanumber"],
          first + "-M")
    a1 = advertisement(dv, c1, META)
    a2 = advertisement(dv, c1, SNAP)
    a3 = advertisement(dv, c1, META)
    check("1st Meta ad", get(dv, "sanidi_advertisements", a1, ["sanidi_name"])["sanidi_name"], first + "-M-01")
    check("1st Snap ad", get(dv, "sanidi_advertisements", a2, ["sanidi_name"])["sanidi_name"], first + "-S-01")
    check("2nd Meta ad", get(dv, "sanidi_advertisements", a3, ["sanidi_name"])["sanidi_name"], first + "-M-02")
    counters = get(dv, "sanidi_campaigns", c1, ["sanidi_lastmetaadnumber", "sanidi_lastsnapadnumber"])
    check("Meta ad counter on campaign", counters["sanidi_lastmetaadnumber"], 2)
    check("Snap ad counter on campaign", counters["sanidi_lastsnapadnumber"], 1)

    print("second campaign, no channels; name sent by the caller is replaced")
    c2 = create(dv, "sanidi_campaigns", {"sanidi_name": "typed by hand", "sanidi_startdate": "2026-11-01",
                                         "sanidi_enddate": "2026-11-30", "sanidi_type": 1})
    check("name", get(dv, "sanidi_campaigns", c2, ["sanidi_name"])["sanidi_name"], f"MC-{YEAR}-02")

    print("8 campaigns saved at the same time")
    results, errors = [], []

    def worker():
        try:
            own = Dataverse()
            results.append(campaign(own, [GOOGLE]))
        except Exception as e:  # reported below; a failed save is a test failure
            errors.append(str(e)[:300])

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for error in errors:
        print(f"  save failed: {error}")
    names = sorted(get(dv, "sanidi_campaigns", r, ["sanidi_name"])["sanidi_name"] for r in results)
    check("8 distinct numbers 03-10", names, [f"MC-{YEAR}-{n:02d}" for n in range(3, 11)])

    print("new year: counter restarts")
    settings = dv.first("sanidi_autonumbersettings?$select=sanidi_autonumbersettingid&$filter=statecode eq 0"
                        "&$orderby=createdon")
    dv.request("PATCH", f"sanidi_autonumbersettings({settings['sanidi_autonumbersettingid']})",
               {"sanidi_currentyear": str(int(YEAR) - 1), "sanidi_lastcampaignnumber": 57})
    c3 = campaign(dv, [TIKTOK])
    row = get(dv, "sanidi_campaigns", c3, numbers)
    check("first number of the year", row["sanidi_name"], first)
    check("TikTok number", row["sanidi_tiktoknumber"], first + "-T")

    print("configurable codes and 3-digit counter")
    dv.request("PATCH", f"sanidi_autonumbersettings({settings['sanidi_autonumbersettingid']})",
               {"sanidi_campaignprefix": "XC", "sanidi_snapcode": "SN", "sanidi_lastcampaignnumber": 99})
    try:
        c4 = campaign(dv, [SNAP])
        row = get(dv, "sanidi_campaigns", c4, numbers)
        check("prefix and 100th campaign", row["sanidi_name"], f"XC-{YEAR}-100")
        check("Snap code", row["sanidi_snapnumber"], f"XC-{YEAR}-100-SN")
    finally:
        dv.request("PATCH", f"sanidi_autonumbersettings({settings['sanidi_autonumbersettingid']})",
                   {"sanidi_campaignprefix": "MC", "sanidi_snapcode": "S"})


if __name__ == "__main__":
    main()
