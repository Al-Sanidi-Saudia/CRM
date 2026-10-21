# TikTok Ads integration: plan (AlSanidi-UAT)

Status: **draft, waiting for approval**. Nothing has been created in UAT yet.

Environment: `https://operations-alsenidiuat.crm4.dynamics.com`
Solution: **AlSanidi | Marketing** (`AlSanidiMarketing`), publisher **AlSanidi Development**, prefix **`sanidi`**
API: TikTok API for Business **v1.3** (`https://business-api.tiktok.com/open_api/v1.3/`)

It follows the Snap and Google Ads integrations:

| | Snap | Google Ads | TikTok (new) |
|---|---|---|---|
| Connector | `sanidi_snap` "Snap" | `sanidi_googleads` "Google Ads" | `sanidi_tiktok` **"TikTok"** |
| Level 1 table | `sanidi_snapcampaign` | `sanidi_googleadscampaign` | `sanidi_tiktokcampaign` **TikTok Campaign** |
| Level 2 table | `sanidi_snapadsquad` | `sanidi_googleadsadgroup` | `sanidi_tiktokadgroup` **TikTok Ad Group** |
| Level 3 table | `sanidi_snapadvertisement` | `sanidi_googleadsadvertisement` | `sanidi_tiktokadvertisement` **TikTok Advertisement** |
| Flow 1 (instant) | Get Snap Campaigns | Get Google Ads Campaigns | **Get TikTok Campaigns** |
| Flow 2 (on L1 added/modified) | Get Snap Ad Squads | Get Google Ads Ad Groups | **Get TikTok Ad Groups** |
| Flow 3 (on L2 added/modified) | Get Snap Advertisements | Get Google Ads Advertisements | **Get TikTok Advertisements** |
| Insights (instant, standalone) | Get Snap Insights | Get Google Ads Insights | **Get TikTok Insights** |

TikTok hierarchy: Advertiser (ad account) → Campaign → Ad group → Ad.

Sources read for this plan:
- [Get campaigns](https://business-api.tiktok.com/portal/docs/get-campaigns/v1.3) (`/campaign/get/`): 39 fields
- [Get ad groups](https://business-api.tiktok.com/portal/docs/get-ad-groups/v1.3) (`/adgroup/get/`): 147 fields
- [Get ads](https://business-api.tiktok.com/portal/docs/get-ads/v1.3) (`/ad/get/`): 93 fields
- [Run a synchronous report](https://business-api.tiktok.com/portal/docs/run-a-synchronous-report/v1.3) (`/report/integrated/get/`, `query_lifetime=true`)
- Basic reports: Supported metrics (1,023 metrics) and Supported dimensions
- Enumerations (status, objective, bid type, placements, CTA, …) and Authentication (long-term access token)

---

## What exists in UAT today (checked 2026-10-21)

- No TikTok tables, connector or connection reference.
- Environment variables `sanidi_TikTokAccessToken` and `sanidi_TikTokAdvertiserIds` exist, both **empty**.
- Legacy flow **"TikTok Ads Sync - Campaigns, Ad Groups, Ads & Insights to Dataverse"** (daily 04:30) has
  **failed every day**. It never stored a token. Its App ID and Secret are typed into the flow itself. They look like a
  Microsoft Entra app ID (a GUID) and an Entra client secret, not TikTok values (a TikTok App ID is a long number).
- Sync Control already has a **TikTok** row in Integration Platform (key `tiktok`, *Set Up* = No, no flows).
- The **Map … Cost** flows add Google Ads + Meta + Snap cost into `sanidi_campaign.sanidi_cost` /
  `sanidi_advertisement.sanidi_cost`. TikTok is not part of them.

---

## 1. Custom connector "TikTok" (`connectors/tiktok-ads/`)

Same layout as Google Ads:
- `spec.py`: source of truth.
- `build_definition.py`: generates the swagger and the operations block of `script.csx`.
- `apiDefinition.swagger.json`
- `script.csx`
- `apiProperties.json`
- `deploy_dataverse.py`
- `deploy.ps1` / `deploy.sh`
- `README.md`

The connector is created **directly in `AlSanidiMarketing` through the Dataverse Web API**, like Google Ads, so its
internal name is `sanidi_tiktok`.

**Authentication.** The connector has no sign-in, like Google Ads. TikTok's long-term access token does not expire,
so it lives in an environment variable. Every action takes it as the `Access-Token` header. The flows read the token
from the environment variable and pass it in.

| Action | TikTok endpoint | Used by |
|---|---|---|
| `GetAccessToken` | `POST /oauth2/access_token/` (app_id + secret + auth_code → long-term token + advertiser IDs) | one-time setup |
| `ListAuthorizedAdvertisers` | `GET /oauth2/advertiser/get/` (app_id + secret + token) | setup / test |
| `GetAdvertiserInfo` | `GET /advertiser/info/` (name, currency, time zone, status) | Flow 1 |
| `ListCampaigns` | `GET /campaign/get/` | Flow 1 |
| `ListAdGroups` | `GET /adgroup/get/` filtered by campaign | Flow 2 |
| `ListAds` | `GET /ad/get/` filtered by ad group | Flow 3 |
| `GetLifetimeInsights` | `GET /report/integrated/get/`, `report_type=BASIC`, `query_lifetime=true`, `data_level` = campaign / ad group / ad | Insights flow |
| `RunReport` | any `/report/integrated/get/` request (date range, daily, …) | ad-hoc / future |

The custom code (`script.csx`) does the following:
- Asks for every field (`fields`) and follows all pages (`page_size` 1000 for lists and reports).
- Returns **flat rows whose keys are the Dataverse column names**, so flows map `sanidi_<key>` = `row.<key>`, as in Google Ads.
- Turns arrays into one value per line and objects into JSON, and cuts text to the column length.
- Converts TikTok's text metrics into numbers.
- Splits the metric list across several report calls when it is too long for one request, then merges the rows.
- Adds `rawpayload` (the full TikTok object) and `lastsyncedon` to every row.

TikTok returns money in the **ad account currency**, not micros. Lifetime metrics are cumulative since the item was
created.

## 2. Environment variables (all keys, in the solution, values set per environment)

| Schema name | Display name | State |
|---|---|---|
| `sanidi_TikTokAppId` | TikTok App ID | **new**: the TikTok for Business developer app ID |
| `sanidi_TikTokAppSecret` | TikTok App Secret | **new**: the app secret. Do not share. |
| `sanidi_TikTokAccessToken` | TikTok Access Token | exists (empty): the long-term access token |
| `sanidi_TikTokAdvertiserIds` | TikTok Advertiser IDs | exists (empty): comma-separated advertiser IDs to sync |

As with Google Ads, the values are **not stored in the solution**, so secrets are never exported to other
environments. The descriptions of the two existing variables still name the legacy flow; I'll update them.

**Getting the token (one time).** The ad account owner opens the app's authorization URL and approves it. TikTok
then redirects with an `auth_code`, which is valid for 1 hour and can be used once. Then either:
- run the connector's **Get access token** action and paste the token and the advertiser IDs into the two
  environment variables, or
- give me the auth code, and `python3 deploy_dataverse.py token --auth-code …` exchanges it and writes both values.

## 3. Tables

All three tables are set up like the Google Ads ones:
- User-owned, in the solution, currency-enabled.
- Primary column = name. Records are matched on the TikTok ID (`sanidi_campaignid` / `sanidi_adgroupid` / `sanidi_adid`).
- Column names are the TikTok field name **without underscores** (`campaign_name` → `sanidi_campaignname`), as in Google Ads.

Type rules (from the documented data types):

| TikTok type | Dataverse column |
|---|---|
| string ID | Text (100) |
| string | Text (400; URLs, templates and deeplinks 2,000) |
| string with documented enum values | **Choice**: every documented value, numbered from 1 (Google Ads convention) |
| string[] with documented enum values (placements, age groups, special industries, …) | **Multi-select choice** |
| string[] without enum (location IDs, audience IDs, keyword IDs, image IDs, ad texts, …) | Multiline text, one per line |
| boolean | Yes/No |
| float/number that is money (budget, bid price, target CPA, deep CPA bid, TopView budget/CPM) | Currency |
| other float/number (ROAS bid, frequency, retention, estimates) | Decimal / Whole number |
| datetime / `YYYY-MM-DD HH:MM:SS` (create, modify, schedule start/end; UTC) | Date and time |
| object / object[] (search keywords, actions, schedule infos, UTM params, disclaimers, showcase products, …) | Multiline text, JSON |

When TikTok sends a choice value that is not in the documented list, the choice column stays empty. The value is
still kept in **Raw Payload**.

**Name clashes with insight metrics.** Two ad group settings share a name with a report metric, so the settings are renamed:
- Ad group `frequency` → **Frequency Cap** (`sanidi_frequencycap`)
- Ad group `cpm` (TopView estimate) → **TopView Estimated CPM** (`sanidi_topviewcpm`)

The insight metrics keep their TikTok names.

### 3.1 `sanidi_tiktokcampaign`: TikTok Campaign (39 API fields + advertiser info + sync + insights)

- **Identity**:
  - Campaign Name (primary), Campaign ID, Advertiser ID
  - Advertiser Name, Currency, Account Time Zone (from `/advertiser/info/`)
  - Campaign System Origin, Created On (TikTok), Modified On (TikTok), PO Number, Is New Structure
- **Status**: Operation Status, Secondary Status (20 values)
- **Objective & Type**:
  - Objective Type (10 values), Virtual Objective Type, Objective (APP / LANDING_PAGE), App Promotion Type, Sales Destination
  - Campaign Type, Campaign Automation Type, Smart Performance Campaign, Search Campaign, Advanced Dedicated Campaign
  - R&F Campaign Type, Product Source, Catalog Enabled, Special Industries (multi), App ID
  - App Profile Page State, SKAN Disabled, Bid Align Type, Postback Window Mode
- **Budget & Bidding**:
  - Budget Mode, Budget, Campaign Budget Optimization (`budget_optimize_on`), Bid Type, Deep Bid Type, ROAS Bid, Optimization Goal
  - RTA ID, RTA Bid Enabled, RTA Product Selection Enabled
- **Insights** (all time): see §4
- **Sync**: Last Synced On, Raw Payload

### 3.2 `sanidi_tiktokadgroup`: TikTok Ad Group (147 API fields + **TikTok Campaign** lookup)

- **Identity**:
  - Ad Group Name (primary), Ad Group ID, Campaign ID, Campaign Name, Advertiser ID
  - Campaign System Origin, Campaign Automation Type, Smart Performance Campaign
  - Created On / Modified On (TikTok), Is New Structure, Split Test Group ID, Split Test Status
- **Status**: Operation Status, Secondary Status (53 values), Skip Learning Phase
- **Promotion & Conversion**:
  - Promotion Type, Promotion Target Type, Promotion Website Type
  - Messaging App Type / Account ID, Phone Region Code / Calling Code / Number
  - App ID, App Type, App Download URL, App Config (JSON), Pixel ID
  - Optimization Event, Custom Conversion ID, Secondary Optimization Event, Message Event Set ID
  - Deep Funnel Optimization Status / Event Source / Event Source ID / Event
- **Shopping**:
  - Shopping Ads Type, Product Source, Catalog ID, Catalog BC ID, Store ID, Store BC ID
  - Identity ID, Identity Type, Identity BC ID
  - Shopping Retargeting Type / Action Days / Custom Audience Relation
  - Included / Excluded Custom Actions (JSON)
- **Placements & Search**:
  - Placement Type, Placements (multi), TikTok Subplacements (multi), Search Result Enabled
  - Automated Keywords Enabled, Search Keywords (JSON), Blocked Pangle App IDs
  - Comments / Video Download / Sharing Disabled
- **Audience**:
  - Location IDs, Zip Code IDs, Languages, Gender, Age Groups (multi), Spending Power, Household Income (multi)
  - Audience IDs, Excluded Audience IDs, Smart Audience, Audience Type, Audience Rule (JSON), Saved Audience ID
  - Interest Category IDs, Interest Keyword IDs, Purchase Intention Keyword IDs
  - Behaviors (`actions`, JSON), Smart Interests & Behaviors
  - Pangle Audience Packages (incl./excl.), Auto Targeting Enabled, Targeting Expansion (JSON), Contextual Tag IDs
- **Devices**:
  - Operating Systems (multi), Min Android Version, Min iOS Version, iOS 14 Targeting, iOS 14 Quota Type
  - Device Model IDs, Network Types (multi), Carrier IDs, ISP IDs, Device Price Ranges
- **Brand Safety**: Brand Safety Type, Brand Safety Partner, Inventory Filter Enabled, Category Exclusion IDs, Vertical Sensitivity ID, HFSS, LHF Compliance
- **Budget & Schedule**:
  - Budget Mode, Budget, Scheduled Budget, Schedule Type, Schedule Start Time, Schedule End Time
  - Dayparting, Pacing, Delivery Mode, Schedule Infos (JSON)
- **Bidding & Optimization**:
  - Optimization Goal, Billing Event, Bid Type, Bid Price, Conversion Bid Price, Deep Bid Type, ROAS Bid, Deep CPA Bid
  - VBO Window, Bid Display Mode, CPV Video Duration, Next Day Retention, Statistic Type
  - Frequency Cap, Frequency Schedule, Creative Material Mode, App Profile Page State, Feed Type
- **Attribution**: Click / Engaged View / View Attribution Window, Attribution Event Count, Conversion Window (deprecated)
- **Reach & Frequency / TopView**:
  - R&F Purchased Type, Purchased Impression, Purchased Reach, R&F Estimated CPR, R&F Estimated Frequency
  - Predicted Impressions, TopView Reach Range, Pre-discount CPM, TopView Estimated CPM
  - Discount Type / Amount / Percentage, Pre-discount Budget
- **Insights** (all time): see §4
- **Related**: TikTok Advertisements sub-grid
- **Sync**: Last Synced On, Raw Payload

### 3.3 `sanidi_tiktokadvertisement`: TikTok Advertisement (93 API fields + **TikTok Ad Group** lookup)

- **Identity**:
  - Ad Name (primary), Ad ID, Ad ID v2, Smart+ Ad ID
  - Ad Group ID, Ad Group Name, Campaign ID, Campaign Name, Advertiser ID
  - Campaign Automation Type, Campaign System Origin, Created On / Modified On (TikTok), Is New Structure
- **Status**: Operation Status, Secondary Status (45 values), Smart Creative (`is_aco`), Creative Authorized
- **Format & Creative**:
  - Ad Format, Creative Type, Dynamic Format, Vertical Video Strategy, Video ID, Image IDs, Carousel Image Index
  - Music ID, End Card CTA, Auto Disclaimer Types (multi), Product Display Fields (multi)
  - Creative Auto-enhancements (multi), AIGC Disclosure Type, Playable URL
- **Text & CTA**:
  - Ad Text, Ad Texts, Call to Action, CTA Portfolio ID, Creative Portfolio ID (`card_id`)
  - Display Name, App Name, Avatar Icon, Profile Image URL
- **Identity & Spark Ads**:
  - Identity ID, Identity Type, Identity BC ID, TikTok Post ID (`tiktok_item_id`)
  - Promotional Music Disabled, Duet Status, Stitch Status, Dark Post Status, Branded Content Disabled
- **Products**:
  - Catalog ID, Product Specific Type, Item Group IDs, Product Set ID, SKU IDs, Vehicle IDs
  - Showcase Products (JSON), Shopping Video Package ID
- **Destination**:
  - Landing Page URL, UTM Params (JSON), Page ID, CPP URL, TikTok Page Category
  - Phone Region Code / Calling Code / Number
  - Deeplink, Deeplink Type, Deeplink Format Type, Shopping Ads Deeplink Type, Deeplink UTM Params (JSON)
  - Shopping Fallback Type, Fallback Type, Dynamic Destination, Auto Message ID
- **Disclaimers**: Disclaimer Type, Disclaimer Text, Clickable Disclaimers (JSON)
- **Tracking & Measurement**:
  - Tracking Pixel ID, Tracking App ID, Offline Event Set IDs, Message Event Set ID, Optimization Event
  - Moat Viewability, Viewability Partner / VAST URL, Brand Safety Partner / VAST URL
  - Impression Tracking URL, Click Tracking URL
  - Comments / Video Download / Sharing Disabled (TopView)
- **Insights** (all time): see §4
- **Sync**: Last Synced On, Raw Payload

## 4. Insights (all time, same columns on all three tables)

The report API documents **1,023 metrics**. They cannot all become columns: a Dataverse table holds at most about 1,024
columns, and every currency column adds a second "base" column. Most of the metrics only apply to app, iOS SKAN,
TikTok Shop or offline campaigns. **The metric groups are the main open question (Q1).** They come from TikTok's
"Supported metrics" page:

| Group | Metrics | Examples | Recommended |
|---|---|---|---|
| Core | 30 | spend, billed_cost, impressions, clicks, ctr, cpc, cpm, reach, frequency, conversion, cost_per_conversion, result, cost_per_result | ✅ |
| Video | 15 | video_play_actions, video_watched_2s/6s, video_views_p25…p100, average_video_play, engaged_view (6s/15s focused views) | ✅ |
| Clicks / engagement | 9 | engagements, engagement_rate, anchor_clicks, duet/stitch/hashtag clicks | ✅ |
| Social | 11 | follows, likes, comments, shares, profile_visits, cost_per_consideration | ✅ |
| Website (pixel events) | 109 | complete_payment(+value/ROAS), add_to_cart, initiate_checkout, view content, landing page views, form, registration, search, subscribe… | ✅ |
| Attribution (click / view / engaged view) | 30 | vta_conversion, cta_conversion, engaged_view_through_conversions, vta/cta purchase | ✅ |
| Messaging | 6 | TikTok direct message / instant messaging app conversations | optional |
| LIVE / Image / Interactive add-ons / Instant experience | 21 | live_views, single_image_ctr, interactive_add_on_*, ix_page_duration_avg | optional |
| TikTok Shop | 24 | onsite_shopping(+ROAS), shop gross revenue, onsite checkout / cart / detail | only if you use TikTok Shop |
| App events | 208 | app_install, registration, purchase (+ROAS day 0/2/6), retention… | only if you promote an app |
| TikTok on-platform (Paid + Native Growth) | 242 | on-TikTok conversion events | not recommended |
| Offline events | 99 | offline purchase / lead events | only if you upload offline events |
| SKAN / SAN (iOS attribution) | 254 | skan_*, san_* | not recommended |

The recommended set comes to about **204 metric columns per table**. Each table also gets **Insights Last Synced On**.
The "Attribute" metrics (names, IDs, budget…) are left out because the record already has them.

Form: an **Insights** tab, like Snap and Meta, with one section per group (Delivery & Cost, Video, Engagement, Social,
Website Conversions, Attribution, plus any optional groups you pick).

Each metric's data type comes from its meaning:
- counts → whole number (or decimal for `conversion` / `result`, which can be fractional)
- `cost_per_*`, `spend`, `cpc`, `cpm`, `value_*` → currency
- `*_rate`, `ctr` → decimal (%)
- `*_roas` → decimal

Before the columns are created, I'll check against the live API that each one is returned at all three levels
(campaign / ad group / ad). Any metric TikTok rejects at a level is dropped from that table, as was done for Google Ads.

## 5. Forms and views

Main form "Information", tabs in the Snap / Google Ads style:

| Table | Tabs → sections |
|---|---|
| Campaign | **General** (Identity, Status, Objective & Type) · **Budget & Bidding** · **Insights** · **Related** (TikTok Ad Groups sub-grid) · **Sync** |
| Ad Group | **General** (Identity, Status) · **Promotion & Shopping** · **Targeting** (Placements & Search, Audience, Devices, Brand Safety) · **Budget & Bidding** (Budget & Schedule, Bidding & Optimization, Attribution, R&F / TopView) · **Insights** · **Related** (TikTok Advertisements sub-grid) · **Sync** |
| Advertisement | **General** (Identity, Status) · **Creative** (Format & Creative, Text & CTA, Identity & Spark Ads, Products) · **Destination & Tracking** (Destination, Disclaimers, Tracking & Measurement) · **Insights** · **Sync** |

The header shows Operation Status, Secondary Status and Last Synced On. The parent lookup is placed first in Identity.

Views:
- **Active** (default): the main columns first, then all others (Raw Payload left out).
  - Campaign: Name, Operation Status, Secondary Status, Objective, Budget Mode, Budget, Spend, Impressions, Clicks, CTR, Conversions, Campaign ID, Advertiser ID, Last Synced On
  - Ad Group: Name, TikTok Campaign, Operation Status, Secondary Status, Optimization Goal, Bid Type, Budget, Spend, Impressions, Clicks, Conversions, Ad Group ID, Last Synced On
  - Advertisement: Name, TikTok Ad Group, Operation Status, Secondary Status, Ad Format, Call to Action, Landing Page URL, Spend, Impressions, Clicks, Conversions, Ad ID, Last Synced On
- **Inactive**: Name, Operation Status, Last Synced On, Created On.

Lookups (cascade **Remove Link**, so synced children are never cascade-deleted):
- `sanidi_tiktokadgroup.sanidi_tiktokcampaign` → TikTok Campaign
- `sanidi_tiktokadvertisement.sanidi_tiktokadgroup` → TikTok Ad Group

## 6. Flows (in the solution, stored connections, turned off when created)

Every flow reads the environment variables and passes the access token to the TikTok actions. Choices are mapped
with a `Choice_maps` compose generated from `spec.py` (TikTok value → option value), as in Google Ads.

Data flows (hierarchical):
1. **Get TikTok Campaigns** (*instant*):
   - For each advertiser ID in `sanidi_TikTokAdvertiserIds`: get its info (currency), then `ListCampaigns`.
   - Find each campaign by Campaign ID, then update or create it, with the currency set from the advertiser.
   - Ends with **Respond to a Power App or flow**, so Sync Control can run it.
2. **Get TikTok Ad Groups** (*when a TikTok Campaign is added or modified*):
   - `ListAdGroups` for that campaign.
   - Update or create each ad group, binding the Campaign lookup.
3. **Get TikTok Advertisements** (*when a TikTok Ad Group is added or modified*):
   - `ListAds` for that ad group.
   - Update or create each ad, binding the Ad Group lookup.

Insights (standalone):

4. **Get TikTok Insights** (*instant*):
   - For each advertiser: `GetLifetimeInsights` at campaign, ad group and ad level. That is one paged report per
     level, not one call per record.
   - Then it lists the active TikTok records and updates **only the insight columns** and Insights Last Synced On.
   - Ends with **Respond to a Power App or flow**.

The data flows do **not** read insights. That differs from Snap and Google Ads, whose data flows also write metrics.

Connection references:
- Dataverse: reuse `sanidi_sharedcommondataserviceforapps_79822`, the one the Snap / Meta / Google flows use.
- TikTok: a new reference `sanidi_sharedsanidi5ftiktok…`. You create the connection itself; it needs no sign-in.

## 7. Execution order (I report after each step and stop where something is needed from you)

| # | Step | Where | Who |
|---|---|---|---|
| 1 | `spec.py`: every field and metric with its column name, label, type, choice values and form section (from the docs) | repo | me |
| 2 | Connector files (`build_definition.py` → swagger, `script.csx`, deploy scripts, README), commit, push | repo | me |
| 3 | Create the 2 new environment variables and update the 2 existing descriptions; create the TikTok connector in `AlSanidiMarketing` | UAT | me |
| 4 | TikTok app authorization → access token + advertiser IDs in the environment variables | TikTok + UAT | **you** (auth code), then me |
| 5 | Live check: call campaigns / ad groups / ads / lifetime report and confirm the field and metric lists per level | UAT | me |
| 6 | Create the 3 tables + columns, then the 2 lookups, in the solution | UAT | me |
| 7 | Build the main forms (tabs incl. Insights) and the Active / Inactive views, publish | UAT | me |
| 8 | Create the TikTok connection reference and the 4 flows (turned off) | UAT | me |
| 9 | Create the TikTok connection and bind it in the flows (no sign-in), turn the flows on | UAT | **you** |
| 10 | Test: run Get TikTok Campaigns → check that Ad Groups and Ads follow, then run Get TikTok Insights | UAT | together |
| 11 | Optional items you approve in the questions below (Sync Control, cost roll-up, legacy flow, Arabic labels) | UAT + repo | me |

Everything is also saved in the repo (`connectors/tiktok-ads/`), so it can be reviewed and re-run in another
environment.

---

## Open questions (needed before I start)

1. **Insight metrics**: which groups from the table in §4? All 1,023 can't fit. The recommended set is Core + Video +
   Clicks + Social + Website + Attribution (~204 columns). Do you also run TikTok Shop, app-install, lead / messaging,
   LIVE or offline-event campaigns?
2. **TikTok developer app**: do you have an approved app in the TikTok for Business developer portal (App ID +
   Secret) with *Ad Account Management* and *Reporting* permissions? The values in the legacy flow look like Microsoft
   Entra credentials. Who can authorize the ad accounts, and how many advertiser IDs are there?
3. **Deleted items**: TikTok leaves deleted campaigns / ad groups / ads out by default. Sync them too (their status
   becomes *Deleted*), or only non-deleted? Google Ads syncs everything including removed.
4. **Legacy "TikTok Ads Sync" flow**: leave it untouched (as with the legacy Google / Snap / Meta flows), or turn it off?
   It fails every day.
5. **Trigger loop**: in Snap / Meta / Google, the insights flow updates campaigns and ad groups. Those updates re-run
   the ad group and ad flows, because their triggers fire on any change. For TikTok I recommend limiting the
   Ad Groups / Advertisements triggers to the non-insight columns, so insights don't re-run the data sync. OK?
6. **Sync Control**: register TikTok on the Sync Control page? That means setting the Integration Platform row and
   adding the two cases to *Sync Control - Run Sync Request*.
7. **Cost roll-up**: add TikTok to the Campaign / Advertisement cost roll-up? That means a TikTok lookup on
   `sanidi_campaign` / `sanidi_advertisement` plus two "Map TikTok … Spend" flows like the Snap ones.
8. **Arabic labels**: add ar-SA labels for the new tables and columns, as was done for the rest of the solution?
9. **Out of scope unless you say otherwise**:
   - GMV Max campaigns: TikTok Shop GMV Max uses a separate endpoint, `/gmv_max/campaign/get/`.
   - Creatives / video and image details: separate file endpoints.
   - Daily / breakdown reports: only all-time totals, as you asked.
