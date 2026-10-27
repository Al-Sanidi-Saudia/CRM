"""Moves channel data onto the 4 kept options of the global choice sanidi_socialmediachannel, then removes the rest.

  python3 migrate_channels.py            # dry run: rows that would change, options that would be removed
  python3 migrate_channels.py --apply    # update the rows, then delete the obsolete options

Targets DATAVERSE_URL (UAT by default). Run it in UAT before deploy.py, and in Production after importing the
managed patch: a patch can't delete options from a managed choice, so this removes them there.

The choice is shared by Campaign (multi-select), Advertisement and Influencer (multi-select).
  Facebook (1), Instagram (2) -> Meta (1)      Snapchat (5) -> Snap (5)      TikTok (4) -> TikTok (4)
  Google (6), YouTube (7)     -> Google Ads (6)
  X (3), WhatsApp (8), Other (10) -> removed from the row (an advertisement on one of them is left empty)
Rows are updated with custom plug-ins and flows bypassed, so no numbering or cost flow runs for this clean-up.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

CHOICE = "sanidi_socialmediachannel"
KEEP = [1, 5, 4, 6]  # display order: Meta, Snap, TikTok, Google Ads
MAP = {1: 1, 2: 1, 4: 4, 5: 5, 6: 6, 7: 6}
COLUMNS = [  # (entity set, id column, choice column, multi-select)
    ("sanidi_campaigns", "sanidi_campaignid", "sanidi_socialmediachannel", True),
    ("sanidi_influencers", "sanidi_influencerid", "sanidi_channel", True),
    ("sanidi_advertisements", "sanidi_advertisementid", "sanidi_channel", False),
]
BYPASS = {"MSCRM.BypassBusinessLogicExecution": "CustomSync,CustomAsync"}


def remap(value, multi):
    if value is None:
        return None
    if not multi:
        return MAP.get(value)
    mapped = {MAP[int(v)] for v in str(value).split(",") if int(v) in MAP}
    return ",".join(str(v) for v in KEEP if v in mapped) or None


def same(new, old, multi):
    """Dataverse returns multi-select values sorted, so compare them as sets."""
    if multi and new is not None and old is not None:
        return set(new.split(",")) == set(str(old).split(","))
    return str(new) == str(old)


def rows(dv, entity_set, id_column, column):
    url = f"{entity_set}?$select={id_column},sanidi_name,{column}&$filter={column} ne null"
    while url:
        page = dv.request("GET", url, headers={"Prefer": "odata.maxpagesize=500"})[0]
        yield from page["value"]
        url = page.get("@odata.nextLink")


def main(apply):
    dv = Dataverse()
    print(f"environment: {dv.url}")
    for entity_set, id_column, column, multi in COLUMNS:
        changes = []
        for r in rows(dv, entity_set, id_column, column):
            old = r[column]
            new = remap(old if multi else int(old), multi)
            if not same(new, old, multi):
                changes.append((r[id_column], r.get("sanidi_name"), old, new))
        print(f"{entity_set}.{column}: {len(changes)} rows to update")
        for row_id, name, old, new in changes:
            print(f"  {name}: {old} -> {new}")
            if apply:
                dv.request("PATCH", f"{entity_set}({row_id})", {column: new}, headers=BYPASS)

    choice = dv.get(f"GlobalOptionSetDefinitions(Name='{CHOICE}')")
    remove = [o["Value"] for o in choice["Options"] if o["Value"] not in KEEP]
    print(f"choice {CHOICE}: options to remove {remove or 'none'}")
    if not apply:
        return
    for value in remove:
        dv.request("POST", "DeleteOptionValue", {"OptionSetName": CHOICE, "Value": value}, idempotent=True)
    if remove:
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><optionsets><optionset>{CHOICE}</optionset></optionsets></importexportxml>"})
        print("  removed and published")


if __name__ == "__main__":
    main("--apply" in sys.argv)
