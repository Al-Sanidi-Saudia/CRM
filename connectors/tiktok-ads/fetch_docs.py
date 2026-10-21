"""Builds fields_v1.3.json from the TikTok API for Business v1.3 documentation.

  python3 fetch_docs.py

Reads the response fields of Get campaigns / Get ad groups / Get ads (name, type, description, enum values) and
the enumeration page, through the same JSON endpoint the documentation site uses. Enum values come from the field's
own description, or from the Enumerations page when the description links to it (ENUM_SECTIONS).
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
NODE = "https://business-api.tiktok.com/gateway/api/doc/client/node/get/v2/"
DOC_KEY = "c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b"  # docs site key, public
ENUMERATIONS_DOC = "1737174886619138"
ENDPOINTS = {"campaign": "get-campaigns", "adgroup": "get-ad-groups", "ad": "get-ads"}
METRICS_DOC = "1751443967255553"  # Basic reports - Supported metrics
# Metric groups synced to Dataverse (agreed scope): heading path on the metrics page -> group key
METRIC_GROUPS = {
    "Regular metrics > Core metrics": "core",
    "Regular metrics > Interaction metrics > Videos metrics": "video",
    "Regular metrics > Interaction metrics > Clicks metrics": "engagement",
    "Regular metrics > Interaction metrics > Social metrics": "social",
    "Regular metrics > Conversions metrics > Website metrics": "website",
    "Regular metrics > Conversions metrics > Attribution metrics": "attribution",
}

# field -> section of the Enumerations page, per level (None = all levels)
ENUM_SECTIONS = {
    "objective_type": "Advertising Objective (`objective_type`)",
    "bid_type": "Bidding Strategy (`bid_type`)",
    "deep_bid_type": "Deep Event Bidding Strategy (`deep_bid_type`)",
    "optimization_goal": "Optimization Goal (`optimization_goal`)",
    "budget_mode": "Budget Mode (`budget_mode`)",
    "billing_event": "Billing Event (`billing_event` or `billing_events`)",
    "pacing": "Ad Delivery Speed (`pacing`)",
    "placements": "Placement (`placements`)",
    "promotion_type": "Promotion Type (Optimization location) (`promotion_type`)",
    "age_groups": "Age Group (`age_groups`)",
    "gender": "Gender (`gender`)",
    "operating_systems": "Operating System (`operating_systems`)",
    "network_types": "Connection Type (`network_types`)",
    "schedule_type": "Schedule Type (`schedule_type`)",
    "rf_purchased_type": "Reach & Frequency Buy Type (`rf_purchased_type`)",
    "call_to_action": "Call-to-action (`call_to_action`)",
    "ad_format": "Creative Type (`ad_format`)",
    "audience_type": "App Retargeting Audience Type (`audience_type` for `/adgroup/create/`)",
    "conversion_window": "Conversion Window",
}
SECONDARY_STATUS = {"campaign": "Campaign Status - Secondary Status", "adgroup": "Ad group status - secondary status",
                    "ad": "Ad status - secondary status"}


def node(**params):
    url = NODE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    if data.get("code") != 0:
        raise SystemExit(f"{params}: {data.get('msg')}")
    return data["data"]["content_data"]


def table_rows(md):
    """(depth, name, type, description) of every table row, depth = number of leading '#'."""
    for line in md.splitlines():
        m = re.match(r"^(#*)\|(.*)$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = re.sub(r"\{[^}]*\}|\(deprecated\)", "", cells[0]).strip()
        if re.fullmatch(r"[a-z0-9_]+", name):
            yield len(m.group(1)), name, cells[1], "|".join(cells[2:])


def plain(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&#91;", "[").replace("&#93;", "]").replace("&#123;", "{").replace("&#125;", "}")
    return re.sub(r"\s+", " ", text).strip()


def inline_enums(desc):
    values = re.findall(r"<li>\s*`([A-Z][A-Z0-9_]+)`", desc)
    if not values:
        m = re.search(r"Enum(?:\s*values?)?\s*:?\s*((?:`\s*[A-Z][A-Z0-9_]+\s*`[^`<]{0,40})+)", desc)
        if m:
            values = re.findall(r"`\s*([A-Z][A-Z0-9_]+)\s*`", m.group(1))
    if not values:
        m = re.search(r"(?:either|between|values include|bid for)[^.]*?((?:`\s*[A-Z][A-Z0-9_]+\s*`[^`]{0,60}){2,})", desc)
        if m:
            values = re.findall(r"`\s*([A-Z][A-Z0-9_]+)\s*`", m.group(1))
    out = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def enumerations():
    md = node(identify_key=DOC_KEY, doc_id=ENUMERATIONS_DOC, language="ENGLISH")
    sections, current = {}, None
    for line in md.splitlines():
        h = re.match(r"^## (.+)$", line)
        if h:
            current = h.group(1).strip()
            sections[current] = []
            continue
        m = re.match(r"^#*\|\s*`?([A-Z0-9][A-Z0-9_]*)`?\s*\|", line)
        if m and current and m.group(1) not in sections[current]:
            sections[current].append(m.group(1))
    return sections


def metrics():
    """Metric name -> {group, label, description} for the groups in METRIC_GROUPS, in page order."""
    md = node(identify_key=DOC_KEY, doc_id=METRICS_DOC, language="ENGLISH")
    heading, out = [], {}
    for line in md.splitlines():
        h = re.match(r"^(#{1,4}) (.+)$", line)
        if h:
            heading = heading[:len(h.group(1)) - 1] + [h.group(2).strip()]
            continue
        group = METRIC_GROUPS.get(" > ".join(heading))
        m = re.match(r"^#*\|(.*)$", line)
        if not (group and m):
            continue
        cells = [c.strip() for c in m.group(1).strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"[a-z0-9_]+", cells[0]) and cells[0] not in out:
            out[cells[0]] = {"group": group, "label": plain(cells[2]), "description": plain("|".join(cells[3:]))}
    return out


def main():
    enum_doc = enumerations()
    catalog = {}
    for level, slug in ENDPOINTS.items():
        md = node(content_slug=slug)
        response = md[md.find("## Response"):]
        response = response[:response.find("### Example")]
        fields, parents = {}, {}
        for depth, name, typ, desc in table_rows(response):
            parents[depth] = name
            if depth < 2 or parents.get(1) != "list":
                continue
            path = ".".join([parents[d] for d in range(2, depth)] + [name])
            enums = inline_enums(desc)
            section = SECONDARY_STATUS[level] if name == "secondary_status" and depth == 2 else ENUM_SECTIONS.get(name)
            if section and depth == 2:
                enums = enum_doc[section] + [v for v in enums if v not in enum_doc[section]]
            if typ.strip().lower() == "boolean":
                enums = []
            fields[path] = {"type": typ.strip().replace(" ", ""), "enum": enums, "description": plain(desc)}
        catalog[level] = fields
        print(f"{level}: {sum(1 for p in fields if '.' not in p)} fields, "
              f"{sum(1 for p, f in fields.items() if '.' not in p and f['enum'])} with enum values")
    catalog["metrics"] = metrics()
    print(f"metrics: {len(catalog['metrics'])}")
    (HERE / "fields_v1.3.json").write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
