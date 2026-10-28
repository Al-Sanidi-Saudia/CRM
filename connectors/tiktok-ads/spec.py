"""Single source of truth for the TikTok Ads integration.

Each table lists its columns as (column, label, section, kind, source):
  column  - Dataverse column suffix; logical name is sanidi_<column>. Also the key the connector returns
            for that value, so flows map item/sanidi_<column> = row[<column>].
  section - form section the column is placed in (see FORMS).
  kind    - how the connector converts the TikTok value, and the Dataverse type it lands in:
              str    text                     id     id -> text (numbers too)
              int    whole number             dec    decimal
              money  currency (account currency, as TikTok sends it)
              pct    percentage -> decimal    bool   yes/no
              date   "YYYY-MM-DD HH:MM:SS" (UTC) -> date time
              enum   choice                   enums  string[] of enum values -> multi-select choice
              strs   string[] / number[] -> multiline, one per line
              json   object / object[] -> multiline JSON
              now    sync time                raw    full TikTok object (JSON)
              info   from /advertiser/info/ (text)
  source  - TikTok field (top level of the list item), the metric name, or None.

Fields and their enum values come from fields_v1.3.json (python3 fetch_docs.py). Choice options are every
documented value, numbered from 1 in the order listed there, labelled with the TikTok value.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
API_VERSION = "v1.3"
PREFIX = "sanidi_"
CATALOG = json.loads((HERE / "fields_v1.3.json").read_text())

# Checked live (2026-10-28, both ad accounts): fields TikTok returns that the v1.3 docs don't list, and enum values
# it sends that the docs don't list. Added to the catalog here so fetch_docs.py can still regenerate it.
UNDOCUMENTED_FIELDS = {  # level -> field -> (TikTok type, form section, label)
    "adgroup": {
        "category_id": ("string", "promotion", "Category ID"),
        "package": ("string", "promotion", "App Package"),
        "adgroup_app_profile_page_type": ("string", "promotion", "App Profile Page Type"),
        "keywords": ("object[]", "placements", "Keywords"),
    },
    "ad": {
        "ad_ref_pixel_id": ("number", "tracking", "Reference Pixel ID"),
        "carousel_image_labels": ("object[]", "format", "Carousel Image Labels"),
        "landing_page_urls": ("string[]", "destination", "Landing Page URLs"),
        "product_info": ("object", "products", "Product Info"),
    },
}
UNDOCUMENTED_ENUM_VALUES = {  # (level, field) -> values appended after the documented ones (keeps option numbers)
    ("campaign", "app_promotion_type"): ["UNSET"],
    ("adgroup", "placements"): ["PLACEMENT_TOPBUZZ"],
    ("adgroup", "budget_mode"): ["BUDGET_MODE_DYNAMIC_DAILY_BUDGET"],
    ("adgroup", "creative_material_mode"): ["CATALOG_SALES"],
    ("ad", "identity_type"): ["UNSET"],
    ("ad", "creative_type"): ["SHOPPING_CATALOG_PAGE"],
}
for _level, _fields in UNDOCUMENTED_FIELDS.items():
    for _field, (_type, _, _) in _fields.items():
        CATALOG[_level][_field] = {"type": _type, "enum": [], "undocumented": True,
                                   "description": "Returned by the API, not in the v1.3 docs."}
for (_level, _field), _values in UNDOCUMENTED_ENUM_VALUES.items():
    CATALOG[_level][_field]["enum"] += [v for v in _values if v not in CATALOG[_level][_field]["enum"]]

ACRONYMS = {
    "id": "ID", "ids": "IDs", "url": "URL", "urls": "URLs", "rta": "RTA", "roas": "ROAS", "skan": "SKAN",
    "cpa": "CPA", "cpm": "CPM", "cpv": "CPV", "cpc": "CPC", "cpr": "CPR", "bc": "BC", "ios": "iOS", "ios14": "iOS 14",
    "rf": "R&F", "utm": "UTM", "cta": "CTA", "vbo": "VBO", "po": "PO", "aigc": "AIGC", "hfss": "HFSS", "lhf": "LHF",
    "isp": "ISP", "cpp": "CPP", "vast": "VAST", "sku": "SKU", "tiktok": "TikTok", "topview": "TopView",
    "pangle": "Pangle", "aco": "ACO", "app": "App", "uri": "URI", "tt": "TikTok", "v2": "v2",
}

# Labels that read better than the generated ones (TikTok field -> label).
LABELS = {
    "create_time": "Created On (TikTok)", "modify_time": "Modified On (TikTok)",
    "is_smart_performance_campaign": "Smart Performance Campaign", "is_search_campaign": "Search Campaign",
    "is_advanced_dedicated_campaign": "Advanced Dedicated Campaign", "is_new_structure": "Is New Structure",
    "disable_skan_campaign": "SKAN Disabled", "campaign_app_profile_page_state": "App Profile Page State",
    "adgroup_app_profile_page_state": "App Profile Page State", "campaign_product_source": "Product Source",
    "budget_optimize_on": "Campaign Budget Optimization", "rf_campaign_type": "R&F Campaign Type",
    "postback_window_mode": "SKAN Postback Window Mode", "po_number": "PO Number",
    "adgroup_id": "Ad Group ID", "adgroup_name": "Ad Group Name", "identity_authorized_bc_id": "Identity BC ID",
    "catalog_authorized_bc_id": "Catalog BC ID", "store_authorized_bc_id": "Store BC ID",
    "shopping_ads_retargeting_actions_days": "Shopping Retargeting Action Days",
    "shopping_ads_retargeting_type": "Shopping Retargeting Type",
    "shopping_ads_retargeting_custom_audience_relation": "Shopping Retargeting Audience Relation",
    "included_custom_actions": "Shopping Retargeting Included Actions",
    "excluded_custom_actions": "Shopping Retargeting Excluded Actions",
    "actions": "Behaviors", "smart_interest_behavior_enabled": "Smart Interests & Behaviors",
    "included_pangle_audience_package_ids": "Included Pangle Audience Packages",
    "excluded_pangle_audience_package_ids": "Excluded Pangle Audience Packages",
    "auto_targeting_enabled": "Auto Targeting Enabled (deprecated)",
    "targeting_expansion": "Targeting Expansion (deprecated)", "conversion_window": "Conversion Window (deprecated)",
    "is_hfss": "HFSS Product", "is_lhf_compliance": "LHF Compliance", "predict_impression": "Predicted Impressions (k)",
    "topview_reach_range": "TopView Reach Range (k)", "pre_discount_cpm": "TopView Pre-discount CPM",
    "cpm": "TopView Estimated CPM", "discount_type": "TopView Discount Type", "discount_amount": "TopView Discount Amount",
    "discount_percentage": "TopView Discount (%)", "pre_discount_budget": "TopView Pre-discount Budget",
    "frequency": "Frequency Cap", "frequency_schedule": "Frequency Cap Days", "deep_cpa_bid": "Deep CPA Bid",
    "next_day_retention": "Next Day Retention", "rf_estimated_cpr": "R&F Estimated CPR",
    "rf_estimated_frequency": "R&F Estimated Frequency", "rf_purchased_type": "R&F Purchased Type",
    "skip_learning_phase": "Skip Learning Phase", "ad_id_v2": "Ad ID v2", "smart_plus_ad_id": "Smart+ Ad ID",
    "is_aco": "Smart Creative (ACO)", "tiktok_item_id": "TikTok Post ID", "call_to_action_id": "CTA Portfolio ID",
    "card_id": "Creative Portfolio ID", "creative_auto_enhancement_strategy_list": "Creative Auto-enhancements",
    "product_display_field_list": "Product Display Fields", "avatar_icon_web_uri": "Avatar Icon",
    "vast_moat_enabled": "Moat Viewability Enabled", "viewability_postbid_partner": "Viewability Partner",
    "viewability_vast_url": "Viewability VAST URL", "brand_safety_postbid_partner": "Brand Safety Post-bid Partner",
    "brand_safety_vast_url": "Brand Safety VAST URL", "tracking_offline_event_set_ids": "Tracking Offline Event Set IDs",
    "disclaimer_clickable_texts": "Clickable Disclaimers", "shopping_ads_video_package_id": "Shopping Video Package ID",
    "shopping_ads_deeplink_type": "Shopping Deeplink Type", "shopping_ads_fallback_type": "Shopping Fallback Type",
    "item_duet_status": "Duet Status", "item_stitch_status": "Stitch Status", "end_card_cta": "End Card CTA",
    "zipcode_ids": "Zip Code IDs", "household_income": "Household Income", "device_price_ranges": "Device Price Ranges",
    "min_android_version": "Min Android Version", "min_ios_version": "Min iOS Version",
    "ios14_targeting": "iOS 14 Targeting", "ios14_quota_type": "iOS 14 Quota Type",
    "tiktok_subplacements": "TikTok Subplacements", "blocked_pangle_app_ids": "Blocked Pangle App IDs",
    "comment_disabled": "Comments Disabled", "video_download_disabled": "Video Download Disabled",
    "share_disabled": "Sharing Disabled", "inventory_filter_enabled": "Inventory Filter Enabled",
    "deep_funnel_event_source_id": "Deep Funnel Event Source ID",
    "messaging_app_account_id": "Messaging App Account ID", "app_config": "App Config",
    "creative_material_mode": "Creative Material Mode", "cpv_video_duration": "CPV Video Duration",
    "vbo_window": "VBO Window", "bid_display_mode": "Bid Display Mode", "statistic_type": "Statistic Type",
    "tracking_pixel_id": "Tracking Pixel ID", "page_id": "Page ID",
}

# Column suffixes that differ from the field name without underscores: metric-name clashes and names that would
# exceed Dataverse's length limit (currency columns also get a "_base" twin).
COLUMN_NAMES = {
    "frequency": "frequencycap", "cpm": "topviewcpm",
    "shopping_ads_retargeting_custom_audience_relation": "shoppingretargetingaudiencerelation",
    "shopping_ads_retargeting_actions_days": "shoppingretargetingactiondays",
    "included_pangle_audience_package_ids": "includedpangleaudiencepackages",
    "excluded_pangle_audience_package_ids": "excludedpangleaudiencepackages",
    "creative_auto_enhancement_strategy_list": "creativeautoenhancements",
}
MAX_COLUMN = 38  # sanidi_ + 38 + _base stays within 50 characters

MONEY = {"budget", "scheduled_budget", "bid_price", "conversion_bid_price", "deep_cpa_bid", "pre_discount_cpm", "cpm",
         "discount_amount", "pre_discount_budget", "rf_estimated_cpr"}
INTS = {"shopping_ads_retargeting_actions_days", "predict_impression", "purchased_impression", "purchased_reach",
        "frequency", "frequency_schedule", "carousel_image_index"}
IDS_AS_NUMBER = {"page_id", "tracking_pixel_id"}
DATES = {"create_time", "modify_time", "schedule_start_time", "schedule_end_time"}

# Sections per level: section key -> TikTok fields, in form order. Every documented field is listed exactly once.
SECTIONS = {
    "campaign": {
        "identity": ["campaign_name", "campaign_id", "advertiser_id", "@advertiser_name", "@currency", "@timezone",
                     "campaign_system_origin", "create_time", "modify_time", "po_number", "is_new_structure"],
        "status": ["operation_status", "secondary_status"],
        "objective": ["objective_type", "virtual_objective_type", "objective", "app_promotion_type", "sales_destination",
                      "campaign_type", "campaign_automation_type", "is_smart_performance_campaign", "is_search_campaign",
                      "is_advanced_dedicated_campaign", "rf_campaign_type", "campaign_product_source", "catalog_enabled",
                      "special_industries", "app_id", "campaign_app_profile_page_state", "disable_skan_campaign",
                      "bid_align_type", "postback_window_mode"],
        "budget": ["budget_mode", "budget", "budget_optimize_on"],
        "bidding": ["bid_type", "deep_bid_type", "roas_bid", "optimization_goal", "rta_id", "rta_bid_enabled",
                    "rta_product_selection_enabled"],
    },
    "adgroup": {
        "identity": ["adgroup_name", "adgroup_id", "campaign_id", "campaign_name", "advertiser_id",
                     "campaign_system_origin", "campaign_automation_type", "is_smart_performance_campaign",
                     "create_time", "modify_time", "is_new_structure", "split_test_group_id", "split_test_status"],
        "status": ["operation_status", "secondary_status", "skip_learning_phase"],
        "promotion": ["promotion_type", "promotion_target_type", "promotion_website_type", "messaging_app_type",
                      "messaging_app_account_id", "phone_region_code", "phone_region_calling_code", "phone_number",
                      "app_id", "app_type", "app_download_url", "app_config", "pixel_id", "optimization_event",
                      "custom_conversion_id", "secondary_optimization_event", "message_event_set_id",
                      "deep_funnel_optimization_status", "deep_funnel_event_source", "deep_funnel_event_source_id",
                      "deep_funnel_optimization_event"],
        "shopping": ["shopping_ads_type", "product_source", "catalog_id", "catalog_authorized_bc_id", "store_id",
                     "store_authorized_bc_id", "identity_id", "identity_type", "identity_authorized_bc_id",
                     "shopping_ads_retargeting_type", "shopping_ads_retargeting_actions_days",
                     "shopping_ads_retargeting_custom_audience_relation", "included_custom_actions",
                     "excluded_custom_actions"],
        "placements": ["placement_type", "placements", "tiktok_subplacements", "search_result_enabled",
                       "automated_keywords_enabled", "search_keywords", "blocked_pangle_app_ids", "comment_disabled",
                       "video_download_disabled", "share_disabled"],
        "audience": ["location_ids", "zipcode_ids", "languages", "gender", "age_groups", "spending_power",
                     "household_income", "audience_ids", "excluded_audience_ids", "smart_audience_enabled",
                     "audience_type", "audience_rule", "saved_audience_id", "interest_category_ids",
                     "interest_keyword_ids", "purchase_intention_keyword_ids", "actions",
                     "smart_interest_behavior_enabled", "included_pangle_audience_package_ids",
                     "excluded_pangle_audience_package_ids", "auto_targeting_enabled", "targeting_expansion",
                     "contextual_tag_ids"],
        "devices": ["operating_systems", "min_android_version", "min_ios_version", "ios14_targeting", "ios14_quota_type",
                    "device_model_ids", "network_types", "carrier_ids", "isp_ids", "device_price_ranges"],
        "brandsafety": ["brand_safety_type", "brand_safety_partner", "inventory_filter_enabled",
                        "category_exclusion_ids", "vertical_sensitivity_id", "is_hfss", "is_lhf_compliance"],
        "budget": ["budget_mode", "budget", "scheduled_budget", "schedule_type", "schedule_start_time",
                   "schedule_end_time", "dayparting", "pacing", "delivery_mode", "schedule_infos"],
        "bidding": ["optimization_goal", "billing_event", "bid_type", "bid_price", "conversion_bid_price",
                    "deep_bid_type", "roas_bid", "deep_cpa_bid", "vbo_window", "bid_display_mode",
                    "cpv_video_duration", "next_day_retention", "statistic_type", "frequency", "frequency_schedule",
                    "creative_material_mode", "adgroup_app_profile_page_state", "feed_type"],
        "attribution": ["click_attribution_window", "engaged_view_attribution_window", "view_attribution_window",
                        "attribution_event_count", "conversion_window"],
        "reservation": ["rf_purchased_type", "purchased_impression", "purchased_reach", "rf_estimated_cpr",
                        "rf_estimated_frequency", "predict_impression", "topview_reach_range", "pre_discount_cpm",
                        "cpm", "discount_type", "discount_amount", "discount_percentage", "pre_discount_budget"],
    },
    "ad": {
        "identity": ["ad_name", "ad_id", "ad_id_v2", "smart_plus_ad_id", "adgroup_id", "adgroup_name", "campaign_id",
                     "campaign_name", "advertiser_id", "campaign_automation_type", "campaign_system_origin",
                     "create_time", "modify_time", "is_new_structure"],
        "status": ["operation_status", "secondary_status", "is_aco", "creative_authorized"],
        "format": ["ad_format", "creative_type", "dynamic_format", "vertical_video_strategy", "video_id", "image_ids",
                   "carousel_image_index", "music_id", "end_card_cta", "auto_disclaimer_types",
                   "product_display_field_list", "creative_auto_enhancement_strategy_list", "aigc_disclosure_type",
                   "playable_url"],
        "text": ["ad_text", "ad_texts", "call_to_action", "call_to_action_id", "card_id", "display_name", "app_name",
                 "avatar_icon_web_uri", "profile_image_url"],
        "spark": ["identity_id", "identity_type", "identity_authorized_bc_id", "tiktok_item_id",
                  "promotional_music_disabled", "item_duet_status", "item_stitch_status", "dark_post_status",
                  "branded_content_disabled"],
        "products": ["catalog_id", "product_specific_type", "item_group_ids", "product_set_id", "sku_ids",
                     "vehicle_ids", "showcase_products", "shopping_ads_video_package_id"],
        "destination": ["landing_page_url", "utm_params", "page_id", "cpp_url", "tiktok_page_category",
                        "phone_region_code", "phone_region_calling_code", "phone_number", "deeplink", "deeplink_type",
                        "deeplink_format_type", "shopping_ads_deeplink_type", "deeplink_utm_params",
                        "shopping_ads_fallback_type", "fallback_type", "dynamic_destination", "auto_message_id"],
        "disclaimers": ["disclaimer_type", "disclaimer_text", "disclaimer_clickable_texts"],
        "tracking": ["tracking_pixel_id", "tracking_app_id", "tracking_offline_event_set_ids",
                     "tracking_message_event_set_id", "optimization_event", "vast_moat_enabled",
                     "viewability_postbid_partner", "viewability_vast_url", "brand_safety_postbid_partner",
                     "brand_safety_vast_url", "impression_tracking_url", "click_tracking_url", "comment_disabled",
                     "video_download_disabled", "share_disabled"],
    },
}

# From /advertiser/info/ (campaign level only).
ADVERTISER_INFO = {
    "@advertiser_name": ("advertisername", "Advertiser Name", "name"),
    "@currency": ("currency", "Currency", "currency"),
    "@timezone": ("accounttimezone", "Account Time Zone", "display_timezone"),
}

# Insight metric groups (agreed scope) -> form section key and label, in form order.
METRIC_SECTIONS = [
    ("core", "insightsdelivery", "Delivery & Cost (all time)"),
    ("video", "insightsvideo", "Video (all time)"),
    ("engagement", "insightsengagement", "Engagement (all time)"),
    ("social", "insightssocial", "Social (all time)"),
    ("website", "insightswebsite", "Website Conversions (all time)"),
    ("attribution", "insightsattribution", "Attribution (all time)"),
]
# Corrections to the metric labels in TikTok's documentation.
METRIC_LABELS = {
    "total_complete_payment_rate": "Purchase value (website)",
    "total_page_browse_view_value": "Total Page Browse Value",
    "value_per_page_browse_view": "Value per Page Browse",
}
METRIC_MONEY_OVERRIDE = {"total_complete_payment_rate"}  # a value, despite the name
# Refused by TikTok at campaign, ad group and ad level on both ad accounts (checked live 2026-10-28): cash/voucher
# spend are "invalid metric fields", custom page events have "no relation" to these levels. Their columns stay
# (the tables are already in production and a patch can't remove columns) but they are not requested, not written
# and not shown on forms or views.
REFUSED_METRICS = {"cash_spend", "voucher_spend", "custom_page_events", "cost_per_custom_page_event",
                   "custom_page_event_rate", "value_per_custom_page_event", "custom_page_events_value"}


def metric_kind(name):
    if name in METRIC_MONEY_OVERRIDE:
        return "money"
    if "roas" in name:
        return "dec"
    if name == "ctr" or name.endswith(("_rate", "_rate_v2", "_per_click")):
        return "pct"
    if (name in ("spend", "billed_cost", "cash_spend", "voucher_spend", "cpc", "cpm")
            or name.startswith(("cost_per", "value_per", "avg_value_per", "total_value_per", "real_time_cost_per",
                                "website_cost_per", "website_value_per"))
            or name.endswith("_value")):
        return "money"
    if name in ("frequency", "average_video_play", "average_video_play_per_user", "conversion", "real_time_conversion",
                "result", "real_time_result", "secondary_goal_result"):
        return "dec"
    return "int"


def label_for(field):
    for fields in UNDOCUMENTED_FIELDS.values():
        if field in fields:
            return fields[field][2]
    if field in LABELS:
        return LABELS[field]
    words = field[3:].split("_") if field.startswith("is_") else field.split("_")
    return " ".join(ACRONYMS.get(w, w.capitalize()) for w in words)


def column_for(field):
    return COLUMN_NAMES.get(field, field.replace("_", ""))


def field_kind(level, field):
    info = CATALOG[level][field]
    typ = info["type"].lower()
    if field in DATES:
        return "date"
    if typ == "boolean":
        return "bool"
    if typ.startswith("object"):
        return "json"
    if typ.endswith("[]"):
        return "enums" if info["enum"] else "strs"
    if info["enum"]:
        return "enum"
    if field in MONEY:
        return "money"
    if field in INTS:
        return "int"
    if field in IDS_AS_NUMBER or field.endswith("_id"):
        return "id"
    if typ in ("float", "number", "integer"):
        return "dec"
    return "str"


SYNC = [
    ("lastsyncedon", "Last Synced On", "sync", "now", None),
    ("insightslastsyncedon", "Insights Last Synced On", "sync", "now", "insights"),
    ("rawpayload", "Raw Payload", "sync", "raw", None),
]


def is_refused(column):
    """True for the column of a metric TikTok refuses (see REFUSED_METRICS)."""
    return column[2].startswith("insights") and column[4] in REFUSED_METRICS


def synced_metrics():
    return [c for c in metrics() if c[4] not in REFUSED_METRICS]


def metrics():
    out = []
    for group, section, _ in METRIC_SECTIONS:
        for name, m in CATALOG["metrics"].items():
            if m["group"] == group:
                out.append((name.replace("_", ""), METRIC_LABELS.get(name, m["label"]), section, metric_kind(name), name))
    return out


def level_columns(level):
    cols = []
    sections = {s: list(f) for s, f in SECTIONS[level].items()}
    for field, (_, section, _) in UNDOCUMENTED_FIELDS.get(level, {}).items():
        sections[section].append(field)
    for section, fields in sections.items():
        for f in fields:
            if f in ADVERTISER_INFO:
                col, lbl, src = ADVERTISER_INFO[f]
                cols.append((col, lbl, section, "info", src))
            else:
                cols.append((column_for(f), label_for(f), section, field_kind(level, f), f))
    return cols + metrics() + SYNC


TABLES = {
    "tiktokcampaign": {
        "display": "TikTok Campaign", "plural": "TikTok Campaigns", "level": "campaign",
        "description": "TikTok campaigns synced from the TikTok API for Business by the Get TikTok Campaigns flow.",
        "primary": "campaignname", "tiktokid": "campaignid", "parent": None,
    },
    "tiktokadgroup": {
        "display": "TikTok Ad Group", "plural": "TikTok Ad Groups", "level": "adgroup",
        "description": "TikTok ad groups synced from the TikTok API for Business by the Get TikTok Ad Groups flow.",
        "primary": "adgroupname", "tiktokid": "adgroupid", "parent": ("tiktokcampaign", "TikTok Campaign"),
    },
    "tiktokadvertisement": {
        "display": "TikTok Advertisement", "plural": "TikTok Advertisements", "level": "ad",
        "description": "TikTok ads synced from the TikTok API for Business by the Get TikTok Advertisements flow.",
        "primary": "adname", "tiktokid": "adid", "parent": ("tiktokadgroup", "TikTok Ad Group"),
    },
}
for _t in TABLES.values():
    _t["columns"] = level_columns(_t["level"])

MULTILINE_KINDS = {"strs", "json", "raw"}
LONG_TEXT = ("url", "deeplink", "dayparting", "uri")


def max_length(column, kind):
    """Text length used both for the Dataverse column and for truncation in the connector."""
    if kind == "raw":
        return 100000
    if kind in MULTILINE_KINDS:
        return 20000
    if kind in ("str", "id", "info"):
        if any(k in column for k in LONG_TEXT):
            return 2000
        return 100 if kind == "id" else 400
    return 0


def enum_options(level, field):
    """Every documented value of the field's enum, numbered from 1."""
    return [{"label": v, "value": i} for i, v in enumerate(CATALOG[level][field]["enum"], start=1)]


def description(section, kind, src):
    if kind == "now" and src == "insights":
        return "When the Get TikTok Insights flow last wrote the insight columns of this record."
    if kind == "now":
        return "When the TikTok sync last wrote this record."
    if kind == "raw":
        return "Full TikTok API object (JSON) from the last sync."
    if kind == "info":
        return f"TikTok: /advertiser/info/ {src}."
    if section.startswith("insights"):
        return f"TikTok (all time): {src}."
    return f"TikTok: {src}."


# Main form layout: tab label -> [(section key, section label)]. "@related:<table>" adds a sub-grid of child records.
_INSIGHTS_TAB = ("Insights", [(s, lbl) for _, s, lbl in METRIC_SECTIONS])
FORMS = {
    "tiktokcampaign": [
        ("General", [("identity", "Identity"), ("status", "Status"), ("objective", "Objective & Type")]),
        ("Budget & Bidding", [("budget", "Budget"), ("bidding", "Bidding")]),
        _INSIGHTS_TAB,
        ("Related", [("@related:tiktokadgroup", "TikTok Ad Groups")]),
        ("Sync", [("sync", "Sync")]),
    ],
    "tiktokadgroup": [
        ("General", [("identity", "Identity"), ("status", "Status")]),
        ("Promotion & Shopping", [("promotion", "Promotion & Conversion"), ("shopping", "Shopping")]),
        ("Targeting", [("placements", "Placements & Search"), ("audience", "Audience"), ("devices", "Devices"),
                       ("brandsafety", "Brand Safety")]),
        ("Budget & Bidding", [("budget", "Budget & Schedule"), ("bidding", "Bidding & Optimization"),
                              ("attribution", "Attribution"), ("reservation", "Reach & Frequency / TopView")]),
        _INSIGHTS_TAB,
        ("Related", [("@related:tiktokadvertisement", "TikTok Advertisements")]),
        ("Sync", [("sync", "Sync")]),
    ],
    "tiktokadvertisement": [
        ("General", [("identity", "Identity"), ("status", "Status")]),
        ("Creative", [("format", "Format & Creative"), ("text", "Text & CTA"), ("spark", "Identity & Spark Ads"),
                      ("products", "Products")]),
        ("Destination & Tracking", [("destination", "Destination"), ("disclaimers", "Disclaimers"),
                                    ("tracking", "Tracking & Measurement")]),
        _INSIGHTS_TAB,
        ("Sync", [("sync", "Sync")]),
    ],
}

# Active view: these columns first ("@lookup" = parent lookup), then every other column except Raw Payload.
VIEW_MAIN = {
    "tiktokcampaign": ["campaignname", "operationstatus", "secondarystatus", "objectivetype", "budgetmode", "budget",
                       "spend", "impressions", "clicks", "ctr", "conversion", "campaignid", "advertiserid",
                       "lastsyncedon"],
    "tiktokadgroup": ["adgroupname", "@lookup", "operationstatus", "secondarystatus", "optimizationgoal", "bidtype",
                      "budget", "spend", "impressions", "clicks", "conversion", "adgroupid", "lastsyncedon"],
    "tiktokadvertisement": ["adname", "@lookup", "operationstatus", "secondarystatus", "adformat", "calltoaction",
                            "landingpageurl", "spend", "impressions", "clicks", "conversion", "adid", "lastsyncedon"],
}


def check():
    """Every documented field placed once, unique and short enough column names."""
    for table, t in TABLES.items():
        level = t["level"]
        placed = [c[4] for c in t["columns"] if c[3] not in ("info", "now", "raw") and not c[2].startswith("insights")]
        documented = [f for f in CATALOG[level] if "." not in f]
        missing = sorted(set(documented) - set(placed))
        extra = sorted(set(placed) - set(documented))
        dup = sorted({f for f in placed if placed.count(f) > 1})
        cols = [c[0] for c in t["columns"]]
        dupcols = sorted({c for c in cols if cols.count(c) > 1})
        long = [c for c in cols if len(c) > MAX_COLUMN]
        assert not (missing or extra or dup or dupcols or long), (table, missing, extra, dup, dupcols, long)
        sections = {s for _, secs in FORMS[table] for s, _ in secs}
        unplaced = {c[2] for c in t["columns"]} - sections
        assert not unplaced, (table, unplaced)
    return True


if __name__ == "__main__":
    check()
    from collections import Counter
    for table, t in TABLES.items():
        kinds = Counter(c[3] for c in t["columns"])
        print(f"{PREFIX}{table}: {len(t['columns'])} columns {dict(kinds)}")
