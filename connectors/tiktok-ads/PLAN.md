# TikTok Ads integration: plan (AlSanidi-UAT)

Status: **decisions agreed (2026-10-21), ready to implement once you confirm.** Nothing has been created in UAT yet.
The TikTok developer app is still waiting for TikTok's approval. Everything that doesn't need a live TikTok call is
built now. The live check and the test runs wait for the approval (see §10).

Environment: `https://operations-alsenidiuat.crm4.dynamics.com`
Solution: **AlSanidi | Marketing** (`AlSanidiMarketing`), publisher **AlSanidi Development**, prefix **`sanidi`**
API: TikTok API for Business **v1.3** (`https://business-api.tiktok.com/open_api/v1.3/`)

## Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Insight metrics | The recommended groups only: Core, Video, Clicks, Social, Website, Attribution: **204 metrics** ([INSIGHTS.md](INSIGHTS.md)) |
| 2 | TikTok app | Approval in progress. You set the environment variables once it is approved. |
| 3 | Deleted items | **Synced too**. Their Secondary Status shows *…_DELETE*. |
| 4 | Legacy TikTok sync | **Left untouched**: the flow and its two environment variables. Everything is new, named like Meta / Snap / Google Ads. |
| 5 | Child triggers | **Same as the others**: on any change of the parent row, no column filter. |
| 6 | Sync Control | **Yes**. The TikTok card shows a *connection not active yet* label (TikTok only) until the connection works. |
| 7 | Cost roll-up | **Yes**. TikTok spend is added to Campaign / Advertisement cost. |
| 8 | Arabic | **Yes**. ar-SA for every new label, with the same glossary and conventions as the existing translations. |
| 9 | GMV Max, creative files, daily reports | Out of scope for now |

## Naming (follows Snap / Google Ads)

| Component | Snap | Google Ads | **TikTok (new)** |
|---|---|---|---|
| Connector | `sanidi_snap` "Snap" | `sanidi_googleads` "Google Ads" | `sanidi_tiktok` **"TikTok"** |
| Level 1 table | `sanidi_snapcampaign` Snap Campaign | `sanidi_googleadscampaign` | `sanidi_tiktokcampaign` **TikTok Campaign** |
| Level 2 table | `sanidi_snapadsquad` Snap Ad Squad | `sanidi_googleadsadgroup` | `sanidi_tiktokadgroup` **TikTok Ad Group** |
| Level 3 table | `sanidi_snapadvertisement` Snap Advertisement | `sanidi_googleadsadvertisement` | `sanidi_tiktokadvertisement` **TikTok Advertisement** |
| Lookup L2 → L1 | `sanidi_snapadsquad_snapcampaign_sanidi_snapcampaign` | same pattern | `sanidi_tiktokadgroup_tiktokcampaign_sanidi_tiktokcampaign` |
| Lookup L3 → L2 | | | `sanidi_tiktokadvertisement_tiktokadgroup_sanidi_tiktokadgroup` |
| Data flow 1 (instant) | Get Snap Campaigns | Get Google Ads Campaigns | **Get TikTok Campaigns** |
| Data flow 2 (L1 added/modified) | Get Snap Ad Squads | Get Google Ads Ad Groups | **Get TikTok Ad Groups** |
| Data flow 3 (L2 added/modified) | Get Snap Advertisements | Get Google Ads Advertisements | **Get TikTok Advertisements** |
| Insights flow (instant) | Get Snap Insights | Get Google Ads Insights | **Get TikTok Insights** |
| Cost roll-up flows | Map Snap Campaign / Advertisement Spend to … | Map Google Ads … Cost to … | **Map TikTok Campaign Spend to Campaign**, **Map TikTok Advertisement Spend to Advertisement** |
| Env vars | `sanidi_Snap…` | `sanidi_GoogleAds…` | `sanidi_TikTokAds…` (see §2) |
| App site map group | SnapChat | Google Ads | **TikTok** |

Sources read:
- [Get campaigns](https://business-api.tiktok.com/portal/docs/get-campaigns/v1.3): 39 fields
- [Get ad groups](https://business-api.tiktok.com/portal/docs/get-ad-groups/v1.3): 147 fields
- [Get ads](https://business-api.tiktok.com/portal/docs/get-ads/v1.3): 93 fields
- [Run a synchronous report](https://business-api.tiktok.com/portal/docs/run-a-synchronous-report/v1.3)
- *Basic reports - Supported metrics* and *Supported dimensions*
- *Enumerations*
- *Authentication* (long-term access token)

---

## What exists in UAT today (checked 2026-10-21) and is left as it is

- Legacy flow **"TikTok Ads Sync - Campaigns, Ad Groups, Ads & Insights to Dataverse"**. It fails daily and has
  Microsoft-looking credentials typed into it.
- The legacy flow's environment variables `sanidi_TikTokAccessToken` and `sanidi_TikTokAdvertiserIds`, both empty.
- No TikTok tables, connector, connection reference or flows.
- The Sync Control **TikTok** row (key `tiktok`, *Set Up* = No). It is updated in §8.

---

## 1. Custom connector "TikTok" (`connectors/tiktok-ads/`)

Same layout as Google Ads:
- `spec.py`: source of truth: every column with its label, type, choice values, form section and TikTok source.
- `build_definition.py`: generates `apiDefinition.swagger.json` and the operations block of `script.csx`.
- `apiProperties.json`
- `deploy_dataverse.py`, `deploy.ps1` / `deploy.sh`
- `README.md`

It is created **directly in `AlSanidiMarketing` through the Dataverse Web API**, so its internal name is
`sanidi_tiktok`.

**Authentication.** The connector has no sign-in, like Google Ads. TikTok's long-term access token does not expire,
so it lives in an environment variable. Every action takes it as the `Access-Token` header, and the flows pass it in.

| Action | TikTok endpoint | Used by |
|---|---|---|
| `GetAccessToken` | `POST /oauth2/access_token/`: app_id + secret + auth_code → long-term token + advertiser IDs | one-time setup |
| `ListAuthorizedAdvertisers` | `GET /oauth2/advertiser/get/` | setup / test |
| `GetAdvertiserInfo` | `GET /advertiser/info/`: name, currency, time zone, status | Get TikTok Campaigns |
| `ListCampaigns` | `GET /campaign/get/`, `primary_status=STATUS_ALL` (includes deleted) | Get TikTok Campaigns |
| `ListAdGroups` | `GET /adgroup/get/` for one campaign, `primary_status=STATUS_ALL` | Get TikTok Ad Groups |
| `ListAds` | `GET /ad/get/` for one ad group, `primary_status=STATUS_ALL` | Get TikTok Advertisements |
| `GetLifetimeInsights` | `GET /report/integrated/get/`: `BASIC`, `query_lifetime=true`, data level campaign / ad group / ad, the 204 metrics | Get TikTok Insights |
| `RunReport` | any `/report/integrated/get/` request | ad-hoc / future |

The custom code (`script.csx`) does the following:
- Asks for every field and follows all pages (`page_size` 1000).
- Returns **flat rows whose keys are the Dataverse column names**, so flows map `sanidi_<key>` = `row.<key>`.
- Arrays become one value per line, objects become JSON, and text is cut to the column length.
- TikTok's text metrics become numbers.
- When the metric list is too long for one report request, it is split across several calls and the rows are merged.
- Adds `rawpayload` (the full TikTok object) and `lastsyncedon` to every row.

TikTok returns money in the **ad account currency** (not micros). Lifetime metrics are cumulative since the item was created.

## 2. Environment variables (new, in the solution; values set per environment)

The legacy variables are left alone, so the new ones get the `TikTokAds` name, as Google Ads uses `GoogleAds`:

| Schema name | Display name | Holds |
|---|---|---|
| `sanidi_TikTokAdsAppId` | TikTok Ads App ID | App ID of the TikTok for Business developer app |
| `sanidi_TikTokAdsAppSecret` | TikTok Ads App Secret | App secret. Do not share. |
| `sanidi_TikTokAdsAccessToken` | TikTok Ads Access Token | Long-term access token. Do not share. |
| `sanidi_TikTokAdsAdvertiserIds` | TikTok Ads Advertiser IDs | Comma-separated advertiser (ad account) IDs to sync |

The values are not stored in the solution, as with Google Ads, so secrets are never exported.

**After TikTok approves the app** (your part):
1. In the developer app, set the advertiser redirect URL to any page you control, for example `https://www.alsanidi.com.sa/`.
   Make sure the app has the *Ad Account Management*, *Ads Management* and *Reporting* permissions.
2. Open the app's advertiser authorization URL and approve the ad accounts. TikTok sends the browser to the redirect
   URL with `?auth_code=…`. The code is valid for 1 hour and can be used once.
3. Fill in **TikTok Ads App ID** and **TikTok Ads App Secret** in make.powerapps.com → Solutions → AlSanidi | Marketing →
   Environment variables. Then do one of these:
   - run the connector's **Get access token** action and paste the token and advertiser IDs into the other two variables, or
   - send me the auth code: `python3 deploy_dataverse.py token --auth-code …` exchanges it and writes both values.

## 3. Tables

All three tables are set up like the Google Ads ones:
- User-owned, in the solution, currency-enabled.
- Primary column = name. Records are matched on the TikTok ID (`sanidi_campaignid` / `sanidi_adgroupid` / `sanidi_adid`).
- Column = `sanidi_` + the TikTok field name without underscores (`campaign_name` → `sanidi_campaignname`).

| TikTok type | Dataverse column |
|---|---|
| string ID | Text (100) |
| string | Text (400; URLs, templates and deeplinks 2,000) |
| string with documented enum values | **Choice**: every documented value, numbered from 1, label = TikTok value (as in Google Ads) |
| string[] with documented enum values | **Multi-select choice** |
| string[] without enum values (IDs, ad texts, …) | Multiline text, one per line |
| boolean | Yes/No |
| money (budget, bids, target costs, TopView budget/CPM) | Currency |
| other number | Decimal / Whole number |
| datetime (create, modify, schedule start/end; UTC) | Date and time |
| object / object[] | Multiline text, JSON |

When TikTok sends a choice value that is not in the documented list, the choice column stays empty. The value is
still kept in **Raw Payload**.

Two ad group settings share a name with a metric, so the settings are renamed:
- `frequency` → **Frequency Cap** (`sanidi_frequencycap`)
- `cpm` (TopView estimate) → **TopView Estimated CPM** (`sanidi_topviewcpm`)

Every table also gets **Last Synced On**, **Raw Payload** and **Insights Last Synced On**.

### 3.1 `sanidi_tiktokcampaign`: TikTok Campaign (39 fields + advertiser info)

- **Identity**:
  - Campaign Name (primary), Campaign ID, Advertiser ID
  - Advertiser Name, Currency, Account Time Zone (from `/advertiser/info/`)
  - Campaign System Origin, Created On / Modified On (TikTok), PO Number, Is New Structure
- **Status**: Operation Status, Secondary Status
- **Objective & Type**:
  - Objective Type, Virtual Objective Type, Objective, App Promotion Type, Sales Destination
  - Campaign Type, Campaign Automation Type, Smart Performance Campaign, Search Campaign, Advanced Dedicated Campaign
  - R&F Campaign Type, Product Source, Catalog Enabled, Special Industries (multi), App ID
  - App Profile Page State, SKAN Disabled, Bid Align Type, Postback Window Mode
- **Budget & Bidding**:
  - Budget Mode, Budget, Campaign Budget Optimization, Bid Type, Deep Bid Type, ROAS Bid, Optimization Goal
  - RTA ID, RTA Bid Enabled, RTA Product Selection Enabled

### 3.2 `sanidi_tiktokadgroup`: TikTok Ad Group (147 fields + **TikTok Campaign** lookup)

- **Identity**:
  - Ad Group Name (primary), Ad Group ID, Campaign ID, Campaign Name, Advertiser ID
  - Campaign System Origin, Campaign Automation Type, Smart Performance Campaign
  - Created On / Modified On (TikTok), Is New Structure, Split Test Group ID / Status
- **Status**: Operation Status, Secondary Status, Skip Learning Phase
- **Promotion & Conversion**:
  - Promotion Type / Target Type / Website Type
  - Messaging App Type / Account ID, Phone Region Code / Calling Code / Number
  - App ID, App Type, App Download URL, App Config, Pixel ID
  - Optimization Event, Custom Conversion ID, Secondary Optimization Event, Message Event Set ID
  - Deep Funnel Optimization Status / Event Source / Source ID / Event
- **Shopping**:
  - Shopping Ads Type, Product Source, Catalog ID / BC ID, Store ID / BC ID, Identity ID / Type / BC ID
  - Shopping Retargeting Type / Action Days / Audience Relation
  - Included / Excluded Custom Actions
- **Placements & Search**:
  - Placement Type, Placements, TikTok Subplacements, Search Result Enabled
  - Automated Keywords, Search Keywords, Blocked Pangle App IDs
  - Comments / Video Download / Sharing Disabled
- **Audience**:
  - Location IDs, Zip Code IDs, Languages, Gender, Age Groups, Spending Power, Household Income
  - Audience IDs / Excluded, Smart Audience, Audience Type, Audience Rule, Saved Audience ID
  - Interest Category / Keyword / Purchase Intention IDs, Behaviors, Smart Interests & Behaviors
  - Pangle Audience Packages, Auto Targeting, Targeting Expansion, Contextual Tag IDs
- **Devices**:
  - Operating Systems, Min Android / iOS Version, iOS 14 Targeting / Quota Type
  - Device Model IDs, Network Types, Carrier IDs, ISP IDs, Device Price Ranges
- **Brand Safety**: Type, Partner, Inventory Filter, Category Exclusion IDs, Vertical Sensitivity ID, HFSS, LHF Compliance
- **Budget & Schedule**: Budget Mode, Budget, Scheduled Budget, Schedule Type / Start / End, Dayparting, Pacing, Delivery Mode, Schedule Infos
- **Bidding & Optimization**:
  - Optimization Goal, Billing Event, Bid Type, Bid Price, Conversion Bid Price, Deep Bid Type, ROAS Bid, Deep CPA Bid
  - VBO Window, Bid Display Mode, CPV Video Duration, Next Day Retention, Statistic Type
  - Frequency Cap, Frequency Schedule, Creative Material Mode, App Profile Page State, Feed Type
- **Attribution**: Click / Engaged View / View Attribution Window, Attribution Event Count, Conversion Window (deprecated)
- **Reach & Frequency / TopView**:
  - R&F Purchased Type, Purchased Impression / Reach, R&F Estimated CPR / Frequency
  - Predicted Impressions, TopView Reach Range, Pre-discount CPM, TopView Estimated CPM
  - Discount Type / Amount / Percentage, Pre-discount Budget

### 3.3 `sanidi_tiktokadvertisement`: TikTok Advertisement (93 fields + **TikTok Ad Group** lookup)

- **Identity**:
  - Ad Name (primary), Ad ID, Ad ID v2, Smart+ Ad ID
  - Ad Group ID / Name, Campaign ID / Name, Advertiser ID
  - Campaign Automation Type, Campaign System Origin, Created On / Modified On (TikTok), Is New Structure
- **Status**: Operation Status, Secondary Status, Smart Creative, Creative Authorized
- **Format & Creative**:
  - Ad Format, Creative Type, Dynamic Format, Vertical Video Strategy, Video ID, Image IDs, Carousel Image Index
  - Music ID, End Card CTA, Auto Disclaimer Types, Product Display Fields, Creative Auto-enhancements
  - AIGC Disclosure Type, Playable URL
- **Text & CTA**: Ad Text, Ad Texts, Call to Action, CTA Portfolio ID, Creative Portfolio ID, Display Name, App Name, Avatar Icon, Profile Image URL
- **Identity & Spark Ads**: Identity ID / Type / BC ID, TikTok Post ID, Promotional Music Disabled, Duet / Stitch Status, Dark Post Status, Branded Content Disabled
- **Products**: Catalog ID, Product Specific Type, Item Group IDs, Product Set ID, SKU IDs, Vehicle IDs, Showcase Products, Shopping Video Package ID
- **Destination**:
  - Landing Page URL, UTM Params, Page ID, CPP URL, TikTok Page Category, Phone Region Code / Calling Code / Number
  - Deeplink, Deeplink Type / Format Type, Shopping Deeplink Type, Deeplink UTM Params
  - Shopping Fallback Type, Fallback Type, Dynamic Destination, Auto Message ID
- **Disclaimers**: Disclaimer Type, Disclaimer Text, Clickable Disclaimers
- **Tracking & Measurement**:
  - Tracking Pixel ID, Tracking App ID, Offline Event Set IDs, Message Event Set ID, Optimization Event
  - Moat Viewability, Viewability Partner / VAST URL, Brand Safety Partner / VAST URL
  - Impression / Click Tracking URL, Comments / Video Download / Sharing Disabled

## 4. Insights (all time): 204 metrics on all three tables

The full list with columns, labels and types is in **[INSIGHTS.md](INSIGHTS.md)**: 92 currency, 67 whole number,
35 percentage and 10 decimal.

| Group | Metrics | Form section |
|---|---|---|
| Core | 30 | Delivery & Cost |
| Video | 15 | Video |
| Clicks | 9 | Engagement |
| Social | 11 | Social |
| Website | 109 | Website Conversions |
| Attribution | 30 | Attribution |

Each table's largest size is the ad group: about 360 custom columns plus about 100 currency "base" columns. That is
well under Dataverse's limit of 1,024 columns per table.

## 5. Forms, views, app

Main form "Information", tabs in the Snap / Google Ads style. Each form has an **Insights** tab, with one section per
group from §4.

| Table | Tabs → sections |
|---|---|
| Campaign | **General** (Identity, Status, Objective & Type) · **Budget & Bidding** · **Insights** · **Related** (TikTok Ad Groups) · **Sync** |
| Ad Group | **General** (Identity, Status) · **Promotion & Shopping** · **Targeting** (Placements & Search, Audience, Devices, Brand Safety) · **Budget & Bidding** (Budget & Schedule, Bidding & Optimization, Attribution, R&F / TopView) · **Insights** · **Related** (TikTok Advertisements) · **Sync** |
| Advertisement | **General** (Identity, Status) · **Creative** (Format & Creative, Text & CTA, Identity & Spark Ads, Products) · **Destination & Tracking** · **Insights** · **Sync** |

- The header shows Operation Status, Secondary Status and Last Synced On. The parent lookup comes first in Identity.
- **Active** view (default): the main columns first, then all others (no Raw Payload).
  - Campaign: Name, Operation Status, Secondary Status, Objective Type, Budget Mode, Budget, Cost, Impressions, Clicks, CTR, Conversions, Campaign ID, Advertiser ID, Last Synced On
  - Ad Group: Name, TikTok Campaign, Operation Status, Secondary Status, Optimization Goal, Bid Type, Budget, Cost, Impressions, Clicks, Conversions, Ad Group ID, Last Synced On
  - Advertisement: Name, TikTok Ad Group, Operation Status, Secondary Status, Ad Format, Call to Action, Landing Page URL, Cost, Impressions, Clicks, Conversions, Ad ID, Last Synced On
- **Inactive** view: Name, Operation Status, Last Synced On, Created On.
- Lookups use cascade **Remove Link**, so synced children are never cascade-deleted.
- **App "AlSanidi | Marketing"**: the 3 tables are added to the app. A **TikTok** group goes in the Integration area,
  after Google Ads and before Sync Control.
- **Security role "AlSanidi | Marketing | Manager"**: Read, Append and Append To (organization) on the 3 tables, the
  same as it has on Snap / Meta / Google Ads. The role is not part of the solution, so this is set in UAT itself.

## 6. Flows (in the solution, stored connections, Respond step on the instant ones)

Every flow reads the environment variables and passes the access token to the TikTok actions. Choices are mapped
with a `Choice_maps` compose generated from `spec.py`.

1. **Get TikTok Campaigns** (*instant*):
   - For each ID in TikTok Ads Advertiser IDs: Get advertiser info (currency), then `ListCampaigns`, deleted included.
   - Find each campaign by Campaign ID, then update or create it, with the currency set from the advertiser.
2. **Get TikTok Ad Groups** (*when a TikTok Campaign is added or modified*, any column, like the others):
   - `ListAdGroups` for that campaign.
   - Update or create each ad group, binding the Campaign lookup.
3. **Get TikTok Advertisements** (*when a TikTok Ad Group is added or modified*):
   - `ListAds` for that ad group.
   - Update or create each ad, binding the Ad Group lookup.
4. **Get TikTok Insights** (*instant*, standalone):
   - For each advertiser: `GetLifetimeInsights` at campaign, ad group and ad level, with one paged report per level.
   - Then it lists the TikTok records and updates **only the insight columns** and Insights Last Synced On.

The data flows don't read insights.

Connection references:
- Dataverse: reuse `sanidi_sharedcommondataserviceforapps_79822`.
- TikTok: a new reference for the TikTok connector. You create the connection; it needs no sign-in.

The flows are created **turned off**. They are turned on after the TikTok connection exists.

## 7. Cost roll-up (Campaign / Advertisement)

- New lookups:
  - `sanidi_campaign.sanidi_tiktokcampaign` → **TikTok Campaign**, on the Campaign form in the *Channel* section next to Snap.
  - `sanidi_advertisement.sanidi_tiktokadvertisement` → **TikTok Advertisement**, on the Advertisement form in the *General* section next to Snap.
- New flows:
  - **Map TikTok Campaign Spend to Campaign**: when `sanidi_tiktokcampaign.sanidi_spend` changes, recalculates every linked Campaign's cost.
  - **Map TikTok Advertisement Spend to Advertisement**: the same for Advertisements.
- **The 8 existing roll-up flows also change**, to add TikTok spend to the sum:
  - Map Google Ads / Meta / Snap Campaign … to Campaign
  - Map Google Ads / Meta / Snap Advertisement … to Advertisement
  - Map Social Media Cost to Campaign / Advertisement: these two also add the TikTok lookup to their trigger columns.
  - Their descriptions change from "Google Ads cost + Meta spend + Snap spend" to "… + TikTok spend".
  - The update keeps each flow on. If a trigger doesn't pick up the new column, the flow is turned off and on once.

## 8. Sync Control

1. **Integration Platform** table: new column **Connection Active** (`sanidi_connectionactive`, Yes/No). Empty counts
   as Yes, so Meta, Snap and Google Ads don't change.
2. TikTok row:
   - *Set Up* = Yes; *Data Flows* = Get TikTok Campaigns → Ad Groups → Advertisements; *Insights Flow* = Get TikTok Insights.
   - **Connection Active = No**.
3. Page (`sync-control.tsx`, v5): when Connection Active is No, the card shows its sections with a warning label,
   *"Connection not active yet: waiting for the TikTok app approval"*, and the Sync buttons are disabled. Setting
   Connection Active to Yes removes the label and enables the buttons; the page itself doesn't change again.
   It is redeployed with `pac model genpage upload`. The CLI is installed and signed in to UAT, and the live page
   matches the repo copy.
4. **Sync Control - Run Sync Request**: add the cases `tiktok-100000000` (Get TikTok Campaigns) and
   `tiktok-100000001` (Get TikTok Insights) in `update_dispatcher.py`.
5. `seed_platforms.py` and the Sync Control README are updated to match.

## 9. Arabic (ar-SA)

Same process and conventions as `translations/AlSanidiMarketing/`:
- TikTok stays in English.
- Abbreviations go in parentheses, for example `تكلفة الألف ظهور (CPM)`.
- API-reference descriptions such as `TikTok: campaign_name.` keep the field name.

The process:
1. Export the solution's translations. I checked that this works from here, through the Organization service.
2. Add the new texts to `tool/dict*.py`.
3. Build with `build_text.py`, import, and publish.
4. Update `files/`, `changes_ar-SA.csv` and the README.

What gets translated:
- the 3 tables and all their columns, descriptions and choice values (the TikTok enum values, as was done for Google Ads)
- forms (tabs, sections), views and the site map group
- the 4 environment variables and the 6 new flows
- the new Campaign / Advertisement lookups and the Connection Active column
- the descriptions of the 8 roll-up flows, which change

## 10. Execution order

| # | Step | Where | Needs TikTok approval? |
|---|---|---|---|
| 1 | `spec.py` (every field + metric: column, label, type, choices, section), `INSIGHTS.md` | repo | no |
| 2 | Connector files (swagger, `script.csx`, deploy scripts, README); commit, push | repo | no |
| 3 | The 4 environment variables + the TikTok connector in `AlSanidiMarketing` | UAT | no |
| 4 | 3 tables + columns, 2 lookups, publish | UAT | no |
| 5 | Forms, views, app tables + site map group, Manager role privileges, publish | UAT | no |
| 6 | TikTok connection reference + 4 flows (off) | UAT | no |
| 7 | Cost roll-up: 2 lookups on Campaign / Advertisement + forms, 2 new flows, 8 flows updated | UAT | no |
| 8 | Sync Control: column, TikTok row (Connection Active = No), page v5, dispatcher cases | UAT | no |
| 9 | Arabic translations: build, import, publish; repo files updated | UAT + repo | no |
| 10 | You: environment variable values + auth code (§2); create the TikTok connection | TikTok + UAT | **yes** |
| 11 | Live check of fields / metrics per level; adjust any column TikTok returns differently; turn flows on | UAT | **yes** |
| 12 | Test: Get TikTok Campaigns → Ad Groups → Ads, then Get TikTok Insights, then cost roll-up; set Connection Active = Yes | UAT | **yes** |

Steps 1–9 can be done now. I commit to `claude/tiktok-integration` after each repo step and report after each UAT step.
