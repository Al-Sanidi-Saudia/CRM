# Snap Campaign table (`sanidi_SnapCampaign`)

Stores Snapchat campaigns from the [Snapchat Marketing API](https://developers.snap.com/marketing-api/Ads-API/campaigns),
filled by the **Get Snap Campaigns** flow. It lives in **AlSanidi | Marketing** (publisher AlSanidi Development,
prefix `sanidi`) in **alsenidiuat**.

- Entity set: `sanidi_snapcampaigns`
- Primary name: `sanidi_campaignname`
- Alternate key: `sanidi_snapcampaign_campaignidkey` on `sanidi_campaignid`, so the flow can upsert with
  `PATCH sanidi_snapcampaigns(sanidi_campaignid='<id>')`
- Choices use Snap's values as labels, numbered from 1. Delivery Status is a multi-select backed by the global
  choice `sanidi_snapcampaigndeliverystatus`.
- Money columns hold Snap's micro values divided by 1,000,000.

`build_table_solution.py` holds the column list, form layout and views. It builds a solution package that
contains only this table, using the exported Meta Campaign table as the XML format template:

```bash
pac solution export --name AlSanidiMarketing --path AlSanidiMarketing.zip --environment <env>
python3 build_table_solution.py --template AlSanidiMarketing.zip --out SnapCampaignTable.zip
pac solution import --path SnapCampaignTable.zip --environment <env> --publish-changes
```

IDs are deterministic, so re-importing after a change updates the same table, form and views.
