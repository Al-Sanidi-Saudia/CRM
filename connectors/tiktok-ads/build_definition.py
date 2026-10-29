"""Generates apiDefinition.swagger.json and the OPS block of script.csx for the TikTok connector.

Run: python3 build_definition.py  (re-run after any change to spec.py, commit the output)
"""
import json
import re
from pathlib import Path

import spec

HERE = Path(__file__).parent


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


ACCESS_TOKEN = {
    "name": "Access-Token", "in": "header", "required": True, "type": "string",
    "x-ms-summary": "Access token",
    "description": "TikTok long-term access token (environment variable TikTok Ads Access Token).",
    "x-ms-visibility": "important",
}
ADVERTISER_ID = query("advertiser_id", "Advertiser ID", "TikTok advertiser (ad account) ID.",
                      required=True, visibility="important")
INCLUDE_DELETED = query("include_deleted", "Include deleted",
                        "Also return deleted items (TikTok leaves them out by default).", type_="boolean", default=True)
MAX_ROWS = query("max_rows", "Max rows", "Stop after this many rows. Omit to return everything.", type_="integer")
CAMPAIGN_FILTER = query("campaign_id", "Campaign ID", "Only return items of this campaign.", visibility="important")
ADGROUP_FILTER = query("adgroup_id", "Ad group ID", "Only return items of this ad group.", visibility="important")

KIND_SCHEMA = {
    "str": {"type": "string"}, "id": {"type": "string"}, "info": {"type": "string"},
    "int": {"type": "integer", "format": "int64"}, "dec": {"type": "number"}, "money": {"type": "number"},
    "pct": {"type": "number"}, "bool": {"type": "boolean"}, "date": {"type": "string", "format": "date-time"},
    "enum": {"type": "string"}, "enums": {"type": "array", "items": {"type": "string"}},
    "strs": {"type": "string"}, "json": {"type": "string"},
    "now": {"type": "string", "format": "date-time"}, "raw": {"type": "string"},
}
KIND_NOTE = {
    "money": "In the ad account currency.", "pct": "Percent.", "enums": "TikTok enum values.",
    "strs": "One value per line.", "json": "JSON.", "date": "UTC.", "now": "When the connector read the data (UTC).",
    "raw": "Full TikTok object as JSON.",
}


def row_schema(level, columns):
    props = {}
    for col, label, section, kind, src in columns:
        p = dict(KIND_SCHEMA[kind])
        p["x-ms-summary"] = label
        note = KIND_NOTE.get(kind, "")
        if kind == "enum":
            note = "One of: " + ", ".join(o["label"] for o in spec.enum_options(level, src)) + "."
        if src and kind not in ("now", "raw"):
            note = (note + " Source: " + ("/advertiser/info/ " if kind == "info" else "") + src + ".").strip()
        if note:
            p["description"] = note
        props[col] = p
    return {"type": "object", "properties": props}


def is_metric(c):
    return c[2].startswith("insights") and c[3] != "now"


def entity_columns(table):
    return [c for c in spec.TABLES[table]["columns"] if not c[2].startswith("insights") and c[0] != "insightslastsyncedon"]


def list_response(ref):
    return {"type": "object", "properties": {
        "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"$ref": f"#/definitions/{ref}"}},
    }}


def op(method, operation_id, summary, description, params, schema_ref, body=None):
    return {method: {
        "operationId": operation_id, "summary": summary, "description": description,
        "parameters": params + ([body] if body else []),
        "responses": {
            "200": {"description": "OK", "schema": {"$ref": f"#/definitions/{schema_ref}"}},
            "default": {"description": "Error", "schema": {"$ref": "#/definitions/ErrorResponse"}},
        },
    }}


# ---- operations map for script.csx -------------------------------------------------------------

LEVELS = {  # level -> (table, TikTok path, list id field, filter query param -> TikTok filtering key)
    "campaign": ("tiktokcampaign", "campaign/get/", "campaign_id", {"campaign_id": "campaign_ids"}),
    "adgroup": ("tiktokadgroup", "adgroup/get/", "adgroup_id", {"campaign_id": "campaign_ids", "adgroup_id": "adgroup_ids"}),
    "ad": ("tiktokadvertisement", "ad/get/", "ad_id", {"campaign_id": "campaign_ids", "adgroup_id": "adgroup_ids"}),
}
INSIGHT_LEVELS = {  # level -> (report data level, dimension, id column)
    "campaign": ("AUCTION_CAMPAIGN", "campaign_id", "campaignid"),
    "adgroup": ("AUCTION_ADGROUP", "adgroup_id", "adgroupid"),
    "ad": ("AUCTION_AD", "ad_id", "adid"),
}

ops = {}
for level, (table, path, id_field, filters) in LEVELS.items():
    ops[level] = {
        "path": path, "id": id_field, "filters": filters,
        "columns": [[c, kind, src, spec.max_length(c, kind)] for c, _, _, kind, src in entity_columns(table)],
    }
ops["$metrics"] = [[c, kind, src] for c, _, _, kind, src in spec.synced_metrics()]
ops["$insights"] = {lvl: {"data_level": dl, "dimension": dim, "id_column": col}
                    for lvl, (dl, dim, col) in INSIGHT_LEVELS.items()}

# ---- swagger -------------------------------------------------------------------------------------

insight_props = {
    "campaignid": {"type": "string", "x-ms-summary": "Campaign ID", "description": "Set for level campaign."},
    "adgroupid": {"type": "string", "x-ms-summary": "Ad Group ID", "description": "Set for level adgroup."},
    "adid": {"type": "string", "x-ms-summary": "Ad ID", "description": "Set for level ad."},
    "advertiserid": {"type": "string", "x-ms-summary": "Advertiser ID"},
    "insightslastsyncedon": {"type": "string", "format": "date-time", "x-ms-summary": "Insights Last Synced On"},
}
insight_props.update(row_schema("campaign", spec.synced_metrics())["properties"])

paths = {
    "/oauth2/access_token/": op(
        "post", "GetAccessToken", "Get access token",
        "One-time setup: exchanges the authorization code from the advertiser authorization page for a long-term "
        "access token, and lists the advertiser IDs that were authorized. Store both in the environment variables.",
        [], "AccessTokenResponse",
        body={"name": "body", "in": "body", "required": True, "schema": {
            "type": "object", "required": ["app_id", "secret", "auth_code"], "properties": {
                "app_id": {"type": "string", "x-ms-summary": "App ID"},
                "secret": {"type": "string", "x-ms-summary": "App secret", "format": "password"},
                "auth_code": {"type": "string", "x-ms-summary": "Authorization code", "format": "password",
                              "description": "auth_code from the redirect URL; valid for 1 hour, single use."},
            }}}),
    "/oauth2/advertiser/get/": op(
        "get", "ListAuthorizedAdvertisers", "List authorized advertisers",
        "Lists the advertisers (ad accounts) the access token is authorized for.",
        [ACCESS_TOKEN,
         query("app_id", "App ID", "TikTok developer app ID.", required=True, visibility="important"),
         query("secret", "App secret", "TikTok developer app secret.", required=True, visibility="important",
               format="password")],
        "AuthorizedAdvertisersResponse"),
    "/advertiser/info/": op(
        "get", "GetAdvertiserInfo", "Get advertiser info",
        "Name, currency, time zone and status of an advertiser (ad account).",
        [ACCESS_TOKEN, ADVERTISER_ID], "AdvertiserInfo"),
    "/campaign/get/": op(
        "get", "ListCampaigns", "List campaigns",
        "Lists all campaigns of an advertiser with every field TikTok returns, including deleted ones.",
        [ACCESS_TOKEN, ADVERTISER_ID, CAMPAIGN_FILTER, INCLUDE_DELETED, MAX_ROWS], "CampaignsResponse"),
    "/adgroup/get/": op(
        "get", "ListAdGroups", "List ad groups",
        "Lists ad groups (all of the advertiser, or of one campaign) with every field TikTok returns, including deleted ones.",
        [ACCESS_TOKEN, ADVERTISER_ID, CAMPAIGN_FILTER, ADGROUP_FILTER, INCLUDE_DELETED, MAX_ROWS], "AdGroupsResponse"),
    "/ad/get/": op(
        "get", "ListAds", "List ads",
        "Lists ads (all of the advertiser, or of one ad group) with every field TikTok returns, including deleted ones.",
        [ACCESS_TOKEN, ADVERTISER_ID, ADGROUP_FILTER, CAMPAIGN_FILTER, INCLUDE_DELETED, MAX_ROWS], "AdsResponse"),
    "/insights/lifetime": op(
        "get", "GetLifetimeInsights", "Get lifetime insights",
        "All-time metrics (Core, Video, Clicks, Social, Website, Attribution) for every campaign, ad group or ad of "
        "an advertiser: one row per item, keyed like the Dataverse columns.",
        [ACCESS_TOKEN, ADVERTISER_ID,
         query("level", "Level", "Level to report on.", enum=["campaign", "adgroup", "ad"], default="campaign",
               required=True, visibility="important")],
        "InsightsResponse"),
    "/report/integrated/get/": op(
        "post", "RunReport", "Run report",
        "Runs any synchronous TikTok report (/report/integrated/get/) and returns all pages as flat rows.",
        [ACCESS_TOKEN], "ReportResponse",
        body={"name": "body", "in": "body", "required": True, "schema": {
            "type": "object", "required": ["advertiser_id", "dimensions"], "properties": {
                "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
                "report_type": {"type": "string", "x-ms-summary": "Report type", "default": "BASIC",
                                "enum": ["BASIC", "AUDIENCE", "PLAYABLE_MATERIAL", "CATALOG"]},
                "data_level": {"type": "string", "x-ms-summary": "Data level", "default": "AUCTION_CAMPAIGN",
                               "enum": ["AUCTION_ADVERTISER", "AUCTION_CAMPAIGN", "AUCTION_ADGROUP", "AUCTION_AD"]},
                "dimensions": {"type": "string", "x-ms-summary": "Dimensions (JSON)",
                               "description": "e.g. [\"campaign_id\", \"stat_time_day\"]"},
                "metrics": {"type": "string", "x-ms-summary": "Metrics (JSON)",
                            "description": "e.g. [\"spend\", \"impressions\", \"clicks\"]"},
                "filtering": {"type": "string", "x-ms-summary": "Filtering (JSON)"},
                "start_date": {"type": "string", "x-ms-summary": "Start date", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "x-ms-summary": "End date", "description": "YYYY-MM-DD"},
                "query_lifetime": {"type": "boolean", "x-ms-summary": "Lifetime", "default": False},
                "max_rows": {"type": "integer", "x-ms-summary": "Max rows", "default": 10000},
            }}}),
}

definitions = {
    "ErrorResponse": {"type": "object", "properties": {"error": {"type": "object", "properties": {
        "code": {"type": "integer", "x-ms-summary": "Code"},
        "message": {"type": "string", "x-ms-summary": "Message"},
        "status": {"type": "string", "x-ms-summary": "Status"},
    }}}},
    "AccessTokenResponse": {"type": "object", "properties": {
        "access_token": {"type": "string", "x-ms-summary": "Access token"},
        "scope": {"type": "array", "items": {"type": "integer"}, "x-ms-summary": "Scope"},
        "advertiser_ids": {"type": "array", "items": {"type": "string"}, "x-ms-summary": "Advertiser IDs"},
        "advertiser_ids_text": {"type": "string", "x-ms-summary": "Advertiser IDs (comma-separated)"},
    }},
    "AuthorizedAdvertisersResponse": {"type": "object", "properties": {
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "advertiser_ids_text": {"type": "string", "x-ms-summary": "Advertiser IDs (comma-separated)"},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"type": "object", "properties": {
            "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
            "advertiser_name": {"type": "string", "x-ms-summary": "Advertiser name"},
        }}},
    }},
    "AdvertiserInfo": {"type": "object", "properties": {
        "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
        "name": {"type": "string", "x-ms-summary": "Advertiser name"},
        "currency": {"type": "string", "x-ms-summary": "Currency"},
        "display_timezone": {"type": "string", "x-ms-summary": "Time zone"},
        "timezone": {"type": "string", "x-ms-summary": "Time zone (UTC offset)"},
        "status": {"type": "string", "x-ms-summary": "Status"},
        "company": {"type": "string", "x-ms-summary": "Company"},
        "country": {"type": "string", "x-ms-summary": "Country"},
    }},
    "Campaign": row_schema("campaign", entity_columns("tiktokcampaign")),
    "CampaignsResponse": list_response("Campaign"),
    "AdGroup": row_schema("adgroup", entity_columns("tiktokadgroup")),
    "AdGroupsResponse": list_response("AdGroup"),
    "Ad": row_schema("ad", entity_columns("tiktokadvertisement")),
    "AdsResponse": list_response("Ad"),
    "InsightsRow": {"type": "object", "properties": insight_props},
    "InsightsResponse": {"type": "object", "properties": {
        "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
        "level": {"type": "string", "x-ms-summary": "Level"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "metrics_error": {"type": "string", "x-ms-summary": "Metrics error",
                          "description": "Set when TikTok refused some metrics; the other metrics are still returned."},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"$ref": "#/definitions/InsightsRow"}},
    }},
    "ReportResponse": {"type": "object", "properties": {
        "advertiser_id": {"type": "string", "x-ms-summary": "Advertiser ID"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"type": "object", "additionalProperties": True}},
    }},
}

swagger = {
    "swagger": "2.0",
    "info": {
        "title": "TikTok",
        "description": "Read-only access to TikTok API for Business campaigns, ad groups, ads and their lifetime "
                       "insights. Pass the long-term access token to every action.",
        "version": "1.0.0",
        "contact": {"name": "Al Sanidi Marketing", "email": "sa2@alsanidi.com.sa"},
    },
    "host": "business-api.tiktok.com",
    "basePath": "/open_api/" + spec.API_VERSION,
    "schemes": ["https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "paths": paths,
    "definitions": definitions,
    "securityDefinitions": {},
    "security": [],
    "tags": [],
    "x-ms-connector-metadata": [
        {"propertyName": "Website", "propertyValue": "https://ads.tiktok.com"},
        {"propertyName": "Privacy policy", "propertyValue": "https://www.tiktok.com/legal/page/global/privacy-policy/en"},
        {"propertyName": "Categories", "propertyValue": "Marketing"},
    ],
}

if __name__ == "__main__":
    spec.check()
    (HERE / "apiDefinition.swagger.json").write_text(json.dumps(swagger, indent=2) + "\n")
    script_path = HERE / "script.csx"
    ops_literal = json.dumps(ops, separators=(",", ":")).replace('"', '""')
    script = re.sub(
        r"(// BEGIN GENERATED OPS\n).*?(\n\s*// END GENERATED OPS)",
        lambda m: m.group(1) + f'    private const string OpsJson = @"{ops_literal}";' + m.group(2),
        script_path.read_text(), flags=re.S)
    script_path.write_text(script)
    print(f"Wrote {len(paths)} operations; script ops for {', '.join(k for k in ops if not k.startswith('$'))}, "
          f"{len(ops['$metrics'])} metrics; script {len(script)} chars")
