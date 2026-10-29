"""Adds the custom-code operations to the Meta connector's definition (apiDefinition.swagger.json).

  python3 build_definition.py   # re-run after a change, commit the output

apiDefinition.swagger.json was exported from the live connector (sanidi_meta, 2026-10-29); every other operation is
kept exactly as exported. The operations listed in SCRIPT_OPERATIONS run in script.csx.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT_OPERATIONS = ["GetPeriodInsights"]


def query(name, summary, description, required=True, enum=None, default=None, visibility="important"):
    p = {"name": name, "in": "query", "required": required, "type": "string", "x-ms-summary": summary,
         "description": description, "x-ms-visibility": visibility}
    if enum:
        p["enum"] = enum
    if default:
        p["default"] = default
    return p


PERIOD_INSIGHTS = {"get": {
    "summary": "Get daily or monthly insights",
    "description": "Daily (time_increment=1) or monthly (time_increment=monthly, totalled by Meta) insights for every "
                   "campaign, ad set or ad of an ad account, deleted and archived items included, all pages. Rows are "
                   "keyed like the Dataverse columns (purchases, purchase value, ROAS... taken from Meta's action "
                   "lists as in Get Meta Insights), plus date and rawpayload.",
    "operationId": "GetPeriodInsights",
    "parameters": [
        query("account_id", "Ad account ID", "Meta ad account ID, with or without act_."),
        query("level", "Level", "Level to report on.", enum=["campaign", "adset", "ad"], default="campaign"),
        query("period", "Period", "day: one row per day; month: one row per calendar month.",
              enum=["day", "month"], default="day"),
        query("start_date", "Start date", "YYYY-MM-DD, ad account time zone."),
        query("end_date", "End date", "YYYY-MM-DD, inclusive."),
    ],
    "responses": {"200": {"description": "Rows", "schema": {"type": "object", "properties": {
        "account_id": {"type": "string", "x-ms-summary": "Account ID"},
        "level": {"type": "string", "x-ms-summary": "Level"},
        "period": {"type": "string", "x-ms-summary": "Period"},
        "start_date": {"type": "string", "x-ms-summary": "Start date"},
        "end_date": {"type": "string", "x-ms-summary": "End date"},
        "row_count": {"type": "integer", "x-ms-summary": "Row count"},
        "rows": {"type": "array", "x-ms-summary": "Rows", "items": {"type": "object", "additionalProperties": True}},
    }}}, "default": {"description": "Error"}},
}}


def main():
    path = HERE / "apiDefinition.swagger.json"
    swagger = json.loads(path.read_text())
    swagger["paths"]["/period-insights"] = PERIOD_INSIGHTS
    path.write_text(json.dumps(swagger, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(swagger['paths'])} paths; script operations: {', '.join(SCRIPT_OPERATIONS)}")


if __name__ == "__main__":
    main()
