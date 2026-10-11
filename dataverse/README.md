# Dataverse components for AlSanidi | Marketing

Generators that build small, unmanaged solution packages for the **AlSanidi | Marketing** solution
(publisher AlSanidi Development, prefix `sanidi`). Each package holds only its own component(s), so importing
it doesn't touch anything else in the solution, and IDs are deterministic so re-importing updates in place.

| Folder | Table | Flow |
|---|---|---|
| `snap-campaign/` | Snap Campaign (`sanidi_SnapCampaign`) | Get Snap Campaigns (manual) |
| `snap-adsquad/` | Snap Ad Squad (`sanidi_SnapAdSquad`, lookup to Snap Campaign) | Get Snap Ad Squads (when a Snap Campaign is added or modified) |
| `snap-advertisement/` | Snap Advertisement (`sanidi_SnapAdvertisement`, lookup to Snap Ad Squad) | Get Snap Advertisements (when a Snap Ad Squad is added or modified) |
| `snap-insights/` | – | Get Snap Insights (manual): refreshes only the insight columns on all three tables |

`table_builder.py` holds the shared table logic (columns, choices, lookups, keys, form, views),
`flow_builder.py` the shared "sync a parent's children from Snap" flow logic, and `snap_insights.py` the
all-time insight columns and stats actions shared by all three tables and flows.

## Insights

Each Snap table carries the same all-time (Snap `LIFETIME`) stats on an **Insights** tab, written by its sync
flow in the same Update/Add step as the entity's own columns (one `Get ... stats` call per row, no breakdowns):

- **Delivery:** Impressions, Reach (`uniques`), Frequency, Swipes, Spend
- **Engagement:** Video Views, Engaged Views, Screen Time (sec), Video 25/50/75%, Video Completions,
  Landing Page Views, Place Opens, Place Actions
- **Conversions:** Purchases, Purchase Value, Add to Cart, Start Checkout, View Content, Page Views (Pixel), Sign Ups
- **Calculated in the flow:** Swipe Rate (%), CPM, Cost per Swipe, Cost per Purchase, ROAS (empty when the
  denominator is 0)
- **Sync:** Stats Finalized Through (Snap finalizes lifetime stats 48-72 h later) and Stats Last Synced (empty
  when the stats call failed; the entity columns are still written)

Money values are Snap micro-currency / 1,000,000; conversions use Snap's default attribution windows.

**Get Snap Insights** (manual, modeled on Get Meta Insights) refreshes just these columns without the full
sync cascade: it lists active Snap Campaigns, then Ad Squads, then Advertisements that have a Snap ID, fetches each
row's LIFETIME stats (10 at a time) and updates only the insight columns.

## Template export

The generators copy Dataverse's XML formats from the Meta tables, so they need a solution export containing
**Meta Campaign**, **Meta Ad Set** and **Meta Ad** (`sanidi_metacampaign`, `sanidi_metaadset`, `sanidi_meta_ad`).
An export of AlSanidi | Marketing works:

```bash
pac solution export --name AlSanidiMarketing --path Template.zip
```

If that export ever fails, put those three tables in a temporary solution under the same publisher, export it,
and delete the temporary solution:

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
python3 snap-insights/build_flow_solution.py       --template Template.zip --out GetSnapInsightsFlow.zip

pac solution import --path SnapAdvertisementTable.zip --publish-changes
pac solution import --path SnapAdSquadTable.zip       --publish-changes
pac solution import --path SnapCampaignTable.zip      --publish-changes
pac solution import --path GetSnapCampaignsFlow.zip
pac solution import --path GetSnapAdSquadsFlow.zip
pac solution import --path GetSnapAdvertisementsFlow.zip
pac solution import --path GetSnapInsightsFlow.zip
```

Only one import can run in an environment at a time; if `pac` reports another import running, wait and retry.

Imported flows arrive turned off; turn them on in the portal.

## Connection references

The Snap flows use `sanidi_sharedsanidi5fsnap5f43b530b23a0dc933_a4073` (Snap connector) and
`sanidi_sharedcommondataserviceforapps_79822` (Dataverse); both are set in `flow_builder.py`. The flow packages
reuse them and never create connection references. A Snap connection reference with no connection blocks the
solution export ("requires the custom connector to be added to a dataverse solution"), so delete any such
unused reference.
