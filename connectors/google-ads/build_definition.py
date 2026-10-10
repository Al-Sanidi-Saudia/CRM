"""Generates apiDefinition.swagger.json and the OPS block of script.csx for the Google Ads connector.

Run: python3 build_definition.py  (re-run after any change to spec.py, commit the output)
"""
import json
import re
from pathlib import Path

import spec

HERE = Path(__file__).parent


def path_param(name, summary, description):
    return {
        "name": name, "in": "path", "required": True, "type": "string",
        "x-ms-summary": summary, "description": description, "x-ms-url-encoding": "single",
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


CUSTOMER_ID = path_param("customer_id", "Customer ID",
                         "Google Ads customer (account) ID, 10 digits. Dashes are allowed.")
LOGIN_CUSTOMER_ID = {
    "name": "login-customer-id", "in": "header", "required": False, "type": "string",
    "x-ms-summary": "Manager customer ID",
    "description": "Manager (MCC) account ID to access the customer through. Required when the signed-in "
                   "user reaches the account via a manager account.",
    "x-ms-visibility": "important",
}
STATUS = query("status", "Status", "Filter by status. ALL includes removed items so their status syncs too.",
               enum=["ALL", "NOT_REMOVED", "ENABLED", "PAUSED", "REMOVED"], default="ALL")
INCLUDE_METRICS = query("include_metrics", "Include all-time metrics",
                        "Add all-time performance metrics (impressions, clicks, cost, conversions...).",
                        type_="boolean", default=True)
MAX_ROWS = query("max_rows", "Max rows", "Stop after this many rows. Omit to return everything.", type_="integer")
CAMPAIGN_FILTER = query("campaign_id", "Campaign ID", "Only return items of this campaign.", visibility="important")
AD_GROUP_FILTER = query("ad_group_id", "Ad group ID", "Only return items of this ad group.", visibility="important")

KIND_SCHEMA = {
    "str": {"type": "string"}, "id": {"type": "string"}, "int": {"type": "integer", "format": "int64"},
    "dec": {"type": "number"}, "money": {"type": "number"}, "cur": {"type": "number"},
    "pct": {"type": "number"}, "pctmicros": {"type": "number"}, "bool": {"type": "boolean"},
    "date": {"type": "string", "format": "date-time"}, "enum": {"type": "string"},
    "enums": {"type": "array", "items": {"type": "string"}}, "strs": {"type": "string"},
    "json": {"type": "string"}, "texts": {"type": "string"}, "assets": {"type": "string"},
    "now": {"type": "string", "format": "date-time"}, "raw": {"type": "string"},
}

KIND_NOTE = {
    "money": "In account currency (converted from micros).", "cur": "In account currency.",
    "pct": "Percent (0-100).", "pctmicros": "Percent (0-100).", "enums": "Google Ads enum values.",
    "strs": "One value per line.", "texts": "One text per line.", "assets": "Asset resource names, one per line.",
    "json": "JSON.", "date": "Account time zone.", "now": "When the connector read the data (UTC).",
    "raw": "Full Google Ads row as JSON (without metrics).",
}


def row_schema(columns):
    props = {}
    for col, label, _, kind, src in columns:
        p = dict(KIND_SCHEMA[kind])
        p["x-ms-summary"] = label
        note = KIND_NOTE.get(kind, "")
        if kind == "enum":
            note = "One of: " + ", ".join(o["label"] for o in spec.enum_options(src)) + "."
        if src:
            note = (note + " Source: " + ", ".join(spec.sources(src)) + ".").strip()
        if note:
            p["description"] = note
        props[col] = p
    return {"type": "object", "properties": props}


def list_response(ref):
    return {"type": "object", "properties": {
        "customer_id": {"type": "string", "x-ms-summary": "Customer ID"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "metrics_error": {"type": "string", "x-ms-summary": "Metrics error",
                          "description": "Set when metrics could not be read; the rows are still returned."},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"$ref": f"#/definitions/{ref}"}},
    }}


def op(method, operation_id, summary, description, params, schema_ref, body=None):
    o = {
        "operationId": operation_id, "summary": summary, "description": description,
        "parameters": params + ([body] if body else []),
        "responses": {
            "200": {"description": "OK", "schema": {"$ref": f"#/definitions/{schema_ref}"}},
            "default": {"description": "Error", "schema": {"$ref": "#/definitions/ErrorResponse"}},
        },
    }
    return {method: o}


# ---- operations map for script.csx -------------------------------------------------------------

def script_columns(columns):
    return [[c, kind, spec.sources(src), spec.max_length(c, kind)] for c, _, _, kind, src in columns]


ENTITY_OPS = {
    "ListCampaigns": ("googleadscampaign", {"campaign_id": "campaign.id"}),
    "ListAdGroups": ("googleadsadgroup", {"campaign_id": "campaign.id", "ad_group_id": "ad_group.id"}),
    "ListAds": ("googleadsadvertisement", {"campaign_id": "campaign.id", "ad_group_id": "ad_group.id"}),
}

ops = {}
for operation_id, (table, filters) in ENTITY_OPS.items():
    t = spec.TABLES[table]
    ops[operation_id] = {
        "resource": t["resource"],
        "key": f"{t['resource']}.resource_name",
        "status": f"{t['resource']}.status",
        "filters": filters,
        "columns": script_columns(t["columns"]),
    }

PERF_IDENTITY = {
    "campaign": [("campaignid", "Campaign ID", "", "id", "campaign.id"),
                 ("campaignname", "Campaign Name", "", "str", "campaign.name")],
    "ad_group": [("adgroupid", "Ad Group ID", "", "id", "ad_group.id"),
                 ("adgroupname", "Ad Group Name", "", "str", "ad_group.name"),
                 ("campaignid", "Campaign ID", "", "id", "campaign.id")],
    "ad": [("adid", "Ad ID", "", "id", "ad_group_ad.ad.id"),
           ("adname", "Ad Name", "", "str", "ad_group_ad.ad.name"),
           ("adgroupid", "Ad Group ID", "", "id", "ad_group.id"),
           ("campaignid", "Campaign ID", "", "id", "campaign.id")],
}
PERF_RESOURCE = {"campaign": "campaign", "ad_group": "ad_group", "ad": "ad_group_ad"}
PERF_COLUMNS = {
    level: [("customerid", "Customer ID", "", "id", "customer.id")] + PERF_IDENTITY[level]
    + spec.metrics(PERF_RESOURCE[level])
    for level in PERF_RESOURCE
}
ops["$performance"] = {
    level: {
        "resource": PERF_RESOURCE[level],
        "filters": {"campaign_id": "campaign.id"} if level == "campaign"
        else {"campaign_id": "campaign.id", "ad_group_id": "ad_group.id"},
        "columns": script_columns(PERF_COLUMNS[level]),
    }
    for level in PERF_RESOURCE
}

# ---- swagger -------------------------------------------------------------------------------------

paths = {
    "/customers": op("get", "ListAccessibleCustomers", "List accessible customers",
                     "Lists the customer IDs the signed-in Google user can access directly.", [],
                     "AccessibleCustomersResponse"),
    "/customers/{customer_id}/clients": op(
        "get", "ListClientAccounts", "List client accounts",
        "Lists the accounts under a customer. For a manager (MCC) this is its client accounts; "
        "for a regular account it is the account itself.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID,
         query("include_managers", "Include managers", "Also return manager accounts.", type_="boolean", default=False),
         query("include_hidden", "Include hidden", "Also return hidden accounts.", type_="boolean", default=False),
         query("include_all_levels", "All levels", "Return the whole tree, not just direct children.",
               type_="boolean", default=False)],
        "ClientAccountsResponse"),
    "/customers/{customer_id}/campaigns": op(
        "get", "ListCampaigns", "List campaigns",
        "Lists campaigns with their budget, bidding, network, tracking and channel settings, plus all-time metrics.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID, STATUS, CAMPAIGN_FILTER, INCLUDE_METRICS, MAX_ROWS], "CampaignsResponse"),
    "/customers/{customer_id}/adgroups": op(
        "get", "ListAdGroups", "List ad groups",
        "Lists ad groups with their bids and targeting settings, plus all-time metrics.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID, CAMPAIGN_FILTER, AD_GROUP_FILTER, STATUS, INCLUDE_METRICS, MAX_ROWS],
        "AdGroupsResponse"),
    "/customers/{customer_id}/ads": op(
        "get", "ListAds", "List ads",
        "Lists ads (ad group ads) with their creative, policy review and URLs, plus all-time metrics.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID, AD_GROUP_FILTER, CAMPAIGN_FILTER, STATUS, INCLUDE_METRICS, MAX_ROWS],
        "AdsResponse"),
    "/customers/{customer_id}/performance": op(
        "get", "GetPerformance", "Get performance",
        "Performance metrics per campaign, ad group or ad for a date range, optionally per day/week/month.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID,
         query("level", "Level", "Level to report on.", enum=["campaign", "ad_group", "ad"], default="campaign",
               required=True, visibility="important"),
         query("date_range", "Date range", "Predefined range. Ignored when start and end dates are set.",
               enum=["ALL_TIME", "TODAY", "YESTERDAY", "LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS",
                     "THIS_MONTH", "LAST_MONTH", "LAST_BUSINESS_WEEK", "LAST_WEEK_SUN_SAT", "LAST_WEEK_MON_SUN",
                     "THIS_WEEK_SUN_TODAY", "THIS_WEEK_MON_TODAY"],
               default="LAST_30_DAYS", visibility="important"),
         query("start_date", "Start date", "YYYY-MM-DD, inclusive.", format="date"),
         query("end_date", "End date", "YYYY-MM-DD, inclusive.", format="date"),
         query("granularity", "Granularity", "TOTAL returns one row per entity.",
               enum=["TOTAL", "DAILY", "WEEKLY", "MONTHLY"], default="TOTAL", visibility="important"),
         query("breakdown", "Breakdown", "Split rows by device or network.",
               enum=["NONE", "DEVICE", "AD_NETWORK_TYPE"], default="NONE"),
         CAMPAIGN_FILTER, AD_GROUP_FILTER, MAX_ROWS],
        "PerformanceResponse"),
    "/customers/{customer_id}/query": op(
        "post", "RunQuery", "Run GAQL query",
        "Runs any Google Ads Query Language (GAQL) SELECT and returns all pages.",
        [CUSTOMER_ID, LOGIN_CUSTOMER_ID], "QueryResponse",
        body={"name": "body", "in": "body", "required": True, "schema": {
            "type": "object", "required": ["query"], "properties": {
                "query": {"type": "string", "x-ms-summary": "GAQL query",
                          "description": "e.g. SELECT campaign.id, metrics.clicks FROM campaign "
                                         "WHERE segments.date DURING LAST_7_DAYS"},
                "max_rows": {"type": "integer", "x-ms-summary": "Max rows", "default": 10000},
                "flatten": {"type": "boolean", "x-ms-summary": "Flatten rows", "default": True,
                            "description": "Return rows as flat snake_case keys (campaign_id, metrics_clicks)."},
            }}}),
}

perf_props = {}
for cols in PERF_COLUMNS.values():
    perf_props.update(row_schema(cols)["properties"])
for k, label in [("date", "Date"), ("week", "Week"), ("month", "Month"), ("device", "Device"),
                 ("ad_network_type", "Ad network type")]:
    perf_props[k] = {"type": "string", "x-ms-summary": label}

definitions = {
    "ErrorResponse": {"type": "object", "properties": {"error": {"type": "object", "properties": {
        "code": {"type": "integer", "x-ms-summary": "Code"},
        "message": {"type": "string", "x-ms-summary": "Message"},
        "status": {"type": "string", "x-ms-summary": "Status"},
        "details": {"type": "array", "items": {"type": "object"}, "x-ms-summary": "Details"},
    }}}},
    "AccessibleCustomersResponse": {"type": "object", "properties": {
        "customer_ids": {"type": "array", "items": {"type": "string"}, "x-ms-summary": "Customer IDs"},
        "resource_names": {"type": "array", "items": {"type": "string"}, "x-ms-summary": "Resource names"},
    }},
    "ClientAccount": {"type": "object", "properties": {
        "customer_id": {"type": "string", "x-ms-summary": "Customer ID"},
        "name": {"type": "string", "x-ms-summary": "Account name"},
        "currency_code": {"type": "string", "x-ms-summary": "Currency code"},
        "time_zone": {"type": "string", "x-ms-summary": "Time zone"},
        "manager": {"type": "boolean", "x-ms-summary": "Is manager"},
        "test_account": {"type": "boolean", "x-ms-summary": "Is test account"},
        "level": {"type": "integer", "x-ms-summary": "Level"},
        "status": {"type": "string", "x-ms-summary": "Status"},
        "hidden": {"type": "boolean", "x-ms-summary": "Hidden"},
        "resource_name": {"type": "string", "x-ms-summary": "Resource name"},
    }},
    "ClientAccountsResponse": list_response("ClientAccount"),
    "Campaign": row_schema(spec.TABLES["googleadscampaign"]["columns"]),
    "CampaignsResponse": list_response("Campaign"),
    "AdGroup": row_schema(spec.TABLES["googleadsadgroup"]["columns"]),
    "AdGroupsResponse": list_response("AdGroup"),
    "Ad": row_schema(spec.TABLES["googleadsadvertisement"]["columns"]),
    "AdsResponse": list_response("Ad"),
    "PerformanceRow": {"type": "object", "properties": perf_props},
    "PerformanceResponse": {**list_response("PerformanceRow")},
    "QueryResponse": {"type": "object", "properties": {
        "customer_id": {"type": "string", "x-ms-summary": "Customer ID"},
        "query": {"type": "string", "x-ms-summary": "Query"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "rows": {"type": "array", "x-ms-summary": "Rows",
                 "items": {"type": "object", "additionalProperties": True}},
    }},
}
definitions["PerformanceResponse"]["properties"]["query"] = {"type": "string", "x-ms-summary": "GAQL query"}

swagger = {
    "swagger": "2.0",
    "info": {
        "title": "Google Ads",
        "description": "Read-only access to Google Ads API campaigns, ad groups, ads and their performance.",
        "version": "1.0.0",
        "contact": {"name": "Al Sanidi Marketing", "email": "sa2@alsanidi.com.sa"},
    },
    "host": "googleads.googleapis.com",
    "basePath": "/" + spec.API_VERSION,
    "schemes": ["https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "paths": paths,
    "definitions": definitions,
    "securityDefinitions": {
        "oauth2_auth": {
            "type": "oauth2", "flow": "accessCode",
            "authorizationUrl": "https://accounts.google.com/o/oauth2/v2/auth",
            "tokenUrl": "https://oauth2.googleapis.com/token",
            "scopes": {"https://www.googleapis.com/auth/adwords": "https://www.googleapis.com/auth/adwords"},
        }
    },
    "security": [{"oauth2_auth": ["https://www.googleapis.com/auth/adwords"]}],
    "tags": [],
    "x-ms-connector-metadata": [
        {"propertyName": "Website", "propertyValue": "https://ads.google.com"},
        {"propertyName": "Privacy policy", "propertyValue": "https://policies.google.com/privacy"},
        {"propertyName": "Categories", "propertyValue": "Marketing"},
    ],
}

(HERE / "apiDefinition.swagger.json").write_text(json.dumps(swagger, indent=2) + "\n")

script_path = HERE / "script.csx"
ops_literal = json.dumps(ops, separators=(",", ":")).replace('"', '""')
script = re.sub(
    r"(// BEGIN GENERATED OPS\n).*?(\n\s*// END GENERATED OPS)",
    lambda m: m.group(1) + f'    private const string OpsJson = @"{ops_literal}";' + m.group(2),
    script_path.read_text(), flags=re.S)
script_path.write_text(script)
print(f"Wrote {len(paths)} operations; script ops for {', '.join(k for k in ops if not k.startswith('$'))}")
