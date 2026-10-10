# Google Ads custom connector

Power Platform custom connector for the [Google Ads API](https://developers.google.com/google-ads/api/docs/start) (v25).
It is **read-only** and covers accounts, campaigns, ad groups, ads and their performance. It lives in the
**AlSanidi | Marketing** solution and feeds the Google Ads tables and flows described in [PLAN.md](PLAN.md).

| File | Purpose |
|---|---|
| `spec.py` | Source of truth: every column (Dataverse name, label, form section, type, GAQL source) |
| `fields_v25.json` | Google Ads v25 field types and enum values for the fields in `spec.py` |
| `build_definition.py` | Generates `apiDefinition.swagger.json` and the operations block of `script.csx` |
| `apiDefinition.swagger.json` | OpenAPI 2.0 definition (generated, committed) |
| `script.csx` | Connector custom code: turns each action into GAQL, pages, merges metrics, flattens rows |
| `apiProperties.json` | Google OAuth 2.0 settings; client ID placeholder filled in at deploy time |
| `deploy.ps1` / `deploy.sh` | Creates/updates the connector in the solution via `pac` (Windows / bash) |

## Operations

| Action | What it returns |
|---|---|
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
- Pass **Manager customer ID** (`login-customer-id`) when the signed-in user reaches the account through
  a manager account.

## Deploy

Prerequisites:
- [Power Platform CLI](https://learn.microsoft.com/power-platform/developer/cli/introduction).
- A **Google Ads developer token**, Basic or Standard access (Google Ads → Tools → API Center).
  A test-only token can read test accounts only.
- A **Google Cloud OAuth client** of type *Web application*, with the Google Ads API enabled in the same
  Cloud project. The client used by the old "Google Ads Sync" flow can be reused if it is a Web
  application client.

```powershell
Get-ChildItem . | Unblock-File   # files downloaded from GitHub are blocked by Windows
.\deploy.ps1 -EnvironmentUrl https://operations-alsenidiuat.crm4.dynamics.com `
             -GoogleClientId <client id>.apps.googleusercontent.com `
             -DeveloperToken <developer token>
```

macOS / Linux / Git Bash:
```bash
GOOGLE_CLIENT_ID=<client id> GOOGLE_ADS_DEVELOPER_TOKEN=<token> ./deploy.sh https://operations-alsenidiuat.crm4.dynamics.com
```

The developer token is written only into a temporary copy of `script.csx` that is uploaded and then
deleted. It is never stored in this repo.

Then, in make.powerapps.com → Solutions → AlSanidi | Marketing → **Google Ads** connector:
1. **Security** tab: enter the Google **client secret**, then *Update connector*.
2. Copy the **Redirect URL** shown there (`https://global.consent.azure-apim.net/redirect/...`). In Google
   Cloud Console → APIs & Services → Credentials → the OAuth client, add it to **Authorized redirect URIs**.
3. **Test** tab: create a connection by signing in with a Google user that can open the Ads account.
   Then run `ListAccessibleCustomers`, and `ListClientAccounts` with customer ID `9274270701`.

To ship changes:
1. Edit `spec.py` or `script.csx`.
2. Run `python3 build_definition.py`.
3. Redeploy with `-ConnectorId` (PowerShell) or a third argument (bash).
