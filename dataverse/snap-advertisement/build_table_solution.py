"""Builds an unmanaged solution package that creates or updates the "Snap Advertisement" table
(sanidi_SnapAdvertisement) in the "AlSanidi | Marketing" solution: columns, choices, the lookup
to Snap Ad Squad, alternate key, main form and views.

Field definitions come from https://developers.snap.com/marketing-api/Ads-API/ads.
The package format is described in ../table_builder.py.

Run:
  python3 build_table_solution.py --template <template export zip> [--out SnapAdvertisementTable.zip]
  pac solution import --path SnapAdvertisementTable.zip --environment <env> --publish-changes
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from table_builder import TableSpec, build_package  # noqa: E402

DELIVERY_OPTIONSET = "sanidi_snapaddeliverystatus"

DELIVERY_STATUS = [
    # Common to all Snap entities
    "PENDING", "VALID", "INVALID_NOT_ACTIVE", "INVALID_NOT_EFFECTIVE_ACTIVE", "INVALID_START_TIME",
    "INVALID_END_TIME", "INVALID_EFFECTIVE_START_TIME", "INVALID_EFFECTIVE_END_TIME", "INVALID_EFFECTIVE_DELETED",
    "INVALID_EFFECTIVE_INVALID", "INVALID_START_TIME_AFTER_END_TIME",
    # Ad
    "NOT_APPROVED_AD", "INVALID_NOT_APPROVED_REVIEW_STATUS", "INVALID_PENDING_REVIEW_STATUS",
    "INVALID_DYNAMIC_CONTENT_MARKUP", "INVALID_UNSUPPORTED_AD_TYPE", "INVALID_NO_CREATIVE_EFFECTIVE_ACTIVE",
    "INVALID_DYNAMIC_FILTER", "INVALID_CREATIVE_PACKAGING_STATUS", "INVALID_SKOV_REQUIRES_SKAN",
]

# (logical name, display name, kind, extra, description); kinds are described in table_builder.py.
FIELDS = [
    ("sanidi_adname", "Ad Name", "text", 375, "Snap: name"),
    ("sanidi_adid", "Ad ID", "text", 100, "Snap: id"),
    ("sanidi_snapadsquad", "Snap Ad Squad", "lookup", "sanidi_SnapAdSquad", "Parent ad squad, linked by ad_squad_id"),
    ("sanidi_adsquadid", "Ad Squad ID", "text", 100, "Snap: ad_squad_id"),
    ("sanidi_creativeid", "Creative ID", "text", 100, "Snap: creative_id"),
    ("sanidi_type", "Type", "choice",
     ["SNAP_AD", "APP_INSTALL", "REMOTE_WEBPAGE", "DEEP_LINK", "STORY", "AD_TO_LENS", "AD_TO_CALL", "AD_TO_MESSAGE",
      "FILTER", "LENS", "LENS_WEB_VIEW", "LENS_APP_INSTALL", "LENS_DEEP_LINK", "COLLECTION", "LEAD_GENERATION",
      "REMINDER", "LENS_REMOTE_WEBPAGE"], "Snap: type"),
    ("sanidi_rendertype", "Render Type", "choice", ["STATIC", "DYNAMIC"], "Snap: render_type"),
    ("sanidi_payingadvertisername", "Paying Advertiser Name", "text", 200, "Snap: paying_advertiser_name"),
    ("sanidi_status", "Status", "choice", ["ACTIVE", "PAUSED"], "Snap: status"),
    ("sanidi_deliverystatus", "Delivery Status", "multichoice", (DELIVERY_OPTIONSET, DELIVERY_STATUS),
     "Snap: delivery_status"),
    ("sanidi_deleted", "Deleted", "bool", None, "Snap: deleted"),
    ("sanidi_starttime", "Start Time", "datetime", None, "Snap: start_time"),
    ("sanidi_endtime", "End Time", "datetime", None, "Snap: end_time"),
    ("sanidi_createdat", "Created At", "datetime", None, "Snap: created_at"),
    ("sanidi_updatedat", "Updated At", "datetime", None, "Snap: updated_at"),
    ("sanidi_reviewstatus", "Review Status", "choice", ["PENDING", "APPROVED", "REJECTED"], "Snap: review_status"),
    ("sanidi_reviewstatusreasons", "Review Status Reasons", "multiline", None,
     "Snap: review_status_reasons, one per line"),
    ("sanidi_swipetrackingurls", "Swipe Tracking URLs", "multiline", None,
     "Snap: third_party_on_swipe_tracking_urls (JSON)"),
    ("sanidi_impressiontrackingurls", "Impression Tracking URLs", "multiline", None,
     "Snap: third_party_paid_impression_tracking_urls (JSON)"),
]

FORM = [
    ("general", "General", [
        ("general", "General", ["sanidi_adname", "ownerid", "sanidi_adid", "sanidi_snapadsquad", "sanidi_adsquadid",
                                "sanidi_creativeid", "sanidi_type", "sanidi_rendertype",
                                "sanidi_payingadvertisername"]),
        ("status", "Status", ["sanidi_status", "sanidi_deliverystatus", "sanidi_deleted"]),
        ("schedule", "Schedule", ["sanidi_starttime", "sanidi_endtime", "sanidi_createdat", "sanidi_updatedat"]),
    ]),
    ("reviewtracking", "Review & Tracking", [
        ("review", "Review", ["sanidi_reviewstatus", "sanidi_reviewstatusreasons"]),
        ("tracking", "Tracking", ["sanidi_swipetrackingurls", "sanidi_impressiontrackingurls"]),
    ]),
]

ACTIVE_VIEW_FIRST = ["sanidi_adname", "sanidi_status", "sanidi_deliverystatus", "sanidi_reviewstatus", "sanidi_type",
                     "sanidi_snapadsquad", "sanidi_starttime", "sanidi_endtime", "sanidi_updatedat"]
INACTIVE_VIEW = ["sanidi_adname", "sanidi_status", "sanidi_updatedat", "createdon"]

SPEC = TableSpec(
    schema="sanidi_SnapAdvertisement",
    display="Snap Advertisement",
    plural="Snap Advertisements",
    description="Snapchat ads synced from the Snapchat Marketing API by the Get Snap Advertisements flow.",
    fields=FIELDS,
    form=FORM,
    active_view_first=ACTIVE_VIEW_FIRST,
    inactive_view=INACTIVE_VIEW,
    key_field="sanidi_adid",
    key_display="Ad ID",
    optionsets={DELIVERY_OPTIONSET: ("Snap Ad Delivery Status", DELIVERY_STATUS)},
)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Solution export with the Meta template tables")
    ap.add_argument("--out", default="SnapAdvertisementTable.zip")
    a = ap.parse_args()
    build_package(SPEC, a.template, a.out)
