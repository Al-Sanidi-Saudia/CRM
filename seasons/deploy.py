"""Creates the Season Calendar table in the AlSanidi | Marketing solution and loads season_calendar_<year>.csv.

  python3 deploy.py            # dry run: what would be created / changed
  python3 deploy.py --apply    # create what is missing, update the form, view, app and rows, then publish

Safe to re-run: existing table and columns are kept, rows are matched on Date and only changed values written.

- Table sanidi_seasoncalendar (organization owned): Name (yyyy-mm-dd), Date (date only, alternate key),
  Year (text) and one Yes/No column per season in spec.FLAGS. Labels in English (1033) and Arabic (1025).
- Main form: tab "General" with a Day section and one section per group in spec.SECTIONS.
- Active view: Date, Year and every flag, sorted by Date. Inactive view: Date, Year, Created On.
- App "AlSanidi | Marketing": a "Seasons" group at the end of the General area of the site map. Role
  "AlSanidi | Marketing | Manager": Read, Append, Append To at organization level, like the other tables.
"""
import csv
import sys
import time
import urllib.error
import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

SOLUTION = "AlSanidiMarketing"
APP = "sanidi_AlSanidiMarketing"
GENERAL_AREA = 'Id="area_93dfabcb"'
ROLE = "AlSanidi | Marketing | Manager"
PRIVILEGES = ["Read", "Append", "AppendTo"]
LOGICAL = spec.PREFIX + spec.TABLE
KEY = spec.PREFIX + "seasoncalendar_date"
NS = uuid.UUID("8f0c6a1e-2b7d-4c39-9e51-d4a7b3f60c18")
BOOL_CLASS = "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}"
TEXT_CLASS = "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}"
DATE_CLASS = "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}"


def label(en, ar):
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [
        {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": en, "LanguageCode": 1033},
        {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": ar, "LanguageCode": 1025}]}


def required(level):
    return {"Value": level, "CanBeChanged": True, "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}


def base(column, en, ar, desc_en, desc_ar, level="None"):
    return {"SchemaName": spec.PREFIX + column, "DisplayName": label(en, ar),
            "Description": label(desc_en, desc_ar), "RequiredLevel": required(level)}


def columns():
    """(logical name, metadata) for every column except the primary name, in form order."""
    out = [
        (spec.PREFIX + spec.DATE[0], {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
                                      **base(*spec.DATE, level="ApplicationRequired"),
                                      "Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}}),
        (spec.PREFIX + spec.YEAR_COL[0], {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                                          **base(*spec.YEAR_COL, level="ApplicationRequired"),
                                          "MaxLength": 4, "FormatName": {"Value": "Text"}}),
    ]
    for column, en, ar, _ in spec.FLAGS:
        out.append((spec.PREFIX + column, {
            "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
            **base(column, en, ar, *spec.flag_description(en, ar)), "DefaultValue": False,
            "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                          "TrueOption": {"Value": 1, "Label": label("Yes", "نعم")},
                          "FalseOption": {"Value": 0, "Label": label("No", "لا")}}}))
    return out


def entity_metadata():
    name = {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", **base(*spec.NAME),
            "IsPrimaryName": True, "MaxLength": 100, "FormatName": {"Value": "Text"}}
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata", "SchemaName": LOGICAL,
            "DisplayName": label(*spec.DISPLAY), "DisplayCollectionName": label(*spec.PLURAL),
            "Description": label(*spec.DESCRIPTION), "OwnershipType": "OrganizationOwned",
            "HasActivities": False, "HasNotes": False, "IsActivity": False, "ChangeTrackingEnabled": True,
            "Attributes": [name]}


def table_exists(dv):
    return dv.first(f"EntityDefinitions?$select=LogicalName&$filter=LogicalName eq '{LOGICAL}'") is not None


def deploy_table(dv, apply):
    exists = table_exists(dv)
    existing = set()
    if exists:
        existing = {a["LogicalName"] for a in dv.get(
            f"EntityDefinitions(LogicalName='{LOGICAL}')/Attributes?$select=LogicalName")["value"]}
    todo = [(n, m) for n, m in columns() if n not in existing]
    print(f"{LOGICAL}: table {'exists' if exists else 'create'}; {len(todo)} columns to add")
    if not apply:
        return
    if not exists:
        dv.request("POST", "EntityDefinitions", entity_metadata(), solution=SOLUTION)
        print("  created table")
        time.sleep(20)  # a brand-new table rejects columns for a short while
    for i, (name, metadata) in enumerate(todo, 1):
        add_column(dv, name, metadata)
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} columns")


def add_column(dv, name, metadata):
    """Metadata writes sometimes fail transiently; retry only after checking the column isn't there."""
    path = f"EntityDefinitions(LogicalName='{LOGICAL}')/Attributes"
    for attempt in range(4):
        try:
            dv.request("POST", path, metadata, solution=SOLUTION)
            return
        except (RuntimeError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            text = str(e).lower()
            # "Cannot start another [EntityCustomization]": metadata changes run one at a time per environment.
            transient = not isinstance(e, RuntimeError) or "unexpected error" in text or "cannot start another" in text
            if attempt == 3 or not transient:
                raise
            time.sleep(10 * (attempt + 1))
            if dv.first(f"{path}?$select=LogicalName&$filter=LogicalName eq '{name}'"):
                return


def deploy_key(dv, apply):
    if not table_exists(dv):
        print("alternate key on Date: after the table is created")
        return
    path = f"EntityDefinitions(LogicalName='{LOGICAL}')/Keys"
    key = dv.first(f"{path}?$select=LogicalName,EntityKeyIndexStatus&$filter=LogicalName eq '{KEY}'")
    print(f"alternate key on Date: {key['EntityKeyIndexStatus'] if key else 'create'}")
    if apply and not key:
        dv.request("POST", path, {"SchemaName": KEY, "DisplayName": label("Date", "التاريخ"),
                                  "KeyAttributes": [spec.PREFIX + spec.DATE[0]]}, solution=SOLUTION)
        print("  created (the index builds in the background)")


def gid(*parts):
    return "{" + str(uuid.uuid5(NS, "/".join(parts))) + "}"


def lbl(en, ar):
    return (f'<labels><label description={quoteattr(en)} languagecode="1033" />'
            f'<label description={quoteattr(ar)} languagecode="1025" /></labels>')


def cell(field, en, ar, classid):
    return (f'<row><cell id="{gid("cell", field)}">{lbl(en, ar)}'
            f'<control id="{field}" classid="{classid}" datafieldname="{field}" /></cell></row>')


def section(key, en, ar, rows):
    return (f'<section name="{key}" showlabel="true" showbar="false" IsUserDefined="0" id="{gid("section", key)}" '
            f'columns="1" labelwidth="200">{lbl(en, ar)}<rows>{"".join(rows)}</rows></section>')


def form_xml():
    flags = {c: (en, ar) for c, en, ar, _ in spec.FLAGS}
    day = section(*spec.DAY_SECTION, [cell(spec.PREFIX + spec.DATE[0], spec.DATE[1], spec.DATE[2], DATE_CLASS),
                                      cell(spec.PREFIX + spec.YEAR_COL[0], spec.YEAR_COL[1], spec.YEAR_COL[2],
                                           TEXT_CLASS),
                                      cell(spec.PREFIX + spec.NAME[0], spec.NAME[1], spec.NAME[2], TEXT_CLASS)])
    groups = {key: section(key, en, ar, [cell(spec.PREFIX + c, *flags[c], BOOL_CLASS) for c in cols])
              for key, en, ar, cols in spec.SECTIONS}
    layout = [[day, groups["religious"]], [groups["travel"], groups["paydays"]], [groups["school"]]]
    cols = "".join(f'<column width="33%"><sections>{"".join(s)}</sections></column>' for s in layout)
    key, en, ar = spec.TAB
    return (f'<form><tabs><tab name="{key}" verticallayout="true" id="{gid("tab", key)}" IsUserDefined="1" '
            f'expanded="true" showlabel="true">{lbl(en, ar)}<columns>{cols}</columns></tab></tabs></form>')


def view_xml(otc, view_id, cols, active):
    date = spec.PREFIX + spec.DATE[0]
    attrs = "".join(f'<attribute name="{c}" />' for c in [LOGICAL + "id"] + cols)
    fetch = (f'<fetch version="1.0" mapping="logical" savedqueryid="{view_id}"><entity name="{LOGICAL}">{attrs}'
             f'<order attribute="{date}" descending="false" /><filter type="and">'
             f'<condition attribute="statecode" operator="eq" value="{0 if active else 1}" /></filter></entity></fetch>')
    cells = "".join(f'<cell name="{c}" width="{120 if c == date else 100}" />' for c in cols)
    layout = (f'<grid name="resultset" jump="{spec.PREFIX + spec.NAME[0]}" select="1" icon="1" preview="1" '
              f'object="{otc}"><row name="result" id="{LOGICAL}id">{cells}</row></grid>')
    return fetch, layout


def deploy_ui(dv, apply):
    if not table_exists(dv):
        print("form / views: after the table is created")
        return
    otc = dv.get(f"EntityDefinitions(LogicalName='{LOGICAL}')?$select=ObjectTypeCode")["ObjectTypeCode"]
    form = dv.first(f"systemforms?$select=formid,name&$filter=objecttypecode eq '{LOGICAL}' and type eq 2")
    views = dv.get(f"savedqueries?$select=savedqueryid,name,isdefault&$filter=returnedtypecode eq '{LOGICAL}' "
                   f"and querytype eq 0")["value"]
    active = next(v for v in views if v["isdefault"])
    inactive = next((v for v in views if v["name"].startswith("Inactive")), None)
    flags = [spec.PREFIX + c for c, *_ in spec.FLAGS]
    date_year = [spec.PREFIX + spec.DATE[0], spec.PREFIX + spec.YEAR_COL[0]]
    print(f"form '{form['name']}': tab General, {len(spec.SECTIONS) + 1} sections; "
          f"view '{active['name']}': Date, Year + {len(flags)} flags")
    if not apply:
        return
    dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": form_xml()}, solution=SOLUTION)
    fetch, layout = view_xml(otc, active["savedqueryid"], date_year + flags, True)
    dv.request("PATCH", f"savedqueries({active['savedqueryid']})", {"fetchxml": fetch, "layoutxml": layout},
               solution=SOLUTION)
    if inactive:
        fetch, layout = view_xml(otc, inactive["savedqueryid"], date_year + ["createdon"], False)
        dv.request("PATCH", f"savedqueries({inactive['savedqueryid']})", {"fetchxml": fetch, "layoutxml": layout},
                   solution=SOLUTION)
    dv.request("POST", "PublishXml", idempotent=True, body=
               {"ParameterXml": f"<importexportxml><entities><entity>{LOGICAL}</entity></entities></importexportxml>"})
    print("  updated and published")


def group_xml():
    gid_, en, ar = spec.GROUP
    return (f'<Group Id="{gid_}" ResourceId="SitemapDesigner.NewGroup" IsProfile="false" '
            f'ToolTipResourseId="SitemapDesigner.Unknown"><Titles><Title LCID="1033" Title="{en}" />'
            f'<Title LCID="1025" Title="{ar}" /></Titles>'
            f'<SubArea Id="subarea_{spec.TABLE}" Entity="{LOGICAL}" '
            f'Client="All,Outlook,OutlookLaptopClient,OutlookWorkstationClient,Web" AvailableOffline="true" '
            f'PassParams="false" Sku="All,OnPremise,Live,SPLA" /></Group>')


def deploy_app(dv, apply):
    app = dv.first(f"appmodules?$select=appmoduleid,name&$filter=uniquename eq '{APP}'")
    sitemap = dv.first(f"sitemaps?$select=sitemapid,sitemapxml&$filter=sitemapnameunique eq '{APP}'")
    xml = sitemap["sitemapxml"]
    has_group = f'Id="{spec.GROUP[0]}"' in xml
    print(f"site map: {spec.GROUP[1]} group {'exists' if has_group else 'add at the end of the General area'}")
    meta = dv.first(f"EntityDefinitions?$select=MetadataId&$filter=LogicalName eq '{LOGICAL}'")
    if not apply or not meta:
        return
    if not has_group:
        start = xml.find(GENERAL_AREA)
        end = xml.find("</Area>", start)
        if start < 0 or end < 0:
            raise SystemExit("General area not found in the site map")
        xml = xml[:end] + group_xml() + xml[end:]
        dv.request("PATCH", f"sitemaps({sitemap['sitemapid']})", {"sitemapxml": xml}, solution=SOLUTION)
        print("  added")
    dv.request("POST", "AddAppComponents", idempotent=True, body={"AppId": app["appmoduleid"], "Components": [
        {"@odata.type": "Microsoft.Dynamics.CRM.entity", "entityid": meta["MetadataId"]}]})
    print(f"  table added to app '{app['name']}'")

    roles = dv.get(f"roles?$select=roleid,_parentrootroleid_value&$filter=name eq '{ROLE}'")["value"]
    root = next(r for r in roles if r["roleid"] == r["_parentrootroleid_value"])
    privileges = [{"PrivilegeId": dv.first(f"privileges?$select=privilegeid&$filter=name eq 'prv{op}{LOGICAL}'")
                   ["privilegeid"], "Depth": "Global"} for op in PRIVILEGES]
    dv.request("POST", f"roles({root['roleid']})/Microsoft.Dynamics.CRM.AddPrivilegesRole",
               {"Privileges": privileges}, idempotent=True)
    print(f"  role '{ROLE}': {', '.join(PRIVILEGES)} (organization)")
    dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
               f"<importexportxml><sitemaps><sitemap>{sitemap['sitemapid']}</sitemap></sitemaps>"
               f"<appmodules><appmodule>{app['appmoduleid']}</appmodule></appmodules></importexportxml>"})
    print("  published")


def create_row(dv, day, row):
    """Network blips: retry only after checking the row wasn't created (the Date key also rejects duplicates)."""
    for attempt in range(4):
        try:
            dv.request("POST", f"{LOGICAL}s", row, idempotent=False)
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
            if dv.first(f"{LOGICAL}s?$select={LOGICAL}id&$filter={spec.PREFIX}date eq {day}"):
                return


def deploy_rows(dv, apply):
    path = HERE / f"season_calendar_{spec.YEAR}.csv"
    with open(path, encoding="utf-8") as f:
        wanted = {}
        for r in csv.DictReader(f):
            row = {spec.PREFIX + "name": r["date"], spec.PREFIX + "date": r["date"],
                   spec.PREFIX + "year": r["year"]}
            row.update({spec.PREFIX + c: r[c] == "Yes" for c, *_ in spec.FLAGS})
            wanted[r["date"]] = row
    if not table_exists(dv):
        print(f"rows: {len(wanted)} to create after the table is created")
        return
    fields = list(next(iter(wanted.values())))
    existing, url = {}, f"{LOGICAL}s?$select={LOGICAL}id,{','.join(fields)}"
    while url:
        page = dv.request("GET", url, headers={"Prefer": "odata.maxpagesize=5000"})[0]
        for r in page["value"]:
            existing[r[spec.PREFIX + "date"]] = r
        url = page.get("@odata.nextLink")
    create = [d for d in wanted if d not in existing]
    update = {d: {k: v for k, v in wanted[d].items() if existing[d].get(k) != v} for d in wanted if d in existing}
    update = {d: ch for d, ch in update.items() if ch}
    print(f"rows: {len(create)} to create, {len(update)} to update, {len(wanted) - len(create) - len(update)} "
          f"unchanged ({path.name})")
    if not apply:
        return
    for i, d in enumerate(create, 1):
        create_row(dv, d, wanted[d])
        if i % 50 == 0 or i == len(create):
            print(f"  {i}/{len(create)} created")
    for d, changes in update.items():
        dv.request("PATCH", f"{LOGICAL}s({existing[d][LOGICAL + 'id']})", changes)
    if update:
        print(f"  {len(update)} updated")


def main(apply):
    dv = Dataverse()
    deploy_table(dv, apply)
    if apply:
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><entities><entity>{LOGICAL}</entity></entities></importexportxml>"})
    deploy_key(dv, apply)
    deploy_ui(dv, apply)
    deploy_app(dv, apply)
    deploy_rows(dv, apply)


if __name__ == "__main__":
    main("--apply" in sys.argv)
