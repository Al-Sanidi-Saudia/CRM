"""Creates the TikTok tables and their columns from spec.py in the AlSanidi | Marketing solution.

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


def options(level, src):
    return {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata", "IsGlobal": False,
            "OptionSetType": "Picklist",
            "Options": [{"Value": o["value"], "Label": label(o["label"])} for o in spec.enum_options(level, src)]}


def column_metadata(level, column, display, section, kind, src):
    schema = spec.PREFIX + column
    description = spec.description(section, kind, src)
    base = {"SchemaName": schema, "DisplayName": label(display), "Description": label(description),
            "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                              "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}}
    length = spec.max_length(column, kind)
    if kind in ("str", "id", "info"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", **base,
                "MaxLength": length, "FormatName": {"Value": "Text"}}
    if kind in spec.MULTILINE_KINDS:
        return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", **base,
                "MaxLength": length, "Format": "TextArea"}
    if kind == "int":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", **base,
                "Format": "None", "MinValue": -2147483648, "MaxValue": 2147483647}
    if kind in ("dec", "pct"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata", **base,
                "Precision": 4, "MinValue": -100000000000, "MaxValue": 100000000000}
    if kind == "money":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata", **base,
                "PrecisionSource": 2, "MinValue": -922337203685477, "MaxValue": 922337203685477}
    if kind == "bool":
        return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", **base,
                "DefaultValue": False,
                "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                              "TrueOption": {"Value": 1, "Label": label("Yes")},
                              "FalseOption": {"Value": 0, "Label": label("No")}}}
    if kind in ("date", "now"):
        # TikTok times are UTC: shown in each user's time zone.
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", **base,
                "Format": "DateAndTime", "DateTimeBehavior": {"Value": "UserLocal"}}
    if kind == "enum":
        return {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata", **base,
                "OptionSet": options(level, src)}
    if kind == "enums":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MultiSelectPicklistAttributeMetadata", **base,
                "OptionSet": options(level, src)}
    raise ValueError(f"no Dataverse type for kind {kind}")


def entity_metadata(table, t):
    primary = next(c for c in t["columns"] if c[0] == t["primary"])
    name_attr = {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                 "SchemaName": spec.PREFIX + primary[0], "IsPrimaryName": True,
                 "DisplayName": label(primary[1]),
                 "Description": label(spec.description(primary[2], primary[3], primary[4])),
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
            text = str(e).lower()
            # "Cannot start another [EntityCustomization]": metadata changes run one at a time per environment.
            transient = not isinstance(e, RuntimeError) or "unexpected error" in text or "cannot start another" in text
            if attempt == 3 or not transient:
                raise
            time.sleep(10 * (attempt + 1))
            name = metadata["SchemaName"].lower()
            if dv.first(f"{path}?$select=LogicalName&$filter=LogicalName eq '{name}'"):
                return


def main(apply, only=None):
    dv = Dataverse()
    for table, t in spec.TABLES.items():
        if only and table not in only:
            continue
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
        for i, (column, display, section, kind, src) in enumerate(todo, 1):
            add_column(dv, logical, column_metadata(t["level"], column, display, section, kind, src))
            if i % 20 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} columns")
    if apply:
        tables = "".join(f"<entity>{spec.PREFIX + t}</entity>" for t in spec.TABLES if not only or t in only)
        dv.request("POST", "PublishXml", idempotent=True, body=
                   {"ParameterXml": f"<importexportxml><entities>{tables}</entities></importexportxml>"})
        print("published")


def remove_columns(table, columns, apply):
    """Deletes columns that were dropped from spec.py. Only names passed explicitly, never inferred."""
    dv = Dataverse()
    logical = spec.PREFIX + table
    in_spec = {spec.PREFIX + c[0] for c in spec.TABLES[table]["columns"]}
    for column in columns:
        name = spec.PREFIX + column
        if name in in_spec:
            raise SystemExit(f"{name} is still in spec.py; remove it there first")
        exists = dv.first(f"EntityDefinitions(LogicalName='{logical}')/Attributes?$select=LogicalName"
                          f"&$filter=LogicalName eq '{name}'")
        print(f"{logical}.{name}: {'delete' if exists else 'not found'}")
        if apply and exists:
            dv.request("DELETE", f"EntityDefinitions(LogicalName='{logical}')/Attributes(LogicalName='{name}')")


if __name__ == "__main__":
    # python3 deploy_tables.py --remove=<table>:<col>,<col> [--apply]
    remove = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--remove=")]
    if remove:
        table, cols = remove[0].split(":", 1)
        remove_columns(table, cols.split(","), "--apply" in sys.argv)
    else:
        # --only=<table>[,<table>] limits the run to those tables (e.g. one process per table)
        only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
        main("--apply" in sys.argv, only[0].split(",") if only else None)
