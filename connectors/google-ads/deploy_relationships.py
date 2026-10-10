"""Creates the lookups between the Google Ads tables (like Snap's campaign -> ad squad -> ad).

  sanidi_googleadsadgroup.sanidi_googleadscampaign        -> sanidi_googleadscampaign
  sanidi_googleadsadvertisement.sanidi_googleadsadgroup   -> sanidi_googleadsadgroup

  python3 deploy_relationships.py            # dry run
  python3 deploy_relationships.py --apply    # create missing relationships, then publish

Deleting a parent removes the link only (Remove Link), so synced children are never cascade-deleted.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import spec  # noqa: E402
from deploy_tables import SOLUTION, label  # noqa: E402
from dv import Dataverse  # noqa: E402


def relationship(child, parent, parent_display):
    p, c = spec.PREFIX + parent, spec.PREFIX + child
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        # Same pattern as Snap: sanidi_snapadsquad_snapcampaign_sanidi_snapcampaign
        "SchemaName": f"{c}_{parent}_{p}",
        "ReferencedEntity": p,
        "ReferencingEntity": c,
        "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
                                 "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade",
                                 "RollupView": "NoCascade"},
        "AssociatedMenuConfiguration": {"Behavior": "UseCollectionName", "Group": "Details", "Order": 10000},
        "Lookup": {
            "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "SchemaName": p,
            "DisplayName": label(parent_display),
            "Description": label(f"The {parent_display} this record belongs to (set by the Google Ads sync)."),
            "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                              "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"},
        },
    }


def main(apply):
    dv = Dataverse()
    for child, t in spec.TABLES.items():
        if not t["parent"]:
            continue
        parent, parent_display = t["parent"]
        body = relationship(child, parent, parent_display)
        exists = dv.first("RelationshipDefinitions/Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata"
                          f"?$select=SchemaName&$filter=SchemaName eq '{body['SchemaName']}'")
        print(f"{body['SchemaName']}: {'exists' if exists else 'create'} "
              f"(lookup {body['ReferencingEntity']}.{body['Lookup']['SchemaName']})")
        if apply and not exists:
            dv.request("POST", "RelationshipDefinitions", body, solution=SOLUTION)
    if apply:
        tables = "".join(f"<entity>{spec.PREFIX + t}</entity>" for t in spec.TABLES)
        dv.request("POST", "PublishXml",
                   {"ParameterXml": f"<importexportxml><entities>{tables}</entities></importexportxml>"})
        print("published")


if __name__ == "__main__":
    main("--apply" in sys.argv)
