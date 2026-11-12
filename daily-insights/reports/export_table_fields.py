"""Excel data dictionary of the 26 insight tables: one sheet per table, every column (custom and out-of-box) with the
same details on every sheet, read from the live metadata of an environment (default: Production).

  python3 reports/export_table_fields.py [environment URL]     # -> reports/insight-tables-data-dictionary.xlsx
"""
import os
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402

os.environ["DATAVERSE_URL"] = sys.argv[1] if len(sys.argv) > 1 else "https://operations-alsanidi.crm4.dynamics.com"
from dv import Dataverse  # noqa: E402

NA = "–"
EN, AR = 1033, 1025
COLUMNS = [  # (header, width)
    ("#", 5), ("Logical Name", 34), ("Schema Name", 34), ("Display Name (English)", 30), ("Display Name (Arabic)", 30),
    ("Description (English)", 50), ("Description (Arabic)", 50), ("Data Type", 16), ("Format", 16),
    ("Custom / Out-of-box", 14), ("Managed", 9), ("Requirement Level", 16), ("Primary Key", 9), ("Primary Name", 9),
    ("Alternate Key", 30), ("Max Length", 10), ("Min Value", 16), ("Max Value", 16), ("Precision", 10),
    ("Date Behavior", 14), ("Choices (value: English / Arabic)", 50), ("Default Value", 14), ("Global Choice", 22),
    ("Lookup Target(s)", 30), ("Column Type", 12), ("Attribute Of", 26), ("Logical (system)", 9),
    ("Valid for Create", 9), ("Valid for Update", 9), ("Valid for Read", 9), ("Searchable", 9),
    ("Valid for Advanced Find", 9), ("Sortable", 9), ("Filterable", 9), ("Auditing", 9), ("Field Security", 9),
    ("Customizable", 9), ("Renameable", 9), ("Introduced Version", 12), ("Created On", 12), ("Modified On", 12),
]
CASTS = {  # type name -> metadata cast with the type-specific properties
    "StringType": "StringAttributeMetadata", "MemoType": "MemoAttributeMetadata",
    "IntegerType": "IntegerAttributeMetadata", "BigIntType": "BigIntAttributeMetadata",
    "DecimalType": "DecimalAttributeMetadata", "DoubleType": "DoubleAttributeMetadata",
    "MoneyType": "MoneyAttributeMetadata", "DateTimeType": "DateTimeAttributeMetadata",
    "BooleanType": "BooleanAttributeMetadata", "PicklistType": "PicklistAttributeMetadata",
    "StateType": "StateAttributeMetadata", "StatusType": "StatusAttributeMetadata",
    "LookupType": "LookupAttributeMetadata", "OwnerType": "LookupAttributeMetadata",
    "CustomerType": "LookupAttributeMetadata", "ImageType": "ImageAttributeMetadata",
    "FileType": "FileAttributeMetadata", "MultiSelectPicklistType": "MultiSelectPicklistAttributeMetadata",
}
OPTIONSET = {"BooleanAttributeMetadata", "PicklistAttributeMetadata", "StateAttributeMetadata",
             "StatusAttributeMetadata", "MultiSelectPicklistAttributeMetadata"}


def label(lbl, lang):
    for l in (lbl or {}).get("LocalizedLabels") or []:
        if l.get("LanguageCode") == lang:
            return l.get("Label") or NA
    return NA


def yn(v):
    if isinstance(v, dict):
        v = v.get("Value")
    return NA if v is None else ("Yes" if v else "No")


def val(v):
    return NA if v in (None, "") else v


def options(meta):
    os_ = meta.get("OptionSet") or {}
    if meta.get("@odata.type", "").endswith("BooleanAttributeMetadata"):
        out = []
        for key in ("FalseOption", "TrueOption"):
            o = os_.get(key) or {}
            out.append(f"{o.get('Value')}: {label(o.get('Label'), EN)} / {label(o.get('Label'), AR)}")
        return "\n".join(out)
    return "\n".join(f"{o.get('Value')}: {label(o.get('Label'), EN)} / {label(o.get('Label'), AR)}"
                     for o in os_.get("Options") or []) or NA


def column_type(meta):
    return {0: "Simple", 1: "Calculated", 2: "Rollup", 3: "Formula"}.get(meta.get("SourceType"), "Simple")


def details(dv, table):
    base = dv.get(f"EntityDefinitions(LogicalName='{table}')/Attributes")["value"]
    extra = {}
    for cast in sorted(set(CASTS.values())):
        expand = "?$expand=OptionSet,GlobalOptionSet" if cast in OPTIONSET else ""
        for m in dv.get(f"EntityDefinitions(LogicalName='{table}')/Attributes/Microsoft.Dynamics.CRM.{cast}{expand}")["value"]:
            extra[m["LogicalName"]] = m
    keys = {}
    for k in dv.get(f"EntityDefinitions(LogicalName='{table}')/Keys?$select=SchemaName,KeyAttributes")["value"]:
        for a in k["KeyAttributes"]:
            keys.setdefault(a, []).append(k["SchemaName"])
    rows = []
    for m in sorted(base, key=lambda a: (not a.get("IsPrimaryId"), not a.get("IsPrimaryName"),
                                         not a.get("IsCustomAttribute"), a["LogicalName"])):
        x = {**m, **extra.get(m["LogicalName"], {})}
        typ = (x.get("AttributeTypeName") or {}).get("Value", x.get("AttributeType", "")).replace("Type", "")
        fmt = x.get("FormatName", {}).get("Value") if isinstance(x.get("FormatName"), dict) else x.get("Format")
        dt_behavior = (x.get("DateTimeBehavior") or {}).get("Value") if typ == "DateTime" else None
        default = x.get("DefaultFormValue") if "DefaultFormValue" in x else x.get("DefaultValue")
        os_ = x.get("OptionSet") or {}
        gos = os_ if os_.get("IsGlobal") else {}
        if isinstance(default, bool):
            default = "Yes" if default else "No"
        rows.append([
            None, x["LogicalName"], x.get("SchemaName"), label(x.get("DisplayName"), EN), label(x.get("DisplayName"), AR),
            label(x.get("Description"), EN), label(x.get("Description"), AR), typ, val(fmt),
            "Custom" if x.get("IsCustomAttribute") else "Out-of-box", yn(x.get("IsManaged")),
            val((x.get("RequiredLevel") or {}).get("Value")), yn(x.get("IsPrimaryId")), yn(x.get("IsPrimaryName")),
            ", ".join(keys.get(x["LogicalName"], [])) or NA, val(x.get("MaxLength")),
            val(x.get("MinValue")), val(x.get("MaxValue")), val(x.get("Precision")), val(dt_behavior),
            options(x) if x.get("@odata.type", "").split(".")[-1] in OPTIONSET else NA,
            NA if default in (None, -1) else default, val(gos.get("Name")),
            ", ".join(x.get("Targets") or []) or NA, column_type(x), val(x.get("AttributeOf")),
            yn(x.get("IsLogical")), yn(x.get("IsValidForCreate")), yn(x.get("IsValidForUpdate")),
            yn(x.get("IsValidForRead")), yn(x.get("IsSearchable")), yn(x.get("IsValidForAdvancedFind")),
            yn(x.get("IsSortableEnabled")), yn(x.get("IsFilterable")), yn(x.get("IsAuditEnabled")),
            yn(x.get("IsSecured")), yn(x.get("IsCustomizable")), yn(x.get("IsRenameable")),
            val(x.get("IntroducedVersion")), (x.get("CreatedOn") or NA)[:10], (x.get("ModifiedOn") or NA)[:10],
        ])
    for i, r in enumerate(rows, 1):
        r[0] = i
    return rows


def main():
    dv = Dataverse()
    env = dv.url.split("//")[1].split(".")[0]
    head_fill, alt_fill = PatternFill("solid", fgColor="344054"), PatternFill("solid", fgColor="F9FAFB")
    custom_fill = PatternFill("solid", fgColor="FFF8E6")
    thin = Side(style="thin", color="D0D5DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wb = Workbook()
    index = wb.active
    index.title = "Index"
    index.append(["Insight tables: data dictionary"])
    index["A1"].font = Font(size=16, bold=True)
    index.append([f"Live metadata of {dv.url}, read on {date.today():%d %B %Y}. One sheet per table; every sheet has "
                  f"the same {len(COLUMNS)} details for every column (custom and out-of-box). '{NA}' = not applicable."])
    index.append([])
    hdr = ["#", "Sheet", "Table (logical name)", "Display Name (English)", "Display Name (Arabic)", "Platform",
           "Period", "Related synced table", "Columns", "Custom", "Out-of-box"]
    index.append(hdr)
    for c in index[index.max_row]:
        c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), head_fill, border
    platforms = {"meta": "Meta", "snap": "Snapchat", "google": "Google Ads", "tiktok": "TikTok"}
    for n, (logical, t) in enumerate(spec.tables().items(), 1):
        ent = dv.get(f"EntityDefinitions(LogicalName='{logical}')?$select=DisplayName")
        rows = details(dv, logical)
        sheet = t["display"].replace("Advertisement", "Ad").replace("Google Ads", "GAds")[:31]
        ws = wb.create_sheet(sheet)
        ws.append([f"{t['display']} ({logical})"])
        ws["A1"].font = Font(size=14, bold=True)
        ws.append([f"{label(ent.get('DisplayName'), AR)} · {len(rows)} columns · related to {t['parent']}"])
        ws.append([h for h, _ in COLUMNS])
        for c in ws[3]:
            c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), head_fill, border
            c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        for r in rows:
            ws.append(r)
            custom = r[9] == "Custom"
            for c in ws[ws.max_row]:
                c.border = border
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if custom:
                    c.fill = custom_fill
        for i, (_, w) in enumerate(COLUMNS, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "C4"
        ws.auto_filter.ref = f"A3:{get_column_letter(len(COLUMNS))}{ws.max_row}"
        custom = sum(r[9] == "Custom" for r in rows)
        index.append([n, sheet, logical, t["display"], label(ent.get("DisplayName"), AR), platforms[t["platform"]],
                      t["period"].capitalize(), t["parent"], len(rows), custom, len(rows) - custom])
        cell = index.cell(index.max_row, 2)
        cell.hyperlink, cell.style = f"#'{sheet}'!A1", "Hyperlink"
        for c in index[index.max_row]:
            c.border = border
        print(f"{sheet:31} {len(rows):3} columns ({custom} custom)", flush=True)
    for i, w in enumerate([5, 31, 42, 40, 40, 12, 9, 30, 9, 9, 10], 1):
        index.column_dimensions[get_column_letter(i)].width = w
    out = HERE / f"insight-tables-data-dictionary-{env}.xlsx"
    wb.save(out)
    print(out)


if __name__ == "__main__":
    main()
