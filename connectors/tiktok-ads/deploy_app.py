"""Adds the TikTok tables to the AlSanidi | Marketing app and gives the Manager role access, like Snap / Google Ads.

  python3 deploy_app.py            # dry run
  python3 deploy_app.py --apply    # update the site map + app, set role privileges, publish

- Site map: a "TikTok" group in the Integration area (after Google Ads, before Sync Control) with the 3 tables.
- App "AlSanidi | Marketing": the 3 tables are added as app components (their forms and views come with them).
- Role "AlSanidi | Marketing | Manager": Read, Append and Append To at organization level on the 3 tables, the
  same as it has on the Snap / Meta / Google Ads tables. The role is not in the solution, so this is per environment.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from deploy_tables import SOLUTION  # noqa: E402
from dv import Dataverse  # noqa: E402

APP = "sanidi_AlSanidiMarketing"
GROUP_ID = "group_tiktok"
BEFORE_GROUP = 'Id="group_synccontrol"'
ROLE = "AlSanidi | Marketing | Manager"
PRIVILEGES = ["Read", "Append", "AppendTo"]
SUBAREA = ('<SubArea Id="subarea_{table}" Entity="{entity}" '
           'Client="All,Outlook,OutlookLaptopClient,OutlookWorkstationClient,Web" AvailableOffline="true" '
           'PassParams="false" Sku="All,OnPremise,Live,SPLA" />')


def group_xml():
    subareas = "".join(SUBAREA.format(table=t, entity=spec.PREFIX + t) for t in spec.TABLES)
    return (f'<Group Id="{GROUP_ID}" ResourceId="SitemapDesigner.NewGroup" IsProfile="false" '
            f'ToolTipResourseId="SitemapDesigner.Unknown"><Titles><Title LCID="1033" Title="TikTok" /></Titles>'
            f'{subareas}</Group>')


def main(apply):
    dv = Dataverse()
    app = dv.first(f"appmodules?$select=appmoduleid,name&$filter=uniquename eq '{APP}'")
    sitemap = dv.first(f"sitemaps?$select=sitemapid,sitemapxml&$filter=sitemapnameunique eq '{APP}'")
    xml = sitemap["sitemapxml"]
    has_group = f'Id="{GROUP_ID}"' in xml
    print(f"site map: TikTok group {'exists' if has_group else 'add before Sync Control'}")
    if apply and not has_group:
        i = xml.find(BEFORE_GROUP)
        start = xml.rfind("<Group", 0, i)
        if i < 0 or start < 0:
            raise SystemExit("Sync Control group not found in the site map")
        xml = xml[:start] + group_xml() + xml[start:]
        dv.request("PATCH", f"sitemaps({sitemap['sitemapid']})", {"sitemapxml": xml}, solution=SOLUTION)
        print("  added")

    components = []
    for t in spec.TABLES:
        meta = dv.get(f"EntityDefinitions(LogicalName='{spec.PREFIX + t}')?$select=MetadataId")
        components.append({"@odata.type": "Microsoft.Dynamics.CRM.entity", "entityid": meta["MetadataId"]})
    print(f"app '{app['name']}': add {len(components)} tables")
    if apply:
        dv.request("POST", "AddAppComponents", {"AppId": app["appmoduleid"], "Components": components},
                   idempotent=True)
        print("  added")

    roles = dv.get(f"roles?$select=roleid,_parentrootroleid_value&$filter=name eq '{ROLE}'")["value"]
    root = next(r for r in roles if r["roleid"] == r["_parentrootroleid_value"])
    privileges = []
    for t in spec.TABLES:
        for op in PRIVILEGES:
            priv = dv.first(f"privileges?$select=privilegeid&$filter=name eq 'prv{op}{spec.PREFIX + t}'")
            privileges.append({"PrivilegeId": priv["privilegeid"], "Depth": "Global"})
    print(f"role '{ROLE}': {', '.join(PRIVILEGES)} (organization) on {len(spec.TABLES)} tables")
    if apply:
        dv.request("POST", f"roles({root['roleid']})/Microsoft.Dynamics.CRM.AddPrivilegesRole",
                   {"Privileges": privileges}, idempotent=True)
        print("  set")

    if apply:
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><sitemaps><sitemap>{sitemap['sitemapid']}</sitemap></sitemaps>"
                   f"<appmodules><appmodule>{app['appmoduleid']}</appmodule></appmodules></importexportxml>"})
        print("published")


if __name__ == "__main__":
    main("--apply" in sys.argv)
