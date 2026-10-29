# Social Media Daily and Monthly Insights: feasibility study and plan (AlSanidi-UAT)

Status: **plan and scheduling agreed (2026-10-29), waiting for the go-ahead to build in UAT. Nothing has been changed in Dataverse.**
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
| 11 | Today's partial day | **Included**; overwritten by every run until the day is over (§5) |
| 12 | Month to date | **Up to now, today included**; overwritten by every run until the month is over (§5) |
| 13 | Months with no activity | **A month row is created even when there is no data**, so Power BI has no gaps: every month from the item's start month to the current (or end) month, metrics blank, **No Data** = Yes (may change later). Days with no activity get no row (§5.5) |
| 14 | Daily history | **One full load per environment** (Sync Control *Update All Time*, from **Full Load From**), then the scheduler |
| 15 | Monthly history | Same as 14 |
| 16 | Daily refresh window | **3 days** at 05:00 (today, yesterday, the day before); today only at 08:00 / 12:00 / 16:00; last 28 days (Google Ads 90) on Fridays (§5) |
| 17 | Previous month refresh | Reloaded every Friday (with the current month) until it is closed on the current month's last Friday; Google Ads reloads every month its 90 days touch (§5) |
| 18 | Schedule | **05:00** daily (data + all insights), **08:00 / 12:00 / 16:00** (lifetime, today, current month), **Friday** reloads, last Friday closes the previous month (§5) |
| 19 | Snap calls | **Option B**: add account-level calls to the Snap connector where Snap allows them (§1.3, explained) |
| 20 | Meta connector | **Exported to the repo** (`connectors/meta-ads/`) before it is changed |
| 21 | Sync Control | **3 buttons** per platform: *Data* (existing), *Update Day & Month to Date* (replaces *Insights*), *Update All Time* with an *Insights Only* / *Data and Insights* pop-up and **Full Load From** on the Integration Platform row (§3.3) |
| 22 | Notifications | **Nobody** for scheduled runs; the person who pressed the button for Sync Control runs (as today) |
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
| 33 | Child data flow triggers | **Limited to the data columns**, so insights updates no longer start a data re-sync (§3.2) |
| 34 | 05:00 order | Data → wait for the cascade (max 30 min) → lifetime → daily → monthly; platforms in parallel (§5.2) |
| 35 | Overlaps | Scheduled runs go through *Integration Sync Request* and the dispatcher; one run per platform at a time (§5.3) |
| 36 | Month change | The 05:00 monthly step covers every month the 3-day window touches (§5.1) |
| 37 | Friday daily reload | Last 28 days (Google Ads 90), so daily rows stay consistent with the monthly ones (§5.1) |
| 38 | Flag name | **Period Closed** (period over and refreshed after it ended; not "final") (§5.4) |
| 39 | Intraday data sync | **None**: items created during the day get insights from the next 05:00 run |
| 40 | Time zones | Each account's own time zone, as the API reports it (§5) |

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
- **Period Closed** (Yes/No): set by the rules in §5.4; never Yes for today or the current month.
- **No Data** (Yes/No): Yes on a month row created without platform data (decision 13).
- **Last Synced On**, **Raw Payload**.

Forms and views:
- Main form "Information": General (Name, parent lookup, Date, Platform ID, Period Closed, No Data), the parent's
  Insights sections, and Sync (Last Synced On, Raw Payload).
- Views: **Active** (default, newest first), **Inactive**.
- Each parent form gets **Daily Insights** and **Monthly Insights** subgrids (newest first) in its Insights tab.
- Not in the site map, no charts (decisions 24, 25). The tables are added to the app so the subgrids and forms open.
- Manager role: Read, Append, Append To (organization).

### 3.2 Flows

**New insight flows** (two per platform), in the patch, with stored connections and a Respond step (needed to run them as
child flows):

| Flow | Does |
|---|---|
| **Get \<Platform\> Daily Insights** | Daily rows for a date range (all levels) |
| **Get \<Platform\> Monthly Insights** | Monthly rows for a list of months (all levels) |

Each one:
1. Gets its range from its inputs, set by the platform's run flow (§5).
2. For each ad account and level, calls the platform once per window (daily: ≤ 30 days; monthly: one month), see §1.5.
3. **Driver:** lists that level's records from the synced table (active and inactive, platform ID not empty) and keeps
   only report rows whose ID matches. Rows for items not in Dataverse are skipped and counted.
4. Upserts each row by Insight Key, binding the parent lookup and setting **Period Closed** with the rules in §5.4.
5. Monthly only: creates the **empty month rows** (§5.5).
6. Responds with counts per level: written, empty months created, skipped, errors.

**Run flows** (one per platform), **\<Platform\> - Run Sync** (instant, child flow): run the steps of a sync request in
order (Data, wait for the data cascade, Lifetime, Daily, Monthly). See §5.2.

**Scheduler flow**, **Social Media - Scheduled Sync** (recurrence): creates the scheduled sync requests. See §5.1.

**Changed existing flows:**
- **Sync Control - Run Sync Request** (dispatcher): new sync types go to the platform's *Run Sync* flow (4 new cases),
  and the waiting / skipping rule in §5.3.
- **The 9 child data flows** (Get Meta AdSets / Advertisements, Get Snap Ad Squads / Advertisements, Get Google Ads Ad
  Groups / Advertisements / Asset Groups, Get TikTok Ad Groups / Advertisements): their trigger is limited to the columns
  only the data flows write (suggestion 1). The data sync still cascades as today, but lifetime insights updates no
  longer start a data re-sync. The exact columns per flow are listed in `spec.py` before the change.
  - Why: today the trigger fires on any change of the parent row. Since 15 October in UAT, Get Snap Advertisements ran
    7,439 times and Map Snap Advertisement Spend 12,323 times, against 15 Snap Campaigns / Insights runs.

The lifetime *Get … Insights* flows, their columns and the cost roll-up are not changed (decision 32).

### 3.3 Sync Control

Each platform card has **3 buttons** (decision Q5):

| Button | Sync type | Runs |
|---|---|---|
| **Data** | Data (existing, unchanged) | Get \<Platform\> Campaigns, then the cascade |
| **Update Day & Month to Date** | *Day & Month to Date* (new) | Lifetime → daily (day before yesterday, yesterday, today) → monthly (every month those 3 days touch). No data. Replaces the existing **Insights** button. |
| **Update All Time** | *All Time* (new) | A pop-up asks **Insights Only** or **Data and Insights**. Then (Data and wait if chosen) → lifetime → daily from **Full Load From** to today → monthly from that month to the current month. |

Changes:
- **Integration Platform**: new column **Full Load From** (Date Only). Empty = each platform's maximum history: Meta 37
  months; Google Ads 37 months for daily, 11 years for monthly; Snap and TikTok from each item's start.
- **Integration Sync Request**:
  - Sync Type gets new values: *Day & Month to Date*, *All Time*, *Scheduled Daily (05:00)*, *Scheduled Intraday*.
    The existing *Insights* value is kept for the history rows; the page no longer creates it.
  - New columns: **Include Data** (Yes/No, the pop-up's answer), **Triggered By** (Button / Schedule), **Weekly Run**
    (Yes on Friday's 05:00 run), **Close Previous Month** (Yes on the last Friday of the month), **Steps Log** (text:
    counts and timing per step).
  - Status gets a new value: **Skipped** (§5.3).
- **Page** (`sync-control.tsx`): the 3 buttons, the pop-up, and scheduled runs shown on the cards like button runs.
  Notifications are unchanged: only the person who pressed a button is notified (decision 22).

### 3.4 Arabic (ar-SA)

Same process and glossary as `translations/AlSanidiMarketing/`: the 26 tables, their columns, forms and views, the new
flows, the new Sync Control columns, choice values, buttons and pop-up texts.

### 3.5 Execution order

| # | Step | Where |
|---|---|---|
| 1 | `daily-insights/spec.py`: the 26 tables, columns copied from the parents' insight columns (live metadata), keys, forms, views; the 9 trigger column lists | repo |
| 2 | **Live check:** a temporary test flow in UAT runs one daily and one monthly request per platform and level (read-only API calls). Confirms the fields, deleted items, Google asset-group daily rows, Snap breakdowns, Meta / Snap account time zones and real row counts. Deleted afterwards. | UAT |
| 3 | Connectors: export Meta to the repo; `GetPeriodInsights` for Meta and TikTok; Snap account-level breakdown | repo, then UAT |
| 4 | New patch; 26 tables + columns + alternate keys + lookups, publish | UAT |
| 5 | Forms, views, parent subgrids, app tables, Manager role, publish | UAT |
| 6 | 8 insight flows, 4 run flows (off) | UAT |
| 7 | Test: one week and one month per platform, through the run flows; check the rows against the platforms' own UIs | UAT |
| 8 | Sync Control: new columns and choice values, dispatcher cases, page (3 buttons, pop-up) | UAT |
| 9 | Trigger columns on the 9 child data flows; check that a Data sync still cascades and an Insights run doesn't | UAT |
| 10 | Full load per platform (**Update All Time**, Data and Insights) | UAT |
| 11 | Scheduler flow on | UAT |
| 12 | Arabic translations | UAT |
| — | Production: a separate request after you confirm UAT (decision 31) | Production |

---

## 4. Volume and duration

The 13 tables hold 3,669 items today: Meta 218, Snap 1,387, Google Ads 313, TikTok 1,751.
- **Daily:** a row only for an item that delivered on that day, so at most 3,669 rows a day and in practice far fewer.
- **Monthly:** a row for each item and month from the item's start, including empty months.
- Today's runs in UAT (successful runs since 15 October, median): Get Snap Insights ≈ 9 min, Get TikTok Insights ≈ 8
  min, Get Meta / Google Ads Insights ≈ 1 min; Get Snap Campaigns ≈ 4 min; each child data flow a few seconds to
  minutes. A 05:00 run should finish well before 08:00. The live check and step 7 give the real figures for the new
  flows.

---

## 5. Scheduling (agreed)

All times are Riyadh time. "Today" and every date in a request are in the ad account's time zone (Google Ads and
TikTok accounts are Asia/Riyadh; Meta and Snap are confirmed in the live check). The 4 platforms run in parallel; the
steps of one platform run one after the other.

### 5.1 When

| When | Steps per platform |
|---|---|
| **Every day 05:00** | 1. **Data** (campaigns → cascade), then wait for the cascade (§5.2). 2. **Lifetime** insights on the main tables. 3. **Daily**: today (partial), yesterday, the day before yesterday; the day before yesterday gets Period Closed. 4. **Monthly**: every month those 3 days touch (normally the current month; on the 1st and 2nd also the previous month). |
| **+ on Fridays (05:00 run)** | 5. **Daily** reload of the last **28 days** (Google Ads: **90 days**). 6. **Monthly** reload of the current and previous month (Google Ads: every month the 90 days touch). |
| **+ on the last Friday of the month** | 7. The **previous month** gets Period Closed (after step 6 reloaded it). Example: September is closed on Friday 30 October. |
| **08:00, 12:00, 16:00** | **Lifetime** insights; **daily**: today (partial); **monthly**: the current month. No data sync. |

The scheduler flow runs at 05:00, 08:00, 12:00 and 16:00. For each platform with *Set Up* = Yes and *Connection
Active* not No, it creates one *Integration Sync Request* (Triggered By = Schedule; Weekly Run / Close Previous Month
set on Fridays). The dispatcher runs it like a button press.

### 5.2 Order inside one run (\<Platform\> - Run Sync)

1. **Data** (05:00 run; *All Time* with *Data and Insights*): runs Get \<Platform\> Campaigns. The ad set / ad squad /
   ad group / asset group and ad flows then run on their own, so the run **waits** until none of that platform's child
   data flows has a run in progress (checked every 2 minutes, two quiet checks in a row, at most 30 minutes). After 30
   minutes it continues and writes a warning in Steps Log.
2. **Lifetime**: runs Get \<Platform\> Insights (unchanged flow).
3. **Daily**: runs Get \<Platform\> Daily Insights with the date range.
4. **Monthly**: runs Get \<Platform\> Monthly Insights with the months.
5. Writes Steps Log and the request status. A failed step is recorded and the run continues with the next step; the
   request ends **Failed** if any step failed.

### 5.3 No overlaps

- One run per platform at a time. When a request arrives while the same platform has one *Running*:
  - **Scheduled** request: waits for it (up to 60 minutes), then is marked **Skipped**. The next scheduled run covers
    the same periods again.
  - **Button**: not possible; the page disables the platform's buttons while a sync runs (as today).
- Different platforms never block each other.

### 5.4 Period Closed

The same rules everywhere (scheduler and buttons):
- **Day**: closed when it is the day before yesterday or older.
- **Month**: closed when it is older than the previous month; the **previous month** is closed once the current month's
  last Friday has come (the scheduler closes it on that Friday; a button run after that date closes it too).
- Today and the current month are never closed.
- Closed means the period is over and was refreshed after it ended. The platforms can still change older numbers
  (Meta up to 28 days, Google Ads conversions up to 90 days), which the Friday reloads pick up.

### 5.5 Empty month rows

- Every item in the 13 tables gets a row for **every month from its start month** (its platform start or create date)
  **to the current month**; for an item with an end date, up to its end month.
- A month the platform returns nothing for gets a row with **blank** metrics and **No Data** = Yes.
- Days with no activity get no daily row.

### 5.6 What each sync type covers

| Sync type | Data | Lifetime | Daily | Monthly | Closes |
|---|---|---|---|---|---|
| Scheduled Daily (05:00) | Yes | Yes | D-2 … today | Months of D-2 … today | Day D-2 |
| + Weekly (Friday) | | | + last 28 days (Google Ads 90) | + current and previous month (Google Ads: months of the 90 days) | + previous month on the last Friday |
| Scheduled Intraday (08/12/16) | No | Yes | Today | Current month | Nothing |
| Day & Month to Date (button) | No | Yes | D-2 … today | Months of D-2 … today | Per §5.4 |
| All Time (button) | Pop-up choice | Yes | Full Load From … today | Its month … current month | Per §5.4 |

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
