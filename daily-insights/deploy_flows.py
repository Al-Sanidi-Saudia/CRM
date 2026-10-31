"""Builds the Daily & Monthly Insights flows (PLAN.md §3.2, §5) and creates them, turned off, in the patch.

  Get <Platform> Daily Insights     child flow: daily rows for a date range (all levels)
  Get <Platform> Monthly Insights   child flow: monthly rows for a month range (all levels), empty months included
  <Platform> - Run Sync             child flow: runs the steps of one sync request in order (data, wait, lifetime,
                                    daily, monthly) and reports each step
  Social Media - Scheduled Sync     recurrence 05:00 / 08:00 / 12:00 / 16:00 (Riyadh): one sync request per platform

  python3 deploy_flows.py                       # write flows/*.json for review
  python3 deploy_flows.py --apply               # create the flows that don't exist yet (turned off)
  python3 deploy_flows.py --apply --update-existing ["--only=Get TikTok Daily Insights"]

Every insight flow is driven by the synced tables: a platform row is written only when its campaign / ad set /
ad squad / ad group / asset group / ad is in Dataverse (active or inactive); the others are counted as skipped.
Rows are matched on Insight Key (<platform ID>_<YYYYMMDD> / _<YYYYMM>): updated when they exist, created otherwise.
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402

SOLUTION = spec.SOLUTION
NS = uuid.UUID("4f0c9b1e-6a2d-4c8b-9e7f-1d2c3b4a5f60")
TZ = "Arab Standard Time"  # Riyadh: every ad account here reports in Asia/Riyadh (Google Ads, TikTok checked)
ALL = ["Succeeded", "Failed", "TimedOut", "Skipped"]
ROW_CONCURRENCY = 20

API = {
    "dv": ("shared_commondataserviceforapps", None, "sanidi_sharedcommondataserviceforapps_79822"),
    "meta": ("shared_meta-5f43b530b23a0dc933-5f11fd8d7fb3aebb20", "sanidi_meta",
             "sanidi_sharedmeta5f43b530b23a0dc9335f11fd8d7fb3aebb20_26bce"),
    "snap": ("shared_sanidi-5fsnap-5f43b530b23a0dc933", "sanidi_snap", "sanidi_sharedsanidi5fsnap5f43b530b23a0dc933_a4073"),
    "google": ("shared_sanidi-5fgoogle-20ads-5f43b530b23a0dc933", "sanidi_googleads",
               "sanidi_sharedsanidi5fgoogle20ads5f43b530b23a0dc933_ba16b"),
    "tiktok": ("shared_sanidi-5ftiktok-5f43b530b23a0dc933", "sanidi_tiktok",
               "sanidi_sharedsanidi5ftiktok5f43b530b23a0dc933_3e7c1"),
}
ENV = {
    "tiktok": {"TikTok Ads Access Token (sanidi_TikTokAdsAccessToken)": "sanidi_TikTokAdsAccessToken",
               "TikTok Ads Advertiser IDs (sanidi_TikTokAdsAdvertiserIds)": "sanidi_TikTokAdsAdvertiserIds"},
    "google": {"Google Ads Client ID (sanidi_GoogleAdsClientId)": "sanidi_GoogleAdsClientId",
               "Google Ads Client Secret (sanidi_GoogleAdsClientSecret)": "sanidi_GoogleAdsClientSecret",
               "Google Ads Refresh Token (sanidi_GoogleAdsRefreshToken)": "sanidi_GoogleAdsRefreshToken",
               "Google Ads Developer Token (sanidi_GoogleAdsDeveloperToken)": "sanidi_GoogleAdsDeveloperToken",
               "Google Ads Login Customer ID (sanidi_GoogleAdsLoginCustomerId)": "sanidi_GoogleAdsLoginCustomerId",
               "Google Ads Customer ID (sanidi_GoogleAdsCustomerId)": "sanidi_GoogleAdsCustomerId"},
}

# Existing flows the Run Sync flows call or watch (workflow IDs are kept by solution import).
EXISTING = {
    "meta": {"data": "8b6d991c-d3c0-f111-aaaf-70a8a581e673", "lifetime": "e30b9610-07c5-f111-aaaf-70a8a581e5c5",
             "children": ["947c3f10-d3c0-f111-aaaf-70a8a581e673", "957c3f10-d3c0-f111-aaaf-70a8a581e673"]},
    "snap": {"data": "f0adc814-8c13-5fe3-8ba7-9ad697ea4ea2", "lifetime": "028e8be8-505f-5f70-acc7-85653b1f859f",
             "children": ["ddb71436-2f06-50ad-b721-146978286924", "9c0d86ce-7ccd-5b1e-bb13-55921b643dad"]},
    "google": {"data": "b10505e5-822c-5641-8499-e8324198b469", "lifetime": "59399b2c-080a-50b0-afcf-b803145237cf",
               "children": ["3574fbc1-642c-5d29-8757-9521a4b03c8e", "511feda4-57bc-5009-bf26-21dd79bb8fe9",
                            "5f9e257b-5d19-5fe5-9a1e-974434268472"]},
    "tiktok": {"data": "de45712c-6cd1-59ff-8546-26bb91f692f4", "lifetime": "4bcc7027-25a2-51c9-adc4-9c4b5c5ca128",
               "children": ["49f87836-4262-5c77-b470-5c90c1054813", "1c99d003-a774-5c45-94a8-73e1048fd19c"]},
}

# Platform levels, in run order: (parent key in spec.PARENTS, connector level, ID key in the connector's rows).
LEVELS = {
    "meta": [("metacampaign", "campaign", "campaignid"), ("metaadset", "adset", "adsetid"),
             ("metaadvertisement", "ad", "advertisementid")],
    "snap": [("snapcampaign", "campaign", "id"), ("snapadsquad", "adsquad", "id"), ("snapadvertisement", "ad", "id")],
    "google": [("googleadscampaign", "campaign", "campaignid"), ("googleadsadgroup", "ad_group", "adgroupid"),
               ("googleadsadvertisement", "ad", "adid"), ("googleadsassetgroup", "asset_group", "assetgroupid")],
    "tiktok": [("tiktokcampaign", "campaign", "campaignid"), ("tiktokadgroup", "adgroup", "adgroupid"),
               ("tiktokadvertisement", "ad", "adid")],
}
NAMES = {"meta": "Meta", "snap": "Snap", "google": "Google Ads", "tiktok": "TikTok"}
SNAP_FIELDS = ("impressions,uniques,frequency,swipes,spend,video_views,engaged_views,screen_time_millis,quartile_1,"
               "quartile_2,quartile_3,view_completion,landing_page_views,place_opens,place_actions,conversion_purchases,"
               "conversion_purchases_value,conversion_add_cart,conversion_start_checkout,conversion_view_content,"
               "conversion_page_views,conversion_sign_ups")
# Snap refuses reach (uniques, frequency) for any date before 2021 (E1008), so earlier windows leave them out.
SNAP_FIELDS_BEFORE_2021 = SNAP_FIELDS.replace("uniques,frequency,", "")
# Snap reports in the ad account's time zone; start / end times need its UTC offset (zones without daylight saving).
SNAP_OFFSETS = {"Asia/Riyadh": "+03:00", "Asia/Kuwait": "+03:00", "Asia/Qatar": "+03:00", "Asia/Bahrain": "+03:00",
                "Asia/Aden": "+03:00", "Asia/Baghdad": "+03:00", "Asia/Dubai": "+04:00", "Asia/Muscat": "+04:00",
                "UTC": "+00:00", "Etc/UTC": "+00:00", "GMT": "+00:00"}


def flow_id(name):
    return str(uuid.uuid5(NS, name))


def name_daily(p):
    return f"Get {NAMES[p]} Daily Insights"


def name_monthly(p):
    return f"Get {NAMES[p]} Monthly Insights"


def name_run(p):
    return f"{NAMES[p]} - Run Sync"


SCHEDULER = "Social Media - Scheduled Sync"


# ---- building blocks --------------------------------------------------------------------------------------------

def op(api, operation, params, run_after=None, paginate=False, retry_none=False):
    name = API[api][0]
    a = {"runAfter": run_after or {}, "type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{name}", "operationId": operation,
                 "connectionName": name}}}
    if paginate:
        a["runtimeConfiguration"] = {"paginationPolicy": {"minimumItemCount": 100000}}
    if retry_none:
        a["inputs"]["retryPolicy"] = {"type": "none"}
    return a


def after(*names, statuses=("Succeeded",)):
    return {n: list(statuses) for n in names if n}


def compose(value, run_after=None):
    return {"type": "Compose", "runAfter": run_after or {}, "inputs": value}


def init(name, typ, value, run_after=None):
    return {"type": "InitializeVariable", "runAfter": run_after or {},
            "inputs": {"variables": [{"name": name, "type": typ, "value": value}]}}


def incr(name, run_after, by=1):
    return {"type": "IncrementVariable", "runAfter": run_after, "inputs": {"name": name, "value": by}}


def foreach(items, actions, run_after=None, concurrency=1):
    return {"type": "Foreach", "foreach": items, "runAfter": run_after or {}, "actions": actions,
            "runtimeConfiguration": {"concurrency": {"repetitions": concurrency}}}


def chain(actions):
    """Runs the actions of a dict one after another, in dict order (sets runAfter)."""
    prev = None
    for name, a in actions.items():
        if "runAfter" not in a or not a["runAfter"]:
            a["runAfter"] = after(prev) if prev else {}
        prev = name
    return actions, prev


def json_map(select_name, lst, key_expr, value_expr, run_after):
    """Select + Compose that turn a list into a JSON object {key: value} for constant-time lookups."""
    return {
        select_name: {"type": "Select", "runAfter": run_after, "inputs": {
            "from": f"@coalesce({lst}, json('[]'))",
            "select": f"@concat('\"', {key_expr}, '\":', {value_expr})"}},
        select_name.replace("Select_", "Map_"): compose(f"@json(concat('{{', join(body('{select_name}'), ','), '}}'))",
                                                        after(select_name)),
    }


def definition(platform, triggers, actions, apis):
    refs = {}
    for key in apis:
        api, logical, ref = API[key]
        refs[api] = {"api": {"name": api, **({"logicalName": logical} if logical else {})},
                     "connection": {"connectionReferenceLogicalName": ref}, "runtimeSource": "embedded"}
    params = {"$authentication": {"defaultValue": {}, "type": "SecureObject"},
              "$connections": {"defaultValue": {}, "type": "Object"}}
    for display, schema in ENV.get(platform, {}).items():
        params[display] = {"defaultValue": "", "type": "String", "metadata": {"schemaName": schema}}
    return {"properties": {
        "connectionReferences": refs,
        "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/"
                       "workflowdefinition.json#",
            "contentVersion": "1.0.0.0", "parameters": params, "triggers": triggers, "actions": actions},
        "templateName": ""}, "schemaVersion": "1.0.0.0"}


def manual(fields):
    """Instant trigger with text / boolean inputs (child flows get them from Run a Child Flow)."""
    props, required = {}, []
    for key, (title, typ, description, req) in fields.items():
        props[key] = {"title": title, "type": typ, "description": description, "x-ms-dynamically-added": True,
                      "x-ms-content-hint": "TEXT" if typ == "string" else "BOOLEAN"}
        if req:
            required.append(key)
    return {"manual": {"type": "Request", "kind": "Button",
                       "inputs": {"schema": {"type": "object", "properties": props, "required": required}}}}


def respond(body, run_after):
    return {"type": "Response", "kind": "PowerApp", "runAfter": run_after,
            "inputs": {"statusCode": 200, "body": body, "schema": {
                "type": "object", "properties": {k: {"title": k, "type": "string" if isinstance(v, str) and not
                                                     v.startswith("@variables") else "integer"}
                                                 for k, v in body.items()}}}}


def env(display):
    return f"parameters('{display}')"


# ---- insight row mapping ----------------------------------------------------------------------------------------

def snap_metrics(s, finalized):
    """Snap stats -> columns, the same calculations as Get Snap Insights (micro-currency / 1,000,000)."""
    v = lambda k: f"{s}?['{k}']"
    num = lambda k: f"float(coalesce({v(k)}, 0))"
    money = lambda k: f"if(equals({v(k)}, null), null, div(float({v(k)}), 1000000))"
    return {
        "impressions": f"@{v('impressions')}", "reach": f"@{v('uniques')}",
        "frequency": f"@if(not(equals({v('frequency')}, null)), {v('frequency')}, if(greater({num('uniques')}, 0), "
                     f"div({num('impressions')}, {num('uniques')}), null))",
        "swipes": f"@{v('swipes')}", "spend": f"@{money('spend')}", "videoviews": f"@{v('video_views')}",
        "engagedviews": f"@{v('engaged_views')}",
        "screentimeseconds": f"@if(equals({v('screen_time_millis')}, null), null, div(float({v('screen_time_millis')}), 1000))",
        "quartile1": f"@{v('quartile_1')}", "quartile2": f"@{v('quartile_2')}", "quartile3": f"@{v('quartile_3')}",
        "viewcompletion": f"@{v('view_completion')}", "landingpageviews": f"@{v('landing_page_views')}",
        "placeopens": f"@{v('place_opens')}", "placeactions": f"@{v('place_actions')}",
        "purchases": f"@{v('conversion_purchases')}", "purchasevalue": f"@{money('conversion_purchases_value')}",
        "addtocart": f"@{v('conversion_add_cart')}", "startcheckout": f"@{v('conversion_start_checkout')}",
        "viewcontent": f"@{v('conversion_view_content')}", "pixelpageviews": f"@{v('conversion_page_views')}",
        "signups": f"@{v('conversion_sign_ups')}",
        "swiperate": f"@if(greater({num('impressions')}, 0), div(mul({num('swipes')}, 100), {num('impressions')}), null)",
        "cpm": f"@if(greater({num('impressions')}, 0), div(mul(div({num('spend')}, 1000000), 1000), {num('impressions')}), null)",
        "costperswipe": f"@if(greater({num('swipes')}, 0), div(div({num('spend')}, 1000000), {num('swipes')}), null)",
        "costperpurchase": f"@if(greater({num('conversion_purchases')}, 0), div(div({num('spend')}, 1000000), "
                           f"{num('conversion_purchases')}), null)",
        "roas": f"@if(greater({num('spend')}, 0), div({num('conversion_purchases_value')}, {num('spend')}), null)",
        "statsfinalizedthrough": f"@{finalized}",
    }


def common_fields(t, parent, platform_id, date, monthly, closed_through, no_data, raw, base_currency):
    """item/... parameters every insight row gets (name, date parts, key, flags, lookup, currency)."""
    p = spec.PARENTS[t["key"]]
    fmt = "yyyyMM" if monthly else "yyyyMMdd"
    shown = f"substring({date}, 0, 7)" if monthly else date
    fields = {
        "item/sanidi_name": f"@concat(coalesce({parent}?['{p['name']}'], {platform_id}), ' · ', {shown})",
        "item/sanidi_platformid": f"@{platform_id}",
        "item/sanidi_insightkey": f"@concat({platform_id}, '_', formatDateTime({date}, '{fmt}'))",
        "item/sanidi_date": f"@{date}",
        "item/sanidi_month": f"@int(formatDateTime({date}, 'MM'))",
        "item/sanidi_year": f"@int(formatDateTime({date}, 'yyyy'))",
        "item/sanidi_periodclosed": f"@if(empty({closed_through}), false, lessOrEquals(ticks({date}), ticks({closed_through})))",
        "item/sanidi_nodata": no_data,
        "item/sanidi_lastsyncedon": "@utcNow()",
        f"item/{t['lookup']}@odata.bind": f"/{p['set']}(@{{{parent}?['{PREFIX_PK(t['key'])}']}})",
        "item/transactioncurrencyid@odata.bind":
            f"/transactioncurrencies(@{{coalesce({parent}?['_transactioncurrencyid_value'], {base_currency})}})",
    }
    if raw:
        fields["item/sanidi_rawpayload"] = f"@if(greater(length({raw}), 100000), substring({raw}, 0, 100000), {raw})"
    if not monthly:
        fields["item/sanidi_day"] = f"@int(formatDateTime({date}, 'dd'))"
        fields["item/sanidi_weekday"] = f"@add(dayOfWeek({date}), 1)"
    return fields


def PREFIX_PK(key):
    return f"sanidi_{key}id"


def upsert(t, tag, row, platform_id, date, metrics, monthly, closed_through, raw, existing_map, items_map):
    """Actions for one platform row: skip it when its item isn't synced, else update or create the insight row."""
    parent = f"outputs('Parent_{tag}')"
    child_set = t["schema"] + "s"
    fields = common_fields(t, parent, platform_id, date, monthly, closed_through, False, raw,
                           "outputs('Base_currency')")
    fields.update({f"item/sanidi_{k}": v for k, v in metrics.items()})
    key = f"outputs('Key_{tag}')"
    return {
        f"Parent_{tag}": compose(f"@{items_map}?[{platform_id}]"),
        f"If_synced_{tag}": {
            "type": "If", "runAfter": after(f"Parent_{tag}"),
            "expression": {"and": [{"not": {"equals": [f"@{parent}", "@null"]}}]},
            "actions": {
                f"Key_{tag}": compose(f"@concat({platform_id}, '_', formatDateTime({date}, "
                                      f"'{'yyyyMM' if monthly else 'yyyyMMdd'}'))"),
                f"If_exists_{tag}": {
                    "type": "If", "runAfter": after(f"Key_{tag}"),
                    "expression": {"and": [{"not": {"equals": [f"@coalesce({existing_map}?[{key}], '')", ""]}}]},
                    "actions": {f"Update_{tag}": op("dv", "UpdateOnlyRecord", {
                        "entityName": child_set, "recordId": f"@{existing_map}?[{key}]", **fields})},
                    "else": {"actions": {f"Create_{tag}": op("dv", "CreateRecord", {
                        "entityName": child_set, **fields})}}},
                f"Count_written_{tag}": incr("Written", after(f"If_exists_{tag}")),
                f"Count_failed_{tag}": incr("Failed", after(f"If_exists_{tag}", statuses=("Failed", "TimedOut"))),
                f"Note_failed_{tag}": {
                    "type": "AppendToStringVariable", "runAfter": after(f"Count_failed_{tag}"),
                    "inputs": {"name": "Errors", "value": f"@{{concat({key}, ': ', take(string(coalesce("
                                                           f"actions('Update_{tag}')?['outputs']?['body']?['error']?['message'], "
                                                           f"actions('Create_{tag}')?['outputs']?['body']?['error']?['message'], "
                                                           f"'')), 300), ' | ')}}"}},
            },
            "else": {"actions": {f"Count_skipped_{tag}": incr("Skipped", {})}},
        },
    }


def with_activity(name, rows_expr, spend_key, run_after):
    """Rows with impressions or spend only: a period without delivery gets no data row (the month then gets an
    empty row, No Data = Yes), the same for every platform (TikTok returns zero rows for every item)."""
    return {name: {"type": "Query", "runAfter": run_after, "inputs": {
        "from": rows_expr,
        "where": f"@or(greater(float(coalesce(item()?['impressions'], 0)), 0), "
                 f"greater(float(coalesce(item()?['{spend_key}'], 0)), 0))"}}}


def generic_metrics(t, row):
    return {c["name"][len("sanidi_"):]: f"@{row}?['{c['name'][len('sanidi_'):]}']" for c in t["metrics"]}


# ---- per-platform fetch + write for one window ------------------------------------------------------------------

def window_body(platform, t, level, id_key, monthly, w_start, w_end, existing_map, items_map, tag):
    """Actions that fetch one window (≤ 30 days / one month) of one level and write its rows."""
    closed = "triggerBody()?['closed_through']"
    period = "month" if monthly else "day"
    a = {}
    fail_note = lambda call: {
        "type": "AppendToStringVariable", "runAfter": after(call, statuses=("Failed", "TimedOut")),
        "inputs": {"name": "Errors", "value": f"@{{concat('{tag} ', {w_start}, ': ', "
                                               f"take(string(coalesce(body('{call}'), '')), 400), ' | ')}}"}}

    def rows_loop(loop, rows_expr, call, row_actions):
        a[loop] = foreach(rows_expr, row_actions, after(call), ROW_CONCURRENCY)
        a[f"Note_failed_{call}"] = fail_note(call)

    if platform in ("tiktok", "meta"):
        outer = "For_each_advertiser_" + tag if platform == "tiktok" else "For_each_account_" + tag
        call = f"Get_{tag}"
        if platform == "tiktok":
            get = op("tiktok", "GetPeriodInsights", {
                "Access-Token": f"@trim({env('TikTok Ads Access Token (sanidi_TikTokAdsAccessToken)')})",
                "advertiser_id": f"@items('{outer}')", "level": level, "period": period,
                "start_date": f"@{w_start}", "end_date": f"@{w_end}"}, retry_none=False)
            accounts = "@body('Advertiser_IDs')"
        else:
            get = op("meta", "GetPeriodInsights", {
                "account_id": f"@items('{outer}')", "level": level, "period": period,
                "start_date": f"@{w_start}", "end_date": f"@{w_end}"})
            accounts = "@outputs('Meta_accounts')"
        loop = f"For_each_row_{tag}"
        row = f"items('{loop}')"
        inner = {call: get}
        date = f"{row}?['date']"
        inner_rows = upsert(t, tag, row, f"string({row}?['{id_key}'])", date, generic_metrics(t, row), monthly,
                            closed, f"string(coalesce({row}?['rawpayload'], {row}))", existing_map, items_map)
        inner.update(with_activity(f"Active_rows_{tag}", f"@coalesce(outputs('{call}')?['body/rows'], json('[]'))",
                                   "spend", after(call)))
        inner[loop] = foreach(f"@body('Active_rows_{tag}')", inner_rows, after(f"Active_rows_{tag}"), ROW_CONCURRENCY)
        inner[f"Note_failed_{call}"] = fail_note(call)
        a[outer] = foreach(accounts, inner, {}, 1)
        return a

    if platform == "google":
        outer = "For_each_account_" + tag
        call = f"Get_{tag}"
        # A Google access token lasts an hour: each window gets a fresh one (full loads run for hours).
        headers = google_headers(f"items('{outer}')?['customer_id']", f"Google_token_{tag}")
        inner = {
            call: op("google", "GetPerformance", {
                **headers, "level": level, "granularity": "MONTHLY" if monthly else "DAILY",
                "start_date": f"@{w_start}", "end_date": f"@{w_end}", "breakdown": "NONE"}),
        }
        loop = f"For_each_row_{tag}"
        row = f"items('{loop}')"
        date = f"{row}?['{'month' if monthly else 'date'}']"
        inner.update(with_activity(f"Active_rows_{tag}", f"@coalesce(outputs('{call}')?['body/rows'], json('[]'))",
                                   "cost", after(call)))
        inner[loop] = foreach(f"@body('Active_rows_{tag}')",
                              upsert(t, tag, row, f"string({row}?['{id_key}'])", date, generic_metrics(t, row),
                                     monthly, closed, f"string({row})", existing_map, items_map),
                              after(f"Active_rows_{tag}"), ROW_CONCURRENCY)
        inner[f"Note_failed_{call}"] = fail_note(call)
        a[f"Google_token_{tag}"] = google_token()
        a[outer] = foreach("@outputs('List_client_accounts')?['body/rows']", inner, after(f"Google_token_{tag}"), 1)
        return a

    # Snap: account stats with breakdown=campaign / ad (paged), campaign stats with breakdown=adsquad.
    offset = "outputs('Snap_offset')"
    start_time = f"concat({w_start}, 'T00:00:00', {offset})"
    end_time = (f"concat(formatDateTime(addDays({w_end}, 1), 'yyyy-MM-dd'), 'T00:00:00', {offset})")
    granularity = "TOTAL" if monthly else "DAY"
    fields = f"@if(less(ticks({w_start}), ticks('2021-01-01')), '{SNAP_FIELDS_BEFORE_2021}', '{SNAP_FIELDS}')"
    if level == "adsquad":
        outer = "For_each_campaign_" + tag
        call = f"Get_{tag}"
        camp = f"items('{outer}')"
        get = op("snap", "GetCampaignStats", {
            "campaign_id": f"@{camp}?['sanidi_campaignid']", "granularity": granularity,
            "breakdown": "adsquad", "start_time": f"@{start_time}", "end_time": f"@{end_time}",
            "fields": fields, "omit_empty": True, "limit": 200})
        inner = {call: get}
        inner.update(snap_rows(t, tag, call, monthly, w_start, closed, existing_map, items_map, "adsquad"))
        inner[f"Note_failed_{call}"] = fail_note(call)
        a[f"Live_campaigns_{tag}"] = {"type": "Query", "runAfter": {}, "inputs": {
            "from": "@outputs('List_snap_campaigns')?['body/value']",
            "where": f"@and(lessOrEquals(ticks(formatDateTime(coalesce(item()?['sanidi_starttime'], "
                     f"item()?['sanidi_createdat'], item()?['createdon']), 'yyyy-MM-dd')), ticks({w_end})), "
                     f"or(equals(item()?['sanidi_endtime'], null), greaterOrEquals(ticks(formatDateTime("
                     f"item()?['sanidi_endtime'], 'yyyy-MM-dd')), ticks({w_start}))))"}}
        a[outer] = foreach(f"@body('Live_campaigns_{tag}')", inner, after(f"Live_campaigns_{tag}"), 2)
        return a
    breakdown = "campaign" if level == "campaign" else "ad"
    cursor, more = f"Cursor_{tag}", f"More_{tag}"
    call = f"Get_{tag}"
    page = {
        call: op("snap", "GetAdAccountStats", {
            "ad_account_id": "@outputs('Snap_account_id')", "granularity": granularity, "breakdown": breakdown,
            "start_time": f"@{start_time}", "end_time": f"@{end_time}", "fields": fields, "omit_empty": True,
            "limit": 200, "cursor": f"@if(empty(variables('SnapCursor')), null, variables('SnapCursor'))"}),
    }
    page.update(snap_rows(t, tag, call, monthly, w_start, closed, existing_map, items_map, breakdown))
    page[f"Note_failed_{call}"] = fail_note(call)
    page[f"Next_{tag}"] = {"type": "SetVariable", "runAfter": after(f"For_each_entity_{tag}", statuses=ALL),
                           "inputs": {"name": "SnapCursor", "value":
                                      f"@if(empty(outputs('{call}')?['body/paging']?['next_link']), '', "
                                      f"decodeUriComponent(first(split(last(split(outputs('{call}')?['body/paging']?"
                                      f"['next_link'], 'cursor=')), '&'))))"}}
    a[f"Reset_cursor_{tag}"] = {"type": "SetVariable", "runAfter": {}, "inputs": {"name": "SnapCursor", "value": ""}}
    a[f"Pages_{tag}"] = {"type": "Until", "runAfter": after(f"Reset_cursor_{tag}"),
                         "expression": f"@or(empty(variables('SnapCursor')), equals(actions('{call}')?['status'], 'Failed'))",
                         "limit": {"count": 200, "timeout": "PT6H"}, "actions": page}
    # First pass: the Until checks after the first page, so an empty cursor before the first call is fine.
    return a


def snap_rows(t, tag, call, monthly, w_start, closed, existing_map, items_map, breakdown):
    """Loops over Snap's breakdown entities (and their days) and writes each one."""
    entity_loop = f"For_each_entity_{tag}"
    entity = f"items('{entity_loop}')"
    if monthly:
        entities = (f"@coalesce(outputs('{call}')?['body/total_stats']?[0]?['total_stat']?['breakdown_stats']?"
                    f"['{breakdown}'], json('[]'))")
        finalized = f"outputs('{call}')?['body/total_stats']?[0]?['total_stat']?['finalized_data_end_time']"
        actions = upsert(t, tag, entity, f"string({entity}?['id'])", w_start,
                         snap_metrics(f"{entity}?['stats']", finalized), True, closed, f"string({entity})",
                         existing_map, items_map)
        return {entity_loop: foreach(entities, actions, after(call), ROW_CONCURRENCY)}
    entities = (f"@coalesce(outputs('{call}')?['body/timeseries_stats']?[0]?['timeseries_stat']?['breakdown_stats']?"
                f"['{breakdown}'], json('[]'))")
    finalized = f"outputs('{call}')?['body/timeseries_stats']?[0]?['timeseries_stat']?['finalized_data_end_time']"
    day_loop = f"For_each_day_{tag}"
    day = f"items('{day_loop}')"
    # Days without any delivery are left out (no row), like the other platforms.
    with_data = f"Active_days_{tag}"
    inner = {
        with_data: {"type": "Query", "runAfter": {}, "inputs": {
            "from": f"@coalesce({entity}?['timeseries'], json('[]'))",
            "where": "@or(greater(float(coalesce(item()?['stats']?['impressions'], 0)), 0), "
                     "greater(float(coalesce(item()?['stats']?['spend'], 0)), 0))"}},
    }
    row_actions = upsert(t, tag, day, f"string({entity}?['id'])", f"substring({day}?['start_time'], 0, 10)",
                         snap_metrics(f"{day}?['stats']", finalized), False, closed,
                         f"string(addProperty({day}, 'id', {entity}?['id']))", existing_map, items_map)
    inner[day_loop] = foreach(f"@body('{with_data}')", row_actions, after(with_data), 5)
    return {entity_loop: foreach(entities, inner, after(call), 4)}


def google_headers(customer_expr, token="Google_token"):
    login = (f"@if(empty(trim(coalesce({env('Google Ads Login Customer ID (sanidi_GoogleAdsLoginCustomerId)')}, ''))), "
             f"replace({env('Google Ads Customer ID (sanidi_GoogleAdsCustomerId)')}, '-', ''), "
             f"replace({env('Google Ads Login Customer ID (sanidi_GoogleAdsLoginCustomerId)')}, '-', ''))")
    return {"customer_id": f"@{customer_expr}", "access-token": f"@outputs('{token}')?['body/access_token']",
            "developer-token": f"@{env('Google Ads Developer Token (sanidi_GoogleAdsDeveloperToken)')}",
            "login-customer-id": login}


def google_token():
    return op("google", "GetAccessToken", {
        "body/client_id": f"@{env('Google Ads Client ID (sanidi_GoogleAdsClientId)')}",
        "body/client_secret": f"@{env('Google Ads Client Secret (sanidi_GoogleAdsClientSecret)')}",
        "body/refresh_token": f"@{env('Google Ads Refresh Token (sanidi_GoogleAdsRefreshToken)')}"})


# ---- the insight flows ------------------------------------------------------------------------------------------

def platform_setup(platform):
    """Actions every insight flow of the platform needs first (accounts, tokens, base currency)."""
    a = {
        "Organization": op("dv", "ListRecords", {"entityName": "organizations", "$select": "_basecurrencyid_value",
                                                 "$top": 1}),
        "Base_currency": compose("@first(outputs('Organization')?['body/value'])?['_basecurrencyid_value']"),
    }
    if platform == "tiktok":
        a["Advertiser_ID_list"] = {"type": "Select", "runAfter": {}, "inputs": {
            "from": f"@split(coalesce({env('TikTok Ads Advertiser IDs (sanidi_TikTokAdsAdvertiserIds)')}, ''), ',')",
            "select": "@trim(item())"}}
        a["Advertiser_IDs"] = {"type": "Query", "runAfter": {}, "inputs": {
            "from": "@body('Advertiser_ID_list')", "where": "@not(empty(item()))"}}
    elif platform == "meta":
        a["List_meta_accounts"] = op("dv", "ListRecords", {
            "entityName": "sanidi_metacampaigns", "$select": "sanidi_accountid", "$filter": "sanidi_accountid ne null"},
            paginate=True)
        a["Meta_account_list"] = {"type": "Select", "runAfter": {}, "inputs": {
            "from": "@outputs('List_meta_accounts')?['body/value']", "select": "@item()?['sanidi_accountid']"}}
        a["Meta_accounts"] = compose("@union(body('Meta_account_list'), body('Meta_account_list'))")
    elif platform == "google":
        a["Google_token"] = google_token()
        a["List_client_accounts"] = op("google", "ListClientAccounts", google_headers(
            f"replace({env('Google Ads Customer ID (sanidi_GoogleAdsCustomerId)')}, '-', '')"))
    elif platform == "snap":
        a["List_snap_campaigns"] = op("dv", "ListRecords", {
            "entityName": "sanidi_snapcampaigns",
            "$select": "sanidi_campaignid,sanidi_adaccountid,sanidi_starttime,sanidi_endtime,sanidi_createdat,createdon",
            "$filter": "sanidi_campaignid ne null"}, paginate=True)
        a["Snap_account_id"] = compose("@first(outputs('List_snap_campaigns')?['body/value'])?['sanidi_adaccountid']")
        a["Snap_account"] = op("snap", "GetAdAccount", {"ad_account_id": "@outputs('Snap_account_id')"})
        a["Snap_offsets"] = compose(SNAP_OFFSETS)
        a["Snap_offset"] = compose("@coalesce(outputs('Snap_offsets')?[coalesce(outputs('Snap_account')?"
                                   "['body/adaccounts']?[0]?['adaccount']?['timezone'], '')], "
                                   "int(concat('Unsupported Snap ad account time zone: ', string(outputs('Snap_account')"
                                   "?['body/adaccounts']?[0]?['adaccount']?['timezone']))))")
    chain(a)
    return a


def level_scope(platform, parent_key, level, id_key, monthly):
    """One level: list the synced items (the driver), then each window: existing rows, fetch, write; empty months."""
    t = spec.tables()[f"sanidi_{parent_key}{'monthly' if monthly else 'daily'}insight"]
    p = spec.PARENTS[parent_key]
    tag = f"{level}_{'m' if monthly else 'd'}"
    pk = PREFIX_PK(parent_key)
    child_pk = t["schema"] + "id"
    select = [pk, p["id"], p["name"], "_transactioncurrencyid_value", "createdon"] + \
        [c for c in p["start"] + p["end"] if not c.startswith("@")]
    if p.get("parent_lookup"):
        select.append(f"_{p['parent_lookup']}_value")
    actions = {
        f"List_items_{tag}": op("dv", "ListRecords", {
            "entityName": p["set"], "$select": ",".join(select), "$filter": f"{p['id']} ne null"}, paginate=True),
    }
    actions.update(json_map(f"Select_items_{tag}", f"outputs('List_items_{tag}')?['body/value']",
                            f"item()?['{p['id']}']", "string(item())", after(f"List_items_{tag}")))
    items_map = f"outputs('Map_items_{tag}')"
    # Windows: 30-day ranges (daily) or calendar months (monthly) between the trigger's start and end.
    start, end = "triggerBody()?['start_date']", "triggerBody()?['end_date']"
    loop = f"For_each_window_{tag}"
    idx = f"items('{loop}')"
    if monthly:
        count = (f"@add(add(mul(sub(int(formatDateTime({end}, 'yyyy')), int(formatDateTime({start}, 'yyyy'))), 12), "
                 f"sub(int(formatDateTime({end}, 'MM')), int(formatDateTime({start}, 'MM')))), 1)")
        w_start_expr = f"@formatDateTime(addToTime(formatDateTime({start}, 'yyyy-MM-01'), {idx}, 'Month'), 'yyyy-MM-dd')"
        w_end_expr = (f"@if(greater(ticks(addDays(addToTime(outputs('Window_start_{tag}'), 1, 'Month'), -1)), "
                      f"ticks({end})), {end}, formatDateTime(addDays(addToTime(outputs('Window_start_{tag}'), 1, "
                      f"'Month'), -1), 'yyyy-MM-dd'))")
    else:
        count = f"@add(div(div(sub(ticks({end}), ticks({start})), 864000000000), 30), 1)"
        w_start_expr = f"@formatDateTime(addDays({start}, mul({idx}, 30)), 'yyyy-MM-dd')"
        w_end_expr = (f"@if(greater(ticks(addDays(outputs('Window_start_{tag}'), 29)), ticks({end})), {end}, "
                      f"formatDateTime(addDays(outputs('Window_start_{tag}'), 29), 'yyyy-MM-dd'))")
    w_start, w_end = f"outputs('Window_start_{tag}')", f"outputs('Window_end_{tag}')"
    existing_map = f"outputs('Map_existing_{tag}')"
    win = {
        f"Window_start_{tag}": compose(w_start_expr),
        f"Window_end_{tag}": compose(w_end_expr),
        f"List_existing_{tag}": op("dv", "ListRecords", {
            "entityName": t["schema"] + "s", "$select": f"{child_pk},sanidi_insightkey",
            "$filter": f"sanidi_date ge @{{{w_start}}} and sanidi_date le @{{{w_end}}}"}, paginate=True),
    }
    chain(win)
    win.update(json_map(f"Select_existing_{tag}", f"outputs('List_existing_{tag}')?['body/value']",
                        "item()?['sanidi_insightkey']", f"concat('\"', item()?['{child_pk}'], '\"')",
                        after(f"List_existing_{tag}")))
    body = window_body(platform, t, level, id_key, monthly, w_start, w_end, existing_map, items_map, tag)
    first = next(iter(body))
    body[first]["runAfter"] = after(f"Map_existing_{tag}")
    win.update(body)
    last_of_window = list(body)[-1] if platform != "snap" or level == "adsquad" else f"Pages_{tag}"
    if monthly:
        win.update(empty_months(t, p, tag, w_start, last_of_window, items_map))
    actions[f"Window_count_{tag}"] = compose(count, after(f"Map_items_{tag}"))
    actions[loop] = foreach(f"@range(0, outputs('Window_count_{tag}'))", win, after(f"Window_count_{tag}"), 1)
    return actions


def empty_months(t, p, tag, month, run_after, items_map):
    """Every synced item gets a row for the month (No Data = Yes) when its life covers the month and none exists."""
    child_pk = t["schema"] + "id"
    loop = f"For_each_item_{tag}"
    item = f"items('{loop}')"
    if p["start"] == ["@parent"]:
        # Google Ads ad groups / asset groups: the dates of their campaign (listed by the campaign level).
        camp = f"outputs('Campaign_dates')?[{item}?['_{p['parent_lookup']}_value']]"
        start = f"coalesce({camp}?['sanidi_startdatetime'], {item}?['createdon'])"
        end = f"{camp}?['sanidi_enddatetime']"
    else:
        start = "coalesce(" + ", ".join([f"{item}?['{c}']" for c in p["start"]] + [f"{item}?['createdon']"]) + ")"
        end = (f"coalesce({', '.join(f'{item}?[{chr(39)}{c}{chr(39)}]' for c in p['end'])}, '')"
               if p["end"] else "''")
    month_of = lambda d: f"formatDateTime(convertFromUtc({d}, '{TZ}'), 'yyyy-MM-01')"
    live = (f"@and(lessOrEquals(ticks({month_of(start)}), ticks({month})), "
            f"or(empty({end}), greaterOrEquals(ticks({month_of(end)}), ticks({month}))))")
    key = f"concat({item}?['{p['id']}'], '_', formatDateTime({month}, 'yyyyMM'))"
    fields = common_fields(t, item, f"{item}?['{p['id']}']", month, True, "triggerBody()?['closed_through']",
                           True, None, "outputs('Base_currency')")
    actions = {
        f"List_after_{tag}": op("dv", "ListRecords", {
            "entityName": t["schema"] + "s", "$select": f"{child_pk},sanidi_insightkey",
            "$filter": f"sanidi_date eq @{{{month}}}"}, after(run_after, statuses=ALL), paginate=True),
    }
    actions.update(json_map(f"Select_after_{tag}", f"outputs('List_after_{tag}')?['body/value']",
                            "item()?['sanidi_insightkey']", "'true'", after(f"List_after_{tag}")))
    actions[f"Missing_items_{tag}"] = {"type": "Query", "runAfter": after(f"Map_after_{tag}"), "inputs": {
        "from": f"@outputs('List_items_{tag}')?['body/value']",
        "where": live.replace(item, "item()")}}
    loop_actions = {
        f"If_missing_{tag}": {
            "type": "If", "runAfter": {},
            "expression": {"and": [{"equals": [f"@coalesce(outputs('Map_after_{tag}')?[{key}], false)", False]}]},
            "actions": {
                f"Create_empty_{tag}": op("dv", "CreateRecord", {"entityName": t["schema"] + "s", **fields}),
                f"Count_empty_{tag}": incr("Empty", after(f"Create_empty_{tag}")),
                f"Count_empty_failed_{tag}": incr("Failed", after(f"Create_empty_{tag}", statuses=("Failed",))),
                f"Note_empty_failed_{tag}": {
                    "type": "AppendToStringVariable", "runAfter": after(f"Count_empty_failed_{tag}"),
                    "inputs": {"name": "Errors", "value": f"@{{concat({key}, ' (empty month): ', take(string(coalesce("
                                                           f"actions('Create_empty_{tag}')?['outputs']?['body']?['error']"
                                                           f"?['message'], '')), 300), ' | ')}}"}},
            },
            "else": {"actions": {}}},
    }
    actions[loop] = foreach(f"@body('Missing_items_{tag}')", loop_actions, after(f"Missing_items_{tag}"),
                            ROW_CONCURRENCY)
    return actions


def insight_flow(platform, monthly):
    fields = {
        "start_date": ("Start date", "string", "First day (YYYY-MM-DD); for monthly, any day of the first month.", True),
        "end_date": ("End date", "string", "Last day (YYYY-MM-DD), inclusive; usually today.", True),
        "closed_through": ("Closed through", "string",
                           "Rows dated on or before this date get Period Closed = Yes (YYYY-MM-DD, may be empty).",
                           False),
    }
    actions = {
        "Init_written": init("Written", "integer", 0),
        "Init_skipped": init("Skipped", "integer", 0),
        "Init_failed": init("Failed", "integer", 0),
        "Init_empty": init("Empty", "integer", 0),
        "Init_errors": init("Errors", "string", ""),
        "Init_snap_cursor": init("SnapCursor", "string", ""),
    }
    chain(actions)
    setup = platform_setup(platform)
    first = next(iter(setup))
    setup[first]["runAfter"] = after("Init_snap_cursor")
    actions.update(setup)
    prev = list(setup)[-1]
    if platform == "google" and monthly:
        actions["List_campaign_dates"] = op("dv", "ListRecords", {
            "entityName": "sanidi_googleadscampaigns",
            "$select": "sanidi_googleadscampaignid,sanidi_startdatetime,sanidi_enddatetime"}, after(prev), paginate=True)
        actions.update(json_map("Select_campaign_dates", "outputs('List_campaign_dates')?['body/value']",
                                "item()?['sanidi_googleadscampaignid']", "string(item())",
                                after("List_campaign_dates")))
        actions["Campaign_dates"] = actions.pop("Map_campaign_dates")
        prev = "Campaign_dates"
    for parent_key, level, id_key in LEVELS[platform]:
        scope_name = f"Level_{level}"
        actions[scope_name] = {"type": "Scope", "runAfter": after(prev, statuses=ALL),
                               "actions": level_scope(platform, parent_key, level, id_key, monthly)}
        # A level that fails (not just a row) is reported: Run Sync marks the step Failed when failed > 0.
        actions[f"If_{scope_name}_failed"] = {
            "type": "If", "runAfter": after(scope_name, statuses=ALL),
            "expression": {"and": [{"not": {"equals": [f"@actions('{scope_name}')?['status']", "Succeeded"]}}]},
            "actions": {
                f"Count_{scope_name}_failed": incr("Failed", {}),
                f"Failed_actions_{scope_name}": {
                    "type": "Query", "runAfter": after(f"Count_{scope_name}_failed"),
                    "inputs": {"from": f"@result('{scope_name}')", "where": "@equals(item()?['status'], 'Failed')"}},
                f"Note_{scope_name}_failed": {
                    "type": "AppendToStringVariable", "runAfter": after(f"Failed_actions_{scope_name}"),
                    "inputs": {"name": "Errors", "value": f"@{{concat('Level {level}: ', actions('{scope_name}')?['status'], "
                                                         f"' at ', coalesce(first(body('Failed_actions_{scope_name}'))?['name'], '?'), "
                                                         f"' (', take(string(coalesce(first(body('Failed_actions_{scope_name}'))?"
                                                         "['error']?['message'], '')), 300), ') | ')}"}}},
            "else": {"actions": {}}}
        prev = f"If_{scope_name}_failed"
    actions["Respond_to_a_Power_App_or_flow"] = respond({
        "written": "@variables('Written')", "empty_months": "@variables('Empty')", "skipped": "@variables('Skipped')",
        "failed": "@variables('Failed')", "errors": "@{take(variables('Errors'), 4000)}"}, after(prev, statuses=ALL))
    return definition(platform, manual(fields), actions, ["dv", platform])


# ---- Run Sync and the scheduler ---------------------------------------------------------------------------------

def run_sync_flow(platform):
    """One sync request for one platform: the steps in order, each one reported (PLAN.md §5.2, §5.6)."""
    fields = {
        "run_type": ("Run type", "string", "daily (05:00), intraday, daymonth (button) or alltime (button).", True),
        "include_data": ("Include data", "boolean", "Run the data sync first and wait for its cascade.", False),
        "weekly": ("Weekly run", "boolean", "Friday 05:00: reload the last 28 days (Google Ads 90).", False),
        "full_load_from": ("Full load from", "string", "All time: first day to load (YYYY-MM-DD); empty = the "
                           "platform's maximum history.", False),
    }
    lookback = 89 if platform == "google" else 27
    run_type = "triggerBody()?['run_type']"
    weekly = "equals(triggerBody()?['weekly'], true)"
    a = {
        "Init_log": init("Log", "string", ""),
        "Init_failed_steps": init("FailedSteps", "integer", 0),
        "Today": compose(f"@formatDateTime(convertFromUtc(utcNow(), '{TZ}'), 'yyyy-MM-dd')"),
        "Two_days_ago": compose("@formatDateTime(addDays(outputs('Today'), -2), 'yyyy-MM-dd')"),
        "This_month": compose("@formatDateTime(outputs('Today'), 'yyyy-MM-01')"),
        "Previous_month": compose("@formatDateTime(addToTime(outputs('This_month'), -1, 'Month'), 'yyyy-MM-dd')"),
        "Month_before_previous": compose("@formatDateTime(addToTime(outputs('This_month'), -2, 'Month'), 'yyyy-MM-dd')"),
        "Last_day_of_month": compose("@addDays(addToTime(outputs('This_month'), 1, 'Month'), -1)"),
        "Last_friday_of_month": compose(
            "@formatDateTime(addDays(outputs('Last_day_of_month'), mul(-1, mod(add(sub(dayOfWeek("
            "outputs('Last_day_of_month')), 5), 7), 7))), 'yyyy-MM-dd')"),
        # The previous month is closed from the current month's last Friday on (PLAN.md §5.4).
        "Months_closed_through": compose("@if(greaterOrEquals(ticks(outputs('Today')), ticks(outputs('Last_friday_of_month'))), "
                                         "outputs('Previous_month'), outputs('Month_before_previous'))"),
    }
    if platform in ("meta", "google"):
        a["Earliest"] = compose("@formatDateTime(addDays(addToTime(outputs('Today'), -37, 'Month'), 1), 'yyyy-MM-dd')")
    else:
        p = spec.PARENTS[f"{platform}campaign"]
        col = p["start"][-1]
        a["First_campaign"] = op("dv", "ListRecords", {
            "entityName": p["set"], "$select": col, "$filter": f"{col} ne null", "$orderby": f"{col} asc", "$top": 1})
        a["Earliest"] = compose(f"@formatDateTime(convertFromUtc(coalesce(first(outputs('First_campaign')?['body/value'])"
                                f"?['{col}'], utcNow()), '{TZ}'), 'yyyy-MM-dd')")
    a["Full_load_from"] = compose(f"@if(empty(trim(coalesce(triggerBody()?['full_load_from'], ''))), outputs('Earliest'), "
                                  "formatDateTime(triggerBody()?['full_load_from'], 'yyyy-MM-dd'))")
    a["Daily_from"] = compose(
        f"@if(equals({run_type}, 'alltime'), outputs('Full_load_from'), if(equals({run_type}, 'intraday'), "
        f"outputs('Today'), if({weekly}, formatDateTime(addDays(outputs('Today'), -{lookback}), 'yyyy-MM-dd'), "
        "outputs('Two_days_ago'))))")
    previous_or_lookback = ("formatDateTime(addDays(outputs('Today'), -89), 'yyyy-MM-01')" if platform == "google"
                            else "outputs('Previous_month')")
    a["Monthly_from"] = compose(
        f"@if(equals({run_type}, 'intraday'), outputs('This_month'), if(and({weekly}, not(equals({run_type}, 'alltime'))), "
        f"{previous_or_lookback}, formatDateTime(outputs('Daily_from'), 'yyyy-MM-01')))")
    chain(a)

    def child(name, wid, body, run_after):
        return {"type": "Workflow", "runAfter": run_after,
                "inputs": {"host": {"workflowReferenceName": wid}, "body": body, "retryPolicy": {"type": "none"}}}

    def log(step, run_after, counts=False):
        detail = (f"' (written ', string(coalesce(body('{step}')?['written'], 0)), ', empty months ', "
                  f"string(coalesce(body('{step}')?['empty_months'], 0)), ', skipped ', "
                  f"string(coalesce(body('{step}')?['skipped'], 0)), ', failed ', "
                  f"string(coalesce(body('{step}')?['failed'], 0)), ')', "
                  f"if(empty(body('{step}')?['errors']), '', concat(' ', body('{step}')?['errors'])), "
                  if counts else "")
        return {
            f"Log_{step}": {"type": "AppendToStringVariable", "runAfter": after(step, statuses=ALL), "inputs": {
                "name": "Log", "value": f"@{{concat('{step.replace('_', ' ')}: ', actions('{step}')?['status'], "
                                        f"{detail}' [', formatDateTime(convertFromUtc(utcNow(), '{TZ}'), 'HH:mm'), "
                                        "']', decodeUriComponent('%0A'))}"}},
            f"Count_{step}": {"type": "If", "runAfter": after(f"Log_{step}"),
                              "expression": {"or": [
                                  {"not": {"equals": [f"@actions('{step}')?['status']", "Succeeded"]}},
                                  {"greater": [f"@int(coalesce(body('{step}')?['failed'], 0))", 0]}]
                                  if counts else [{"not": {"equals": [f"@actions('{step}')?['status']", "Succeeded"]}}]},
                              "actions": {f"Failed_{step}": incr("FailedSteps", {})}, "else": {"actions": {}}},
        }

    prev = list(a)[-1]
    with_data = f"or(equals({run_type}, 'daily'), and(equals({run_type}, 'alltime'), equals(triggerBody()?['include_data'], true)))"
    data_ids = " or ".join(f"_workflow_value eq {w}" for w in EXISTING[platform]["children"])
    data_steps = {
        "Data_sync": child("Data_sync", EXISTING[platform]["data"], {}, {}),
        "Wait_before_checking": {"type": "Wait", "runAfter": after("Data_sync", statuses=ALL),
                                 "inputs": {"interval": {"count": 3, "unit": "Minute"}}},
        "Init_quiet": {"type": "SetVariable", "runAfter": after("Wait_before_checking"),
                       "inputs": {"name": "QuietChecks", "value": 0}},
        "Wait_for_cascade": {
            "type": "Until", "runAfter": after("Init_quiet"),
            "expression": "@greaterOrEquals(variables('QuietChecks'), 2)",
            "limit": {"count": 15, "timeout": "PT40M"},
            "actions": {
                "Running_child_flows": op("dv", "ListRecords", {
                    "entityName": "flowruns", "$select": "flowrunid",
                    "$filter": f"({data_ids}) and status eq 'Running'", "$top": 1}),
                "If_quiet": {"type": "If", "runAfter": after("Running_child_flows"),
                             "expression": {"and": [{"equals": [
                                 "@length(outputs('Running_child_flows')?['body/value'])", 0]}]},
                             "actions": {"Quiet": incr("QuietChecks", {})},
                             "else": {"actions": {"Busy": {"type": "SetVariable", "runAfter": {},
                                                           "inputs": {"name": "QuietChecks", "value": 0}}}}},
                "Wait_2_minutes": {"type": "Wait", "runAfter": after("If_quiet"),
                                   "inputs": {"interval": {"count": 2, "unit": "Minute"}}},
            }},
        "Log_wait": {"type": "AppendToStringVariable", "runAfter": after("Wait_for_cascade", statuses=ALL),
                     "inputs": {"name": "Log", "value": "@{concat('Data cascade: ', if(greaterOrEquals("
                                "variables('QuietChecks'), 2), 'finished', 'still running after 30 minutes, continued'), "
                                "decodeUriComponent('%0A'))}"}},
    }
    data_steps.update(log("Data_sync", {}))
    data_steps["Log_Data_sync"]["runAfter"] = after("Data_sync", statuses=ALL)
    a["Init_quiet_checks"] = init("QuietChecks", "integer", 0, after(prev))
    a["If_data"] = {"type": "If", "runAfter": after("Init_quiet_checks"),
                    "expression": {"and": [{"equals": [f"@{with_data}", True]}]},
                    "actions": data_steps, "else": {"actions": {}}}
    a["Lifetime_insights"] = child("Lifetime_insights", EXISTING[platform]["lifetime"], {}, after("If_data", statuses=ALL))
    a.update(log("Lifetime_insights", {}))
    a["Daily_insights"] = child("Daily_insights", flow_id(name_daily(platform)), {
        "start_date": "@outputs('Daily_from')", "end_date": "@outputs('Today')",
        "closed_through": "@outputs('Two_days_ago')"}, after("Count_Lifetime_insights", statuses=ALL))
    a.update(log("Daily_insights", {}, counts=True))
    a["Monthly_insights"] = child("Monthly_insights", flow_id(name_monthly(platform)), {
        "start_date": "@outputs('Monthly_from')", "end_date": "@outputs('Today')",
        "closed_through": "@outputs('Months_closed_through')"}, after("Count_Daily_insights", statuses=ALL))
    a.update(log("Monthly_insights", {}, counts=True))
    a["Respond_to_a_Power_App_or_flow"] = respond({
        "status": "@{if(greater(variables('FailedSteps'), 0), 'Failed', 'Succeeded')}",
        "log": "@{variables('Log')}"}, after("Count_Monthly_insights", statuses=ALL))
    return definition(platform, manual(fields), a, ["dv"])


def scheduler_flow():
    """05:00, 08:00, 12:00, 16:00 Riyadh: one Integration Sync Request per platform that is set up and active."""
    a = {
        "Now": compose(f"@convertFromUtc(utcNow(), '{TZ}')"),
        "Morning_run": compose("@equals(formatDateTime(outputs('Now'), 'HH'), '05')"),
        "Friday": compose("@equals(dayOfWeek(outputs('Now')), 5)"),
        "List_platforms": op("dv", "ListRecords", {
            "entityName": "sanidi_integrationplatforms", "$select": "sanidi_integrationplatformid,sanidi_name",
            "$filter": "sanidi_isconfigured eq true and (sanidi_connectionactive eq true or sanidi_connectionactive eq null)"}),
    }
    chain(a)
    a["For_each_platform"] = foreach("@outputs('List_platforms')?['body/value']", {
        "Create_request": op("dv", "CreateRecord", {
            "entityName": "sanidi_integrationsyncrequests",
            "item/sanidi_name": "@{items('For_each_platform')?['sanidi_name']} - @{if(outputs('Morning_run'), "
                                "'Scheduled Daily', 'Scheduled Intraday')} - @{formatDateTime(outputs('Now'), "
                                "'yyyy-MM-dd HH:mm')}",
            # The connector names a lookup by its navigation property (sanidi_Platform), not its column.
            "item/sanidi_Platform@odata.bind": "/sanidi_integrationplatforms(@{items('For_each_platform')?"
                                               "['sanidi_integrationplatformid']})",
            "item/sanidi_status": 100000000,
            "item/sanidi_startedon": "@utcNow()",
            "item/sanidi_synctype": "@if(outputs('Morning_run'), 100000004, 100000005)",
            "item/sanidi_triggeredby": 100000001,
            "item/sanidi_includedata": "@outputs('Morning_run')",
            "item/sanidi_weeklyrun": "@and(outputs('Morning_run'), outputs('Friday'))",
        })}, after("List_platforms"), 4)
    triggers = {"Recurrence": {"type": "Recurrence", "recurrence": {
        "frequency": "Day", "interval": 1, "timeZone": TZ,
        "schedule": {"hours": ["5", "8", "12", "16"], "minutes": [0]}}}}
    return definition(None, triggers, a, ["dv"])


def all_flows():
    flows = {}
    for p in LEVELS:
        flows[name_daily(p)] = (lambda p=p: insight_flow(p, False),
                                f"Child flow: daily {NAMES[p]} statistics for a date range, every level, into the "
                                f"{NAMES[p]} daily insight tables (driven by the synced tables).")
        flows[name_monthly(p)] = (lambda p=p: insight_flow(p, True),
                                  f"Child flow: monthly {NAMES[p]} statistics (totalled by {NAMES[p]}) for a month "
                                  f"range, every level, into the {NAMES[p]} monthly insight tables; months without "
                                  "data get an empty row.")
        flows[name_run(p)] = (lambda p=p: run_sync_flow(p),
                              f"Child flow run by Sync Control - Run Sync Request: one {NAMES[p]} sync request in "
                              "order (data and its cascade, lifetime, daily and monthly insights), each step logged.")
    flows[SCHEDULER] = (scheduler_flow, "Every day at 05:00, 08:00, 12:00 and 16:00 (Riyadh): creates one "
                                        "Integration Sync Request per active platform (05:00: data and all insights; "
                                        "otherwise today, the current month and lifetime).")
    return flows


def main(apply, update_existing=False, only=None):
    out = HERE / "flows"
    out.mkdir(exist_ok=True)
    built = {}
    for name, (build, description) in all_flows().items():
        clientdata = build()
        built[name] = (clientdata, description)
        path = out / (name.lower().replace(" - ", "-").replace(" ", "-") + ".json")
        path.write_text(json.dumps(clientdata, indent=1, ensure_ascii=False) + "\n")
        print(f"{name}: {len(json.dumps(clientdata)) // 1024} KB -> {path.name}")
    if not apply:
        return
    from dv import Dataverse
    dv = Dataverse()
    for name, (clientdata, description) in built.items():
        if only and name not in only:
            continue
        wid = flow_id(name)
        existing = dv.first(f"workflows?$select=workflowid,statecode&$filter=workflowid eq {wid}")
        body = {"name": name, "description": description, "clientdata": json.dumps(clientdata)}
        if existing and not update_existing:
            print(f"{name}: exists, left unchanged")
            continue
        if existing:
            was_on = existing["statecode"] == 1
            if was_on:
                dv.request("PATCH", f"workflows({wid})", {"statecode": 0, "statuscode": 1})
            try:
                dv.request("PATCH", f"workflows({wid})", body, solution=SOLUTION)
            finally:
                if was_on:
                    dv.request("PATCH", f"workflows({wid})", {"statecode": 1, "statuscode": 2})
            print(f"updated {name} ({wid}){', turned back on' if was_on else ''}")
        else:
            dv.request("POST", "workflows", {"workflowid": wid, "category": 5, "type": 1, "primaryentity": "none",
                                             **body}, solution=SOLUTION)
            print(f"created {name} ({wid}), turned off")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    main("--apply" in sys.argv, "--update-existing" in sys.argv, only or None)
