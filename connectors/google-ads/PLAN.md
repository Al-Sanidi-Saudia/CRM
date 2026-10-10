# Google Ads integration: plan (AlSanidi-UAT)

Status: **approved** (2026-10-10). Step 1 (connector in repo) done; every step that changes UAT still needs approval.

Decisions:
- **Legacy items are left untouched**: the `sanidi_google_*` tables and the daily "Google Ads Sync" flow.
- **Metrics are all-time totals**, refreshed on every sync.
- **Credentials:** reuse the Google OAuth client of the old sync flow. The old flow has no developer
  token (it never synced: `campaigns=0`, errors on every run), so a **developer token is still needed**.
- **Choices:** every Google Ads enum becomes a Dataverse choice with **all** v25 enum values (including
  `UNSPECIFIED` / `UNKNOWN`), numbered **from 1**. Repeated enums become multi-select choices.

Environment: `https://operations-alsenidiuat.crm4.dynamics.com`
Solution: **AlSanidi | Marketing** (`AlSanidiMarketing`), publisher prefix **`sanidi`**

It follows the existing Snap integration exactly:

| | Snap (existing) | Google Ads (new) |
|---|---|---|
| Connector | `sanidi_snap` "Snap" | `sanidi_googleads` "Google Ads" |
| Level 1 table | `sanidi_snapcampaign` | `sanidi_googleadscampaign` |
| Level 2 table | `sanidi_snapadsquad` | `sanidi_googleadsadgroup` |
| Level 3 table | `sanidi_snapadvertisement` | `sanidi_googleadsadvertisement` |
| Flow 1 (instant) | Get Snap Campaigns | **Get Google Ads Campaigns** |
| Flow 2 (on L1 create/update) | Get Snap Ad Squads | **Get Google Ads Ad Groups** |
| Flow 3 (on L2 create/update) | Get Snap Advertisements | **Get Google Ads Advertisements** |

Google Ads hierarchy: Customer (account) → Campaign → Ad group → Ad group ad (ad).
API: Google Ads API **v25** (matches the existing `sanidi_GoogleAdsApiVersion` env var).

---

## 1. Custom connector "Google Ads" (`connectors/google-ads/`)

Same file layout as the Snap connector (`build_definition.py` → swagger, `apiProperties.json`,
`deploy.ps1` / `deploy.sh`, README), plus `script.csx`. Google Ads reads go through one GAQL
search endpoint, so the C# script turns each action into a GAQL query, follows paging, and returns
flat rows. That keeps the flows as simple as the Snap ones.

Read-only actions:

| Action | Used by |
|---|---|
| `ListAccessibleCustomers` | setup / test |
| `ListClientAccounts`: accounts under a manager (MCC), including itself | Flow 1 |
| `GetCustomer` | Flow 1 (currency, time zone, name) |
| `ListCampaigns` (all campaign + budget + bidding fields, optional metrics) | Flow 1 |
| `ListAdGroups` (by campaign) | Flow 2 |
| `ListAds` (by ad group) | Flow 3 |
| `GetCampaignPerformance`, `GetAdGroupPerformance`, `GetAdPerformance` (date range, daily/total) | reporting / future |
| `RunQuery`: any GAQL query | ad-hoc |

- Money values arrive in micros and are converted to currency units in the connector.
- Auth: Google OAuth 2.0 (scope `https://www.googleapis.com/auth/adwords`, offline access).
- The **developer token** and optional **manager (login) customer ID** are injected at deploy time.
  They are never committed.
- Deployed into `AlSanidiMarketing` with `pac connector create`, like Snap. The client secret is
  entered on the connector's Security tab.

## 2. Tables

The exact column list (logical name, label, type, GAQL source, form section) is in
[`spec.py`](spec.py). The lists below summarise it.

All three tables are:
- User-owned and in the solution.
- Currency-enabled for the money columns.
- Primary column = name.
- Matched on the Google ID, like Snap's `sanidi_campaignid`.

Choice values start at 1, like Snap. Arrays (status reasons, URLs, labels, headlines) go to
multiline text, comma- or newline-joined. Every table also gets **Raw payload** (the full Google
JSON) and **Last synced on**, so no data from the API is lost.

### 2.1 `sanidi_googleadscampaign`: Google Ads Campaign (115 columns)

**Identity**
- Campaign Name (primary, 375)
- Campaign ID
- Resource Name
- Customer ID
- Customer Name
- Currency Code
- Account Time Zone
- Campaign Group
- Base Campaign
- Labels

**Status**
- Status: ENABLED, PAUSED, REMOVED, UNKNOWN
- Serving Status: SERVING, NONE, ENDED, PENDING, SUSPENDED
- Primary Status: ELIGIBLE, PAUSED, REMOVED, ENDED, PENDING, MISCONFIGURED, LIMITED, LEARNING, NOT_ELIGIBLE
- Primary Status Reasons
- Experiment Type: BASE, DRAFT, EXPERIMENT
- Ad Serving Optimization Status
- Optimization Score

**Channel**
- Advertising Channel Type: SEARCH, DISPLAY, SHOPPING, HOTEL, VIDEO, MULTI_CHANNEL, LOCAL, SMART, PERFORMANCE_MAX, LOCAL_SERVICES, TRAVEL, DEMAND_GEN
- Advertising Channel Sub Type
- Payment Mode: CLICKS, CONVERSION_VALUE, CONVERSIONS, GUEST_STAY

**Schedule**
- Start Date Time
- End Date Time

**Budget**
- Budget ID
- Budget Name
- Daily Budget (money)
- Total Budget (money)
- Recommended Budget (money)
- Budget Delivery Method: STANDARD, ACCELERATED
- Budget Period: DAILY, CUSTOM_PERIOD
- Budget Explicitly Shared
- Budget Status

**Bidding**
- Bidding Strategy Type: TARGET_CPA, TARGET_ROAS, MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE, TARGET_SPEND, MANUAL_CPC, MANUAL_CPM, MANUAL_CPV, TARGET_IMPRESSION_SHARE, TARGET_CPM, FIXED_CPM, COMMISSION, PERCENT_CPC, …
- Portfolio Bidding Strategy
- Target CPA (money)
- Target ROAS
- Enhanced CPC Enabled
- Target Impression Share Location
- Target Impression Share %
- CPC Bid Ceiling (money)

**Networks and geo**
- Target Google Search
- Target Search Network
- Target Content Network
- Target Partner Search Network
- Target YouTube
- Target Google TV
- Positive Geo Target Type
- Negative Geo Target Type

**Tracking**
- Tracking URL Template
- Final URL Suffix
- URL Custom Parameters
- URL Expansion Opt-out

**Channel settings**
- Merchant ID
- Feed Label
- DSA Domain
- DSA Language
- App ID
- App Store
- App Bidding Goal
- Hotel Center ID
- Brand Guidelines Enabled
- Video Brand Safety Suitability
- Contains EU Political Advertising
- Frequency Caps
- Excluded Parent Asset Field Types

**Performance (all-time)**
- Impressions
- Clicks
- CTR
- Avg. CPC
- Avg. CPM
- Cost
- Conversions
- Conversions Value
- Cost / Conversion
- Conversion Rate
- All Conversions
- View-through Conversions
- Interactions
- Interaction Rate
- Search Impression Share
- Metrics Period

**Sync**
- Last Synced On
- Raw Payload

### 2.2 `sanidi_googleadsadgroup`: Google Ads Ad Group (78 columns + campaign lookup)

**Identity**
- Ad Group Name (primary)
- Ad Group ID
- Resource Name
- Campaign ID
- Customer ID
- **Google Ads Campaign** (lookup)
- Labels

**Status**
- Status
- Primary Status
- Primary Status Reasons

**Type**
- Ad Group Type: SEARCH_STANDARD, DISPLAY_STANDARD, SHOPPING_PRODUCT_ADS, HOTEL_ADS, VIDEO_RESPONSIVE, VIDEO_BUMPER, VIDEO_TRUE_VIEW_IN_STREAM, VIDEO_NON_SKIPPABLE_IN_STREAM, SEARCH_DYNAMIC_ADS, SMART_CAMPAIGN_ADS, TRAVEL_ADS, …
- Ad Rotation Mode

**Bids**
- CPC Bid
- CPM Bid
- CPV Bid
- Target CPA
- Target CPM
- Target ROAS
- Percent CPC Bid
- Effective CPC Bid
- Effective Target CPA
- Effective Target ROAS
- Effective CPC Bid Source
- Effective Target CPA Source
- Effective Target ROAS Source

**Targeting**
- Optimized Targeting Enabled
- Exclude Demographic Expansion
- Use Audience Grouped
- Display Custom Bid Dimension

**Tracking**
- Tracking URL Template
- Final URL Suffix
- URL Custom Parameters

**Performance**
- The same metric set as campaigns

**Sync**
- Last Synced On
- Raw Payload

### 2.3 `sanidi_googleadsadvertisement`: Google Ads Advertisement (75 columns + ad group lookup)

**Identity**
- Ad Name (primary; falls back to the first headline / ad ID when Google has no name)
- Ad ID
- Resource Name
- Ad Group ID
- Campaign ID
- Customer ID
- **Google Ads Ad Group** (lookup)
- Labels

**Status**
- Status
- Primary Status
- Primary Status Reasons
- Ad Strength: PENDING, NO_ADS, POOR, AVERAGE, GOOD, EXCELLENT
- Action Items

**Policy**
- Approval Status: APPROVED, APPROVED_LIMITED, AREA_OF_INTEREST_ONLY, DISAPPROVED
- Review Status: REVIEW_IN_PROGRESS, REVIEWED, UNDER_APPEAL, ELIGIBLE_MAY_SERVE
- Policy Topics

**Ad**
- Ad Type: RESPONSIVE_SEARCH_AD, RESPONSIVE_DISPLAY_AD, VIDEO_RESPONSIVE_AD, DEMAND_GEN_MULTI_ASSET_AD, IMAGE_AD, APP_AD, CALL_AD, SHOPPING_PRODUCT_AD, … (~35 values)
- Device Preference
- Added by Google Ads
- System Managed Source

**Creative**
- Headlines
- Long Headline
- Descriptions
- Business Name
- Call to Action
- Path 1
- Path 2
- Display URL
- Image Assets
- Video Assets

**URLs**
- Final URLs
- Final Mobile URLs
- Final App URLs
- Tracking URL Template
- Final URL Suffix
- URL Custom Parameters

**Performance**
- The same metric set as campaigns

**Sync**
- Last Synced On
- Raw Payload

## 3. Forms ("Information" main form, same tab style as Snap)

| Table | Tabs → sections |
|---|---|
| Campaign | **General** (Identity, Status, Schedule) · **Budget & Bidding** (Budget, Bidding) · **Networks & Targeting** (Networks, Geo, Channel settings) · **Tracking** · **Performance** · **Related** (Ad Groups subgrid) · **Sync** (Last synced, Raw payload) |
| Ad Group | **General** (Identity, Status, Type) · **Bidding** (Bids, Effective bids) · **Targeting & Tracking** · **Performance** · **Related** (Ads subgrid) · **Sync** |
| Advertisement | **General** (Identity, Status, Type) · **Creative** (Text, Assets) · **Review & Policy** · **URLs & Tracking** · **Performance** · **Sync** |

## 4. Views

The **Active** view is the default and shows the main fields first, then the rest, like Snap.

| Table | Default view columns |
|---|---|
| Campaign | Name, Status, Primary Status, Channel Type, Bidding Strategy, Daily Budget, Start, End, Impressions, Clicks, Cost, Conversions, Campaign ID, Customer ID, Last Synced On |
| Ad Group | Name, Status, Primary Status, Campaign (lookup), Type, CPC Bid, Impressions, Clicks, Cost, Conversions, Ad Group ID, Last Synced On |
| Advertisement | Name, Status, Approval Status, Ad Strength, Ad Type, Ad Group (lookup), Final URL, Impressions, Clicks, Cost, Conversions, Ad ID, Last Synced On |

Each table also gets an **Inactive** view (Name, Status, Last Synced On, Created On), as Snap has.

## 5. Flows (in the solution, connection references reused or added)

1. **Get Google Ads Campaigns**: *instant (manual)*.
   1. Read `sanidi_GoogleAdsCustomerId` (env var, already `9274270701`).
   2. List client accounts (handles both a single account and an MCC).
   3. For each non-manager account → `ListCampaigns`.
   4. For each campaign: find it by Campaign ID, then update it or create it.
   5. Map choices with a `Choice_maps` compose, as Snap does.
   6. Write a summary to `sanidi_GoogleAdsLastSyncStatus`.
2. **Get Google Ads Ad Groups**: *trigger: Google Ads Campaign added or modified* (organization scope).
   1. `ListAdGroups(customer_id, campaign_id)`.
   2. Update or create each ad group, binding the Campaign lookup.
3. **Get Google Ads Advertisements**: *trigger: Google Ads Ad Group added or modified*.
   1. `ListAds(customer_id, ad_group_id)`.
   2. Update or create each ad, binding the Ad Group lookup.

Connection references:
- Dataverse: reuse `sanidi_sharedcommondataserviceforapps_79822`.
- Google Ads: a new reference to the Google Ads connector.

## 6. Execution order (each step needs your approval before I run it)

| # | Step | Where | Who |
|---|---|---|---|
| 1 | Build the connector files, commit, push | repo | me |
| 2 | Deploy the connector to `AlSanidiMarketing`, add the secret, register the redirect URL, test | UAT | you run `deploy.ps1` (no `pac` in my sandbox); I guide |
| 3 | Create the 3 tables + columns in the solution | UAT (Web API with solution header) | me, after approval |
| 4 | Create the lookups / relationships | UAT | me, after approval |
| 5 | Build the main forms (tabs/sections) + views, publish | UAT | me, after approval |
| 6 | Create the 3 flows in the solution (off), then you create the Google Ads connection | UAT | me, after approval; connection by you |
| 7 | Turn on and test-run Flow 1 → check Flows 2 and 3 cascade | UAT | together |

Table/form/view/flow definitions are also saved in the repo (`dataverse/google-ads/`) so they can
be reviewed and re-run.
