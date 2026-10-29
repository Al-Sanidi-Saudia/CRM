"""Reads the insight columns of the 13 synced tables from Dataverse into parent_insight_columns.json.

  python3 snapshot_parent_columns.py

The insight columns are the ones the lifetime "Get <Platform> Insights" flows write (their "Update ... insights"
actions). For each column it keeps what the daily / monthly copies need: schema name, type, labels (all languages),
descriptions, length / precision / range and choice options.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from dv import Dataverse  # noqa: E402

INSIGHTS_FLOWS = ["Get Meta Insights", "Get Snap Insights", "Get Google Ads Insights", "Get TikTok Insights"]
CAST = {
    "IntegerType": ("IntegerAttributeMetadata", "Format,MinValue,MaxValue"),
    "DecimalType": ("DecimalAttributeMetadata", "Precision,MinValue,MaxValue"),
    "MoneyType": ("MoneyAttributeMetadata", "Precision,PrecisionSource,MinValue,MaxValue"),
    "DoubleType": ("DoubleAttributeMetadata", "Precision,MinValue,MaxValue"),
    "StringType": ("StringAttributeMetadata", "MaxLength,FormatName"),
    "MemoType": ("MemoAttributeMetadata", "MaxLength"),
    "DateTimeType": ("DateTimeAttributeMetadata", "Format,DateTimeBehavior"),
    "PicklistType": ("PicklistAttributeMetadata", None),
    "BooleanType": ("BooleanAttributeMetadata", None),
}


def labels(label):
    return {str(l["LanguageCode"]): l["Label"] for l in (label or {}).get("LocalizedLabels", [])}


def written_columns(dv):
    """entity set -> insight columns, from the Update actions of the lifetime insights flows."""
    out = {}

    def walk(actions):
        for a in actions.values():
            inputs = a.get("inputs") or {}
            if a.get("type") == "OpenApiConnection" and inputs.get("host", {}).get("operationId") == "UpdateOnlyRecord":
                p = inputs["parameters"]
                out[p["entityName"]] = [k[5:] for k in p if k.startswith("item/")]
            walk(a.get("actions", {}))
            walk(a.get("else", {}).get("actions", {}))
            for case in a.get("cases", {}).values():
                walk(case.get("actions", {}))

    for name in INSIGHTS_FLOWS:
        flow = dv.first(f"workflows?$select=clientdata&$filter=name eq '{name}' and category eq 5")
        walk(json.loads(flow["clientdata"])["properties"]["definition"]["actions"])
    return out


def main():
    dv = Dataverse()
    written = written_columns(dv)
    result = {}
    for entity_set, columns in written.items():
        logical = dv.first(f"EntityDefinitions?$select=LogicalName&$filter=EntitySetName eq '{entity_set}'")["LogicalName"]
        base = f"EntityDefinitions(LogicalName='{logical}')/Attributes"
        attrs = {a["LogicalName"]: a for a in dv.get(
            f"{base}?$select=LogicalName,SchemaName,AttributeTypeName,DisplayName,Description")["value"]}
        details = {}
        for type_name, (cast, select) in CAST.items():
            query = f"{base}/Microsoft.Dynamics.CRM.{cast}?$select=LogicalName" + (f",{select}" if select else "")
            if type_name == "PicklistType":
                query += "&$expand=OptionSet($select=Options)"
            for a in dv.get(query)["value"]:
                details[a["LogicalName"]] = a
        cols = []
        for name in columns:
            a, x = attrs[name], details[name]
            type_name = a["AttributeTypeName"]["Value"]
            col = {"name": name, "schema": a["SchemaName"], "type": type_name,
                   "label": labels(a["DisplayName"]), "description": labels(a["Description"])}
            select = CAST[type_name][1]
            for k in (select.split(",") if select else []):
                col[k] = x.get(k)
            if type_name == "PicklistType":
                col["options"] = [[o["Value"], labels(o["Label"])] for o in x["OptionSet"]["Options"]]
            cols.append(col)
        result[logical] = cols
        print(f"{logical}: {len(cols)} columns")
    (HERE / "parent_insight_columns.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
