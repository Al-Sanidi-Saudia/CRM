"""Single source of truth for the Google Ads integration.

Each table lists its columns as (column, label, section, kind, source):
  column  - Dataverse column suffix; logical name is sanidi_<column>. Also the key the
            connector returns for that value, so flows map item/sanidi_<column> = row[<column>].
  section - form tab/section the column is placed in (see FORMS).
  kind    - how the connector converts the GAQL value, and the Dataverse type it lands in:
              str      text                        id      INT64 id -> text
              int      whole number                dec     decimal
              money    micros / 1,000,000 -> currency      cur     already in currency units -> currency
              pct      ratio x 100 -> decimal (%)  pctmicros  micros / 10,000 -> decimal (%)
              bool     yes/no                      date    "yyyy-MM-dd HH:mm:ss" -> date time
              enum     choice                      enums   repeated enum -> multi-select choice
              strs     repeated text -> multiline (one per line)
              json     message -> multiline JSON
              text     AdTextAsset -> text         texts   AdTextAsset[] -> multiline
              assets   AdImageAsset/AdVideoAsset[] -> multiline asset resource names
            (a repeated field mapped to str/id keeps its first value)
  source  - GAQL field, or a list of fields (first non-empty wins).

Choice options are every value of the Google Ads v25 enum (fields_v25.json), numbered from 1
in the order listed there.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
API_VERSION = "v25"
PREFIX = "sanidi_"
CATALOG = json.loads((HERE / "fields_v25.json").read_text())


def metrics(level):
    """All-time performance columns. Impression share needs a search level (not ads)."""
    cols = [
        ("impressions", "Impressions", "performance", "int", "metrics.impressions"),
        ("clicks", "Clicks", "performance", "int", "metrics.clicks"),
        ("ctr", "CTR (%)", "performance", "pct", "metrics.ctr"),
        ("averagecpc", "Avg. CPC", "performance", "money", "metrics.average_cpc"),
        ("averagecpm", "Avg. CPM", "performance", "money", "metrics.average_cpm"),
        ("averagecost", "Avg. Cost", "performance", "money", "metrics.average_cost"),
        ("cost", "Cost", "performance", "money", "metrics.cost_micros"),
        ("interactions", "Interactions", "performance", "int", "metrics.interactions"),
        ("interactionrate", "Interaction Rate (%)", "performance", "pct", "metrics.interaction_rate"),
        ("engagements", "Engagements", "performance", "int", "metrics.engagements"),
        ("engagementrate", "Engagement Rate (%)", "performance", "pct", "metrics.engagement_rate"),
        ("conversions", "Conversions", "conversions", "dec", "metrics.conversions"),
        ("conversionsvalue", "Conversions Value", "conversions", "cur", "metrics.conversions_value"),
        ("costperconversion", "Cost / Conversion", "conversions", "money", "metrics.cost_per_conversion"),
        ("valueperconversion", "Value / Conversion", "conversions", "cur", "metrics.value_per_conversion"),
        ("conversionrate", "Conversion Rate (%)", "conversions", "pct",
         "metrics.conversions_from_interactions_rate"),
        ("allconversions", "All Conversions", "conversions", "dec", "metrics.all_conversions"),
        ("allconversionsvalue", "All Conversions Value", "conversions", "cur",
         "metrics.all_conversions_value"),
        ("viewthroughconversions", "View-through Conversions", "conversions", "int",
         "metrics.view_through_conversions"),
        ("phonecalls", "Phone Calls", "conversions", "int", "metrics.phone_calls"),
        ("videoviews", "Video Views", "video", "int", "metrics.video_trueview_views"),
        ("videoviewrate", "Video View Rate (%)", "video", "pct", "metrics.video_trueview_view_rate"),
        ("topimpressionpct", "Top Impression (%)", "video", "pct", "metrics.top_impression_percentage"),
        ("absolutetopimpressionpct", "Absolute Top Impression (%)", "video", "pct",
         "metrics.absolute_top_impression_percentage"),
    ]
    if level in ("campaign", "ad_group"):
        cols += [
            ("searchimpressionshare", "Search Impression Share (%)", "video", "pct",
             "metrics.search_impression_share"),
            ("searchtopimpressionshare", "Search Top Impression Share (%)", "video", "pct",
             "metrics.search_top_impression_share"),
            ("searchabsolutetopimpressionshare", "Search Abs. Top Impression Share (%)", "video", "pct",
             "metrics.search_absolute_top_impression_share"),
        ]
    if level == "campaign":
        cols.append(("invalidclicks", "Invalid Clicks", "performance", "int", "metrics.invalid_clicks"))
    return cols


SYNC = [
    ("lastsyncedon", "Last Synced On", "sync", "now", None),
    ("rawpayload", "Raw Payload", "sync", "raw", None),
]

CAMPAIGN = [
    # identity
    ("campaignname", "Campaign Name", "identity", "str", "campaign.name"),
    ("campaignid", "Campaign ID", "identity", "id", "campaign.id"),
    ("resourcename", "Resource Name", "identity", "str", "campaign.resource_name"),
    ("customerid", "Customer ID", "identity", "id", "customer.id"),
    ("customername", "Customer Name", "identity", "str", "customer.descriptive_name"),
    ("currencycode", "Currency Code", "identity", "str", "customer.currency_code"),
    ("accounttimezone", "Account Time Zone", "identity", "str", "customer.time_zone"),
    ("campaigngroup", "Campaign Group", "identity", "str", "campaign.campaign_group"),
    ("basecampaign", "Base Campaign", "identity", "str", "campaign.base_campaign"),
    ("labels", "Labels", "identity", "strs", "campaign.labels"),
    # status
    ("status", "Status", "status", "enum", "campaign.status"),
    ("servingstatus", "Serving Status", "status", "enum", "campaign.serving_status"),
    ("primarystatus", "Primary Status", "status", "enum", "campaign.primary_status"),
    ("primarystatusreasons", "Primary Status Reasons", "status", "enums", "campaign.primary_status_reasons"),
    ("experimenttype", "Experiment Type", "status", "enum", "campaign.experiment_type"),
    ("adservingoptimizationstatus", "Ad Serving Optimization Status", "status", "enum",
     "campaign.ad_serving_optimization_status"),
    ("biddingstrategysystemstatus", "Bidding Strategy System Status", "status", "enum",
     "campaign.bidding_strategy_system_status"),
    ("optimizationscore", "Optimization Score (%)", "status", "pct", "campaign.optimization_score"),
    # channel / schedule
    ("advertisingchanneltype", "Advertising Channel Type", "channel", "enum", "campaign.advertising_channel_type"),
    ("advertisingchannelsubtype", "Advertising Channel Sub Type", "channel", "enum",
     "campaign.advertising_channel_sub_type"),
    ("paymentmode", "Payment Mode", "channel", "enum", "campaign.payment_mode"),
    ("keywordmatchtype", "Keyword Match Type", "channel", "enum", "campaign.keyword_match_type"),
    ("listingtype", "Listing Type", "channel", "enum", "campaign.listing_type"),
    ("startdatetime", "Start Date Time", "schedule", "date", "campaign.start_date_time"),
    ("enddatetime", "End Date Time", "schedule", "date", "campaign.end_date_time"),
    # budget
    ("budgetid", "Budget ID", "budget", "id", "campaign_budget.id"),
    ("budgetname", "Budget Name", "budget", "str", "campaign_budget.name"),
    ("budgetamount", "Budget Amount", "budget", "money", "campaign_budget.amount_micros"),
    ("totalbudget", "Total Budget", "budget", "money", "campaign_budget.total_amount_micros"),
    ("budgetperiod", "Budget Period", "budget", "enum", "campaign_budget.period"),
    ("budgetdeliverymethod", "Budget Delivery Method", "budget", "enum", "campaign_budget.delivery_method"),
    ("budgettype", "Budget Type", "budget", "enum", "campaign_budget.type"),
    ("budgetstatus", "Budget Status", "budget", "enum", "campaign_budget.status"),
    ("budgetexplicitlyshared", "Budget Explicitly Shared", "budget", "bool", "campaign_budget.explicitly_shared"),
    ("budgetreferencecount", "Campaigns Sharing Budget", "budget", "int", "campaign_budget.reference_count"),
    ("hasrecommendedbudget", "Has Recommended Budget", "budget", "bool", "campaign_budget.has_recommended_budget"),
    ("recommendedbudget", "Recommended Budget", "budget", "money", "campaign_budget.recommended_budget_amount_micros"),
    # bidding
    ("biddingstrategytype", "Bidding Strategy Type", "bidding", "enum", "campaign.bidding_strategy_type"),
    ("portfoliobiddingstrategy", "Portfolio Bidding Strategy", "bidding", "str", "campaign.bidding_strategy"),
    ("accessiblebiddingstrategy", "Accessible Bidding Strategy", "bidding", "str",
     "campaign.accessible_bidding_strategy"),
    ("targetcpa", "Target CPA", "bidding", "money",
     ["campaign.target_cpa.target_cpa_micros", "campaign.maximize_conversions.target_cpa_micros"]),
    ("targetroas", "Target ROAS", "bidding", "dec",
     ["campaign.target_roas.target_roas", "campaign.maximize_conversion_value.target_roas"]),
    ("targetcpc", "Target CPC", "bidding", "money", "campaign.target_cpc.target_cpc_micros"),
    ("cpcbidceiling", "CPC Bid Ceiling", "bidding", "money",
     ["campaign.target_cpa.cpc_bid_ceiling_micros", "campaign.target_roas.cpc_bid_ceiling_micros",
      "campaign.target_impression_share.cpc_bid_ceiling_micros", "campaign.target_spend.cpc_bid_ceiling_micros",
      "campaign.percent_cpc.cpc_bid_ceiling_micros"]),
    ("cpcbidfloor", "CPC Bid Floor", "bidding", "money",
     ["campaign.target_cpa.cpc_bid_floor_micros", "campaign.target_roas.cpc_bid_floor_micros"]),
    ("targetimpressionsharelocation", "Target Impression Share Location", "bidding", "enum",
     "campaign.target_impression_share.location"),
    ("targetimpressionshare", "Target Impression Share (%)", "bidding", "pctmicros",
     "campaign.target_impression_share.location_fraction_micros"),
    ("enhancedcpcenabled", "Enhanced CPC Enabled", "bidding", "bool", "campaign.manual_cpc.enhanced_cpc_enabled"),
    ("commissionrate", "Commission Rate (%)", "bidding", "pctmicros", "campaign.commission.commission_rate_micros"),
    ("viewthroughconversionoptimization", "View-through Conversion Optimization", "bidding", "bool",
     "campaign.view_through_conversion_optimization_enabled"),
    # networks / geo
    ("targetgooglesearch", "Target Google Search", "networks", "bool", "campaign.network_settings.target_google_search"),
    ("targetsearchnetwork", "Target Search Network", "networks", "bool", "campaign.network_settings.target_search_network"),
    ("targetcontentnetwork", "Target Content Network", "networks", "bool",
     "campaign.network_settings.target_content_network"),
    ("targetpartnersearchnetwork", "Target Partner Search Network", "networks", "bool",
     "campaign.network_settings.target_partner_search_network"),
    ("targetyoutube", "Target YouTube", "networks", "bool", "campaign.network_settings.target_youtube"),
    ("targetgoogletvnetwork", "Target Google TV Network", "networks", "bool",
     "campaign.network_settings.target_google_tv_network"),
    ("realtimebiddingoptin", "Real-time Bidding Opt-in", "networks", "bool", "campaign.real_time_bidding_setting.opt_in"),
    ("positivegeotargettype", "Positive Geo Target Type", "geo", "enum",
     "campaign.geo_target_type_setting.positive_geo_target_type"),
    ("negativegeotargettype", "Negative Geo Target Type", "geo", "enum",
     "campaign.geo_target_type_setting.negative_geo_target_type"),
    ("targetrestrictions", "Targeting Restrictions", "geo", "json", "campaign.targeting_setting.target_restrictions"),
    ("useaudiencegrouped", "Use Audience Grouped", "geo", "bool", "campaign.audience_setting.use_audience_grouped"),
    ("frequencycaps", "Frequency Caps", "geo", "json", "campaign.frequency_caps"),
    # channel settings
    ("merchantid", "Merchant Center ID", "channelsettings", "id", "campaign.shopping_setting.merchant_id"),
    ("feedlabel", "Feed Label", "channelsettings", "str", "campaign.shopping_setting.feed_label"),
    ("campaignpriority", "Shopping Campaign Priority", "channelsettings", "int",
     "campaign.shopping_setting.campaign_priority"),
    ("enablelocal", "Shopping Local Inventory", "channelsettings", "bool", "campaign.shopping_setting.enable_local"),
    ("dsadomain", "DSA Domain", "channelsettings", "str", "campaign.dynamic_search_ads_setting.domain_name"),
    ("dsalanguage", "DSA Language", "channelsettings", "str", "campaign.dynamic_search_ads_setting.language_code"),
    ("dsasuppliedurlsonly", "DSA Supplied URLs Only", "channelsettings", "bool",
     "campaign.dynamic_search_ads_setting.use_supplied_urls_only"),
    ("appid", "App ID", "channelsettings", "str", "campaign.app_campaign_setting.app_id"),
    ("appstore", "App Store", "channelsettings", "enum", "campaign.app_campaign_setting.app_store"),
    ("appbiddinggoal", "App Bidding Goal", "channelsettings", "enum",
     "campaign.app_campaign_setting.bidding_strategy_goal_type"),
    ("hotelcenterid", "Hotel Center ID", "channelsettings", "id", "campaign.hotel_setting.hotel_center_id"),
    ("travelaccountid", "Travel Account ID", "channelsettings", "id",
     "campaign.travel_campaign_settings.travel_account_id"),
    ("locationsourcetype", "Location Source Type", "channelsettings", "enum",
     "campaign.local_campaign_setting.location_source_type"),
    ("brandguidelinesenabled", "Brand Guidelines Enabled", "channelsettings", "bool",
     "campaign.brand_guidelines_enabled"),
    ("aimaxenabled", "AI Max Enabled", "channelsettings", "bool", "campaign.ai_max_setting.enable_ai_max"),
    ("containseupoliticaladvertising", "Contains EU Political Advertising", "channelsettings", "enum",
     "campaign.contains_eu_political_advertising"),
    ("optimizationgoaltypes", "Optimization Goal Types", "channelsettings", "enums",
     "campaign.optimization_goal_setting.optimization_goal_types"),
    ("excludedparentassetfieldtypes", "Excluded Parent Asset Field Types", "channelsettings", "enums",
     "campaign.excluded_parent_asset_field_types"),
    ("selectiveoptimizationactions", "Selective Optimization Conversion Actions", "channelsettings", "strs",
     "campaign.selective_optimization.conversion_actions"),
    # tracking
    ("trackingurltemplate", "Tracking URL Template", "tracking", "str", "campaign.tracking_url_template"),
    ("finalurlsuffix", "Final URL Suffix", "tracking", "str", "campaign.final_url_suffix"),
    ("urlcustomparameters", "URL Custom Parameters", "tracking", "json", "campaign.url_custom_parameters"),
    ("trackingurl", "Tracking URL", "tracking", "str", "campaign.tracking_setting.tracking_url"),
] + metrics("campaign") + SYNC

AD_GROUP = [
    ("adgroupname", "Ad Group Name", "identity", "str", "ad_group.name"),
    ("adgroupid", "Ad Group ID", "identity", "id", "ad_group.id"),
    ("resourcename", "Resource Name", "identity", "str", "ad_group.resource_name"),
    ("campaignid", "Campaign ID", "identity", "id", "campaign.id"),
    ("campaignname", "Campaign Name", "identity", "str", "campaign.name"),
    ("customerid", "Customer ID", "identity", "id", "customer.id"),
    ("baseadgroup", "Base Ad Group", "identity", "str", "ad_group.base_ad_group"),
    ("labels", "Labels", "identity", "strs", "ad_group.labels"),
    ("status", "Status", "status", "enum", "ad_group.status"),
    ("primarystatus", "Primary Status", "status", "enum", "ad_group.primary_status"),
    ("primarystatusreasons", "Primary Status Reasons", "status", "enums", "ad_group.primary_status_reasons"),
    ("type", "Ad Group Type", "status", "enum", "ad_group.type"),
    ("adrotationmode", "Ad Rotation Mode", "status", "enum", "ad_group.ad_rotation_mode"),
    # bids
    ("cpcbid", "Max CPC Bid", "bids", "money", "ad_group.cpc_bid_micros"),
    ("cpmbid", "Max CPM Bid", "bids", "money", "ad_group.cpm_bid_micros"),
    ("cpvbid", "Max CPV Bid", "bids", "money", "ad_group.cpv_bid_micros"),
    ("fixedcpm", "Fixed CPM", "bids", "money", "ad_group.fixed_cpm_micros"),
    ("percentcpcbid", "Percent CPC Bid (%)", "bids", "pctmicros", "ad_group.percent_cpc_bid_micros"),
    ("targetcpa", "Target CPA", "bids", "money", "ad_group.target_cpa_micros"),
    ("targetcpc", "Target CPC", "bids", "money", "ad_group.target_cpc_micros"),
    ("targetcpm", "Target CPM", "bids", "money", "ad_group.target_cpm_micros"),
    ("targetcpv", "Target CPV", "bids", "money", "ad_group.target_cpv_micros"),
    ("targetroas", "Target ROAS", "bids", "dec", "ad_group.target_roas"),
    ("effectivecpcbid", "Effective CPC Bid", "effectivebids", "money", "ad_group.effective_cpc_bid_micros"),
    ("effectivetargetcpa", "Effective Target CPA", "effectivebids", "money", "ad_group.effective_target_cpa_micros"),
    ("effectivetargetcpasource", "Effective Target CPA Source", "effectivebids", "enum",
     "ad_group.effective_target_cpa_source"),
    ("effectivetargetcpc", "Effective Target CPC", "effectivebids", "money", "ad_group.effective_target_cpc"),
    ("effectivetargetcpcsource", "Effective Target CPC Source", "effectivebids", "enum",
     "ad_group.effective_target_cpc_source"),
    ("effectivetargetroas", "Effective Target ROAS", "effectivebids", "dec", "ad_group.effective_target_roas"),
    ("effectivetargetroassource", "Effective Target ROAS Source", "effectivebids", "enum",
     "ad_group.effective_target_roas_source"),
    # targeting
    ("optimizedtargetingenabled", "Optimized Targeting Enabled", "targeting", "bool",
     "ad_group.optimized_targeting_enabled"),
    ("excludedemographicexpansion", "Exclude Demographic Expansion", "targeting", "bool",
     "ad_group.exclude_demographic_expansion"),
    ("useaudiencegrouped", "Use Audience Grouped", "targeting", "bool", "ad_group.audience_setting.use_audience_grouped"),
    ("displaycustombiddimension", "Display Custom Bid Dimension", "targeting", "enum",
     "ad_group.display_custom_bid_dimension"),
    ("disablesearchtermmatching", "AI Max: Disable Search Term Matching", "targeting", "bool",
     "ad_group.ai_max_ad_group_setting.disable_search_term_matching"),
    ("targetrestrictions", "Targeting Restrictions", "targeting", "json", "ad_group.targeting_setting.target_restrictions"),
    ("excludedparentassetfieldtypes", "Excluded Parent Asset Field Types", "targeting", "enums",
     "ad_group.excluded_parent_asset_field_types"),
    ("channelconfig", "Demand Gen Channel Config", "demandgen", "enum",
     "ad_group.demand_gen_ad_group_settings.channel_controls.channel_config"),
    ("channelstrategy", "Demand Gen Channel Strategy", "demandgen", "enum",
     "ad_group.demand_gen_ad_group_settings.channel_controls.channel_strategy"),
] + [
    (f"channel{c.replace('_', '')}", f"Demand Gen: {label}", "demandgen", "bool",
     f"ad_group.demand_gen_ad_group_settings.channel_controls.selected_channels.{c}")
    for c, label in [("youtube_in_stream", "YouTube In-stream"), ("youtube_in_feed", "YouTube In-feed"),
                     ("youtube_shorts", "YouTube Shorts"), ("discover", "Discover"), ("gmail", "Gmail"),
                     ("display", "Display"), ("maps", "Maps")]
] + [
    ("trackingurltemplate", "Tracking URL Template", "tracking", "str", "ad_group.tracking_url_template"),
    ("finalurlsuffix", "Final URL Suffix", "tracking", "str", "ad_group.final_url_suffix"),
    ("urlcustomparameters", "URL Custom Parameters", "tracking", "json", "ad_group.url_custom_parameters"),
] + metrics("ad_group") + SYNC

A = "ad_group_ad.ad."
RDA, RSA, DGM, DGV, DGC, VRA, APP = (A + x + "." for x in (
    "responsive_display_ad", "responsive_search_ad", "demand_gen_multi_asset_ad",
    "demand_gen_video_responsive_ad", "demand_gen_carousel_ad", "video_responsive_ad", "app_ad"))

ADVERTISEMENT = [
    ("adname", "Ad Name", "identity", "str", A + "name"),
    ("adid", "Ad ID", "identity", "id", A + "id"),
    ("resourcename", "Resource Name", "identity", "str", "ad_group_ad.resource_name"),
    ("adgroupid", "Ad Group ID", "identity", "id", "ad_group.id"),
    ("adgroupname", "Ad Group Name", "identity", "str", "ad_group.name"),
    ("campaignid", "Campaign ID", "identity", "id", "campaign.id"),
    ("campaignname", "Campaign Name", "identity", "str", "campaign.name"),
    ("customerid", "Customer ID", "identity", "id", "customer.id"),
    ("labels", "Labels", "identity", "strs", "ad_group_ad.labels"),
    ("status", "Status", "status", "enum", "ad_group_ad.status"),
    ("primarystatus", "Primary Status", "status", "enum", "ad_group_ad.primary_status"),
    ("primarystatusreasons", "Primary Status Reasons", "status", "enums", "ad_group_ad.primary_status_reasons"),
    ("adstrength", "Ad Strength", "status", "enum", "ad_group_ad.ad_strength"),
    ("actionitems", "Action Items", "status", "strs", "ad_group_ad.action_items"),
    ("startdatetime", "Start Date Time", "status", "date", "ad_group_ad.start_date_time"),
    ("enddatetime", "End Date Time", "status", "date", "ad_group_ad.end_date_time"),
    ("type", "Ad Type", "status", "enum", A + "type"),
    ("devicepreference", "Device Preference", "status", "enum", A + "device_preference"),
    ("addedbygoogleads", "Added by Google Ads", "status", "bool", A + "added_by_google_ads"),
    ("systemmanagedsource", "System Managed Source", "status", "enum", A + "system_managed_resource_source"),
    ("approvalstatus", "Approval Status", "policy", "enum", "ad_group_ad.policy_summary.approval_status"),
    ("reviewstatus", "Review Status", "policy", "enum", "ad_group_ad.policy_summary.review_status"),
    ("policytopics", "Policy Topics", "policy", "json", "ad_group_ad.policy_summary.policy_topic_entries"),
    # creative text
    ("headlines", "Headlines", "text", "texts",
     [RSA + "headlines", RDA + "headlines", DGM + "headlines", DGV + "headlines", VRA + "headlines", APP + "headlines"]),
    ("longheadline", "Long Headline", "text", "texts",
     [RDA + "long_headline", DGV + "long_headlines", VRA + "long_headlines", DGC + "headline"]),
    ("descriptions", "Descriptions", "text", "texts",
     [RSA + "descriptions", RDA + "descriptions", DGM + "descriptions", DGV + "descriptions", VRA + "descriptions",
      APP + "descriptions", DGC + "description"]),
    ("businessname", "Business Name", "text", "texts",
     [RDA + "business_name", DGM + "business_name", DGV + "business_name", VRA + "business_name",
      DGC + "business_name"]),
    ("calltoaction", "Call to Action", "text", "texts",
     [RDA + "call_to_action_text", DGM + "call_to_action_text", DGC + "call_to_action_text",
      VRA + "call_to_actions", DGV + "call_to_actions"]),
    ("path1", "Path 1", "text", "str", RSA + "path1"),
    ("path2", "Path 2", "text", "str", RSA + "path2"),
    ("displayurl", "Display URL", "text", "str", A + "display_url"),
    ("mandatoryadtext", "Mandatory Ad Text", "text", "texts", APP + "mandatory_ad_text"),
    # creative assets
    ("marketingimages", "Marketing Images", "assets", "assets",
     [RDA + "marketing_images", DGM + "marketing_images", APP + "images"]),
    ("squaremarketingimages", "Square Marketing Images", "assets", "assets",
     [RDA + "square_marketing_images", DGM + "square_marketing_images"]),
    ("portraitmarketingimages", "Portrait Marketing Images", "assets", "assets",
     DGM + "portrait_marketing_images"),
    ("logoimages", "Logo Images", "assets", "assets",
     [RDA + "logo_images", DGM + "logo_images", DGV + "logo_images", VRA + "logo_images", DGC + "logo_image"]),
    ("videos", "Videos", "assets", "assets",
     [RDA + "youtube_videos", VRA + "videos", DGV + "videos", APP + "youtube_videos"]),
    ("carouselcards", "Carousel Cards", "assets", "assets", DGC + "carousel_cards"),
    ("imageurl", "Image URL", "assets", "str", A + "image_ad.image_url"),
    ("imagename", "Image Name", "assets", "str", A + "image_ad.name"),
    ("imagewidth", "Image Width (px)", "assets", "int", A + "image_ad.pixel_width"),
    ("imageheight", "Image Height (px)", "assets", "int", A + "image_ad.pixel_height"),
    # urls
    ("finalurl", "Final URL", "urls", "str", A + "final_urls"),
    ("finalurls", "Final URLs", "urls", "strs", A + "final_urls"),
    ("finalmobileurls", "Final Mobile URLs", "urls", "strs", A + "final_mobile_urls"),
    ("finalappurls", "Final App URLs", "urls", "json", A + "final_app_urls"),
    ("trackingurltemplate", "Tracking URL Template", "urls", "str", A + "tracking_url_template"),
    ("finalurlsuffix", "Final URL Suffix", "urls", "str", A + "final_url_suffix"),
    ("urlcustomparameters", "URL Custom Parameters", "urls", "json", A + "url_custom_parameters"),
] + metrics("ad_group_ad") + SYNC

TABLES = {
    "googleadscampaign": {
        "display": "Google Ads Campaign", "plural": "Google Ads Campaigns",
        "description": "Google Ads campaigns synced from the Google Ads API by the Get Google Ads Campaigns flow.",
        "resource": "campaign", "primary": "campaignname", "googleid": "campaignid",
        "columns": CAMPAIGN, "parent": None,
    },
    "googleadsadgroup": {
        "display": "Google Ads Ad Group", "plural": "Google Ads Ad Groups",
        "description": "Google Ads ad groups synced from the Google Ads API by the Get Google Ads Ad Groups flow.",
        "resource": "ad_group", "primary": "adgroupname", "googleid": "adgroupid",
        "columns": AD_GROUP, "parent": ("googleadscampaign", "Google Ads Campaign"),
    },
    "googleadsadvertisement": {
        "display": "Google Ads Advertisement", "plural": "Google Ads Advertisements",
        "description": "Google Ads ads synced from the Google Ads API by the Get Google Ads Advertisements flow.",
        "resource": "ad_group_ad", "primary": "adname", "googleid": "adid",
        "columns": ADVERTISEMENT, "parent": ("googleadsadgroup", "Google Ads Ad Group"),
    },
}


MULTILINE_KINDS = {"strs", "json", "texts", "assets", "raw"}


def max_length(column, kind):
    """Text length used both for the Dataverse column and for truncation in the connector."""
    if kind == "raw":
        return 100000
    if kind in MULTILINE_KINDS:
        return 20000
    if kind in ("str", "id"):
        if any(k in column for k in ("url", "template", "suffix")):
            return 2000
        return 100 if kind == "id" else 400
    return 0


def sources(src):
    return [] if src is None else ([src] if isinstance(src, str) else list(src))


def enum_options(src):
    """Every value of the field's enum, numbered from 1."""
    values = CATALOG[sources(src)[0]]["enum"]
    return [{"label": v, "value": i} for i, v in enumerate(values, start=1)]


def gaql_fields(columns, metrics_only=False):
    out = []
    for _, _, _, _, src in columns:
        for f in sources(src):
            if f.startswith("metrics.") == metrics_only and f not in out:
                out.append(f)
    return out
