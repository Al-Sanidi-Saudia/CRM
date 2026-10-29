# Social Media Daily and Monthly Insights: feasibility study and plan (AlSanidi-UAT)

Status: **decisions agreed (2026-10-29); scheduling still to be designed. Nothing has been changed in Dataverse.**
Nothing is started in UAT before the plan, including the scheduling, is confirmed. Everything below comes from
read-only checks of UAT (tables, connectors, flows) and from each platform's official API documentation only.

Environment: `https://operations-alsenidiuat.crm4.dynamics.com`
Solution: **AlSanidi | Marketing** (`AlSanidiMarketing`), publisher prefix **`sanidi`**; delivered as a new patch.

Goal, for Meta, Snap, TikTok and Google Ads:
- **Daily:** one row per day per synced item (campaign / ad set, ad squad or ad group / asset group / ad), with that
  day's statistics as the platform reports them.
- **Monthly:** one row per month per synced item, with the month's statistics **as the platform reports them for the
  month** (never summed from the daily rows).
- The **driver is the 13 tables we already sync**: a row is written only for an item that exists in those tables, and
  it is linked to that item.

---

## 0. Agreed decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Daily table design | **13 daily tables**, one per synced table (§3.1) |
| 2 | Monthly table design | **13 separate monthly tables** (§3.1) |
| 3 | Metrics | **All** the metrics we sync as lifetime insights today, on both daily and monthly tables (§1.4) |
| 4 | Raw Payload | **Yes**: every row keeps the platform's original row as JSON |
| 5 | Ownership | **User-owned** |
| 6 | Driver | Confirmed: rows are written only for items that exist in the 13 tables; the others are skipped and counted |
| 7 | Records in our tables | **Active and inactive** records |
| 8 | Deleted / archived items on the platforms | **Included** (Meta `ad.effective_status` filter, TikTok `STATUS_ALL`) |
| 9 | Levels | **All 13**, Google Ads Asset Groups included |
| 10 | Ad accounts | The same accounts the current sync reads (existing environment variables and connections) |
| 11 | Today's partial day | **Included** (the day row is overwritten until the day is over). Mechanism: in the scheduling design (§5) |
| 12 | Month to date | **Up to now, today included**. Mechanism: in the scheduling design (§5) |
| 13 | Months with no activity | **A month row is created even when there is no data**, so Power BI has no gaps. Details still to confirm (§6, Q1–Q3) |
| 14 | Daily history | **One full load per environment** of all the data, then the scheduler keeps it up to date |
| 15 | Monthly history | **One full load per environment** of all the data, then the scheduler keeps it up to date |
| 16 | Daily refresh window | **2 (maybe 3) days**, to be agreed in the scheduling design (§5) |
| 17 | Previous month refresh | Reloaded for the first **28 days** of the new month (**90** for Google Ads) |
| 18 | Schedule | Once a day at **05:00** (Riyadh); Google Ads 90-day reload weekly on **Friday**. Final shape in §5 |
| 19 | Snap calls | **Option B**: add account-level calls to the Snap connector where Snap allows them (§1.3, explained) |
| 20 | Meta connector | **Exported to the repo** (`connectors/meta-ads/`) before it is changed |
| 21 | Sync Control | **Two new buttons** per platform: *Daily Insights* and *Monthly Insights*; plus a **full-load button**, configured on the Integration Platform row. The period each button reloads is agreed in §5 |
| 22 | Notifications | **Nobody** for scheduled runs; the person who pressed the button for Sync Control runs (as today). Revisited with the scheduling (§5) |
| 23 | Forms | **Daily Insights** and **Monthly Insights** subgrids on each of the 13 parent forms (Insights tab) |
| 24 | Site map | **None for now**: the new tables are reached through the parent forms' subgrids |
| 25 | Charts | **None for now** |
| 26 | Security | **AlSanidi \| Marketing \| Manager**: Read, Append, Append To (organization). No other role for now |
| 27 | Arabic | **Yes** (ar-SA, existing glossary) |
| 28 | Solution | **New patch**: *AlSanidi \| Marketing \| Daily & Monthly Insights* |
| 29 | Live check | **A temporary test flow in UAT**, deleted afterwards (§3.6 step 2) |
| 30 | Approvals in UAT | **One approval for the whole UAT build**; a report after each step |
| 31 | Production | **A separate request** after you confirm UAT |
| 32 | Existing lifetime insights | **Unchanged**: lifetime *Get … Insights* flows, lifetime columns and the cost roll-up (their schedule is part of §5) |

---

## 1. Feasibility study (official API documentation)

### 1.1 Daily statistics: all 4 platforms provide them

| Platform | Daily statistics? | How you ask for one row per day | Levels with daily data |
|---|---|---|---|
| **Meta** (Graph API v26.0) | **Yes** | Insights edge with `time_increment=1` ("number of days from 1 to 90") and `time_range`, `level` = campaign / adset / ad | Campaign, Ad set, Ad |
| **Snap** (Marketing API v1) | **Yes** | Stats endpoints with `granularity=DAY`, `start_time` / `end_time` on the ad account's day boundaries | Campaign, Ad squad, Ad |
| **TikTok** (API for Business v1.3) | **Yes** | `/report/integrated/get/` with `stat_time_day` in `dimensions`, `data_level` = AUCTION_CAMPAIGN / ADGROUP / AD | Campaign, Ad group, Ad |
| **Google Ads** (API v25) | **Yes** | GAQL with `segments.date` in the SELECT and a finite date range in the WHERE | Campaign, Ad group, Ad, Asset group (`date` is a selectable segment for `asset_group`) |

### 1.2 Monthly statistics from the source: all 4 platforms provide them

The platform calculates the month total itself, so unique metrics (reach, uniques, frequency) are real monthly values.

| Platform | Month (or month-to-date) in one request | Monthly unit? | Unique metrics for the month |
|---|---|---|---|
| **Meta** | `time_range` = 1st of the month → today, or `date_preset=this_month` / `last_month`; `time_increment=monthly` gives "one result set for each calendar month" | **Yes** (`time_increment=monthly`) | Reach / frequency for the period requested |
| **Snap** | `granularity=TOTAL` with `start_time` = 1st of the month 00:00 and `end_time` = a day boundary, ad account time zone | No MONTH granularity; TOTAL over the month gives the month | `uniques` / `frequency` allowed with TOTAL (not with HOUR) |
| **TikTok** | `/report/integrated/get/` with only the ID dimension (no `stat_time_day`), `start_date` = 1st of the month, `end_date` = today: one total per item | No month dimension (only `stat_time_day` / `stat_time_hour`); a range without a time dimension gives the month | `reach` = "unique users who saw your ads at least once"; `frequency` "over a given time period" |
| **Google Ads** | `segments.date DURING THIS_MONTH` / `LAST_MONTH`, or `segments.month` | **Yes** (`segments.month`) | None in our metric set |

### 1.3 Limits that shape the design

| | Meta | Snap | TikTok | Google Ads |
|---|---|---|---|---|
| Max range per daily request | `time_increment` 1, range up to 37 months | **31 days** (DAY, synchronous); async requests have no cap | **30 days** with `stat_time_day` | No cap (finite range required) |
| Max range per monthly request | 37 months | No cap stated for TOTAL | **365 days** without a time dimension | No cap |
| How far back | **37 months** | Async reports from 2013-01-01 | Not stated | Daily **37 months** (since 1 June 2026); monthly **11 years** |
| Day boundary | Ad account time zone | Ad account time zone | Ad account time zone | Account time zone |
| When a day stops changing | "do not change after **28 days**" | "finalized **48 hours** after the end of the day"; conversions can still change | Not stated (observed in the live check) | Conversions arrive for the conversion window (up to **90 days**) |
| Deleted / archived items | Returned only with an `ad.effective_status` filter (DELETED / ARCHIVED) or by ID | Returned by ID | Left out by default (`campaign_status` / `adgroup_status` / `ad_status` = `STATUS_NOT_DELETE`); returned with `STATUS_ALL` | Returned (REMOVED status) |
| Money | Account currency | **Micro-currency** (÷ 1,000,000) | Account currency | Micros (connector converts) |
| Response size | Paged | ≤ 200 entities per page; very large synchronous responses are rejected (E9001) → async | Paged (1,000 per page) | Paged |

What this means for the design:
1. **Refresh windows.** Recent days and months keep changing, so runs reload a window, not just the last day. The daily
   window (2–3 days) is set in §5; the previous month is reloaded for 28 days (Google Ads 90).
2. **Chunking.** Daily loads are split into 30-day windows (TikTok's limit, under Snap's 31). Monthly loads are one
   request per month.
3. **Date-only columns.** Day and month are the platform's account-time-zone dates, stored as *Date Only* so they never
   shift with the user's time zone.
4. **Unique metrics** (reach, uniques, frequency) are kept per day and per month as the platform sends them. They must
   never be summed across days or months.
5. **Rates** (CTR, CPC, CPM, ROAS…) are kept as sent. Totals over a period must be recalculated from the counts.

### 1.4 Metrics (all of today's lifetime metrics, on both daily and monthly tables)

| Platform | Columns per level |
|---|---|
| Meta | 28 (campaign / ad set / ad), including the values taken from `actions` (purchases, landing page views…) |
| Snap | 29 |
| Google Ads | 28 campaign, 27 ad group, 23 ad, 18 asset group |
| TikTok | 198 (the 204 agreed metrics minus the ones TikTok refuses) |

### 1.5 Connectors

| Connector | Daily and monthly: change |
|---|---|
| **Google Ads** `sanidi_googleads` | **None.** `GetPerformance` already has `granularity = DAILY / MONTHLY`, `start_date` / `end_date` and `THIS_MONTH` / `LAST_MONTH`, for all 4 levels. |
| **Snap** `sanidi_snap` | Decision 19 (B): add `breakdown` to `GetAdAccountStats`, plus `limit` / paging. See the explanation below. |
| **TikTok** `sanidi_tiktok` | New action **`GetPeriodInsights`**: the same as `GetLifetimeInsights` (metric chunks of 50, merged rows) with a *period* input. Day uses `stat_time_day` and ≤ 30-day ranges; month uses no time dimension, one request per month. The status filters are set to `STATUS_ALL`. |
| **Meta** `sanidi_meta` | Exported to `connectors/meta-ads/` first. New action **`GetPeriodInsights`**: `GET /act_{account_id}/insights` with `level`, `time_range`, `time_increment` (1 or `monthly`), and `filtering` on `ad.effective_status` including DELETED / ARCHIVED, all pages. |

**Snap: what decision 19 means.** Snap reports statistics per object: you ask an ad account, a campaign, an ad squad or
an ad for its stats. The `breakdown` parameter makes one request return the stats of that object's children too. The
official docs allow these combinations:

| Request on | `breakdown=campaign` | `breakdown=adsquad` | `breakdown=ad` |
|---|---|---|---|
| Ad account | **Yes** (only here) | No | **Yes** |
| Campaign | No | **Yes** (only here) | **Yes** |

- **Today's connector (option A)** only has `breakdown` on the campaign request. Every level therefore costs one request
  **per campaign** (192 campaigns today), per period window: about 192 requests for campaigns, 192 for ad squads and
  192 for ads.
- **Option B (agreed)** adds `breakdown` to the ad account request:
  - Campaigns: **1 request per ad account**.
  - Ads: **1 request per ad account**.
  - Ad squads: still **1 request per campaign**, because Snap only gives the ad squad breakdown on the campaign request.
- Large account-level pages are paged (≤ 200 per page). If Snap rejects a page as too large (E9001), the connector
  switches to Snap's async report for that request.

---

## 2. Option comparison (decided: separate tables)

| | One table for everything | **13 tables per period (chosen)** |
|---|---|---|
| Columns | ~280 metrics + ~110 currency base columns + 13 lookups; a Meta row uses ~30 | Each table only its own 18–198 metrics + 1 lookup |
| Fidelity | Mixed platform metrics | Same columns and names as the parent's Insights tab |
| Cross-platform reporting | In the app | In Power BI |
| Maintenance | Shared table for every change | Same pattern and scripts as the 13 synced tables |

Daily and monthly are kept in separate tables, so a report can never add monthly rows to daily rows.

---

## 3. Build plan (UAT; one approval for the whole build, a report after each step)

### 3.1 Tables (26)

| Parent table | Daily table | Monthly table |
|---|---|---|
| `sanidi_metacampaign` | `sanidi_metacampaigndailyinsight` | `sanidi_metacampaignmonthlyinsight` |
| `sanidi_metaadset` | `sanidi_metaadsetdailyinsight` | `sanidi_metaadsetmonthlyinsight` |
| `sanidi_metaadvertisement` | `sanidi_metaadvertisementdailyinsight` | `sanidi_metaadvertisementmonthlyinsight` |
| `sanidi_snapcampaign` | `sanidi_snapcampaigndailyinsight` | `sanidi_snapcampaignmonthlyinsight` |
| `sanidi_snapadsquad` | `sanidi_snapadsquaddailyinsight` | `sanidi_snapadsquadmonthlyinsight` |
| `sanidi_snapadvertisement` | `sanidi_snapadvertisementdailyinsight` | `sanidi_snapadvertisementmonthlyinsight` |
| `sanidi_googleadscampaign` | `sanidi_googleadscampaigndailyinsight` | `sanidi_googleadscampaignmonthlyinsight` |
| `sanidi_googleadsadgroup` | `sanidi_googleadsadgroupdailyinsight` | `sanidi_googleadsadgroupmonthlyinsight` |
| `sanidi_googleadsadvertisement` | `sanidi_googleadsadvertisementdailyinsight` | `sanidi_googleadsadvertisementmonthlyinsight` |
| `sanidi_googleadsassetgroup` | `sanidi_googleadsassetgroupdailyinsight` | `sanidi_googleadsassetgroupmonthlyinsight` |
| `sanidi_tiktokcampaign` | `sanidi_tiktokcampaigndailyinsight` | `sanidi_tiktokcampaignmonthlyinsight` |
| `sanidi_tiktokadgroup` | `sanidi_tiktokadgroupdailyinsight` | `sanidi_tiktokadgroupmonthlyinsight` |
| `sanidi_tiktokadvertisement` | `sanidi_tiktokadvertisementdailyinsight` | `sanidi_tiktokadvertisementmonthlyinsight` |

Display names follow the parent: *Meta Campaign Daily Insight* / *Meta Campaign Monthly Insight*, and so on. The
longest logical name, `sanidi_googleadsadvertisementmonthlyinsight`, is 43 characters, under Dataverse's limit of 50.

Every table:
- User-owned, currency-enabled, in the patch.
- **Name** (primary): `<item name> · YYYY-MM-DD` (daily) / `<item name> · YYYY-MM` (monthly).
- **Date** (`sanidi_date`, Date Only; for monthly tables it is the 1st of the month).
- **Platform ID**: the campaign / ad set / … ID, as text.
- **Insight Key** (`<platform ID>_<YYYYMMDD>` / `<platform ID>_<YYYYMM>`) with an **alternate key**, so every write
  is an upsert and a period is never duplicated.
- The parent lookup (cascade **Remove Link**, like the existing lookups).
- All the parent's insight columns: same logical names, labels, types and choices.
- **Period Complete** (Yes/No): No for today's partial day / the running month; Yes once the period is over.
- **No Data** (Yes/No): Yes on a month row created without platform data (decision 13).
- **Last Synced On**, **Raw Payload**.

Forms and views:
- Main form "Information": General (Name, parent lookup, Date, Platform ID, Period Complete, No Data), the parent's
  Insights sections, and Sync (Last Synced On, Raw Payload).
- Views: **Active** (default, newest first), **Inactive**.
- Each parent form gets **Daily Insights** and **Monthly Insights** subgrids (newest first) in its Insights tab.
- Not in the site map, no charts (decisions 24, 25). The tables are added to the app so the subgrids and forms open.
- Manager role: Read, Append, Append To (organization).

### 3.2 Flows

Two flows per platform, in the patch, with stored connections and a Respond step (needed to run them from Sync Control):

| Flow | Does |
|---|---|
| **Get \<Platform\> Daily Insights** | Daily rows for a date range (all levels) |
| **Get \<Platform\> Monthly Insights** | Monthly rows for a month range (all levels) |

Each flow:
1. Gets its range from its inputs (set by the scheduler, a Sync Control button or the full load, see §5).
2. For each ad account and level, calls the platform once per window (daily: ≤ 30 days; monthly: one month), see §1.5.
3. **Driver:** lists that level's records from the synced table (active and inactive, platform ID not empty) and keeps
   only report rows whose ID matches. Rows for items not in Dataverse are skipped and counted.
4. Upserts each row by Insight Key, binding the parent lookup and setting Period Complete.
5. Monthly only: creates the empty month rows (decision 13, details in §6).
6. Responds with counts per level: written, empty months created, skipped, errors.

The lifetime *Get … Insights* flows and the cost roll-up are not changed (decision 32).

### 3.3 Sync Control

- Two new sync types: **Daily Insights** and **Monthly Insights**, each with its own button per platform card. The
  dispatcher flow gets the matching cases (8 new child-flow cases), and the page is updated.
- **Full load** button and its configuration on the Integration Platform row (decision 21, details in §6 Q4).
- What each button reloads is set in §5.

### 3.4 Arabic (ar-SA)

Same process and glossary as `translations/AlSanidiMarketing/`: the 26 tables, their columns, forms, views, flows, new
Sync Control texts and any new environment variables.

### 3.5 Execution order

| # | Step | Where |
|---|---|---|
| 1 | `daily-insights/spec.py`: the 26 tables, columns copied from the parents' insight columns (live metadata), keys, forms, views | repo |
| 2 | **Live check:** a temporary test flow in UAT runs one daily and one monthly request per platform and level (read-only API calls). Confirms the fields, deleted items, Google asset-group daily rows, Snap breakdowns and real row counts. The flow is deleted afterwards. | UAT |
| 3 | Connectors: export Meta to the repo; `GetPeriodInsights` for Meta and TikTok; Snap account-level breakdown | repo, then UAT |
| 4 | New patch; 26 tables + columns + alternate keys + lookups, publish | UAT |
| 5 | Forms, views, parent subgrids, app tables, Manager role, publish | UAT |
| 6 | 8 flows + the scheduling pieces from §5 (off) | UAT |
| 7 | Test: one week and one month per platform; check the rows against the platforms' own UIs | UAT |
| 8 | Full load (daily and monthly), then the scheduler on | UAT |
| 9 | Sync Control (buttons, full load configuration) and Arabic translations | UAT |
| — | Production: a separate request after you confirm UAT (decision 31) | Production |

---

## 4. Volume

The 13 tables hold 3,669 items today: Meta 218, Snap 1,387, Google Ads 313, TikTok 1,751.
- **Daily:** a row only for an item that delivered on that day, so at most 3,669 rows a day and in practice far fewer.
- **Monthly:** a row for each item and month, including empty months (decision 13). The real counts come out of the
  live check and Q1 in §6.

---

## 5. Scheduling (to be designed next)

Covers every sync, not just the new ones:
- **Data**: campaigns → ad sets / ad squads / ad groups / asset groups → ads.
- **Lifetime insights** in the 13 main tables.
- **Daily insights**: the 2–3 day window, today's partial day.
- **Monthly insights**: month to date, the previous month for 28 days (Google Ads 90).
- The Google Ads weekly 90-day reload.
- The **full load** per environment.
- What each Sync Control button reloads, how runs avoid overlapping, and who is notified.

---

## 6. Open points (to confirm before the build)

| # | Question |
|---|---|
| Q1 | **Empty months: which months get a row for an item?** Proposal: every month from the month of the item's start (its platform start or create date) to the current month. If the item has an end date, the months after the end month get no row. |
| Q2 | **Empty months: blank or zero?** Proposal: metric columns stay **blank**, and **No Data** = Yes, so "no data from the platform" can be told apart from a real 0. |
| Q3 | **Empty days:** days with no activity get **no** daily row (only months get empty rows). Confirm. |
| Q4 | **Full-load button:** proposal: a **Full Load From** date (and an optional **Full Load To** date, empty = today) on the platform's Integration Platform row. The button loads daily and monthly insights for that range. Empty From = from the platform's maximum history (Meta 37 months; Google Ads 37 months daily, 11 years monthly; Snap and TikTok from each item's start). Confirm, or tell me what "to a certain date" should mean. |

---

## Sources (official documentation)

- Meta: [Ad Account Insights reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/)
  (`time_increment` incl. `monthly`, `level`, `time_range`, `date_preset` incl. `this_month` / `last_month`, 37 months),
  [Insights API](https://developers.facebook.com/docs/marketing-api/insights/) (deleted / archived objects),
  [Limits and best practices](https://developers.facebook.com/docs/marketing-api/insights/best-practices/) (stable after
  28 days, rate limits)
- Snap: [Measurement](https://developers.snap.com/api/marketing-api/Ads-API/measurement) (DAY 31-day limit, day
  boundaries, finalized after 48 hours, TOTAL with start / end, uniques not at HOUR, `breakdown` per endpoint, 200 per
  page, E9001, async)
- TikTok: [Run a synchronous report](https://business-api.tiktok.com/portal/docs/run-a-synchronous-report/v1.3)
  (`stat_time_day`, 30-day limit, 365 days without a time dimension, `query_lifetime`),
  [Basic reports: supported dimensions](https://business-api.tiktok.com/portal/docs?id=1751443956638721) (time
  dimensions, `STATUS_NOT_DELETE` default),
  [Basic reports: supported metrics](https://business-api.tiktok.com/portal/docs?id=1751443967255553) (reach, frequency)
- Google Ads: [Segmentation](https://developers.google.com/google-ads/api/docs/reporting/segmentation),
  [Date ranges](https://developers.google.com/google-ads/api/docs/query/date-ranges) (THIS_MONTH / LAST_MONTH,
  `segments.month`, 37 months daily, 11 years monthly),
  [Data retention policy, 1 June 2026](https://ads-developers.googleblog.com/2026/05/new-data-retention-policy-for-google.html),
  [asset_group fields](https://developers.google.com/google-ads/api/fields/v26/asset_group) (`date` segment selectable),
  [Conversion window](https://support.google.com/google-ads/answer/3123169) (up to 90 days)
