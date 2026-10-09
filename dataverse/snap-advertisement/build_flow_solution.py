"""Builds an unmanaged solution package that adds the "Get Snap Advertisements" cloud flow
to the "AlSanidi | Marketing" solution.

Trigger: Dataverse "When a row is added, modified or deleted" (added or modified) on
Snap Ad Squad. For that ad squad the flow reads its ads from the Snap connector, maps
choice labels to option values, and uses List rows on Ad ID to update the existing
Snap Advertisement row or add a new one, linked to the ad squad. Ads that no longer come
back from Snap are left in place. The flow logic lives in ../flow_builder.py.

Run:
  python3 build_flow_solution.py --template <template export zip> [--out GetSnapAdvertisementsFlow.zip]
  pac solution import --path GetSnapAdvertisementsFlow.zip --environment <env>
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_table_solution import FIELDS  # noqa: E402
from flow_builder import ChildSyncFlow  # noqa: E402

# Where each column's value sits in a Snap ad object.
SOURCE = {
    "sanidi_adname": ["name"],
    "sanidi_adid": ["id"],
    "sanidi_adsquadid": ["ad_squad_id"],
    "sanidi_creativeid": ["creative_id"],
    "sanidi_type": ["type"],
    "sanidi_rendertype": ["render_type"],
    "sanidi_payingadvertisername": ["paying_advertiser_name"],
    "sanidi_status": ["status"],
    "sanidi_deliverystatus": ["delivery_status"],
    "sanidi_deleted": ["deleted"],
    "sanidi_starttime": ["start_time"],
    "sanidi_endtime": ["end_time"],
    "sanidi_createdat": ["created_at"],
    "sanidi_updatedat": ["updated_at"],
    "sanidi_reviewstatus": ["review_status"],
    "sanidi_reviewstatusreasons": ["review_status_reasons"],
    "sanidi_swipetrackingurls": ["third_party_on_swipe_tracking_urls"],
    "sanidi_impressiontrackingurls": ["third_party_paid_impression_tracking_urls"],
}

FLOW = ChildSyncFlow(
    name="Get Snap Advertisements", key="get-snap-advertisements", fields=FIELDS, source=SOURCE,
    noun="ad", nouns="ads",
    child_set="sanidi_snapadvertisements", child_key="sanidi_adid", child_pk="sanidi_snapadvertisementid",
    lookup="sanidi_snapadsquad",
    parent_entity="sanidi_snapadsquad", parent_label="Snap_Ad_Squad", parent_set="sanidi_snapadsquads",
    parent_pk="sanidi_snapadsquadid", parent_snap_id="sanidi_adsquadid",
    list_operation="ListAdsByAdSquad", list_parameter="ad_squad_id", list_key="ads", item_key="ad",
    # Rejection reasons: one per line.
    overrides={"sanidi_reviewstatusreasons": lambda s: (
        f"@if(empty({s}), null, join({s}, decodeUriComponent('%0A')))")},
)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export (any) for the package skeleton")
    ap.add_argument("--out", default="GetSnapAdvertisementsFlow.zip")
    a = ap.parse_args()
    FLOW.build(a.template, a.out)
