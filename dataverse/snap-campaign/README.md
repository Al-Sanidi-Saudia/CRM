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

`build_table_solution.py` holds the column list, form layout (including a Related tab listing the campaign's
Snap Ad Squads) and views. See `../README.md` for building and importing.

## Get Snap Campaigns flow

`build_flow_solution.py` builds the **Get Snap Campaigns** cloud flow (manual trigger) into the same solution,
modeled on Meta's "Get Campaigns":

1. **Choice maps**: a lookup of Snap value → option value for every choice column, generated from the table's
   column list so the two can't drift apart.
2. **Snap → List organizations** (with ad accounts), then for each ad account **List campaigns**.
3. For each campaign: map Delivery Status to its option values, **List rows** on Campaign ID, then
   **Update a row** if it exists or **Add a new row** if not. Money values are divided by 1,000,000.

It uses a new connection reference `sanidi_snapconnection` (Snap connector) and the existing Dataverse reference
`sanidi_sharedcommondataserviceforapps_79822`. See `../README.md` for building and importing.
