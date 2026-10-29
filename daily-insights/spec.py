"""Source of truth for the Social Media Daily and Monthly Insights tables (see PLAN.md).

Every synced table (the 13 "parents") gets a daily and a monthly insight table. Their metric columns are copied from
the parent's insight columns: same logical name, label, type, precision, choices and description. The parent's
columns were read from UAT into parent_insight_columns.json (the columns the lifetime "Get <Platform> Insights" flows
write); rebuild that file with snapshot_parent_columns.py if a parent's insight columns change.

  python3 spec.py        # checks the spec and prints a summary
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
PREFIX = "sanidi_"
SOLUTION = "AlSanidiMarketing_Patch_DailyMonthlyInsights"  # created by deploy_tables.py (see PATCH)
PATCH = {"uniquename": SOLUTION, "displayname": "AlSanidi | Marketing | Daily & Monthly Insights",
         "parent": "AlSanidiMarketing", "version": "1.0.3.0"}

# Parent columns written by the lifetime insights flows that are sync bookkeeping, not metrics.
NOT_METRICS = {"sanidi_datestart", "sanidi_datestop", "sanidi_insightslastsyncedon", "sanidi_statslastsynced"}

PLATFORMS = {
    "meta": {"display": "Meta", "order": 1},
    "snap": {"display": "Snap", "order": 2},
    "google": {"display": "Google Ads", "order": 3},
    "tiktok": {"display": "TikTok", "order": 4},
}

# The 13 synced tables. id = the platform ID column; account = the ad account column;
# start / end = date columns used for the empty month rows (first non-empty wins; "@parent" = the parent's dates);
# level = the level name the connectors use; parent_lookup = the lookup to the next level up (for "@parent").
PARENTS = {
    "metacampaign": dict(platform="meta", display="Meta Campaign", set="sanidi_metacampaigns",
                         id="sanidi_campaignid", name="sanidi_campaignname", account="sanidi_accountid",
                         start=["sanidi_starttime", "sanidi_createdtime"], end=[], level="campaign"),
    "metaadset": dict(platform="meta", display="Meta Ad Set", set="sanidi_metaadsets",
                      id="sanidi_adsetid", name="sanidi_adsetname", account="sanidi_accountid",
                      start=["sanidi_starttime", "sanidi_createdtime"], end=["sanidi_endtime"], level="adset"),
    "metaadvertisement": dict(platform="meta", display="Meta Advertisement", set="sanidi_metaadvertisements",
                              id="sanidi_advertisementid", name="sanidi_advertisementname",
                              account="sanidi_accountid", start=["sanidi_createdtime"], end=[], level="ad"),
    "snapcampaign": dict(platform="snap", display="Snap Campaign", set="sanidi_snapcampaigns",
                         id="sanidi_campaignid", name="sanidi_campaignname", account="sanidi_adaccountid",
                         start=["sanidi_starttime", "sanidi_createdat"], end=["sanidi_endtime"], level="campaign"),
    "snapadsquad": dict(platform="snap", display="Snap Ad Squad", set="sanidi_snapadsquads",
                        id="sanidi_adsquadid", name="sanidi_adsquadname", account=None,
                        start=["sanidi_starttime", "sanidi_createdat"], end=["sanidi_endtime"], level="adsquad"),
    "snapadvertisement": dict(platform="snap", display="Snap Advertisement", set="sanidi_snapadvertisements",
                              id="sanidi_adid", name="sanidi_adname", account=None,
                              start=["sanidi_starttime", "sanidi_createdat"], end=["sanidi_endtime"], level="ad"),
    "googleadscampaign": dict(platform="google", display="Google Ads Campaign", set="sanidi_googleadscampaigns",
                              id="sanidi_campaignid", name="sanidi_campaignname", account="sanidi_customerid",
                              start=["sanidi_startdatetime"], end=["sanidi_enddatetime"], level="campaign"),
    "googleadsadgroup": dict(platform="google", display="Google Ads Ad Group", set="sanidi_googleadsadgroups",
                             id="sanidi_adgroupid", name="sanidi_adgroupname", account="sanidi_customerid",
                             start=["@parent"], end=["@parent"], parent_lookup="sanidi_googleadscampaign",
                             parent="googleadscampaign", level="ad_group"),
    "googleadsadvertisement": dict(platform="google", display="Google Ads Advertisement",
                                   set="sanidi_googleadsadvertisements", id="sanidi_adid", name="sanidi_adname",
                                   account="sanidi_customerid", start=["sanidi_startdatetime"],
                                   end=["sanidi_enddatetime"], level="ad"),
    "googleadsassetgroup": dict(platform="google", display="Google Ads Asset Group",
                                set="sanidi_googleadsassetgroups", id="sanidi_assetgroupid",
                                name="sanidi_assetgroupname", account="sanidi_customerid", start=["@parent"],
                                end=["@parent"], parent_lookup="sanidi_googleadscampaign",
                                parent="googleadscampaign", level="asset_group"),
    "tiktokcampaign": dict(platform="tiktok", display="TikTok Campaign", set="sanidi_tiktokcampaigns",
                           id="sanidi_campaignid", name="sanidi_campaignname", account="sanidi_advertiserid",
                           start=["sanidi_createtime"], end=[], level="campaign"),
    "tiktokadgroup": dict(platform="tiktok", display="TikTok Ad Group", set="sanidi_tiktokadgroups",
                          id="sanidi_adgroupid", name="sanidi_adgroupname", account="sanidi_advertiserid",
                          start=["sanidi_schedulestarttime", "sanidi_createtime"], end=["sanidi_scheduleendtime"],
                          level="adgroup"),
    "tiktokadvertisement": dict(platform="tiktok", display="TikTok Advertisement",
                                set="sanidi_tiktokadvertisements", id="sanidi_adid", name="sanidi_adname",
                                account="sanidi_advertiserid", start=["sanidi_createtime"], end=[], level="ad"),
}

# Main insight fields per platform, shown first in the Active views (after Name, parent, Date).
VIEW_METRICS = {
    "meta": ["sanidi_spend", "sanidi_impressions", "sanidi_reach", "sanidi_clicks", "sanidi_ctr", "sanidi_cpc",
             "sanidi_purchases", "sanidi_purchasevalue", "sanidi_purchaseroas"],
    "snap": ["sanidi_spend", "sanidi_impressions", "sanidi_reach", "sanidi_swipes", "sanidi_swiperate",
             "sanidi_purchases", "sanidi_purchasevalue", "sanidi_roas"],
    "google": ["sanidi_cost", "sanidi_impressions", "sanidi_clicks", "sanidi_ctr", "sanidi_averagecpc",
               "sanidi_conversions", "sanidi_conversionsvalue"],
    "tiktok": ["sanidi_spend", "sanidi_impressions", "sanidi_reach", "sanidi_clicks", "sanidi_ctr", "sanidi_cpc",
               "sanidi_conversion", "sanidi_costperconversion"],
}

# Global choices shared by all 26 tables. Values start at 1.
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
GLOBAL_CHOICES = {
    "sanidi_month": ("Month", "Calendar month (1 = January).", MONTHS),
    "sanidi_weekday": ("Weekday", "Day of the week (1 = Sunday).", WEEKDAYS),
}

# Arabic labels of the global choices and common columns (the rest goes through the translation tool).
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر",
             "ديسمبر"]
WEEKDAYS_AR = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]


def parent_columns():
    return json.loads((HERE / "parent_insight_columns.json").read_text())


def metric_columns(parent):
    """The parent's insight columns copied to its daily / monthly tables (sync bookkeeping left out)."""
    return [c for c in parent_columns()[PREFIX + parent] if c["name"] not in NOT_METRICS]


def common_columns(period):
    """(logical name, label, kind, description) of the columns every insight table has, in form order."""
    daily = period == "daily"
    cols = [
        ("sanidi_platformid", "Platform ID", "text100",
         "ID of the campaign / ad set / ad squad / ad group / asset group / ad on the platform."),
        ("sanidi_date", "Date", "dateonly",
         "The day of the statistics (ad account time zone)." if daily else
         "First day of the month of the statistics (ad account time zone)."),
    ]
    if daily:
        cols.append(("sanidi_day", "Day", "day", "Day of the month (1-31)."))
    cols.append(("sanidi_month", "Month", "month", "Month of the statistics (1 = January)."))
    cols.append(("sanidi_year", "Year", "year", "Year of the statistics."))
    if daily:
        cols.append(("sanidi_weekday", "Weekday", "weekday", "Day of the week (1 = Sunday)."))
    cols += [
        ("sanidi_periodclosed", "Period Closed", "bool",
         "Yes when the " + ("day" if daily else "month") + " is over and was refreshed after it ended. "
         "The platform can still adjust older numbers (conversions, attribution); the weekly reload picks that up."),
        ("sanidi_nodata", "No Data", "bool",
         "Yes when the platform returned no statistics for this " + ("day." if daily else "month: the row only "
                                                                     "exists so the month is not missing in reports.")),
        ("sanidi_insightkey", "Insight Key", "text150",
         "Unique key: <platform ID>_" + ("YYYYMMDD" if daily else "YYYYMM") + ". Used to update the row."),
        ("sanidi_lastsyncedon", "Last Synced On", "datetime", "When this row was last written by the sync."),
        ("sanidi_rawpayload", "Raw Payload", "memo", "The platform's original row (JSON)."),
    ]
    return cols


def tables():
    """All 26 insight tables: logical name -> definition."""
    out = {}
    for key, p in PARENTS.items():
        for period, word in (("daily", "Daily"), ("monthly", "Monthly")):
            logical = f"{PREFIX}{key}{period}insight"
            out[logical] = {
                "key": key, "period": period, "parent": PREFIX + key, "platform": p["platform"],
                "schema": f"{PREFIX}{key}{period}insight",
                "display": f"{p['display']} {word} Insight", "plural": f"{p['display']} {word} Insights",
                "description": f"{word} statistics of a {p['display']}, as reported by {PLATFORMS[p['platform']]['display']}"
                               + (" for each day." if period == "daily" else " for each month (not summed from days)."),
                "lookup": PREFIX + key,  # lookup column to the parent
                "lookup_display": p["display"],
                "relationship": f"{PREFIX}{key}{period}insight_{key}_{PREFIX}{key}",
                "key_name": f"{PREFIX}{key}{period}insight_insightkey",
                "common": common_columns(period),
                "metrics": metric_columns(key),
            }
    return out


def check():
    t = tables()
    assert len(t) == 26
    for logical, d in t.items():
        assert len(logical) <= 50, logical
        names = [c[0] for c in d["common"]] + [c["name"] for c in d["metrics"]] + [d["lookup"], "sanidi_name"]
        dupes = {n for n in names if names.count(n) > 1}
        assert not dupes, (logical, dupes)
        missing = [m for m in VIEW_METRICS[d["platform"]] if m not in [c["name"] for c in d["metrics"]]]
        assert not missing, (logical, missing)
    return t


if __name__ == "__main__":
    for logical, d in check().items():
        print(f"{logical:45} {d['display']:45} metrics={len(d['metrics']):3} common={len(d['common'])}")
