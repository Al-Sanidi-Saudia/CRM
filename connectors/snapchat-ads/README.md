# Snapchat Ads custom connector

Power Platform custom connector for the [Snapchat Marketing API](https://developers.snap.com/api/marketing-api/Ads-API/introduction).
It is **read-only** and limited to campaigns, their structure, and their insights. It lives in the
**AlSanidi | Marketing** solution.

| File | Purpose |
|---|---|
| `build_definition.py` | Source of truth; generates `apiDefinition.swagger.json` |
| `apiDefinition.swagger.json` | OpenAPI 2.0 definition (generated, committed) |
| `apiProperties.json` | OAuth 2.0 settings; client ID placeholder filled in at deploy time |
| `deploy.sh` | Creates/updates the connector in the solution via `pac` |

## Operations

**Structure**
- `GetMe`: authenticated user
- `ListOrganizations`: organizations, optionally with their ad accounts
- `ListAdAccounts`, `GetAdAccount`
- `ListCampaigns`, `GetCampaign`
- `ListAdSquadsByAdAccount`, `ListAdSquadsByCampaign`, `GetAdSquad`
- `ListAdsByAdAccount`, `ListAdsByAdSquad`, `GetAd`
- `ListCreatives`, `GetCreative`

**Insights**
- `GetAdAccountStats` (breakdown `campaign`)
- `GetCampaignStats` (breakdown `adsquad` / `ad`)
- `GetAdSquadStats` (breakdown `ad`)
- `GetAdStats`
- `GetStatsReport`: polls an async report (`async=true` on any stats call)

Hierarchy: Organization → Ad account → Campaign → Ad squad → Ad → Creative.

Notes:
- Money fields (`spend`, `*_micro`, `conversion_purchases_value`) are in **micro-currency**; divide by 1,000,000.
- DAY/HOUR stats need `start_time`/`end_time` on hour boundaries in the ad account's time zone.
- List calls return everything by default. Set `limit` (50–1000) and follow `paging.next_link` → `cursor` to page.

## Deploy

Prerequisites: [Power Platform CLI](https://learn.microsoft.com/power-platform/developer/cli/introduction)
and a Snap OAuth app (Snap Business Manager → Business Details → OAuth Apps) with the Marketing API scope.

```bash
# 1. Find the unique name of the "AlSanidi | Marketing" solution
pac solution list

# 2. Create the connector in that solution
SNAP_CLIENT_ID=<client id> ./deploy.sh https://<org>.crm4.dynamics.com <SolutionUniqueName>
```

Then in make.powerapps.com → Solutions → AlSanidi | Marketing → the connector:
1. **Security** tab: enter the Snap **client secret** → *Update connector*. The secret is never stored in this repo.
2. Copy the **Redirect URL** shown there (`https://global.consent.azure-apim.net/redirect/...`) into the Snap OAuth app's redirect URI.
3. **Test** tab: create a connection (sign in with a Snapchat Business account that has access to the ad accounts) and run `ListOrganizations`.

To ship changes, edit `build_definition.py`, then run
`./deploy.sh <env> <solution> <connector-id>`. That updates the connector, and the solution then carries it to other environments.
