"""Adds TikTok to the Campaign / Advertisement cost roll-up, like Google Ads, Meta and Snap.

  python3 deploy_costrollup.py            # dry run: shows what would change
  python3 deploy_costrollup.py --apply    # apply in AlSanidi | Marketing, then publish

1. Lookups  sanidi_campaign.sanidi_tiktokcampaign -> TikTok Campaign
            sanidi_advertisement.sanidi_tiktokadvertisement -> TikTok Advertisement
   (cascade Remove Link, like the Snap ones)
2. Forms    the new lookup goes right after the Snap lookup on every form that has it (main + quick create),
            hidden like the others: the form scripts show it when the channel is TikTok.
3. Scripts  webresources/sanidi_/scripts/campaign.form.js and advertisement.form.js (TikTok = channel 4).
4. Flows    new: Map TikTok Campaign Spend to Campaign, Map TikTok Advertisement Spend to Advertisement
            (copies of the Snap ones, triggered by sanidi_spend of the TikTok record);
            changed: the 8 existing roll-up flows add TikTok spend to the sum (and the two Social Media flows
            also trigger on the TikTok lookup). Each changed flow stays on. Safe to re-run: flows that already
            include TikTok are left alone.
"""
import base64
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_tables import SOLUTION, label  # noqa: E402
from dv import Dataverse  # noqa: E402

NS = uuid.UUID("9d1f4b2c-6a7e-4c3d-8e5f-0a1b2c3d4e5f")
LEVELS = {
    # roll-up table -> (TikTok table, lookup label, Snap lookup it follows, loop name, Snap map flow, new flow name)
    "sanidi_campaign": ("sanidi_tiktokcampaign", "TikTok Campaign", "sanidi_snapcampaign", "For_each_Campaign",
                        "fd296862-5dcc-f111-a05a-70a8a581e673", "Map TikTok Campaign Spend to Campaign"),
    "sanidi_advertisement": ("sanidi_tiktokadvertisement", "TikTok Advertisement", "sanidi_snapadvertisement",
                             "For_each_Advertisement", "79ce7e68-5dcc-f111-a05a-70a8a581e673",
                             "Map TikTok Advertisement Spend to Advertisement"),
}
EXISTING_FLOWS = {
    "sanidi_campaign": ["ec66d361-5dcc-f111-a05a-e4fb1ef50921", "5e159a64-5dcc-f111-a05a-70a8a581e1be",
                        "fd296862-5dcc-f111-a05a-70a8a581e673", "a9b0b168-5dcc-f111-a05a-e4fb1ef50921"],
    "sanidi_advertisement": ["182a6862-5dcc-f111-a05a-70a8a581e673", "5bce7e68-5dcc-f111-a05a-70a8a581e673",
                             "79ce7e68-5dcc-f111-a05a-70a8a581e673", "b2ce7e68-5dcc-f111-a05a-70a8a581e673"],
}
WEB_RESOURCES = ["sanidi_/scripts/campaign.form.js", "sanidi_/scripts/advertisement.form.js"]
SUM_TEXT = ("Google Ads cost + Meta spend + Snap spend", "Google Ads cost + Meta spend + Snap spend + TikTok spend")
LOOKUP_CLASS = "{270BD3DB-D9AF-4782-9025-509E298DEC0A}"


def relationship(table, tiktok, display):
    child = table.replace("sanidi_", "")
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        "SchemaName": f"{table}_{tiktok.replace('sanidi_', '')}_{tiktok}",
        "ReferencedEntity": tiktok, "ReferencingEntity": table,
        "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Archive": "RemoveLink",
                                 "Merge": "NoCascade", "Reparent": "NoCascade", "Share": "NoCascade",
                                 "Unshare": "NoCascade", "RollupView": "NoCascade"},
        "AssociatedMenuConfiguration": {"Behavior": "UseCollectionName", "Group": "Details", "Order": 10000},
        "Lookup": {
            "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "SchemaName": tiktok, "DisplayName": label(display),
            "Description": label(f"The {display} this {child} is linked to; its spend counts toward Cost."),
            "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                              "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"},
        },
    }


def form_with_lookup(xml, form_id, tiktok, display, after):
    """Inserts a hidden lookup row after the row holding `after`. None when it is already there or `after` isn't."""
    if f'datafieldname="{tiktok}"' in xml or f'datafieldname="{after}"' not in xml:
        return None
    i = xml.find(f'datafieldname="{after}"')
    end = xml.find("</row>", i) + len("</row>")
    cell = "{" + str(uuid.uuid5(NS, f"{form_id}/{tiktok}")) + "}"
    row = (f'<row><cell id="{cell}" locklevel="0" colspan="1" rowspan="1" visible="false">'
           f'<labels><label description="{display}" languagecode="1033" /></labels>'
           f'<control id="{tiktok}" classid="{LOOKUP_CLASS}" datafieldname="{tiktok}" disabled="false" /></cell></row>')
    return xml[:end] + row + xml[end:]


def add_tiktok(definition, table, loop):
    """Adds the TikTok spend to the List ($expand), the Total_Cost sum and the has-value check of a roll-up flow."""
    tiktok = LEVELS[table][0]
    item = f"items('{loop}')?['{tiktok}']?['sanidi_spend']"
    actions = definition["actions"]
    lst = actions[next(k for k in actions if k.startswith("List_"))]
    lst["inputs"]["parameters"]["$expand"] += f",{tiktok}($select=sanidi_spend)"
    body = actions[loop]["actions"]
    total = body["Total_Cost"]
    total["inputs"] = f"@add({total['inputs'][1:]}, float(coalesce({item}, 0)))"
    check = body["Has_Value_And_Changed"]["expression"]["and"][0]["or"]
    check.append({"not": {"equals": [f"@{item}", None]}})
    return definition


def patch_flow(dv, wid, body):
    """Saves a flow and keeps it on: turned off for the save, then on again even when the save failed."""
    was_on = dv.get(f"workflows({wid})?$select=statecode")["statecode"] == 1
    if was_on:
        dv.request("PATCH", f"workflows({wid})", {"statecode": 0, "statuscode": 1})
    try:
        dv.request("PATCH", f"workflows({wid})", body, solution=SOLUTION)
    finally:
        if was_on:
            dv.request("PATCH", f"workflows({wid})", {"statecode": 1, "statuscode": 2})


def main(apply):
    dv = Dataverse()
    out = HERE / "flows"
    out.mkdir(exist_ok=True)
    entities = []
    for table, (tiktok, display, after, loop, snap_flow, new_name) in LEVELS.items():
        # 1. lookup
        rel = relationship(table, tiktok, display)
        exists = dv.first("RelationshipDefinitions/Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata"
                          f"?$select=SchemaName&$filter=SchemaName eq '{rel['SchemaName']}'")
        print(f"{rel['SchemaName']}: {'exists' if exists else 'create'}")
        if apply and not exists:
            dv.request("POST", "RelationshipDefinitions", rel, solution=SOLUTION)
        entities.append(table)

        # 2. forms
        for form in dv.get(f"systemforms?$select=formid,name,type,formxml&$filter=objecttypecode eq '{table}'")["value"]:
            xml = form_with_lookup(form["formxml"], form["formid"], tiktok, display, after)
            if xml is None:
                continue
            print(f"  form '{form['name']}' (type {form['type']}): add {tiktok} after {after}")
            if apply:
                dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": xml}, solution=SOLUTION)

        # 4a. new TikTok map flow, from the Snap one
        snap = dv.get(f"workflows({snap_flow})?$select=clientdata,description")
        clientdata = json.loads(snap["clientdata"])
        definition = clientdata["properties"]["definition"]
        if tiktok not in json.dumps(definition):
            add_tiktok(definition, table, loop)
        trigger = next(iter(definition["triggers"].values()))["inputs"]["parameters"]
        snap_table = after
        trigger["subscriptionRequest/entityname"] = tiktok
        lst = definition["actions"][next(k for k in definition["actions"] if k.startswith("List_"))]
        lst["inputs"]["parameters"]["$filter"] = (f"_{tiktok}_value eq @{{triggerOutputs()?['body/{tiktok}id']}}")
        assert snap_table not in json.dumps(trigger)
        for conn in clientdata["properties"]["connectionReferences"].values():
            conn["connection"].pop("name", None)  # bind through the connection reference only
        description = (f"When {tiktok}.sanidi_spend is created or updated, recalculates {table}.sanidi_cost "
                       f"({SUM_TEXT[1]}) on every {display.split()[-1]} linked to it.")
        (out / (new_name.lower().replace(" ", "-") + ".json")).write_text(json.dumps(clientdata, indent=2) + "\n")
        existing = dv.first(f"workflows?$select=workflowid&$filter=name eq '{new_name}' and category eq 5")
        print(f"  flow '{new_name}': {'exists' if existing else 'create (turned on after the lookups are published)'}")
        if apply and not existing:
            wid = str(uuid.uuid5(NS, new_name))
            dv.request("POST", "workflows", {"workflowid": wid, "category": 5, "type": 1, "primaryentity": "none",
                                             "name": new_name, "description": description,
                                             "clientdata": json.dumps(clientdata)}, solution=SOLUTION)

    # 3. web resources
    for name in WEB_RESOURCES:
        content = (ROOT / "webresources" / name).read_text()
        wr = dv.first(f"webresourceset?$select=webresourceid,content&$filter=name eq '{name}'")
        current = base64.b64decode(wr["content"]).decode()
        print(f"{name}: {'up to date' if current == content else 'update'}")
        if apply and current != content:
            dv.request("PATCH", f"webresourceset({wr['webresourceid']})",
                       {"content": base64.b64encode(content.encode()).decode()}, solution=SOLUTION)

    if apply:
        rows = "".join(f"<entity>{e}</entity>" for e in entities)
        ids = [dv.first(f"webresourceset?$select=webresourceid&$filter=name eq '{n}'")["webresourceid"] for n in WEB_RESOURCES]
        wrs = "".join(f"<webresource>{i}</webresource>" for i in ids)
        dv.request("POST", "PublishXml", idempotent=True, body={
            "ParameterXml": f"<importexportxml><entities>{rows}</entities><webresources>{wrs}</webresources></importexportxml>"})
        print("published")

    # 4b. existing roll-up flows
    for table, wids in EXISTING_FLOWS.items():
        tiktok, _, _, loop, _, _ = LEVELS[table]
        for wid in wids:
            w = dv.get(f"workflows({wid})?$select=name,clientdata,description")
            clientdata = json.loads(w["clientdata"])
            definition = clientdata["properties"]["definition"]
            if tiktok in json.dumps(definition):
                print(f"flow '{w['name']}': already includes TikTok")
                continue
            add_tiktok(definition, table, loop)
            trigger = next(iter(definition["triggers"].values()))["inputs"]["parameters"]
            if trigger.get("subscriptionRequest/entityname") == table:  # Social Media flows: trigger on the lookups
                trigger["subscriptionRequest/filteringattributes"] += f",{tiktok}"
            description = (w["description"] or "").replace(SUM_TEXT[0], SUM_TEXT[1])
            (out / ("updated-" + w["name"].lower().replace(" ", "-") + ".json")).write_text(
                json.dumps(clientdata, indent=2) + "\n")
            print(f"flow '{w['name']}': add TikTok spend")
            if apply:
                patch_flow(dv, wid, {"clientdata": json.dumps(clientdata), "description": description})

    # turn the new flows on
    if apply:
        for _, (_, _, _, _, _, new_name) in LEVELS.items():
            w = dv.first(f"workflows?$select=workflowid,statecode&$filter=name eq '{new_name}' and category eq 5")
            if w and w["statecode"] != 1:
                dv.request("PATCH", f"workflows({w['workflowid']})", {"statecode": 1, "statuscode": 2})
                print(f"turned on '{new_name}'")


if __name__ == "__main__":
    main("--apply" in sys.argv)
