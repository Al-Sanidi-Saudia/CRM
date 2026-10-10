# Google Ads custom connector

Power Platform custom connector for the [Google Ads API](https://developers.google.com/google-ads/api/docs/start) (v25).
It is **read-only** and covers accounts, campaigns, ad groups, ads and their performance. It lives in the
**AlSanidi | Marketing** solution and feeds the Google Ads tables and flows described in [PLAN.md](PLAN.md).

Authentication: the connector has **no sign-in**. Its **Get access token** action exchanges the Google
OAuth client ID, client secret and refresh token for an access token, which is valid for one hour.
Every other action takes that **access token** and the Google Ads **developer token** as inputs. The
flows read all four values from environment variables:

| Environment variable | Holds |
|---|---|
| `sanidi_GoogleAdsClientId` | Google Cloud OAuth client ID |
| `sanidi_GoogleAdsClientSecret` | OAuth client secret |
| `sanidi_GoogleAdsRefreshToken` | OAuth refresh token (adwords scope) |
| `sanidi_GoogleAdsDeveloperToken` | Google Ads API developer token |
| `sanidi_GoogleAdsLoginCustomerId` | Manager (MCC) ID, when the account is reached through a manager |
| `sanidi_GoogleAdsCustomerId` | Ads account to sync (already existed) |

The first three were copied from the legacy "Google Ads Sync" flow. Their values are kept out of the
solution, so they are not exported to other environments; set them per environment.

| File | Purpose |
|---|---|
| `spec.py` | Source of truth: every column (Dataverse name, label, form section, type, GAQL source) |
| `fields_v25.json` | Google Ads v25 field types and enum values for the fields in `spec.py` |
| `build_definition.py` | Generates `apiDefinition.swagger.json` and the operations block of `script.csx` |
| `apiDefinition.swagger.json` | OpenAPI 2.0 definition (generated, committed) |
| `script.csx` | Connector custom code: token exchange, GAQL per action, paging, metrics merge, flat rows |
| `apiProperties.json` | Connector properties (no auth) |
| `deploy_dataverse.py` | Creates/updates the connector and the environment variables in the solution via the Dataverse Web API |
| `deploy.ps1` / `deploy.sh` | Alternative: create/update the connector with `pac` |

## Operations

| Action | What it returns |
|---|---|
| `GetAccessToken` | A Google access token from client ID, client secret and refresh token |
| `ListAccessibleCustomers` | Customer IDs the signed-in Google user can open directly |
| `ListClientAccounts` | Accounts under a manager (MCC); a regular account returns itself |
| `ListCampaigns` | Campaigns with budget, bidding, networks, geo, tracking and channel settings + all-time metrics |
| `ListAdGroups` | Ad groups with bids, effective bids, targeting, Demand Gen channels + all-time metrics |
| `ListAds` | Ads with type, strength, policy review, headlines/descriptions, assets, URLs + all-time metrics |
| `GetPerformance` | Metrics per campaign / ad group / ad for a date range, total or per day/week/month, optional device/network split |
| `RunQuery` | Any GAQL `SELECT`, all pages, optionally flattened to `campaign_id` / `metrics_clicks` style keys |

Hierarchy: Customer (account) → Campaign → Ad group → Ad.

Notes:
- The keys of each `List*` row are the Dataverse column names without `sanidi_` (see `spec.py`), so flows
  map `sanidi_<key>` = `row.<key>`.
- Money is in the account currency: micros are already divided by 1,000,000. Rates (CTR, impression share,
  optimization score…) are percentages, 0–100.
- Enum fields come back as Google's enum names (`ENABLED`, `SEARCH`…). The Dataverse choice options use
  every v25 enum value, numbered from 1 in the order in `fields_v25.json`.
- Every `List*` call also returns `rawpayload` (the full Google row as JSON) and `lastsyncedon`.
- Metrics are read with a second query, so paused or new items with no activity are still returned.
  If metrics can't be read, the rows are still returned and `metrics_error` says why.
- Pass **Manager customer ID** (`login-customer-id`) when the Google user reaches the account through
  a manager account.

## Deploy

Uses the service principal from `scripts/dataverse-mcp.sh` (`DATAVERSE_*` variables):

```bash
python3 deploy_dataverse.py env-vars            # dry run: shows what would be created
python3 deploy_dataverse.py env-vars --apply    # environment variables (+ values copied from the legacy flow)
python3 deploy_dataverse.py connector --apply   # create or update the "Google Ads" connector in AlSanidiMarketing
```

Then:
1. In make.powerapps.com → Solutions → AlSanidi | Marketing → Environment variables, set
   **Google Ads Developer Token**. If the account is reached through a manager, also set **Login Customer ID**.
2. Create a connection to **Google Ads**; no sign-in is needed. Run **Get access token** with the three
   environment variable values, then **List client accounts** with customer `9274270701`.

`deploy.ps1` / `deploy.sh` do the same with `pac connector create|update` if you prefer the CLI.

The developer token must have Basic or Standard access to read live accounts. A test-only token can
read test accounts only. The refresh token must belong to a Google user who can open the Ads account,
and must have been issued for the `https://www.googleapis.com/auth/adwords` scope.

To ship changes:
1. Edit `spec.py` or `script.csx`.
2. Run `python3 build_definition.py`.
3. Run `python3 deploy_dataverse.py connector --apply`, which updates the existing connector.
