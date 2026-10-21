"""Sync Control for TikTok: adds the Connection Active column to Integration Platform and sets up the TikTok row.

Usage: python3 add_tiktok.py <dir containing dv.py> [--apply]

- sanidi_connectionactive (Connection Active, Yes/No): empty counts as Yes. No shows the card's
  "Connection not active yet" notice and turns its Sync buttons off. Set it to Yes once the platform's
  connection works.
- TikTok row: Set Up = Yes, its data flows and insights flow (same values as seed_platforms.py),
  Connection Active = No.
"""
import sys, json; sys.path.insert(0, sys.argv[1])
import dv


def L(t): return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [
    {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": t, "LanguageCode": 1033}]}


def boolean(schema, label, desc):  # same shape as create_tables.py
    return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", "SchemaName": schema,
            "DisplayName": L(label), "Description": L(desc),
            "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                              "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"},
            "DefaultValue": False,
            "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                          "TrueOption": {"Value": 1, "Label": L("Yes")}, "FalseOption": {"Value": 0, "Label": L("No")}}}

APPLY = "--apply" in sys.argv
COLUMN = boolean("sanidi_ConnectionActive", "Connection Active",
                 "No while the platform's connection isn't working yet: Sync Control shows a notice and no sync can "
                 "start. Empty counts as Yes.")
COLUMN["DefaultValue"] = True


def flows(*pairs): return json.dumps([{"name": n, "id": i} for n, i in pairs])


TIKTOK = {
    "sanidi_isconfigured": True,
    "sanidi_connectionactive": False,
    "sanidi_dataflows": flows(("Get TikTok Campaigns", "de45712c-6cd1-59ff-8546-26bb91f692f4"),
                              ("Get TikTok Ad Groups", "49f87836-4262-5c77-b470-5c90c1054813"),
                              ("Get TikTok Advertisements", "1c99d003-a774-5c45-94a8-73e1048fd19c")),
    "sanidi_insightsflowname": "Get TikTok Insights",
    "sanidi_insightsflowid": "4bcc7027-25a2-51c9-adc4-9c4b5c5ca128",
}

st, b, _ = dv.call('GET', "EntityDefinitions(LogicalName='sanidi_integrationplatform')/Attributes"
                          "?$select=LogicalName&$filter=LogicalName%20eq%20'sanidi_connectionactive'", solution=None)
exists = bool(b and b.get("value"))
print("column sanidi_connectionactive:", "exists" if exists else "create")
if APPLY and not exists:
    st, b, _ = dv.call('POST', "EntityDefinitions(LogicalName='sanidi_integrationplatform')/Attributes", COLUMN)
    print("  created", st, '' if st < 300 else b)
    st, b, _ = dv.call('POST', 'PublishXml', {"ParameterXml": "<importexportxml><entities><entity>"
                       "sanidi_integrationplatform</entity></entities></importexportxml>"}, solution=None)
    print("  published", st)

st, b, _ = dv.call('GET', "sanidi_integrationplatforms?$select=sanidi_integrationplatformid&$filter=sanidi_platformkey%20eq%20'tiktok'",
                   solution=None)
row = b["value"][0]
print("TikTok row", row["sanidi_integrationplatformid"], ": set", ", ".join(TIKTOK))
if APPLY:
    # Rows are data, not solution components: no solution header.
    st, b, _ = dv.call('PATCH', f"sanidi_integrationplatforms({row['sanidi_integrationplatformid']})", TIKTOK, solution=None)
    print("  updated", st, '' if st < 300 else b)
