# Dataverse components for AlSanidi | Marketing

Generators that build small, unmanaged solution packages for the **AlSanidi | Marketing** solution
(publisher AlSanidi Development, prefix `sanidi`). Each package holds only its own component(s), so importing
it doesn't touch anything else in the solution, and IDs are deterministic so re-importing updates in place.

| Folder | Table | Flow |
|---|---|---|
| `snap-campaign/` | Snap Campaign (`sanidi_SnapCampaign`) | Get Snap Campaigns (manual) |
| `snap-adsquad/` | Snap Ad Squad (`sanidi_SnapAdSquad`, lookup to Snap Campaign) | Get Snap Ad Squads (when a Snap Campaign is added or modified) |

`table_builder.py` holds the shared table logic (columns, choices, lookups, keys, form, views).

## Template export

The generators copy Dataverse's XML formats from the Meta tables, so they need a solution export containing
**Meta Campaign**, **Meta Ad Set** and **Meta Ad** (`sanidi_metacampaign`, `sanidi_metaadset`, `sanidi_meta_ad`).
An export of AlSanidi | Marketing works when it exports cleanly; otherwise put those three tables in a temporary
solution under the same publisher, export it, and delete the temporary solution:

```bash
pac solution add-solution-component --solutionUniqueName <TempSolution> --component sanidi_metacampaign --componentType 1
pac solution add-solution-component --solutionUniqueName <TempSolution> --component sanidi_metaadset --componentType 1
pac solution add-solution-component --solutionUniqueName <TempSolution> --component sanidi_meta_ad --componentType 1
pac solution export --name <TempSolution> --path Template.zip
pac solution delete --solution-name <TempSolution>
```

## Build and import (order matters)

```bash
python3 snap-adsquad/build_table_solution.py  --template Template.zip --out SnapAdSquadTable.zip
python3 snap-campaign/build_table_solution.py --template Template.zip --out SnapCampaignTable.zip  # Related tab needs Snap Ad Squad
python3 snap-campaign/build_flow_solution.py  --template Template.zip --out GetSnapCampaignsFlow.zip
python3 snap-adsquad/build_flow_solution.py   --template Template.zip --out GetSnapAdSquadsFlow.zip

pac solution import --path SnapAdSquadTable.zip  --publish-changes
pac solution import --path SnapCampaignTable.zip --publish-changes
pac solution import --path GetSnapCampaignsFlow.zip
pac solution import --path GetSnapAdSquadsFlow.zip
```

Imported flows arrive turned off; turn them on in the portal.
