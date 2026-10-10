"""Customizes the main form and the Active / Inactive views of the Google Ads tables (like Snap's).

  python3 deploy_ui.py            # dry run: shows the layout
  python3 deploy_ui.py --apply    # update the forms and views in AlSanidiMarketing, then publish

Main form "Information": tabs and sections from spec.FORMS, every column placed, parent lookup first,
child records in a sub-grid on the Related tab.
Active view: main columns from spec.VIEW_MAIN first, then every other column (Raw Payload left out).
Inactive view: name, status, last synced on, created on.
"""
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from deploy_tables import SOLUTION  # noqa: E402
from dv import Dataverse  # noqa: E402

NS = uuid.UUID("6f6e1c2e-5a8b-4f0e-9d7a-3c1b2a4d5e6f")
CLASS = {
    "text": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}", "memo": "{E0DECE4B-6FC8-4a8f-A065-082708572369}",
    "choice": "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}", "multi": "{4AA28AB7-9C13-4F57-A73D-AD894D048B5F}",
    "bool": "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}", "int": "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}",
    "decimal": "{C3EFE0C3-0EC6-42be-8349-CBD9079DFD8E}", "money": "{533B9E00-756B-4312-95A0-DC888637AC78}",
    "date": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}", "lookup": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "subgrid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}",
}
KIND_CLASS = {
    "str": "text", "id": "text", "int": "int", "dec": "decimal", "pct": "decimal", "pctmicros": "decimal",
    "money": "money", "cur": "money", "bool": "bool", "date": "date", "now": "date", "enum": "choice",
    "enums": "multi", "strs": "memo", "json": "memo", "texts": "memo", "assets": "memo", "raw": "memo",
}


def gid(*parts):
    return "{" + str(uuid.uuid5(NS, "/".join(parts))) + "}"


def lbl(text):
    return f'<labels><label description={quoteattr(text)} languagecode="1033" /></labels>'


def cell(table, field, display, cls):
    return (f'<row><cell id="{gid(table, "cell", field)}">{lbl(display)}'
            f'<control id="{field}" classid="{CLASS[cls]}" datafieldname="{field}" /></cell></row>')


def subgrid(table, child, display, view_id):
    child_t = spec.TABLES[child]
    rel = f"{spec.PREFIX}{child}_{table}_{spec.PREFIX}{table}"
    rows = "<row />" * 9
    return (f'<section name="{child}" showlabel="false" showbar="false" IsUserDefined="0" '
            f'id="{gid(table, "section", child)}" columns="1">{lbl(display)}<rows><row>'
            f'<cell id="{gid(table, "cell", child)}" showlabel="true" rowspan="10" colspan="1" auto="false">'
            f'{lbl(display)}<control id="{child}s" classid="{CLASS["subgrid"]}" indicationOfSubgrid="true" '
            f'uniqueid="{gid(table, "grid", child)}"><parameters>'
            f'<TargetEntityType>{spec.PREFIX}{child}</TargetEntityType><ViewId>{view_id}</ViewId>'
            f'<RelationshipName>{rel}</RelationshipName><AutoExpand>Fixed</AutoExpand>'
            f'<EnableQuickFind>false</EnableQuickFind><EnableViewPicker>true</EnableViewPicker><ViewIds />'
            f'<EnableJumpBar>false</EnableJumpBar><ChartGridMode>Grid</ChartGridMode><VisualizationId />'
            f'<IsUserView>false</IsUserView><IsUserChart>false</IsUserChart><RecordsPerPage>10</RecordsPerPage>'
            f'<HeaderColorCode>#F3F3F3</HeaderColorCode></parameters></control></cell></row>{rows}</rows></section>')


def form_xml(table, active_view_ids):
    t = spec.TABLES[table]
    by_section = {}
    for col, display, section, kind, _ in t["columns"]:
        by_section.setdefault(section, []).append((spec.PREFIX + col, display, KIND_CLASS[kind]))
    tabs = []
    for tab_label, sections in spec.FORMS[table]:
        columns = []
        width = f"{100 // len(sections)}%"
        for key, section_label in sections:
            if key.startswith("@related:"):
                child = key.split(":", 1)[1]
                body = subgrid(table, child, section_label, active_view_ids[child])
            else:
                rows = []
                if key == "identity":
                    first = by_section[key][0]
                    rows.append(cell(table, *first))
                    if t["parent"]:
                        parent, parent_display = t["parent"]
                        rows.append(cell(table, spec.PREFIX + parent, parent_display, "lookup"))
                    rows.append(cell(table, "ownerid", "Owner", "lookup"))
                    rows += [cell(table, *c) for c in by_section[key][1:]]
                else:
                    rows = [cell(table, *c) for c in by_section[key]]
                body = (f'<section name="{key}" showlabel="true" showbar="false" IsUserDefined="0" '
                        f'id="{gid(table, "section", key)}" columns="1" labelwidth="200">{lbl(section_label)}'
                        f'<rows>{"".join(rows)}</rows></section>')
            columns.append(f'<column width="{width}"><sections>{body}</sections></column>')
        name = tab_label.lower().replace(" & ", "").replace(" ", "")
        tabs.append(f'<tab name="{name}" verticallayout="true" id="{gid(table, "tab", name)}" IsUserDefined="1" '
                    f'expanded="true" showlabel="true">{lbl(tab_label)}<columns>{"".join(columns)}</columns></tab>')
    header_fields = [c for c in t["columns"] if c[0] in ("status", "primarystatus", "lastsyncedon")]
    header = "".join(
        f'<cell id="{gid(table, "header", c[0])}">{lbl(c[1])}<control id="header_{spec.PREFIX}{c[0]}" '
        f'classid="{CLASS[KIND_CLASS[c[3]]]}" datafieldname="{spec.PREFIX}{c[0]}" disabled="true" /></cell>'
        for c in header_fields)
    return (f'<form headerdensity="HighWithControls"><tabs>{"".join(tabs)}</tabs>'
            f'<header id="{gid(table, "header")}" celllabelposition="Top" columns="111" labelwidth="115" '
            f'celllabelalignment="Left"><rows><row>{header}</row></rows></header></form>')


def view_columns(table):
    t = spec.TABLES[table]
    names = []
    for c in spec.VIEW_MAIN[table]:
        names.append(spec.PREFIX + (t["parent"][0] if c == "@lookup" else c))
    for col, _, _, kind, _ in t["columns"]:
        if kind != "raw" and spec.PREFIX + col not in names:
            names.append(spec.PREFIX + col)
    return names


def view_xml(table, otc, view_id, columns, active):
    logical = spec.PREFIX + table
    primary = spec.PREFIX + spec.TABLES[table]["primary"]
    attrs = "".join(f'<attribute name="{c}" />' for c in [logical + "id"] + columns)
    fetch = (f'<fetch version="1.0" mapping="logical" savedqueryid="{view_id.strip("{}")}"><entity name="{logical}">'
             f'{attrs}<order attribute="{primary}" descending="false" /><filter type="and">'
             f'<condition attribute="statecode" operator="eq" value="{0 if active else 1}" /></filter></entity></fetch>')
    cells = "".join(f'<cell name="{c}" width="{300 if c == primary else 150}" />' for c in columns)
    layout = (f'<grid name="resultset" jump="{primary}" select="1" icon="1" preview="1" object="{otc}">'
              f'<row name="result" id="{logical}id">{cells}</row></grid>')
    return fetch, layout


def main(apply):
    dv = Dataverse()
    views = {}
    for table in spec.TABLES:
        logical = spec.PREFIX + table
        views[table] = {v["name"]: v for v in dv.get(
            f"savedqueries?$select=savedqueryid,name,isdefault&$filter=returnedtypecode eq '{logical}' "
            f"and querytype eq 0")["value"]}
    active_ids = {t: "{" + next(v["savedqueryid"] for v in views[t].values() if v["isdefault"]) + "}"
                  for t in spec.TABLES}
    for table, t in spec.TABLES.items():
        logical = spec.PREFIX + table
        otc = dv.get(f"EntityDefinitions(LogicalName='{logical}')?$select=ObjectTypeCode")["ObjectTypeCode"]
        form = dv.first(f"systemforms?$select=formid,name&$filter=objecttypecode eq '{logical}' and type eq 2")
        xml = form_xml(table, active_ids)
        print(f"{logical}: form '{form['name']}' -> tabs "
              f"{', '.join(tab for tab, _ in spec.FORMS[table])} ({xml.count('<control ')} controls)")
        active = next(v for v in views[table].values() if v["isdefault"])
        inactive = next((v for n, v in views[table].items() if n.startswith("Inactive")), None)
        cols = view_columns(table)
        print(f"  view '{active['name']}': {len(cols)} columns, first: "
              f"{', '.join(c.replace(spec.PREFIX, '') for c in cols[:8])}...")
        if inactive:
            print(f"  view '{inactive['name']}': name, status, last synced on, created on")
        if not apply:
            continue
        dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": xml}, solution=SOLUTION)
        fetch, layout = view_xml(table, otc, active_ids[table], cols, True)
        dv.request("PATCH", f"savedqueries({active['savedqueryid']})",
                   {"fetchxml": fetch, "layoutxml": layout}, solution=SOLUTION)
        if inactive:
            short = [spec.PREFIX + t["primary"], spec.PREFIX + "status", spec.PREFIX + "lastsyncedon", "createdon"]
            fetch, layout = view_xml(table, otc, "{" + inactive["savedqueryid"] + "}", short, False)
            dv.request("PATCH", f"savedqueries({inactive['savedqueryid']})",
                       {"fetchxml": fetch, "layoutxml": layout}, solution=SOLUTION)
    if apply:
        tables = "".join(f"<entity>{spec.PREFIX + t}</entity>" for t in spec.TABLES)
        dv.request("POST", "PublishXml",
                   {"ParameterXml": f"<importexportxml><entities>{tables}</entities></importexportxml>"})
        print("published")


if __name__ == "__main__":
    main("--apply" in sys.argv)
