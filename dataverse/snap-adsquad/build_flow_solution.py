"""Builds an unmanaged solution package that adds the "Get Snap Ad Squads" cloud flow to
the "AlSanidi | Marketing" solution.

Trigger: Dataverse "When a row is added, modified or deleted" (added or modified) on
Snap Campaign. For that campaign the flow reads its ad squads from the Snap connector,
maps choice labels to option values, and uses List rows on Ad Squad ID to update the
existing Snap Ad Squad row or add a new one, linked to the campaign. Ad squads that no
longer come back from Snap are left in place. The flow logic lives in ../flow_builder.py.

Run:
  python3 build_flow_solution.py --template <template export zip> [--out GetSnapAdSquadsFlow.zip]
  pac solution import --path GetSnapAdSquadsFlow.zip --environment <env>

The flow reuses the existing Snap and Dataverse connection references (see ../flow_builder.py).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_table_solution import FIELDS  # noqa: E402
from flow_builder import ChildSyncFlow  # noqa: E402

# Where each column's value sits in a Snap ad squad object.
SOURCE = {
    "sanidi_adsquadname": ["name"],
    "sanidi_adsquadid": ["id"],
    "sanidi_campaignid": ["campaign_id"],
    "sanidi_type": ["type"],
    "sanidi_childadtype": ["child_ad_type"],
    "sanidi_storyadcreativetype": ["story_ad_creative_type"],
    "sanidi_forcedviewsetting": ["forced_view_setting"],
    "sanidi_status": ["status"],
    "sanidi_deliverystatus": ["delivery_status"],
    "sanidi_reachandfrequencystatus": ["reach_and_frequency_status"],
    "sanidi_targetingreachstatus": ["targeting_reach_status"],
    "sanidi_creationstate": ["creation_state"],
    "sanidi_deleted": ["deleted"],
    "sanidi_starttime": ["start_time"],
    "sanidi_endtime": ["end_time"],
    "sanidi_createdat": ["created_at"],
    "sanidi_updatedat": ["updated_at"],
    "sanidi_dailybudget": ["daily_budget_micro"],
    "sanidi_lifetimebudget": ["lifetime_budget_micro"],
    "sanidi_deliveryconstraint": ["delivery_constraint"],
    "sanidi_pacingtype": ["pacing_type"],
    "sanidi_bidstrategy": ["bid_strategy"],
    "sanidi_bid": ["bid_micro"],
    "sanidi_billingevent": ["billing_event"],
    "sanidi_roasvalue": ["roas_value_micro"],
    "sanidi_autobid": ["auto_bid"],
    "sanidi_targetbid": ["target_bid"],
    "sanidi_optimizationgoal": ["optimization_goal"],
    "sanidi_conversionwindow": ["conversion_window"],
    "sanidi_reachgoal": ["reach_goal"],
    "sanidi_impressiongoal": ["impression_goal"],
    "sanidi_placementconfig": ["placement_v2", "config"],
    "sanidi_platforms": ["placement_v2", "platforms"],
    "sanidi_snapchatpositions": ["placement_v2", "snapchat_positions"],
    "sanidi_includedcontenttypes": ["placement_v2", "inclusion", "content_types"],
    "sanidi_excludedcontenttypes": ["placement_v2", "exclusion", "content_types"],
    "sanidi_brandsafetyinventory": ["brand_safety_config", "inventory_option"],
    "sanidi_targeting": ["targeting"],
    "sanidi_separatedtypes": ["separated_types"],
    "sanidi_capandexclusionconfig": ["cap_and_exclusion_config"],
    "sanidi_adschedulingconfig": ["ad_scheduling_config"],
    "sanidi_pixelid": ["pixel_id"],
    "sanidi_eventsources": ["event_sources"],
    "sanidi_measurementproviders": ["measurement_provider_names"],
    "sanidi_skadnetworkstatus": ["skadnetwork_properties", "status"],
    "sanidi_ecidenrollmentstatus": ["skadnetwork_properties", "ecid_enrollment_status"],
    "sanidi_enableskoverlay": ["skadnetwork_properties", "enable_skoverlay"],
    "sanidi_createdbyappid": ["created_by_app_id"],
    "sanidi_createdbyuser": ["created_by_user"],
}
FLOW = ChildSyncFlow(
    name="Get Snap Ad Squads", key="get-snap-ad-squads", fields=FIELDS, source=SOURCE,
    noun="ad_squad", nouns="ad_squads",
    child_set="sanidi_snapadsquads", child_key="sanidi_adsquadid", child_pk="sanidi_snapadsquadid",
    lookup="sanidi_snapcampaign",
    parent_entity="sanidi_snapcampaign", parent_label="Snap_Campaign", parent_set="sanidi_snapcampaigns",
    parent_pk="sanidi_snapcampaignid", parent_snap_id="sanidi_campaignid",
    list_operation="ListAdSquadsByCampaign", list_parameter="campaign_id", list_key="adsquads", item_key="adsquad",
    # Snap's docs spell this value with a space.
    extra_labels={"sanidi_deliverystatus": {"LEARNING PHASE": 26}},
    # separated_types may come back as an array or a string -> comma-joined text.
    overrides={"sanidi_separatedtypes": lambda s: (
        f"@if(empty({s}), null, replace(replace(replace(string({s}), '[', ''), ']', ''), '\"', ''))")},
)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export (any) for the package skeleton")
    ap.add_argument("--out", default="GetSnapAdSquadsFlow.zip")
    a = ap.parse_args()
    FLOW.build(a.template, a.out)
