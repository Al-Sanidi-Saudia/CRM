"""Generates apiDefinition.swagger.json for the Snapchat Ads custom connector.

Run: python3 build_definition.py  (re-run after any change, commit the output)
"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def path_param(name, summary, description):
    return {
        "name": name, "in": "path", "required": True, "type": "string",
        "x-ms-summary": summary, "description": description,
        "x-ms-url-encoding": "single",
    }


def query(name, summary, description, type_="string", enum=None, default=None,
          visibility="advanced", required=False, **extra):
    p = {"name": name, "in": "query", "required": required, "type": type_,
         "x-ms-summary": summary, "description": description}
    if enum:
        p["enum"] = enum
    if default is not None:
        p["default"] = default
    if visibility:
        p["x-ms-visibility"] = visibility
    p.update(extra)
    return p


AD_ACCOUNT_ID = path_param("ad_account_id", "Ad account ID", "The Snapchat ad account ID.")
ORG_ID = path_param("organization_id", "Organization ID", "The Snapchat organization ID.")
CAMPAIGN_ID = path_param("campaign_id", "Campaign ID", "The Snapchat campaign ID.")
AD_SQUAD_ID = path_param("ad_squad_id", "Ad squad ID", "The Snapchat ad squad (ad set) ID.")
AD_ID = path_param("ad_id", "Ad ID", "The Snapchat ad ID.")
CREATIVE_ID = path_param("creative_id", "Creative ID", "The Snapchat creative ID.")

PAGING = [
    query("limit", "Page size", "Records per page (50-1000). Omit to return everything in one response.",
          type_="integer", minimum=50, maximum=1000),
    query("cursor", "Cursor", "Paging cursor taken from paging.next_link of the previous response."),
]

DEFAULT_FIELDS = ",".join([
    "impressions", "swipes", "spend", "video_views", "screen_time_millis",
    "quartile_1", "quartile_2", "quartile_3", "view_completion",
    "conversion_purchases", "conversion_purchases_value",
    "conversion_sign_ups", "conversion_add_cart", "conversion_page_views",
])


def stats_params(breakdowns):
    params = [
        query("granularity", "Granularity",
              "TOTAL and LIFETIME return one total; DAY and HOUR return a time series (start/end time required).",
              enum=["TOTAL", "DAY", "HOUR", "LIFETIME"], default="DAY", required=True, visibility="important"),
        query("start_time", "Start time",
              "ISO 8601 start, aligned to the hour in the ad account time zone, e.g. 2026-10-01T00:00:00+03:00.",
              visibility="important", format="date-time"),
        query("end_time", "End time", "ISO 8601 end (exclusive), aligned to the hour.",
              visibility="important", format="date-time"),
        query("fields", "Metrics", "Comma-separated metric names. Spend values are in micro-currency (divide by 1,000,000).",
              default=DEFAULT_FIELDS),
    ]
    if breakdowns:
        params.append(query("breakdown", "Breakdown", "Return stats per child entity as well.", enum=breakdowns))
    params += [
        query("report_dimension", "Report dimension",
              "Split stats by audience attribute, e.g. age, gender, age,gender, country, os."),
        query("swipe_up_attribution_window", "Swipe attribution window", "Click-through attribution window.",
              enum=["1_DAY", "7_DAY", "28_DAY"]),
        query("view_attribution_window", "View attribution window", "View-through attribution window.",
              enum=["none", "1_HOUR", "3_HOUR", "6_HOUR", "1_DAY", "7_DAY"]),
        query("action_report_time", "Action report time", "Attribute conversions to conversion or impression time.",
              enum=["conversion", "impression"]),
        query("conversion_source_types", "Conversion sources",
              "Comma-separated: web, app, offline, total, total_off_platform, total_on_platform."),
        query("omit_empty", "Omit empty", "Drop rows with no activity.", type_="boolean"),
        query("async", "Async report",
              "Set to true for large pulls; returns a report_run_id to poll with 'Get async stats report'.",
              type_="boolean"),
        query("async_format", "Async format", "File format of an async report.", enum=["csv", "excel"]),
    ]
    return params


def op(operation_id, summary, description, params, schema_ref):
    return {
        "get": {
            "operationId": operation_id,
            "summary": summary,
            "description": description,
            "parameters": params,
            "responses": {
                "200": {"description": "OK", "schema": {"$ref": f"#/definitions/{schema_ref}"}},
                "default": {"description": "Error", "schema": {"$ref": "#/definitions/ErrorResponse"}},
            },
        }
    }


paths = {
    # --- account structure -------------------------------------------------
    "/v1/me": op("GetMe", "Get authenticated user",
                 "Returns the Snapchat user the connection is signed in as.", [], "MeResponse"),
    "/v1/me/organizations": op(
        "ListOrganizations", "List organizations",
        "Lists the organizations the user belongs to, optionally with their ad accounts.",
        [query("with_ad_accounts", "Include ad accounts", "Embed each organization's ad accounts.",
               type_="boolean", default=True, visibility="important")],
        "OrganizationsResponse"),
    "/v1/organizations/{organization_id}/adaccounts": op(
        "ListAdAccounts", "List ad accounts", "Lists all ad accounts in an organization.",
        [ORG_ID], "AdAccountsResponse"),
    "/v1/adaccounts/{ad_account_id}": op(
        "GetAdAccount", "Get ad account", "Returns one ad account (currency, time zone, status).",
        [AD_ACCOUNT_ID], "AdAccountsResponse"),
    # --- campaigns ---------------------------------------------------------
    "/v1/adaccounts/{ad_account_id}/campaigns": op(
        "ListCampaigns", "List campaigns", "Lists all campaigns in an ad account.",
        [AD_ACCOUNT_ID] + PAGING, "CampaignsResponse"),
    "/v1/campaigns/{campaign_id}": op(
        "GetCampaign", "Get campaign", "Returns one campaign.", [CAMPAIGN_ID], "CampaignsResponse"),
    # --- ad squads ---------------------------------------------------------
    "/v1/adaccounts/{ad_account_id}/adsquads": op(
        "ListAdSquadsByAdAccount", "List ad squads in ad account", "Lists all ad squads in an ad account.",
        [AD_ACCOUNT_ID] + PAGING, "AdSquadsResponse"),
    "/v1/campaigns/{campaign_id}/adsquads": op(
        "ListAdSquadsByCampaign", "List ad squads in campaign", "Lists the ad squads of a campaign.",
        [CAMPAIGN_ID] + PAGING, "AdSquadsResponse"),
    "/v1/adsquads/{ad_squad_id}": op(
        "GetAdSquad", "Get ad squad", "Returns one ad squad, including targeting and budget.",
        [AD_SQUAD_ID], "AdSquadsResponse"),
    # --- ads ---------------------------------------------------------------
    "/v1/adaccounts/{ad_account_id}/ads": op(
        "ListAdsByAdAccount", "List ads in ad account", "Lists all ads in an ad account.",
        [AD_ACCOUNT_ID] + PAGING, "AdsResponse"),
    "/v1/adsquads/{ad_squad_id}/ads": op(
        "ListAdsByAdSquad", "List ads in ad squad", "Lists the ads of an ad squad.",
        [AD_SQUAD_ID] + PAGING, "AdsResponse"),
    "/v1/ads/{ad_id}": op("GetAd", "Get ad", "Returns one ad.", [AD_ID], "AdsResponse"),
    # --- creatives ---------------------------------------------------------
    "/v1/adaccounts/{ad_account_id}/creatives": op(
        "ListCreatives", "List creatives", "Lists all creatives in an ad account.",
        [AD_ACCOUNT_ID] + PAGING, "CreativesResponse"),
    "/v1/creatives/{creative_id}": op(
        "GetCreative", "Get creative", "Returns one creative (headline, call to action, landing URL).",
        [CREATIVE_ID], "CreativesResponse"),
    # --- insights ----------------------------------------------------------
    "/v1/adaccounts/{ad_account_id}/stats": op(
        "GetAdAccountStats", "Get ad account stats",
        "Performance metrics for an ad account; use breakdown=campaign for per-campaign rows.",
        [AD_ACCOUNT_ID] + stats_params(["campaign"]), "StatsResponse"),
    "/v1/campaigns/{campaign_id}/stats": op(
        "GetCampaignStats", "Get campaign stats",
        "Performance metrics for a campaign; use breakdown=adsquad or ad for child rows.",
        [CAMPAIGN_ID] + stats_params(["adsquad", "ad"]), "StatsResponse"),
    "/v1/adsquads/{ad_squad_id}/stats": op(
        "GetAdSquadStats", "Get ad squad stats",
        "Performance metrics for an ad squad; use breakdown=ad for per-ad rows.",
        [AD_SQUAD_ID] + stats_params(["ad"]), "StatsResponse"),
    "/v1/ads/{ad_id}/stats": op(
        "GetAdStats", "Get ad stats", "Performance metrics for a single ad.",
        [AD_ID] + stats_params(None), "StatsResponse"),
    "/v1/{entity_type}/{entity_id}/stats_report": op(
        "GetStatsReport", "Get async stats report",
        "Polls an async stats report; when status is COMPLETED, result holds a download URL valid for 7 days.",
        [
            {**path_param("entity_type", "Level", "The level the report was requested on."),
             "enum": ["adaccounts", "campaigns", "adsquads", "ads"], "default": "adaccounts"},
            path_param("entity_id", "Entity ID", "ID of the ad account, campaign, ad squad or ad."),
            query("report_run_id", "Report run ID", "report_run_id returned by the async stats request.",
                  required=True, visibility="important"),
        ],
        "StatsReportResponse"),
}


def obj(props, **extra):
    return {"type": "object", "properties": props, **extra}


S = {"type": "string"}
I = {"type": "integer", "format": "int64"}
B = {"type": "boolean"}
DT = {"type": "string", "format": "date-time"}
STRS = {"type": "array", "items": S}


def prop(schema, summary, description=None):
    p = dict(schema)
    p["x-ms-summary"] = summary
    if description:
        p["description"] = description
    return p


ENVELOPE = {
    "request_status": prop(S, "Request status"),
    "request_id": prop(S, "Request ID"),
}
PAGING_SCHEMA = prop(obj({"next_link": prop(S, "Next page link")}), "Paging")


def list_response(collection, singular, ref):
    return obj({
        **ENVELOPE,
        collection: {"type": "array", "items": obj({
            "sub_request_status": prop(S, "Sub request status"),
            singular: {"$ref": f"#/definitions/{ref}"},
        })},
        "paging": PAGING_SCHEMA,
    })


COMMON = {
    "id": prop(S, "ID"),
    "name": prop(S, "Name"),
    "status": prop(S, "Status", "ACTIVE or PAUSED."),
    "created_at": prop(DT, "Created at"),
    "updated_at": prop(DT, "Updated at"),
}

metrics = {
    "impressions": prop(I, "Impressions"),
    "swipes": prop(I, "Swipes"),
    "spend": prop(I, "Spend (micro)", "Spend in micro-currency; divide by 1,000,000."),
    "video_views": prop(I, "Video views"),
    "screen_time_millis": prop(I, "Screen time (ms)"),
    "quartile_1": prop(I, "25% views"),
    "quartile_2": prop(I, "50% views"),
    "quartile_3": prop(I, "75% views"),
    "view_completion": prop(I, "Completed views"),
    "uniques": prop(I, "Reach"),
    "frequency": prop({"type": "number"}, "Frequency"),
    "conversion_purchases": prop(I, "Purchases"),
    "conversion_purchases_value": prop(I, "Purchase value (micro)"),
    "conversion_sign_ups": prop(I, "Sign ups"),
    "conversion_add_cart": prop(I, "Add to cart"),
    "conversion_page_views": prop(I, "Page views"),
}
STATS = obj(metrics, additionalProperties=True, **{"x-ms-summary": "Stats"})

stat_body = {
    "id": prop(S, "Entity ID"),
    "type": prop(S, "Entity type"),
    "granularity": prop(S, "Granularity"),
    "start_time": prop(DT, "Start time"),
    "end_time": prop(DT, "End time"),
    "finalized_data_end_time": prop(DT, "Finalized data end time"),
    "stats": STATS,
    "timeseries": {"type": "array", "x-ms-summary": "Time series", "items": obj({
        "start_time": prop(DT, "Period start"),
        "end_time": prop(DT, "Period end"),
        "stats": STATS,
    })},
    "breakdown_stats": prop(obj({}, additionalProperties=True), "Breakdown stats",
                            "Child entity rows keyed by level (campaign, adsquad, ad)."),
}

definitions = {
    "ErrorResponse": obj({
        **ENVELOPE,
        "debug_message": prop(S, "Debug message"),
        "display_message": prop(S, "Display message"),
        "error_code": prop(S, "Error code"),
    }),
    "MeResponse": obj({**ENVELOPE, "me": obj({
        "id": prop(S, "User ID"),
        "email": prop(S, "Email"),
        "display_name": prop(S, "Display name"),
        "organization_id": prop(S, "Organization ID"),
    })}),
    "Organization": obj({
        **COMMON,
        "type": prop(S, "Type"),
        "country": prop(S, "Country"),
        "ad_accounts": {"type": "array", "x-ms-summary": "Ad accounts",
                        "items": {"$ref": "#/definitions/AdAccount"}},
    }),
    "AdAccount": obj({
        **COMMON,
        "type": prop(S, "Type"),
        "organization_id": prop(S, "Organization ID"),
        "currency": prop(S, "Currency"),
        "timezone": prop(S, "Time zone"),
        "advertiser": prop(S, "Advertiser"),
        "billing_type": prop(S, "Billing type"),
        "funding_source_ids": prop(STRS, "Funding source IDs"),
    }),
    "Campaign": obj({
        **COMMON,
        "ad_account_id": prop(S, "Ad account ID"),
        "objective": prop(S, "Objective"),
        "buy_model": prop(S, "Buy model"),
        "start_time": prop(DT, "Start time"),
        "end_time": prop(DT, "End time"),
        "daily_budget_micro": prop(I, "Daily budget (micro)"),
        "lifetime_spend_cap_micro": prop(I, "Lifetime spend cap (micro)"),
        "delivery_status": prop(STRS, "Delivery status"),
        "objective_v2_properties": prop(obj({}, additionalProperties=True), "Objective properties"),
    }),
    "AdSquad": obj({
        **COMMON,
        "campaign_id": prop(S, "Campaign ID"),
        "type": prop(S, "Type"),
        "placement_v2": prop(obj({}, additionalProperties=True), "Placement"),
        "targeting": prop(obj({}, additionalProperties=True), "Targeting"),
        "billing_event": prop(S, "Billing event"),
        "optimization_goal": prop(S, "Optimization goal"),
        "bid_strategy": prop(S, "Bid strategy"),
        "bid_micro": prop(I, "Bid (micro)"),
        "daily_budget_micro": prop(I, "Daily budget (micro)"),
        "lifetime_budget_micro": prop(I, "Lifetime budget (micro)"),
        "start_time": prop(DT, "Start time"),
        "end_time": prop(DT, "End time"),
        "pacing_type": prop(S, "Pacing type"),
        "pixel_id": prop(S, "Pixel ID"),
        "delivery_status": prop(STRS, "Delivery status"),
    }),
    "Ad": obj({
        **COMMON,
        "ad_squad_id": prop(S, "Ad squad ID"),
        "creative_id": prop(S, "Creative ID"),
        "type": prop(S, "Type"),
        "render_type": prop(S, "Render type"),
        "review_status": prop(S, "Review status"),
        "review_status_reasons": prop(STRS, "Review status reasons"),
        "delivery_status": prop(STRS, "Delivery status"),
    }),
    "Creative": obj({
        **COMMON,
        "ad_account_id": prop(S, "Ad account ID"),
        "type": prop(S, "Type"),
        "headline": prop(S, "Headline"),
        "brand_name": prop(S, "Brand name"),
        "call_to_action": prop(S, "Call to action"),
        "shareable": prop(B, "Shareable"),
        "render_type": prop(S, "Render type"),
        "review_status": prop(S, "Review status"),
        "top_snap_media_id": prop(S, "Top snap media ID"),
        "web_view_properties": prop(obj({"url": prop(S, "Landing URL")}, additionalProperties=True),
                                    "Web view properties"),
        "deep_link_properties": prop(obj({}, additionalProperties=True), "Deep link properties"),
        "app_install_properties": prop(obj({}, additionalProperties=True), "App install properties"),
    }),
    "OrganizationsResponse": list_response("organizations", "organization", "Organization"),
    "AdAccountsResponse": list_response("adaccounts", "adaccount", "AdAccount"),
    "CampaignsResponse": list_response("campaigns", "campaign", "Campaign"),
    "AdSquadsResponse": list_response("adsquads", "adsquad", "AdSquad"),
    "AdsResponse": list_response("ads", "ad", "Ad"),
    "CreativesResponse": list_response("creatives", "creative", "Creative"),
    "StatsResponse": obj({
        **ENVELOPE,
        "report_run_id": prop(S, "Report run ID", "Returned instead of stats when async=true."),
        "timeseries_stats": {"type": "array", "x-ms-summary": "Time series stats", "items": obj({
            "sub_request_status": prop(S, "Sub request status"),
            "timeseries_stat": obj(stat_body),
        })},
        "total_stats": {"type": "array", "x-ms-summary": "Total stats", "items": obj({
            "sub_request_status": prop(S, "Sub request status"),
            "total_stat": obj(stat_body),
        })},
        "paging": PAGING_SCHEMA,
    }),
    "StatsReportResponse": obj({
        **ENVELOPE,
        "async_stats_reports": {"type": "array", "items": obj({
            "sub_request_status": prop(S, "Sub request status"),
            "async_stats_report": obj({
                "report_run_id": prop(S, "Report run ID"),
                "async_status": prop(S, "Report status", "STARTED, RUNNING or COMPLETED."),
                "result": prop(S, "Download URL"),
            }, additionalProperties=True),
        })},
    }),
}

swagger = {
    "swagger": "2.0",
    "info": {
        "title": "Snap",
        "description": "Read-only access to Snapchat Marketing API campaigns, their structure "
                       "(organizations, ad accounts, ad squads, ads, creatives) and performance stats.",
        "version": "1.0.0",
        "contact": {"name": "Al Sanidi Marketing", "email": "sa2@alsanidi.com.sa"},
    },
    "host": "adsapi.snapchat.com",
    "basePath": "/",
    "schemes": ["https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "paths": paths,
    "definitions": definitions,
    "securityDefinitions": {
        "oauth2_auth": {
            "type": "oauth2",
            "flow": "accessCode",
            "authorizationUrl": "https://accounts.snapchat.com/login/oauth2/authorize",
            "tokenUrl": "https://accounts.snapchat.com/login/oauth2/access_token",
            "scopes": {"snapchat-marketing-api": "snapchat-marketing-api"},
        }
    },
    "security": [{"oauth2_auth": ["snapchat-marketing-api"]}],
    "tags": [],
    "x-ms-connector-metadata": [
        {"propertyName": "Website", "propertyValue": "https://forbusiness.snapchat.com"},
        {"propertyName": "Privacy policy", "propertyValue": "https://values.snap.com/privacy/privacy-policy"},
        {"propertyName": "Categories", "propertyValue": "Marketing"},
    ],
}

(HERE / "apiDefinition.swagger.json").write_text(json.dumps(swagger, indent=2) + "\n")
print(f"Wrote {len(paths)} operations")
