# TikTok Ads integration

Power Platform custom connector, tables, flows and app pieces for the
[TikTok API for Business](https://business-api.tiktok.com/portal/docs) **v1.3**. It is **read-only**:
campaigns, ad groups, ads and their all-time insights. Everything lives in the **AlSanidi | Marketing** solution
(`AlSanidiMarketing`, prefix `sanidi`) and follows the Snap and Google Ads integrations. The agreed scope and
decisions are in [PLAN.md](PLAN.md), and the 204 insight metrics are in [INSIGHTS.md](INSIGHTS.md).

Hierarchy: Advertiser (ad account) → Campaign → Ad group → Ad.

## Components

| Component | Name |
|---|---|
| Connector | `sanidi_tiktok` **TikTok** (no sign-in) |
| Environment variables | `sanidi_TikTokAdsAppId`, `sanidi_TikTokAdsAppSecret`, `sanidi_TikTokAdsAccessToken`, `sanidi_TikTokAdsAdvertiserIds` |
| Tables | `sanidi_tiktokcampaign` TikTok Campaign, `sanidi_tiktokadgroup` TikTok Ad Group, `sanidi_tiktokadvertisement` TikTok Advertisement |
| Lookups | Ad Group → TikTok Campaign, Advertisement → TikTok Ad Group; Campaign → TikTok Campaign, Advertisement → TikTok Advertisement (cost roll-up) |
| Flows | Get TikTok Campaigns (instant), Get TikTok Ad Groups (TikTok Campaign added/modified), Get TikTok Advertisements (TikTok Ad Group added/modified), Get TikTok Insights (instant), Map TikTok Campaign Spend to Campaign, Map TikTok Advertisement Spend to Advertisement |
| App | TikTok group in the Integration area of AlSanidi \| Marketing; Manager role reads the three tables |
| Sync Control | TikTok card (Data + Insights), with *Connection Active* = No until the connection works |

The legacy "TikTok Ads Sync" flow and its environment variables (`sanidi_TikTokAccessToken`,
`sanidi_TikTokAdvertiserIds`) are not used or changed.

## Files

| File | Purpose |
|---|---|
| `fetch_docs.py` | Reads the TikTok docs (Get campaigns / ad groups / ads, enumerations, supported metrics) into `fields_v1.3.json` |
| `fields_v1.3.json` | Every response field with its type and documented enum values, plus the 204 metrics (generated) |
| `spec.py` | Source of truth: every column (Dataverse name, label, form section, type, TikTok source), forms and views |
| `build_definition.py` | Generates `apiDefinition.swagger.json` and the operations block of `script.csx` |
| `script.csx` | Connector custom code: TikTok calls, paging, deleted items, metric chunks, flat rows keyed by column name |
| `apiProperties.json` | Connector properties (no auth) |
| `deploy_dataverse.py` | Environment variables, the connector, and the one-time access token |
| `deploy_tables.py`, `deploy_relationships.py` | Tables + columns, lookups |
| `deploy_ui.py`, `deploy_app.py` | Forms and views; site map, app tables, Manager role |
| `deploy_flows.py` | The four sync flows (`flows/*.json` for review) |
| `deploy_costrollup.py` | Cost roll-up lookups, forms, form scripts and flows |
| `deploy.ps1` / `deploy.sh` | Alternative: create/update the connector with `pac` |

The form scripts are in `webresources/sanidi_/scripts/` (`campaign.form.js`, `advertisement.form.js`). Sync Control
changes are in `sync-control/` (`scripts/add_tiktok.py`, `update_dispatcher.py`, `page/sync-control.tsx`).

## Operations

| Action | What it returns |
|---|---|
| `GetAccessToken` | Long-term access token + authorized advertiser IDs, from App ID, App secret and an authorization code |
| `ListAuthorizedAdvertisers` | Advertisers the token can read |
| `GetAdvertiserInfo` | Name, currency, time zone, status of an advertiser |
| `ListCampaigns` / `ListAdGroups` / `ListAds` | Every field TikTok returns, all pages, deleted items included (second query with `primary_status = STATUS_DELETE`) |
| `GetLifetimeInsights` | All-time metrics per campaign / ad group / ad of an advertiser (`query_lifetime`), one row per item |
| `RunReport` | Any `/report/integrated/get/` request, all pages, flat rows |

Notes:
- Row keys are the Dataverse column names without `sanidi_`, so flows map `sanidi_<key>` = `row.<key>`.
- Money is in the ad account currency, as TikTok sends it. Rates are percentages.
- Choice values are TikTok's enum names. The Dataverse options are every documented value, numbered from 1 in the
  order of `fields_v1.3.json`. A value TikTok adds later leaves the choice empty but is kept in Raw Payload.
- Insights are read in chunks of 50 metrics. A chunk TikTok refuses is split until only the refused metric is dropped.
  The response then has `metrics_error`, naming the refused metric.
- TikTok answers errors with HTTP 200 and a non-zero `code`. The connector returns them as HTTP 400 (429 for rate
  limits) with TikTok's message and request ID.

## Setup after TikTok approves the app

1. In the TikTok for Business developer app:
   - Set the advertiser redirect URL to a page you control, for example `https://www.alsanidi.com.sa/`.
   - Make sure the app has the *Ad Account Management*, *Ads Management* and *Reporting* permissions.
2. Open the app's advertiser authorization URL and approve the ad accounts. Copy `auth_code` from the address bar of
   the page TikTok redirects to. It is valid for 1 hour and can be used once.
3. In make.powerapps.com, go to Solutions → AlSanidi | Marketing → Environment variables and set **TikTok Ads App ID**
   and **TikTok Ads App Secret**. Then do either of these:
   - `python3 deploy_dataverse.py token --auth-code <code> --apply`, which writes **TikTok Ads Access Token** and
     **TikTok Ads Advertiser IDs**, or
   - run the connector's **Get access token** action and paste both values yourself.
4. Create a **TikTok** connection (no sign-in) and set it on the TikTok connection reference
   (`sanidi_sharedsanidi5ftiktok5f43b530b23a0dc933_3e7c1`). Then turn on the four Get TikTok flows.
5. Run **Get TikTok Campaigns**. Ad groups and ads follow automatically. Then run **Get TikTok Insights**.
6. In Integration Platform, set **Connection Active** to Yes on the TikTok row. Sync Control then enables its buttons.

## Deploy (service principal from `scripts/dataverse-mcp.sh`, `DATAVERSE_*` variables)

Every script is a dry run without `--apply`, and each one is safe to re-run.

```bash
python3 fetch_docs.py && python3 build_definition.py   # after a docs or spec change
python3 deploy_dataverse.py env-vars --apply
python3 deploy_dataverse.py connector --apply
python3 deploy_tables.py --apply             # one table at a time: --only=tiktokadgroup
python3 deploy_relationships.py --apply
python3 deploy_ui.py --apply
python3 deploy_app.py --apply
python3 deploy_flows.py --apply              # --update-existing to replace definitions
python3 deploy_costrollup.py --apply
```

Dataverse runs one table change at a time per environment, so the table scripts can't run in parallel. Each column
takes about 5 seconds.
