# Social Media Daily and Monthly Insights: feasibility study and plan (AlSanidi-UAT)

Status: **draft for approval. Nothing has been changed in Dataverse.** Everything below comes from read-only checks of
UAT (tables, connectors, flows) and from each platform's official API documentation.

Environment: `https://operations-alsenidiuat.crm4.dynamics.com`
Solution: **AlSanidi | Marketing** (`AlSanidiMarketing`), publisher prefix **`sanidi`**

Goal: one row per day per synced item (campaign / ad set or ad squad or ad group / asset group / ad) with that day's
statistics (and one row per month, §1.6), for Meta, Snap, TikTok and Google Ads. The **driver is the 13 tables we already sync**: a daily row is
written only for an item that exists in those tables, and it is linked to that item.

---

## 1. Feasibility study

### 1.1 Answer: all 4 platforms provide daily statistics

| Platform | Daily statistics? | How you ask for one row per day (official API) | Levels with daily data |
|---|---|---|---|
| **Meta** (Graph API v26.0) | **Yes** | Insights edge with `time_increment=1` ("number of days from 1 to 90") and `time_range`, `level` = campaign / adset / ad | Campaign, Ad set, Ad |
| **Snap** (Marketing API v1) | **Yes** | Stats endpoints with `granularity=DAY`, `start_time` / `end_time` on the ad account's day boundaries | Campaign, Ad squad, Ad |
| **TikTok** (API for Business v1.3) | **Yes** | `/report/integrated/get/` with `stat_time_day` in `dimensions`, `data_level` = AUCTION_CAMPAIGN / ADGROUP / AD | Campaign, Ad group, Ad |
| **Google Ads** (API v25) | **Yes** | GAQL with `segments.date` in the SELECT and a finite date range in the WHERE | Campaign, Ad group, Ad, **Asset group** (`date` is a selectable segment for `asset_group`) |

**None of the 4 lacks daily statistics.** All 13 tables have a matching daily report.

### 1.2 Limits that shape the design

| | Meta | Snap | TikTok | Google Ads |
|---|---|---|---|---|
| Max days per request | 37 months per query (`date_preset=maximum` limit); `time_increment` 1 | **31 days** (DAY granularity, sync request); async reports have no cap | **30 days** when `stat_time_day` is a dimension | No per-request cap (finite range required) |
| How far back | **37 months** | Async reports from 2013-01-01 | Not stated in the docs | **37 months** for daily (`segments.date`) since 1 June 2026 |
| Day boundary | Ad account time zone | Ad account time zone (must align to its day boundaries) | Ad account time zone | Account time zone |
| When a day stops changing | "Insights … do not change after **28 days**" | "Metrics are finalized **48 hours** after the end of the day"; conversions can still change after that | Not stated in the report docs (checked in the live check, §3 step 2) | Conversions keep arriving for the conversion window (up to 90 days) |
| Deleted / archived items | Only returned when filtered with `ad.effective_status` (DELETED / ARCHIVED), or queried by ID | Returned by ID | Left out by default (`campaign_status` / `adgroup_status` / `ad_status` default to `STATUS_NOT_DELETE`); returned with `STATUS_ALL` | Returned (REMOVED status) |
| Money | Account currency | **Micro-currency** (÷ 1,000,000) | Account currency | Micros (connector already converts) |

What this means for the design:
1. **Rolling refresh.** Each run reloads the last *N* days, not just yesterday, because recent days keep changing.
   Proposed default N = **28 days** (Meta's stable point; well past Snap's 48 hours). Google Ads conversions can
   move for up to 90 days, so Google gets a weekly 90-day refresh.
2. **Chunking.** Back-fills and refreshes are split into 30-day windows (TikTok's limit, and under Snap's 31).
3. **Date-only column.** The day is the platform's account-time-zone day, stored as a Dataverse *Date Only* column
   so it never shifts with the user's time zone.
4. **Reach / uniques / frequency per day are daily uniques**: they cannot be added up into a month or lifetime value.
   They are kept, but reports must not sum them.
5. **Rates** (CTR, CPC, CPM, ROAS…) per day are kept as the platform sends them; totals over a period must be
   recalculated from the counts, not averaged.

### 1.3 Connectors: what changes

| Connector | Today (lifetime insights) | Daily: change needed |
|---|---|---|
| **Google Ads** `sanidi_googleads` | `GetPerformance` with `ALL_TIME` / `TOTAL` | **None.** `GetPerformance` already has `granularity = DAILY` + `start_date` / `end_date` for all 4 levels. |
| **Snap** `sanidi_snap` | `Get…Stats` per item with `granularity=LIFETIME` | **None required.** `GetCampaignStats` already accepts `DAY`, `start_time` / `end_time` and `breakdown = adsquad / ad`. Optional: add `breakdown` to `GetAdAccountStats` (one call per account instead of one per campaign). |
| **TikTok** `sanidi_tiktok` | `GetLifetimeInsights` (metric chunks of 50, merged rows) | **Small:** new action `GetDailyInsights`, the same as `GetLifetimeInsights` but with `stat_time_day` + `start_date` / `end_date` (≤ 30 days), and the status filter set to `STATUS_ALL` so deleted items are included. `RunReport` alone can't be used because the 198 metrics have to be split into chunks and merged. |
| **Meta** `sanidi_meta` | `GetDetailsFromAdID` per item with `insights.date_preset(maximum){…}` | **Small:** new action `GetDailyInsights` → `GET /act_{account_id}/insights` with `level`, `time_range`, `time_increment=1`, `filtering` (to include DELETED / ARCHIVED), all pages. The connector's existing account-insights action has unfilled path placeholders and no `level`, so it can't be used as is. The connector's definition is not in the repo yet; it is exported to `connectors/meta-ads/` first. |

### 1.4 Metrics per daily table (same columns as today's lifetime insights)

| Platform | Insight columns per level today | Daily table gets |
|---|---|---|
| Meta | 28 (campaign / ad set / ad) | the same 28 |
| Snap | 29 | the same 29 |
| Google Ads | 28 campaign, 27 ad group, 23 ad, 18 asset group | the same per level |
| TikTok | 198 (204 minus the refused ones) | the same 198 |

### 1.5 Volume

The 13 tables hold 3,669 items today (Meta 218, Snap 1,387, Google Ads 313, TikTok 1,751). A daily row exists only
for an item that delivered on that day, so a day has at most 3,669 rows and in practice far fewer.
A 28-day rolling refresh means at most about 100,000 updates a run, and in practice a small part of that. A year of
daily rows stays well inside normal Dataverse capacity. The exact numbers come out of the live check (§3, step 2).

### 1.6 Monthly statistics straight from the source (not summed from the daily rows)

**All 4 platforms can return a month, or month-to-date, as one total per item in one request.** The platform calculates
the total itself, so unique metrics (reach, uniques, frequency) are real monthly values. Summing daily rows can't give
those.

| Platform | Month-to-date in one call (official API) | Monthly unit available? | Unique metrics for the month | History |
|---|---|---|---|---|
| **Meta** | `date_preset=this_month` (also `last_month`), `level` = campaign / adset / ad; or `time_range` + `time_increment=monthly` ("one result set for each calendar month") | **Yes** (`time_increment=monthly`) | Reach / frequency for the period requested | 37 months |
| **Snap** | `granularity=TOTAL` with `start_time` = 1st of the month 00:00 and `end_time` = today 00:00, ad account time zone ("time must be of day boundary") | No MONTH granularity; TOTAL over the month gives the same result | `uniques` / `frequency` are allowed with TOTAL (not with HOUR) | No cap stated for TOTAL |
| **TikTok** | `/report/integrated/get/` with only the ID dimension (`campaign_id` / `adgroup_id` / `ad_id`, **no** `stat_time_day`) and `start_date` = 1st of the month, `end_date` = today: one total per item | No month dimension (only `stat_time_day` / `stat_time_hour`); a range without a time dimension gives the month total | `reach` = "unique users who saw your ads at least once", `frequency` "over a given time period" | Up to 365 days per request |
| **Google Ads** | `segments.date DURING THIS_MONTH` (also `LAST_MONTH`), or `segments.month` | **Yes** (`segments.month`) | Google's metric set here has no unique metrics | **11 years** for monthly (daily: 37 months) |

Connectors:
- **Google Ads:** none. `GetPerformance` already has `date_range = THIS_MONTH / LAST_MONTH` and `granularity = MONTHLY`.
- **Snap:** none. `Get…Stats` already accepts `TOTAL` with `start_time` / `end_time`.
- **Meta / TikTok:** the new `GetDailyInsights` actions (§1.3) get a *period* input (day or month), so one action serves both.

How the monthly figures are kept up to date:
- Every run reloads the **current month** (month-to-date). The same row is overwritten until the month ends.
- The **previous month** is still reloaded for the first 28 days of the new month (90 for Google Ads), because its
  conversions keep changing (§1.2). After that it is final.
- Back-fill: one request per month, per account and per level (Snap: per campaign, unless the account-level option in
  §1.3 is added).

Where to store them: **13 monthly tables**, `sanidi_<parent>monthlyinsight` (for example
`sanidi_metacampaignmonthlyinsight`), built exactly like the daily ones but with **Month** (Date Only, 1st of the
month) and **Month to Date** (Yes while the month is still running). Keeping them separate from the daily tables means
a view or a report can never add monthly rows to daily rows and count the same spend twice. The other way would be
one table per structure with a *Period* column (Day / Month): half the tables, but every view, chart and report then
has to filter on Period. (Decision 7.)

---

## 2. Option comparison

### Option A: one table for all platforms and levels

`sanidi_socialmediadailyinsight`: Platform (choice), Level (choice), Date, **13 lookups** (only one filled per row),
plus the union of all metrics.

### Option B: one daily table per synced table (13 tables)

`sanidi_<parent>dailyinsight`, one lookup to its parent, the parent's insight columns, Date.

| | **A. One table** | **B. 13 tables** |
|---|---|---|
| Columns | Union of all metrics: ~280 metrics + ~110 currency base columns + 13 lookups. A Meta row uses ~30 of them. | Each table only its own: 18–198 metrics + 1 lookup. |
| Fidelity per platform | Common metrics (spend, impressions, clicks…) can share one column, but most metrics are platform-specific. | Exact: same columns and names as the parent's Insights tab. |
| Lookups | 13 lookups on one table. Each parent's subgrid filters on its own lookup. | 1 lookup per table. Clean parent → daily subgrid. |
| Unique key | Platform + Level + platform ID + date (text key) | Platform ID + date (text key) |
| Cross-platform reporting in the app | **Easy**: one view / chart for "spend per platform per day". | Needs Power BI (or 13 views). Model-driven charts can't combine tables. |
| Flows | Same mapping per platform; all write to one table. | Flows reuse today's mappings 1:1 (`sanidi_<key>` = `row.<key>`). |
| Forms / views / translations | 1 table, but its form must show/hide platform sections. | 13 tables to build and translate (scripted, same as TikTok). |
| Security | One privilege set for all platforms. | Per platform / per level if ever needed. |
| Adding a metric later | Touches the shared table for every platform. | Touches one table only. |
| Matches today's design | No: today every platform has its own tables. | **Yes**: same pattern as the 13 tables. |

**Recommendation: Option B.** Most metrics are platform-specific (TikTok alone has 198), so one shared table would
be mostly empty columns and harder to maintain. B also keeps the same structure, names and scripts as today. If you
need cross-platform daily reports, a Power BI report over the 13 tables gives that. A small shared table with only the
common metrics (spend, impressions, clicks, conversions, conversion value) can be added later if it is needed inside
the app.

---

## 3. Plan on Dataverse (Option B; each step after your approval)

### 3.1 Tables (13)

| Parent table | Daily table | Lookup |
|---|---|---|
| `sanidi_metacampaign` | `sanidi_metacampaigndailyinsight` Meta Campaign Daily Insight | Meta Campaign |
| `sanidi_metaadset` | `sanidi_metaadsetdailyinsight` Meta Ad Set Daily Insight | Meta Ad Set |
| `sanidi_metaadvertisement` | `sanidi_metaadvertisementdailyinsight` Meta Advertisement Daily Insight | Meta Advertisement |
| `sanidi_snapcampaign` | `sanidi_snapcampaigndailyinsight` Snap Campaign Daily Insight | Snap Campaign |
| `sanidi_snapadsquad` | `sanidi_snapadsquaddailyinsight` Snap Ad Squad Daily Insight | Snap Ad Squad |
| `sanidi_snapadvertisement` | `sanidi_snapadvertisementdailyinsight` Snap Advertisement Daily Insight | Snap Advertisement |
| `sanidi_googleadscampaign` | `sanidi_googleadscampaigndailyinsight` Google Ads Campaign Daily Insight | Google Ads Campaign |
| `sanidi_googleadsadgroup` | `sanidi_googleadsadgroupdailyinsight` Google Ads Ad Group Daily Insight | Google Ads Ad Group |
| `sanidi_googleadsadvertisement` | `sanidi_googleadsadvertisementdailyinsight` Google Ads Advertisement Daily Insight | Google Ads Advertisement |
| `sanidi_googleadsassetgroup` | `sanidi_googleadsassetgroupdailyinsight` Google Ads Asset Group Daily Insight | Google Ads Asset Group |
| `sanidi_tiktokcampaign` | `sanidi_tiktokcampaigndailyinsight` TikTok Campaign Daily Insight | TikTok Campaign |
| `sanidi_tiktokadgroup` | `sanidi_tiktokadgroupdailyinsight` TikTok Ad Group Daily Insight | TikTok Ad Group |
| `sanidi_tiktokadvertisement` | `sanidi_tiktokadvertisementdailyinsight` TikTok Advertisement Daily Insight | TikTok Advertisement |

Every daily table:
- User-owned, currency-enabled, in the solution, like the 13 parents.
- **Name** (primary): `<item name> · YYYY-MM-DD`.
- **Date** (`sanidi_date`, Date Only), **Platform ID** (the campaign / ad set / … ID, text),
  **Insight Key** (`<platform ID>_<YYYYMMDD>`, text) with an **alternate key** on it, so every write is an upsert and
  re-running a day never creates duplicates.
- The parent lookup (cascade **Remove Link**, like the existing lookups).
- The parent's insight columns: same logical names, labels, types and choices.
- **Last Synced On**, **Raw Payload** (the platform's row as JSON).

Forms, views, app:
- Main form "Information": General (Name, parent lookup, Date, Platform ID) + the parent's Insights sections.
- Views: **Active** (default, newest date first), **Last 30 days**, **Inactive**.
- Each parent form gets a **Daily Insights** subgrid (newest first) in its Insights tab.
- App **AlSanidi | Marketing**: the 13 tables are added. The site map gets a *Daily Insights* entry in each platform group.
- Security role **AlSanidi | Marketing | Manager**: Read, Append, Append To (organization), like the parents.

### 3.2 Environment variables

| Schema name | Default | Use |
|---|---|---|
| `sanidi_DailyInsightsLookbackDays` | 28 | Days reloaded on every run |
| `sanidi_DailyInsightsGoogleAdsLookbackDays` | 90 | Days reloaded by the weekly Google Ads run |
| `sanidi_DailyInsightsBackfillFrom` | (empty) | First day to load on a back-fill run (YYYY-MM-DD); empty = no back-fill |

### 3.3 Flows (in the solution, stored connections, Respond step, like today)

1. **Get Meta Daily Insights**, **Get Snap Daily Insights**, **Get TikTok Daily Insights**, **Get Google Ads Daily
   Insights** (*instant*, so Sync Control can run them as child flows). Each one does this:
   1. Works out the date range: the lookback, or the back-fill start to yesterday, in 30-day windows.
   2. For each ad account and each level, calls the daily report **once per window for the whole account**
      (Snap: once per campaign with `breakdown`, unless the optional account-level action is added).
   3. **Driver:** lists that level's records from the synced table (`statecode = 0`, platform ID not empty) and keeps
      only report rows whose ID matches. Report rows for items not in Dataverse are skipped and counted.
   4. Upserts each row by Insight Key, binding the parent lookup.
   5. Responds with counts per level: written, skipped, errors.
2. **Daily Insights - Schedule** (*recurrence*, daily ~05:00 Riyadh time): runs the 4 flows one after the other.
   On Fridays it also runs the Google Ads one with the 90-day lookback.

The existing lifetime **Get … Insights** flows and the cost roll-up are **not changed**.

### 3.4 Sync Control

Add a third action, **Daily Insights**, per platform. This needs a new value in the request-type choice, two-to-four
new cases in *Sync Control - Run Sync Request*, and a page update for the third button. The alternative is to run the
daily flow straight after the lifetime one, under the existing *Insights* button: no page change, but that button
takes longer. (Decision 4.)

### 3.5 Arabic (ar-SA)

Same process and glossary as `translations/AlSanidiMarketing/`: the 13 tables, columns, forms, views, site map
entries, environment variables and flows.

### 3.6 Execution order

| # | Step | Where |
|---|---|---|
| 1 | `daily-insights/spec.py`: the 13 tables, columns copied from the parents' insight columns (live metadata), keys, forms, views | repo |
| 2 | **Live check (read-only API calls):** one daily request per platform and level, for one recent week, using the existing connections. Confirms the fields, the deleted-items behaviour (Meta, TikTok), Google asset-group daily rows, and the real row counts. | UAT connectors, no Dataverse writes |
| 3 | Connectors: export Meta to `connectors/meta-ads/`, add `GetDailyInsights` to Meta and TikTok (and optionally Snap account-level breakdown) | repo, then UAT |
| 4 | 13 tables + columns + alternate keys + lookups, publish | UAT |
| 5 | Forms, views, parent subgrids, app site map, Manager role, publish | UAT |
| 6 | 3 environment variables, 4 daily flows + schedule flow (off) | UAT |
| 7 | Test: one week, all platforms; check the daily rows against the platforms' own UIs and against the lifetime totals | UAT |
| 8 | Back-fill from the agreed start date (decision 2), then turn on the schedule | UAT |
| 9 | Sync Control (decision 4) and Arabic translations | UAT |
| 10 | Production: a patch of AlSanidi \| Marketing, imported as managed, like the TikTok patch | Production |

---

## 4. Decisions needed

| # | Topic | Proposal |
|---|---|---|
| 1 | Option A or B | **B** (13 tables) |
| 2 | Back-fill start | For example 2026-01-01, or the full 37 months (Meta, Google Ads). Longer back-fills only make the first run longer. |
| 3 | Lookback | 28 days on every run; Google Ads 90 days weekly |
| 4 | Sync Control | Separate *Daily Insights* button (page change) or under the existing *Insights* button |
| 5 | Deleted / archived items | Load their days too (Meta via the `effective_status` filter), as long as the item exists in the synced table |
| 6 | Solution | New patch "AlSanidi \| Marketing \| Daily Insights" |
| 7 | Monthly statistics (§1.6) | Yes, from the source: 13 separate `…monthlyinsight` tables, refreshed together with the daily ones by the same 4 flows |

---

## Sources (official documentation)

- Meta: [Ad Account Insights reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/)
  (`time_increment` incl. `monthly`, `level`, `time_range`, `date_preset` incl. `this_month` / `last_month`, 37 months), [Insights API](https://developers.facebook.com/docs/marketing-api/insights/)
  (deleted / archived objects), [Limits and best practices](https://developers.facebook.com/docs/marketing-api/insights/best-practices/)
  (stable after 28 days, rate limits)
- Snap: [Measurement](https://developers.snap.com/api/marketing-api/Ads-API/measurement) (DAY granularity, 31-day
  limit, day boundaries, finalized after 48 hours, `breakdown`, TOTAL with start / end, uniques not at HOUR)
- TikTok: [Run a synchronous report](https://business-api.tiktok.com/portal/docs/run-a-synchronous-report/v1.3)
  (`stat_time_day`, 30-day limit, 365 days without a time dimension, `query_lifetime`),
  [Basic reports: supported dimensions](https://business-api.tiktok.com/portal/docs?id=1751443956638721) (time
  dimensions, `STATUS_NOT_DELETE` default), [Basic reports: supported metrics](https://business-api.tiktok.com/portal/docs?id=1751443967255553) (reach, frequency)
- Google Ads: [Segmentation](https://developers.google.com/google-ads/api/docs/reporting/segmentation),
  [Date ranges](https://developers.google.com/google-ads/api/docs/query/date-ranges) (THIS_MONTH / LAST_MONTH,
  `segments.month`, 37 months for daily, 11 years for monthly),
  [Data retention policy, 1 June 2026](https://ads-developers.googleblog.com/2026/05/new-data-retention-policy-for-google.html),
  [asset_group fields](https://developers.google.com/google-ads/api/fields/v26/asset_group) (`date` segment selectable),
  [Conversion window](https://support.google.com/google-ads/answer/3123169) (up to 90 days)
