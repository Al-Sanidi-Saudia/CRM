"""All-time (LIFETIME) Snap stats stored on the Snap Campaign, Snap Ad Squad and Snap
Advertisement rows, plus the flow actions that fetch and map them.

Every table gets the same INSIGHT_FIELDS (columns) and INSIGHT_TAB (form tab). Every
sync flow adds stats_actions() for the row it is processing and merges stats_columns()
into its Update/Add row parameters. Stats are fetched with granularity=LIFETIME and no
breakdown. If the stats call fails, the row is still written with empty stats and an
empty "Stats Last Synced", so one failing call doesn't block the entity sync.
"""

# Snap metric for each stored column ("" = computed in the flow).
METRICS = {
    "sanidi_impressions": "impressions",
    "sanidi_reach": "uniques",
    "sanidi_frequency": "frequency",
    "sanidi_swipes": "swipes",
    "sanidi_spend": "spend",
    "sanidi_videoviews": "video_views",
    "sanidi_engagedviews": "engaged_views",
    "sanidi_screentimeseconds": "screen_time_millis",
    "sanidi_quartile1": "quartile_1",
    "sanidi_quartile2": "quartile_2",
    "sanidi_quartile3": "quartile_3",
    "sanidi_viewcompletion": "view_completion",
    "sanidi_landingpageviews": "landing_page_views",
    "sanidi_placeopens": "place_opens",
    "sanidi_placeactions": "place_actions",
    "sanidi_purchases": "conversion_purchases",
    "sanidi_purchasevalue": "conversion_purchases_value",
    "sanidi_addtocart": "conversion_add_cart",
    "sanidi_startcheckout": "conversion_start_checkout",
    "sanidi_viewcontent": "conversion_view_content",
    "sanidi_pixelpageviews": "conversion_page_views",
    "sanidi_signups": "conversion_sign_ups",
}
STATS_FIELDS = ",".join(METRICS.values())

INSIGHT_FIELDS = [
    ("sanidi_impressions", "Impressions", "int", None, "All-time Snap stat: impressions"),
    ("sanidi_reach", "Reach", "int", None, "All-time Snap stat: uniques (unique people reached)"),
    ("sanidi_frequency", "Frequency", "decimal", None, "All-time Snap stat: frequency (impressions per person)"),
    ("sanidi_swipes", "Swipes", "int", None, "All-time Snap stat: swipes"),
    ("sanidi_spend", "Spend", "money", None, "All-time Snap stat: spend / 1,000,000"),
    ("sanidi_videoviews", "Video Views", "int", None, "All-time Snap stat: video_views (2s+ or swipe)"),
    ("sanidi_engagedviews", "Engaged Views", "int", None, "All-time Snap stat: engaged_views (5s+)"),
    ("sanidi_screentimeseconds", "Screen Time (sec)", "decimal", None,
     "All-time Snap stat: screen_time_millis / 1,000"),
    ("sanidi_quartile1", "Video 25%", "int", None, "All-time Snap stat: quartile_1"),
    ("sanidi_quartile2", "Video 50%", "int", None, "All-time Snap stat: quartile_2"),
    ("sanidi_quartile3", "Video 75%", "int", None, "All-time Snap stat: quartile_3"),
    ("sanidi_viewcompletion", "Video Completions", "int", None, "All-time Snap stat: view_completion"),
    ("sanidi_landingpageviews", "Landing Page Views", "int", None, "All-time Snap stat: landing_page_views"),
    ("sanidi_placeopens", "Place Opens", "int", None, "All-time Snap stat: place_opens"),
    ("sanidi_placeactions", "Place Actions", "int", None, "All-time Snap stat: place_actions"),
    ("sanidi_purchases", "Purchases", "int", None, "All-time Snap stat: conversion_purchases"),
    ("sanidi_purchasevalue", "Purchase Value", "money", None,
     "All-time Snap stat: conversion_purchases_value / 1,000,000"),
    ("sanidi_addtocart", "Add to Cart", "int", None, "All-time Snap stat: conversion_add_cart"),
    ("sanidi_startcheckout", "Start Checkout", "int", None, "All-time Snap stat: conversion_start_checkout"),
    ("sanidi_viewcontent", "View Content", "int", None, "All-time Snap stat: conversion_view_content"),
    ("sanidi_pixelpageviews", "Page Views (Pixel)", "int", None, "All-time Snap stat: conversion_page_views"),
    ("sanidi_signups", "Sign Ups", "int", None, "All-time Snap stat: conversion_sign_ups"),
    ("sanidi_swiperate", "Swipe Rate (%)", "decimal", None, "Calculated: Swipes / Impressions x 100"),
    ("sanidi_cpm", "CPM", "money", None, "Calculated: Spend / Impressions x 1,000"),
    ("sanidi_costperswipe", "Cost per Swipe", "money", None, "Calculated: Spend / Swipes"),
    ("sanidi_costperpurchase", "Cost per Purchase", "money", None, "Calculated: Spend / Purchases"),
    ("sanidi_roas", "ROAS", "decimal", None, "Calculated: Purchase Value / Spend"),
    ("sanidi_statsfinalizedthrough", "Stats Finalized Through", "datetime", None,
     "Snap: finalized_data_end_time (lifetime stats finalize 48-72 hours after the fact)"),
    ("sanidi_statslastsynced", "Stats Last Synced", "datetime", None,
     "When the flow last fetched the stats; empty if the stats call failed"),
]
INSIGHT_NAMES = {f[0] for f in INSIGHT_FIELDS}

INSIGHT_TAB = ("insights", "Insights", [
    ("delivery", "Delivery", ["sanidi_impressions", "sanidi_reach", "sanidi_frequency", "sanidi_swipes",
                              "sanidi_spend", "sanidi_swiperate", "sanidi_cpm", "sanidi_costperswipe"]),
    ("engagement", "Engagement", ["sanidi_videoviews", "sanidi_engagedviews", "sanidi_screentimeseconds",
                                  "sanidi_quartile1", "sanidi_quartile2", "sanidi_quartile3",
                                  "sanidi_viewcompletion", "sanidi_landingpageviews", "sanidi_placeopens",
                                  "sanidi_placeactions"]),
    ("conversions", "Conversions", ["sanidi_purchases", "sanidi_purchasevalue", "sanidi_costperpurchase",
                                    "sanidi_roas", "sanidi_addtocart", "sanidi_startcheckout", "sanidi_viewcontent",
                                    "sanidi_pixelpageviews", "sanidi_signups"]),
    ("sync", "Sync", ["sanidi_statsfinalizedthrough", "sanidi_statslastsynced"]),
])
assert {f for _, _, fs in INSIGHT_TAB[2] for f in fs} == INSIGHT_NAMES

STATS = "outputs('Lifetime_stats')"


def _m(metric):
    return f"{STATS}?['stats']?['{metric}']"


def _num(metric):
    return f"float(coalesce({_m(metric)}, 0))"


def _ratio(numerator, denominator):
    """numerator / denominator, or null when the denominator is 0 or missing."""
    return f"if(greater(coalesce({_m(denominator)}, 0), 0), div({numerator}, {_num(denominator)}), null)"


def stats_actions(snap_api, operation, parameter, id_expr, run_after):
    """Get_stats (LIFETIME) plus Lifetime_stats, which runs even if Get_stats fails."""
    return {
        "Get_stats": {
            "type": "OpenApiConnection", "runAfter": run_after,
            "inputs": {"parameters": {parameter: id_expr, "granularity": "LIFETIME", "fields": STATS_FIELDS},
                       "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{snap_api}",
                                "operationId": operation, "connectionName": snap_api}}},
        "Lifetime_stats": {
            "type": "Compose", "runAfter": {"Get_stats": ["Succeeded", "Failed", "TimedOut", "Skipped"]},
            "inputs": "@if(equals(outputs('Get_stats')?['statusCode'], 200), coalesce("
                      "body('Get_stats')?['lifetime_stats']?[0]?['lifetime_stat'], "
                      "body('Get_stats')?['total_stats']?[0]?['total_stat']), null)"},
    }


def stats_columns():
    spend = f"div({_num('spend')}, 1000000)"
    cols = {}
    for name, _, kind, _, _ in INSIGHT_FIELDS:
        metric = METRICS.get(name)
        if not metric:
            continue
        v = _m(metric)
        if kind == "money":
            cols[name] = f"@if(equals({v}, null), null, div(float({v}), 1000000))"
        elif name == "sanidi_screentimeseconds":
            cols[name] = f"@if(equals({v}, null), null, div(float({v}), 1000))"
        elif name == "sanidi_frequency":
            cols[name] = (f"@if(not(equals({v}, null)), {v}, "
                          f"{_ratio(_num('impressions'), 'uniques')})")
        else:
            cols[name] = f"@{v}"
    swipes = _num("swipes")
    cols["sanidi_swiperate"] = f"@{_ratio(f'mul({swipes}, 100)', 'impressions')}"
    cols["sanidi_cpm"] = f"@{_ratio(f'mul({spend}, 1000)', 'impressions')}"
    cols["sanidi_costperswipe"] = f"@{_ratio(spend, 'swipes')}"
    cols["sanidi_costperpurchase"] = f"@{_ratio(spend, 'conversion_purchases')}"
    cols["sanidi_roas"] = f"@{_ratio(_num('conversion_purchases_value'), 'spend')}"
    cols["sanidi_statsfinalizedthrough"] = f"@{STATS}?['finalized_data_end_time']"
    cols["sanidi_statslastsynced"] = "@if(equals(outputs('Get_stats')?['statusCode'], 200), utcNow(), null)"
    assert set(cols) == INSIGHT_NAMES
    return {f"item/{k}": v for k, v in cols.items()}
