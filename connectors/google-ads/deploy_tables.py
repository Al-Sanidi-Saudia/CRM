"""Creates the Google Ads tables and their columns from spec.py in the AlSanidi | Marketing solution.

  python3 deploy_tables.py            # dry run: what would be created
  python3 deploy_tables.py --apply    # create missing tables/columns, then publish

Safe to re-run: existing tables and columns are skipped (never changed or deleted).
Lookups between the tables are created by deploy_relationships.py.
"""
import sys
import time
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

SOLUTION = "AlSanidiMarketing"
LANG = 1033


def label(text):
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label",
            "LocalizedLabels": [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                                 "Label": text, "LanguageCode": LANG}]}


def options(src):
    return {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata", "IsGlobal": False,
            "OptionSetType": "Picklist",
            "Options": [{"Value": o["value"], "Label": label(o["label"])} for o in spec.enum_options(src)]}


def column_metadata(column, display, kind, src):
    schema = spec.PREFIX + column
    srcs = spec.sources(src)
    description = "Google Ads: " + ", ".join(srcs) + "." if srcs else {
        "now": "When the Google Ads sync last wrote this record.",
        "raw": "Full Google Ads API row (JSON, without metrics) from the last sync."}[kind]
    base = {"SchemaName": schema, "DisplayName": label(display), "Description": label(description),
            "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                              "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}}
    length = spec.max_length(column, kind)
    if kind in ("str", "id"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", **base,
                "MaxLength": length, "FormatName": {"Value": "Text"}}
    if kind in spec.MULTILINE_KINDS:
        return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", **base,
                "MaxLength": length, "Format": "TextArea"}
    if kind == "int":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", **base,
                "Format": "None", "MinValue": -2147483648, "MaxValue": 2147483647}
    if kind in ("dec", "pct", "pctmicros"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata", **base,
                "Precision": 4, "MinValue": -100000000000, "MaxValue": 100000000000}
    if kind in ("money", "cur"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata", **base,
                "PrecisionSource": 2, "MinValue": -922337203685477, "MaxValue": 922337203685477}
    if kind == "bool":
        return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", **base,
                "DefaultValue": False,
                "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                              "TrueOption": {"Value": 1, "Label": label("Yes")},
                              "FalseOption": {"Value": 0, "Label": label("No")}}}
    if kind in ("date", "now"):
        # Google dates are in the account time zone: store them as-is (time zone independent).
        behavior = "TimeZoneIndependent" if kind == "date" else "UserLocal"
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", **base,
                "Format": "DateAndTime", "DateTimeBehavior": {"Value": behavior}}
    if kind == "enum":
        return {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata", **base, "OptionSet": options(src)}
    if kind == "enums":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MultiSelectPicklistAttributeMetadata", **base,
                "OptionSet": options(src)}
    raise ValueError(f"no Dataverse type for kind {kind}")


def entity_metadata(table, t):
    primary = next(c for c in t["columns"] if c[0] == t["primary"])
    name_attr = {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                 "SchemaName": spec.PREFIX + primary[0], "IsPrimaryName": True,
                 "DisplayName": label(primary[1]),
                 "Description": label("Google Ads: " + ", ".join(spec.sources(primary[4])) + "."),
                 "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                                   "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"},
                 "MaxLength": 400, "FormatName": {"Value": "Text"}}
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": spec.PREFIX + table, "DisplayName": label(t["display"]),
            "DisplayCollectionName": label(t["plural"]), "Description": label(t["description"]),
            "OwnershipType": "UserOwned", "HasActivities": False, "HasNotes": False, "IsActivity": False,
            "ChangeTrackingEnabled": True, "Attributes": [name_attr]}


def add_column(dv, logical, metadata):
    """Metadata writes sometimes fail transiently; retry only after checking the column isn't there."""
    path = f"EntityDefinitions(LogicalName='{logical}')/Attributes"
    for attempt in range(4):
        try:
            dv.request("POST", path, metadata, solution=SOLUTION)
            return
        except (RuntimeError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            transient = not isinstance(e, RuntimeError) or "unexpected error" in str(e).lower()
            if attempt == 3 or not transient:
                raise
            time.sleep(10 * (attempt + 1))
            name = metadata["SchemaName"].lower()
            if dv.first(f"{path}?$select=LogicalName&$filter=LogicalName eq '{name}'"):
                return


def main(apply):
    dv = Dataverse()
    for table, t in spec.TABLES.items():
        logical = spec.PREFIX + table
        exists = dv.first(f"EntityDefinitions?$select=LogicalName&$filter=LogicalName eq '{logical}'")
        existing_cols = set()
        if exists:
            existing_cols = {a["LogicalName"] for a in dv.get(
                f"EntityDefinitions(LogicalName='{logical}')/Attributes?$select=LogicalName")["value"]}
        todo = [c for c in t["columns"] if c[0] != t["primary"] and spec.PREFIX + c[0] not in existing_cols]
        print(f"{logical}: table {'exists' if exists else 'create'}; {len(todo)} columns to add")
        if not apply:
            continue
        if not exists:
            dv.request("POST", "EntityDefinitions", entity_metadata(table, t), solution=SOLUTION)
            print(f"  created table {logical}")
            time.sleep(20)  # a brand-new table rejects columns for a short while
        for i, (column, display, _, kind, src) in enumerate(todo, 1):
            add_column(dv, logical, column_metadata(column, display, kind, src))
            if i % 20 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} columns")
    if apply:
        tables = "".join(f"<entity>{spec.PREFIX + t}</entity>" for t in spec.TABLES)
        dv.request("POST", "PublishXml",
                   {"ParameterXml": f"<importexportxml><entities>{tables}</entities></importexportxml>"})
        print("published")


if __name__ == "__main__":
    main("--apply" in sys.argv)
