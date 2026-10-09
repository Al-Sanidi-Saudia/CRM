# Dataverse components for AlSanidi | Marketing

Generators that build small, unmanaged solution packages for the **AlSanidi | Marketing** solution
(publisher AlSanidi Development, prefix `sanidi`). Each package holds only its own component(s), so importing
it doesn't touch anything else in the solution, and IDs are deterministic so re-importing updates in place.

| Folder | Table | Flow |
|---|---|---|
| `snap-campaign/` | Snap Campaign (`sanidi_SnapCampaign`) | Get Snap Campaigns (manual) |
| `snap-adsquad/` | Snap Ad Squad (`sanidi_SnapAdSquad`, lookup to Snap Campaign) | Get Snap Ad Squads (when a Snap Campaign is added or modified) |
| `snap-advertisement/` | Snap Advertisement (`sanidi_SnapAdvertisement`, lookup to Snap Ad Squad) | Get Snap Advertisements (when a Snap Ad Squad is added or modified) |

`table_builder.py` holds the shared table logic (columns, choices, lookups, keys, form, views) and
`flow_builder.py` the shared "sync a parent's children from Snap" flow logic.

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

Tables are imported child-first, because each parent's Related tab points at its child table:

```bash
python3 snap-advertisement/build_table_solution.py --template Template.zip --out SnapAdvertisementTable.zip
python3 snap-adsquad/build_table_solution.py       --template Template.zip --out SnapAdSquadTable.zip
python3 snap-campaign/build_table_solution.py      --template Template.zip --out SnapCampaignTable.zip
python3 snap-campaign/build_flow_solution.py       --template Template.zip --out GetSnapCampaignsFlow.zip
python3 snap-adsquad/build_flow_solution.py        --template Template.zip --out GetSnapAdSquadsFlow.zip
python3 snap-advertisement/build_flow_solution.py  --template Template.zip --out GetSnapAdvertisementsFlow.zip

pac solution import --path SnapAdvertisementTable.zip --publish-changes
pac solution import --path SnapAdSquadTable.zip       --publish-changes
pac solution import --path SnapCampaignTable.zip      --publish-changes
pac solution import --path GetSnapCampaignsFlow.zip
pac solution import --path GetSnapAdSquadsFlow.zip
pac solution import --path GetSnapAdvertisementsFlow.zip
```

Only one import can run in an environment at a time; if `pac` reports another import running, wait and retry.

Imported flows arrive turned off; turn them on in the portal.
