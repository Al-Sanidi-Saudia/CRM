"""Builds an unmanaged solution package that creates or updates the "Snap Ad Squad" table
(sanidi_SnapAdSquad) in the "AlSanidi | Marketing" solution: columns, choices, the lookup
to Snap Campaign, alternate key, main form and views.

Field definitions come from https://developers.snap.com/marketing-api/Ads-API/ad-squads.
The package format is described in ../table_builder.py.

Run:
  python3 build_table_solution.py --template <template export zip> [--out SnapAdSquadTable.zip]
  pac solution import --path SnapAdSquadTable.zip --environment <env> --publish-changes
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from table_builder import TableSpec, build_package  # noqa: E402

DELIVERY_OPTIONSET = "sanidi_snapadsquaddeliverystatus"
PLATFORM_OPTIONSET = "sanidi_snapplatform"
POSITION_OPTIONSET = "sanidi_snapplacementposition"
CONTENT_OPTIONSET = "sanidi_snapcontenttype"
PROVIDER_OPTIONSET = "sanidi_snapmeasurementprovider"

DELIVERY_STATUS = [
    # Common to all Snap entities
    "PENDING", "VALID", "INVALID_NOT_ACTIVE", "INVALID_NOT_EFFECTIVE_ACTIVE", "INVALID_START_TIME",
    "INVALID_END_TIME", "INVALID_EFFECTIVE_START_TIME", "INVALID_EFFECTIVE_END_TIME", "INVALID_EFFECTIVE_DELETED",
    "INVALID_EFFECTIVE_INVALID", "INVALID_START_TIME_AFTER_END_TIME",
    # Ad squad
    "INVALID_TARGETING_REACH_STATUS", "INVALID_PENDING_TARGETING_REACH_STATUS", "INVALID_AD_SQUAD_HAS_NO_ACTIVE_ADS",
    "INVALID_AD_SQUAD_WIREOBJECT", "INVALID_INTERNAL_PLACEMENT", "INVALID_AD_SQUAD_HAS_UNSUPPORTED_AD_TYPE",
    "INVALID_UNSUPPORTED_AD_SQUAD_TYPE", "INVALID_AD_SQUAD_LIFETIME_SPEND_CAP",
    "INVALID_OVER_BUDGET_AD_SQUAD_FINALIZED_LIFETIME_SPEND", "INVALID_OVER_BUDGET_AD_SQUAD_REALTIME_LIFETIME_SPEND",
    "INVALID_AD_SQUAD_DAILY_SPEND_CAP", "INVALID_OVER_BUDGET_AD_SQUAD_DAILY_SPEND",
    "INVALID_AD_SQUAD_RESERVED_STATUS_NOT_ACTIVE", "NOT_DELIVERING_AD_CONTAINS_INVALID_AUDIENCE", "LEARNING_PHASE",
]
PLATFORMS = ["SNAPCHAT"]
POSITIONS = ["INTERSTITIAL_USER", "INTERSTITIAL_CONTENT", "INTERSTITIAL_SPOTLIGHT", "INSTREAM",
             "PUBLIC_STORIES_INSTREAM", "CHAT_FEED", "FEED", "CAMERA", "POST_CAPTURE_CAROUSEL"]
CONTENT_TYPES = ["NEWS", "ENTERTAINMENT", "SCIENCE_TECHNOLOGY", "BEAUTY_FASHION", "MENS_LIFESTYLE",
                 "WOMENS_LIFESTYLE", "GAMING", "GENERAL_LIFESTYLE", "FOOD", "SPORTS", "YOUNG_BOLD"]
PROVIDERS = ["DOUBLEVERIFY"]

# (logical name, display name, kind, extra, description); kinds are described in table_builder.py.
FIELDS = [
    ("sanidi_adsquadname", "Ad Squad Name", "text", 375, "Snap: name"),
    ("sanidi_adsquadid", "Ad Squad ID", "text", 100, "Snap: id"),
    ("sanidi_snapcampaign", "Snap Campaign", "lookup", "sanidi_SnapCampaign", "Parent campaign, linked by campaign_id"),
    ("sanidi_campaignid", "Campaign ID", "text", 100, "Snap: campaign_id"),
    ("sanidi_type", "Type", "choice", ["SNAP_ADS", "LENS", "FILTER"], "Snap: type"),
    ("sanidi_childadtype", "Child Ad Type", "choice",
     ["SNAP_AD", "LONGFORM_VIDEO", "APP_INSTALL", "REMOTE_WEBPAGE", "DEEP_LINK", "STORY", "AD_TO_LENS", "AD_TO_CALL",
      "AD_TO_MESSAGE", "FILTER", "LENS", "LENS_WEB_VIEW", "LENS_APP_INSTALL", "LENS_DEEP_LINK",
      "LENS_LONGFORM_VIDEO", "COLLECTION"], "Snap: child_ad_type"),
    ("sanidi_storyadcreativetype", "Story Ad Creative Type", "choice", ["APP_INSTALL", "WEB_VIEW", "DEEP_LINK"],
     "Snap: story_ad_creative_type"),
    ("sanidi_forcedviewsetting", "Forced View Setting", "choice", ["FULL_DURATION", "SIX_SECONDS", "NONE"],
     "Snap: forced_view_setting"),
    ("sanidi_status", "Status", "choice", ["ACTIVE", "PAUSED"], "Snap: status"),
    ("sanidi_deliverystatus", "Delivery Status", "multichoice", (DELIVERY_OPTIONSET, DELIVERY_STATUS),
     "Snap: delivery_status"),
    ("sanidi_reachandfrequencystatus", "Reach and Frequency Status", "choice", ["PENDING", "ACTIVE", "FAILED"],
     "Snap: reach_and_frequency_status"),
    ("sanidi_targetingreachstatus", "Targeting Reach Status", "text", 100, "Snap: targeting_reach_status"),
    ("sanidi_creationstate", "Creation State", "text", 100, "Snap: creation_state"),
    ("sanidi_deleted", "Deleted", "bool", None, "Snap: deleted"),
    ("sanidi_starttime", "Start Time", "datetime", None, "Snap: start_time"),
    ("sanidi_endtime", "End Time", "datetime", None, "Snap: end_time"),
    ("sanidi_createdat", "Created At", "datetime", None, "Snap: created_at"),
    ("sanidi_updatedat", "Updated At", "datetime", None, "Snap: updated_at"),
    ("sanidi_dailybudget", "Daily Budget", "money", None, "Snap: daily_budget_micro / 1,000,000"),
    ("sanidi_lifetimebudget", "Lifetime Budget", "money", None, "Snap: lifetime_budget_micro / 1,000,000"),
    ("sanidi_deliveryconstraint", "Delivery Constraint", "choice",
     ["DAILY_BUDGET", "LIFETIME_BUDGET", "REACH_AND_FREQUENCY"], "Snap: delivery_constraint"),
    ("sanidi_pacingtype", "Pacing Type", "choice", ["STANDARD", "ACCELERATED"], "Snap: pacing_type"),
    ("sanidi_bidstrategy", "Bid Strategy", "choice",
     ["AUTO_BID", "LOWEST_COST_WITH_MAX_BID", "MIN_ROAS", "TARGET_COST"], "Snap: bid_strategy"),
    ("sanidi_bid", "Bid", "money", None, "Snap: bid_micro / 1,000,000"),
    ("sanidi_billingevent", "Billing Event", "choice", ["IMPRESSION"], "Snap: billing_event"),
    ("sanidi_roasvalue", "ROAS Value", "decimal", None, "Snap: roas_value_micro / 1,000,000 (deprecated)"),
    ("sanidi_autobid", "Auto Bid", "bool", None, "Snap: auto_bid (deprecated)"),
    ("sanidi_targetbid", "Target Bid", "bool", None, "Snap: target_bid (deprecated)"),
    ("sanidi_optimizationgoal", "Optimization Goal", "choice",
     ["IMPRESSIONS", "SWIPES", "APP_INSTALLS", "VIDEO_VIEWS", "VIDEO_VIEWS_15_SEC", "USES", "STORY_OPENS",
      "PIXEL_PAGE_VIEW", "PIXEL_ADD_TO_CART", "LANDING_PAGE_VIEW", "LEAD_FORM_SUBMISSIONS", "PIXEL_PURCHASE",
      "PIXEL_SIGNUP", "APP_ADD_TO_CART", "APP_PURCHASE", "APP_SIGNUP"], "Snap: optimization_goal"),
    ("sanidi_conversionwindow", "Conversion Window", "choice", ["SWIPE_28DAY_VIEW_1DAY", "SWIPE_7DAY"],
     "Snap: conversion_window"),
    ("sanidi_reachgoal", "Reach Goal", "int", None, "Snap: reach_goal"),
    ("sanidi_impressiongoal", "Impression Goal", "int", None, "Snap: impression_goal"),
    ("sanidi_placementconfig", "Placement Config", "choice", ["AUTOMATIC", "CUSTOM"], "Snap: placement_v2.config"),
    ("sanidi_platforms", "Platforms", "multichoice", (PLATFORM_OPTIONSET, PLATFORMS), "Snap: placement_v2.platforms"),
    ("sanidi_snapchatpositions", "Snapchat Positions", "multichoice", (POSITION_OPTIONSET, POSITIONS),
     "Snap: placement_v2.snapchat_positions"),
    ("sanidi_includedcontenttypes", "Included Content Types", "multichoice", (CONTENT_OPTIONSET, CONTENT_TYPES),
     "Snap: placement_v2.inclusion.content_types"),
    ("sanidi_excludedcontenttypes", "Excluded Content Types", "multichoice", (CONTENT_OPTIONSET, CONTENT_TYPES),
     "Snap: placement_v2.exclusion.content_types"),
    ("sanidi_brandsafetyinventory", "Brand Safety Inventory", "choice", ["FULL_INVENTORY", "LIMITED_INVENTORY"],
     "Snap: brand_safety_config.inventory_option"),
    ("sanidi_targeting", "Targeting", "multiline", None, "Snap: targeting (JSON)"),
    ("sanidi_separatedtypes", "Separated Types", "text", 200, "Snap: separated_types, comma-joined"),
    ("sanidi_capandexclusionconfig", "Cap and Exclusion Config", "multiline", None,
     "Snap: cap_and_exclusion_config (JSON)"),
    ("sanidi_adschedulingconfig", "Ad Scheduling Config", "multiline", None, "Snap: ad_scheduling_config (JSON)"),
    ("sanidi_pixelid", "Pixel ID", "text", 100, "Snap: pixel_id"),
    ("sanidi_eventsources", "Event Sources", "multiline", None, "Snap: event_sources (JSON)"),
    ("sanidi_measurementproviders", "Measurement Providers", "multichoice", (PROVIDER_OPTIONSET, PROVIDERS),
     "Snap: measurement_provider_names"),
    ("sanidi_skadnetworkstatus", "SKAdNetwork Status", "choice", ["ENROLLED", "NEVER_ENROLLED", "WITHDRAWN"],
     "Snap: skadnetwork_properties.status"),
    ("sanidi_ecidenrollmentstatus", "ECID Enrollment Status", "choice", ["ATTACHED", "DETACHED"],
     "Snap: skadnetwork_properties.ecid_enrollment_status"),
    ("sanidi_enableskoverlay", "Enable SKOverlay", "bool", None, "Snap: skadnetwork_properties.enable_skoverlay"),
    ("sanidi_createdbyappid", "Created By App ID", "text", 100, "Snap: created_by_app_id"),
    ("sanidi_createdbyuser", "Created By User", "text", 200, "Snap: created_by_user"),
]

FORM = [
    ("general", "General", [
        ("general", "General", ["sanidi_adsquadname", "ownerid", "sanidi_adsquadid", "sanidi_snapcampaign",
                                "sanidi_campaignid", "sanidi_type", "sanidi_childadtype",
                                "sanidi_storyadcreativetype", "sanidi_forcedviewsetting"]),
        ("status", "Status", ["sanidi_status", "sanidi_deliverystatus", "sanidi_reachandfrequencystatus",
                              "sanidi_targetingreachstatus", "sanidi_creationstate", "sanidi_deleted"]),
        ("schedule", "Schedule", ["sanidi_starttime", "sanidi_endtime", "sanidi_createdat", "sanidi_updatedat"]),
    ]),
    ("budgetbidding", "Budget & Bidding", [
        ("budget", "Budget", ["sanidi_dailybudget", "sanidi_lifetimebudget", "sanidi_deliveryconstraint",
                              "sanidi_pacingtype"]),
        ("bidding", "Bidding", ["sanidi_bidstrategy", "sanidi_bid", "sanidi_billingevent", "sanidi_roasvalue",
                                "sanidi_autobid", "sanidi_targetbid"]),
        ("optimization", "Optimization", ["sanidi_optimizationgoal", "sanidi_conversionwindow", "sanidi_reachgoal",
                                          "sanidi_impressiongoal"]),
    ]),
    ("placementtargeting", "Placement & Targeting", [
        ("placement", "Placement", ["sanidi_placementconfig", "sanidi_platforms", "sanidi_snapchatpositions",
                                    "sanidi_includedcontenttypes", "sanidi_excludedcontenttypes",
                                    "sanidi_brandsafetyinventory"]),
        ("targeting", "Targeting", ["sanidi_targeting", "sanidi_separatedtypes", "sanidi_capandexclusionconfig",
                                    "sanidi_adschedulingconfig"]),
    ]),
    ("measurement", "Measurement", [
        ("measurement", "Measurement", ["sanidi_pixelid", "sanidi_eventsources", "sanidi_measurementproviders"]),
        ("skadnetwork", "SKAdNetwork", ["sanidi_skadnetworkstatus", "sanidi_ecidenrollmentstatus",
                                        "sanidi_enableskoverlay"]),
        ("origin", "Origin", ["sanidi_createdbyappid", "sanidi_createdbyuser"]),
    ]),
]

ACTIVE_VIEW_FIRST = ["sanidi_adsquadname", "sanidi_status", "sanidi_deliverystatus", "sanidi_snapcampaign",
                     "sanidi_optimizationgoal", "sanidi_bidstrategy", "sanidi_dailybudget", "sanidi_starttime",
                     "sanidi_endtime", "sanidi_updatedat"]
INACTIVE_VIEW = ["sanidi_adsquadname", "sanidi_status", "sanidi_updatedat", "createdon"]

SPEC = TableSpec(
    schema="sanidi_SnapAdSquad",
    display="Snap Ad Squad",
    plural="Snap Ad Squads",
    description="Snapchat ad squads synced from the Snapchat Marketing API by the Get Snap Ad Squads flow.",
    fields=FIELDS,
    form=FORM,
    active_view_first=ACTIVE_VIEW_FIRST,
    inactive_view=INACTIVE_VIEW,
    key_field="sanidi_adsquadid",
    key_display="Ad Squad ID",
    optionsets={
        DELIVERY_OPTIONSET: ("Snap Ad Squad Delivery Status", DELIVERY_STATUS),
        PLATFORM_OPTIONSET: ("Snap Platform", PLATFORMS),
        POSITION_OPTIONSET: ("Snap Placement Position", POSITIONS),
        CONTENT_OPTIONSET: ("Snap Content Type", CONTENT_TYPES),
        PROVIDER_OPTIONSET: ("Snap Measurement Provider", PROVIDERS),
    },
)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export with the Meta template tables")
    ap.add_argument("--out", default="SnapAdSquadTable.zip")
    a = ap.parse_args()
    build_package(SPEC, a.template, a.out)
