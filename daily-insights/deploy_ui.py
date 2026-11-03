"""Forms, views, parent-form subgrids, the "Social Media Insights" site map area, the app tables and the Manager role
for the 26 insight tables (PLAN.md §3.1). Everything is saved in the patch (spec.SOLUTION).

  python3 deploy_ui.py            # dry run
  python3 deploy_ui.py --apply    # forms + views of the 26 tables, then parents, app, role; publish
  python3 deploy_ui.py --apply --only=forms|parents|app|role

Main form "Information" (same style as the Snap / Google Ads / TikTok tables):
  header: Date, Period Closed, Last Synced On
  General: Identity (Name, parent, Owner, Platform ID) | Period (Date, Day, Month, Year, Weekday) | Status
  Insights: the parent's Insights (or Performance) sections, same order and labels, with the copied columns
  Sync: Last Synced On, Raw Payload
Views: Active (newest first: Name, parent, Date, the platform's main metrics, Period Closed, Last Synced On) and
Inactive (Name, parent, Date, Period Closed, Last Synced On, Created On).
"""
import html
import re
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

SOLUTION = spec.SOLUTION
EN, AR = 1033, 1025
NS = uuid.UUID("7a1d3c5e-2b4f-4e6a-9c8d-0f1e2d3c4b5a")
APP = "sanidi_AlSanidiMarketing"
AREA_ID = "area_socialmediainsights"
ROLE = "AlSanidi | Marketing | Manager"
PRIVILEGES = ["Read", "Append", "AppendTo"]
GROUP_TITLES = {"meta": "Meta", "snap": "SnapChat", "google": "Google Ads", "tiktok": "TikTok"}
CLASS = {
    "StringType": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}", "MemoType": "{E0DECE4B-6FC8-4a8f-A065-082708572369}",
    "PicklistType": "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}", "BooleanType": "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}",
    "IntegerType": "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}", "DecimalType": "{C3EFE0C3-0EC6-42be-8349-CBD9079DFD8E}",
    "DoubleType": "{0D2C745A-E5A8-4c8f-BA63-C6D3BB604660}", "MoneyType": "{533B9E00-756B-4312-95A0-DC888637AC78}",
    "DateTimeType": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}", "LookupType": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "OwnerType": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}", "subgrid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}",
}
TAB_AR = {"General": "عام", "Insights": "مؤشرات الأداء", "Sync": "المزامنة"}
SECTION_AR = {"Identity": "الهوية", "Period": "الفترة", "Status": "الحالة", "Sync": "المزامنة",
              "Other": "أخرى", "Daily Insights": "مؤشرات الأداء اليومية",
              "Monthly Insights": "مؤشرات الأداء الشهرية"}
AREA_TITLE = ("Social Media Insights", "مؤشرات أداء وسائل التواصل الاجتماعي")


def gid(*parts):
    return "{" + str(uuid.uuid5(NS, "/".join(parts))) + "}"


def lbl(en, ar=None):
    ar_label = f'<label description={quoteattr(ar)} languagecode="{AR}" />' if ar else ""
    return f'<labels><label description={quoteattr(en)} languagecode="{EN}" />{ar_label}</labels>'


def attributes(dv, logical):
    """logical name -> (type, English label, Arabic label)."""
    out = {}
    for a in dv.get(f"EntityDefinitions(LogicalName='{logical}')/Attributes"
                    "?$select=LogicalName,AttributeTypeName,DisplayName")["value"]:
        labels = {l["LanguageCode"]: l["Label"] for l in (a["DisplayName"] or {}).get("LocalizedLabels", [])}
        out[a["LogicalName"]] = (a["AttributeTypeName"]["Value"], labels.get(EN, a["LogicalName"]), labels.get(AR))
    return out


def cell(table, field, attrs, disabled=False):
    typ, en, ar = attrs[field]
    dis = ' disabled="true"' if disabled else ""
    return (f'<row><cell id="{gid(table, "cell", field)}">{lbl(en, ar)}'
            f'<control id="{field}" classid="{CLASS[typ]}" datafieldname="{field}"{dis} /></cell></row>')


def section(table, key, en, ar, rows_xml):
    return (f'<section name="{key}" showlabel="true" showbar="false" IsUserDefined="0" id="{gid(table, "section", key)}" '
            f'columns="1" labelwidth="200">{lbl(en, ar)}<rows>{rows_xml}</rows></section>')


def tab(table, key, en, ar, sections):
    # Forms allow at most 3 columns per tab: extra sections stack in the last column.
    groups = [[s] for s in sections[:2]] + [sections[2:]] if len(sections) > 3 else [[s] for s in sections]
    width = f"{100 // len(groups)}%"
    cols = "".join(f'<column width="{width}"><sections>{"".join(g)}</sections></column>' for g in groups)
    return (f'<tab name="{key}" verticallayout="true" id="{gid(table, "tab", key)}" IsUserDefined="1" expanded="true" '
            f'showlabel="true">{lbl(en, ar)}<columns>{cols}</columns></tab>')


def parent_insight_sections(dv, parent):
    """(name, English label, Arabic label, [fields]) of the parent form's Insights / Performance tab, in order."""
    form = dv.first(f"systemforms?$select=formxml&$filter=objecttypecode eq '{parent}' and type eq 2 "
                    "and name eq 'Information'")
    xml = form["formxml"]
    m = re.search(r'<tab [^>]*name="(insights|performance)".*?</tab>', xml, re.S)
    if not m:
        return []
    out = []
    for s in re.finditer(r'<section [^>]*name="([^"]+)"[^>]*>(.*?)</section>', m.group(0), re.S):
        body = s.group(2)
        # Labels come escaped from the form XML; they are escaped again when written. "(all time)" only fits the
        # parent's lifetime insights.
        labels = {int(l): re.sub(r"\s*\((all time|طوال المدة)\)", "", html.unescape(d)) for d, l in re.findall(
            r'<label description="([^"]*)" languagecode="(\d+)"', body.split("<rows>")[0])}
        fields = re.findall(r'datafieldname="([^"]+)"', body)
        out.append((s.group(1), labels.get(EN, s.group(1)), labels.get(AR), fields))
    return out


def form_xml(dv, logical, t, attrs):
    daily = t["period"] == "daily"
    identity = "".join(cell(logical, f, attrs) for f in ["sanidi_name", t["lookup"], "ownerid", "sanidi_platformid"])
    period_fields = ["sanidi_date", "sanidi_day", "sanidi_month", "sanidi_year", "sanidi_weekday"] if daily else \
        ["sanidi_date", "sanidi_month", "sanidi_year"]
    general = [section(logical, "identity", "Identity", SECTION_AR["Identity"], identity),
               section(logical, "period", "Period", SECTION_AR["Period"],
                       "".join(cell(logical, f, attrs) for f in period_fields)),
               section(logical, "status", "Status", SECTION_AR["Status"],
                       "".join(cell(logical, f, attrs) for f in ["sanidi_periodclosed", "sanidi_nodata"]))]
    metrics = [c["name"] for c in t["metrics"]]
    placed, insight_sections = set(), []
    for name, en, ar, fields in parent_insight_sections(dv, t["parent"]):
        mine = [f for f in fields if f in metrics and f not in placed]
        if not mine:
            continue
        placed.update(mine)
        insight_sections.append(section(logical, name, en, ar, "".join(cell(logical, f, attrs) for f in mine)))
    rest = [f for f in metrics if f not in placed]
    if rest:
        insight_sections.append(section(logical, "other", "Other", SECTION_AR["Other"],
                                        "".join(cell(logical, f, attrs) for f in rest)))
    sync = [section(logical, "sync", "Sync", SECTION_AR["Sync"],
                    "".join(cell(logical, f, attrs) for f in ["sanidi_lastsyncedon", "sanidi_rawpayload"]))]
    tabs = (tab(logical, "general", "General", TAB_AR["General"], general)
            + tab(logical, "insights", "Insights", TAB_AR["Insights"], insight_sections)
            + tab(logical, "sync", "Sync", TAB_AR["Sync"], sync))
    header = "".join(
        f'<cell id="{gid(logical, "header", f)}">{lbl(attrs[f][1], attrs[f][2])}<control id="header_{f}" '
        f'classid="{CLASS[attrs[f][0]]}" datafieldname="{f}" disabled="true" /></cell>'
        for f in ["sanidi_date", "sanidi_periodclosed", "sanidi_lastsyncedon"])
    return (f'<form headerdensity="HighWithControls"><tabs>{tabs}</tabs>'
            f'<header id="{gid(logical, "header")}" celllabelposition="Top" columns="111" labelwidth="115" '
            f'celllabelalignment="Left"><rows><row>{header}</row></rows></header></form>'), len(placed), len(rest)


def view_xml(logical, otc, view_id, columns, active):
    attrs = "".join(f'<attribute name="{c}" />' for c in [logical + "id"] + columns)
    fetch = (f'<fetch version="1.0" mapping="logical" savedqueryid="{view_id}"><entity name="{logical}">{attrs}'
             f'<order attribute="sanidi_date" descending="true" /><order attribute="sanidi_name" descending="false" />'
             f'<filter type="and"><condition attribute="statecode" operator="eq" value="{0 if active else 1}" />'
             f'</filter></entity></fetch>')
    widths = {"sanidi_name": 300}
    cells = "".join(f'<cell name="{c}" width="{widths.get(c, 150 if c != columns[1] else 200)}" />' for c in columns)
    layout = (f'<grid name="resultset" jump="sanidi_name" select="1" icon="1" preview="1" object="{otc}">'
              f'<row name="result" id="{logical}id">{cells}</row></grid>')
    return fetch, layout


def forms_and_views(dv, apply, tables):
    for logical, t in tables.items():
        attrs = attributes(dv, logical)
        otc = dv.get(f"EntityDefinitions(LogicalName='{logical}')?$select=ObjectTypeCode")["ObjectTypeCode"]
        form = dv.first(f"systemforms?$select=formid,name&$filter=objecttypecode eq '{logical}' and type eq 2")
        xml, placed, rest = form_xml(dv, logical, t, attrs)
        views = dv.get(f"savedqueries?$select=savedqueryid,name,isdefault&$filter=returnedtypecode eq '{logical}' "
                       "and querytype eq 0")["value"]
        active = next(v for v in views if v["isdefault"])
        inactive = next((v for v in views if v["name"].startswith("Inactive")), None)
        main = ["sanidi_name", t["lookup"], "sanidi_date"] + spec.VIEW_METRICS[t["platform"]] + \
               ["sanidi_periodclosed", "sanidi_lastsyncedon"]
        short = ["sanidi_name", t["lookup"], "sanidi_date", "sanidi_periodclosed", "sanidi_lastsyncedon", "createdon"]
        print(f"{logical}: form '{form['name']}' ({xml.count('<control ')} controls; {placed} metrics in parent "
              f"sections, {rest} in Other); views '{active['name']}' ({len(main)} cols)"
              + (f", '{inactive['name']}'" if inactive else ""))
        if not apply:
            continue
        dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": xml}, solution=SOLUTION)
        fetch, layout = view_xml(logical, otc, active["savedqueryid"], main, True)
        dv.request("PATCH", f"savedqueries({active['savedqueryid']})", {"fetchxml": fetch, "layoutxml": layout},
                   solution=SOLUTION)
        if inactive:
            fetch, layout = view_xml(logical, otc, inactive["savedqueryid"], short, False)
            dv.request("PATCH", f"savedqueries({inactive['savedqueryid']})",
                       {"fetchxml": fetch, "layoutxml": layout}, solution=SOLUTION)


def subgrid_section(parent, t, logical, view_id, word):
    key = f"{t['period']}insights"
    en = f"{word} Insights"
    rows = "<row />" * 9
    return (f'<section name="{key}" showlabel="true" showbar="false" IsUserDefined="0" id="{gid(parent, "section", key)}" '
            f'columns="1">{lbl(en, SECTION_AR[en])}<rows><row>'
            f'<cell id="{gid(parent, "cell", key)}" showlabel="false" rowspan="10" colspan="1" auto="false">'
            f'{lbl(en, SECTION_AR[en])}<control id="{logical}s" classid="{CLASS["subgrid"]}" indicationOfSubgrid="true" '
            f'uniqueid="{gid(parent, "grid", key)}"><parameters>'
            f'<TargetEntityType>{logical}</TargetEntityType><ViewId>{{{view_id}}}</ViewId>'
            f'<RelationshipName>{t["relationship"]}</RelationshipName><AutoExpand>Fixed</AutoExpand>'
            f'<EnableQuickFind>false</EnableQuickFind><EnableViewPicker>true</EnableViewPicker><ViewIds />'
            f'<EnableJumpBar>false</EnableJumpBar><ChartGridMode>Grid</ChartGridMode><VisualizationId />'
            f'<IsUserView>false</IsUserView><IsUserChart>false</IsUserChart><RecordsPerPage>10</RecordsPerPage>'
            f'<HeaderColorCode>#F3F3F3</HeaderColorCode></parameters></control></cell></row>{rows}</rows></section>')


def parent_subgrids(dv, apply, tables):
    """Daily / Monthly Insights subgrids at the end of each parent form's Insights (or Performance) tab."""
    by_parent = {}
    for logical, t in tables.items():
        by_parent.setdefault(t["parent"], []).append((logical, t))
    for parent, children in by_parent.items():
        form = dv.first(f"systemforms?$select=formid,formxml&$filter=objecttypecode eq '{parent}' and type eq 2 "
                        "and name eq 'Information'")
        xml = form["formxml"]
        m = re.search(r'(<tab [^>]*name="(insights|performance)".*?)(</sections></column></columns></tab>)', xml, re.S)
        if not m:
            raise SystemExit(f"{parent}: no Insights / Performance tab")
        added = []
        new_sections = ""
        for logical, t in sorted(children, key=lambda c: c[1]["period"]):
            if f"<TargetEntityType>{logical}</TargetEntityType>" in xml:
                continue
            view = dv.first(f"savedqueries?$select=savedqueryid&$filter=returnedtypecode eq '{logical}' "
                            "and querytype eq 0 and isdefault eq true")
            new_sections += subgrid_section(parent, t, logical, view["savedqueryid"],
                                            "Daily" if t["period"] == "daily" else "Monthly")
            added.append(logical)
        print(f"{parent}: {'add ' + ', '.join(added) if added else 'subgrids exist'} ({m.group(2)} tab)")
        if apply and added:
            # New sections go into the last column of the tab, after its existing sections.
            xml = xml[:m.start(3)] + new_sections + xml[m.start(3):]
            dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": xml}, solution=SOLUTION)


def area_xml(tables):
    groups = ""
    for platform, title in GROUP_TITLES.items():
        subareas = "".join(
            f'<SubArea Id="subarea_{logical.replace("sanidi_", "")}" Entity="{logical}" '
            'Client="All,Outlook,OutlookLaptopClient,OutlookWorkstationClient,Web" AvailableOffline="true" '
            'PassParams="false" Sku="All,OnPremise,Live,SPLA" />'
            for logical, t in tables.items() if t["platform"] == platform)
        groups += (f'<Group Id="group_insights_{platform}" ResourceId="SitemapDesigner.NewGroup" IsProfile="false" '
                   f'ToolTipResourseId="SitemapDesigner.Unknown"><Titles><Title LCID="{EN}" Title="{title}" />'
                   f'<Title LCID="{AR}" Title="{title}" /></Titles>{subareas}</Group>')
    return (f'<Area Id="{AREA_ID}" ResourceId="SitemapDesigner.NewArea" ShowGroups="true"><Titles>'
            f'<Title LCID="{EN}" Title="{AREA_TITLE[0]}" /><Title LCID="{AR}" Title="{AREA_TITLE[1]}" /></Titles>'
            f'{groups}</Area>')


def app(dv, apply, tables):
    appmodule = dv.first(f"appmodules?$select=appmoduleid,name&$filter=uniquename eq '{APP}'")
    sitemap = dv.first(f"sitemaps?$select=sitemapid,sitemapxml&$filter=sitemapnameunique eq '{APP}'")
    xml = sitemap["sitemapxml"]
    has_area = f'Id="{AREA_ID}"' in xml
    print(f"site map: area '{AREA_TITLE[0]}' {'exists' if has_area else 'add (after Integration)'}")
    if apply and not has_area:
        xml = xml.replace("</SiteMap>", area_xml(tables) + "</SiteMap>")
        dv.request("PATCH", f"sitemaps({sitemap['sitemapid']})", {"sitemapxml": xml}, solution=SOLUTION)
    components = [{"@odata.type": "Microsoft.Dynamics.CRM.entity",
                   "entityid": dv.get(f"EntityDefinitions(LogicalName='{logical}')?$select=MetadataId")["MetadataId"]}
                  for logical in tables]
    print(f"app '{appmodule['name']}': add {len(components)} tables")
    if apply:
        dv.request("POST", "AddAppComponents", {"AppId": appmodule["appmoduleid"], "Components": components},
                   idempotent=True)
        # The app module and its site map belong to the base solution; add them to the patch so the changes ship.
        for component_id, component_type in ((appmodule["appmoduleid"], 80), (sitemap["sitemapid"], 62)):
            dv.request("POST", "AddSolutionComponent", {
                "ComponentId": component_id, "ComponentType": component_type, "SolutionUniqueName": SOLUTION,
                "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}, idempotent=True)
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><sitemaps><sitemap>{sitemap['sitemapid']}</sitemap></sitemaps>"
                   f"<appmodules><appmodule>{appmodule['appmoduleid']}</appmodule></appmodules></importexportxml>"})
        print("  site map + app published")


def role(dv, apply, tables):
    roles = dv.get(f"roles?$select=roleid,_parentrootroleid_value&$filter=name eq '{ROLE}'")["value"]
    root = next(r for r in roles if r["roleid"] == r["_parentrootroleid_value"])
    privileges = []
    for logical in tables:
        for op in PRIVILEGES:
            priv = dv.first(f"privileges?$select=privilegeid&$filter=name eq 'prv{op}{logical}'")
            privileges.append({"PrivilegeId": priv["privilegeid"], "Depth": "Global"})
    print(f"role '{ROLE}': {', '.join(PRIVILEGES)} (organization) on {len(tables)} tables")
    if apply:
        dv.request("POST", f"roles({root['roleid']})/Microsoft.Dynamics.CRM.AddPrivilegesRole",
                   {"Privileges": privileges}, idempotent=True)
        dv.request("POST", "AddSolutionComponent", {
            "ComponentId": root["roleid"], "ComponentType": 20, "SolutionUniqueName": SOLUTION,
            "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}, idempotent=True)
        print("  set; role added to the patch")


def main(apply, only):
    dv = Dataverse()
    tables = spec.tables()
    if only in (None, "forms"):
        forms_and_views(dv, apply, tables)
        if apply:
            xml = "".join(f"<entity>{t}</entity>" for t in tables)
            dv.request("POST", "PublishXml", idempotent=True,
                       body={"ParameterXml": f"<importexportxml><entities>{xml}</entities></importexportxml>"})
            print("published the 26 tables")
    if only in (None, "parents"):
        parent_subgrids(dv, apply, tables)
        if apply:
            parents = sorted({t["parent"] for t in tables.values()})
            xml = "".join(f"<entity>{p}</entity>" for p in parents)
            dv.request("POST", "PublishXml", idempotent=True,
                       body={"ParameterXml": f"<importexportxml><entities>{xml}</entities></importexportxml>"})
            print("published the 13 parent tables")
    if only in (None, "app"):
        app(dv, apply, tables)
    if only in (None, "role"):
        role(dv, apply, tables)


if __name__ == "__main__":
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    main("--apply" in sys.argv, only)
