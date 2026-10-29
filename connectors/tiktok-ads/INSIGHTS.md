# TikTok insight metrics (all time)

The 204 metrics approved for the **Insights** tab of TikTok Campaign, TikTok Ad Group and TikTok Advertisement.
Source: TikTok API for Business v1.3, *Basic reports - Supported metrics* (Core, Videos, Clicks, Social,
Website and Attribution groups). Column = `sanidi_` + the metric name without underscores.

**Refused by TikTok (checked live 2026-10-28, both ad accounts, all three levels):** `cash_spend`, `voucher_spend`
("invalid metric fields") and the five `custom_page_event*` / `custom_page_events*` website metrics ("no relation" to
these levels). Their columns exist but are not requested, written or shown; 197 metrics are synced.

Labels are TikTok's own (Ads Manager) names, with these corrections to errors in TikTok's documentation:
- `total_complete_payment_rate` is labelled *Purchase value (website)* in the docs, so it is stored as currency, not as a rate.
- `total_page_browse_view_value` and `value_per_page_browse_view`: the docs swap their labels; they are corrected here.

## Delivery & Cost (30)

| Metric | Column | Label | Type |
|---|---|---|---|
| `spend` | `sanidi_spend` | Cost | Currency |
| `billed_cost` | `sanidi_billedcost` | Net cost | Currency |
| `cash_spend` | `sanidi_cashspend` | Cost Charged by Cash | Currency |
| `voucher_spend` | `sanidi_voucherspend` | Cost Charged by Voucher | Currency |
| `cpc` | `sanidi_cpc` | CPC (destination) | Currency |
| `cpm` | `sanidi_cpm` | CPM | Currency |
| `impressions` | `sanidi_impressions` | Impressions | Whole number |
| `gross_impressions` | `sanidi_grossimpressions` | Gross Impressions (Includes Invalid Impressions) | Whole number |
| `clicks` | `sanidi_clicks` | Clicks (destination) | Whole number |
| `ctr` | `sanidi_ctr` | CTR (destination) | Decimal (%) |
| `reach` | `sanidi_reach` | Reach | Whole number |
| `cost_per_1000_reached` | `sanidi_costper1000reached` | Cost per 1,000 people reached | Currency |
| `frequency` | `sanidi_frequency` | Frequency | Decimal |
| `conversion` | `sanidi_conversion` | Conversions | Decimal |
| `cost_per_conversion` | `sanidi_costperconversion` | Cost per conversion | Currency |
| `conversion_rate` | `sanidi_conversionrate` | Conversion rate (CVR, clicks) | Decimal (%) |
| `conversion_rate_v2` | `sanidi_conversionratev2` | Conversion rate (CVR) | Decimal (%) |
| `real_time_conversion` | `sanidi_realtimeconversion` | Conversions by conversion time | Decimal |
| `real_time_cost_per_conversion` | `sanidi_realtimecostperconversion` | Cost per conversion by conversion time | Currency |
| `real_time_conversion_rate` | `sanidi_realtimeconversionrate` | Real-time conversion rate (CVR, clicks) | Decimal (%) |
| `real_time_conversion_rate_v2` | `sanidi_realtimeconversionratev2` | Conversion rate (CVR) by conversion time | Decimal (%) |
| `result` | `sanidi_result` | Results | Decimal |
| `cost_per_result` | `sanidi_costperresult` | Cost per result | Currency |
| `result_rate` | `sanidi_resultrate` | Result rate | Decimal (%) |
| `real_time_result` | `sanidi_realtimeresult` | Real-time results | Decimal |
| `real_time_cost_per_result` | `sanidi_realtimecostperresult` | Real-time cost per result | Currency |
| `real_time_result_rate` | `sanidi_realtimeresultrate` | Real-time result rate | Decimal (%) |
| `secondary_goal_result` | `sanidi_secondarygoalresult` | Deep funnel result | Decimal |
| `cost_per_secondary_goal_result` | `sanidi_costpersecondarygoalresult` | Cost per deep funnel result | Currency |
| `secondary_goal_result_rate` | `sanidi_secondarygoalresultrate` | Deep funnel result rate | Decimal (%) |

## Video (15)

| Metric | Column | Label | Type |
|---|---|---|---|
| `video_play_actions` | `sanidi_videoplayactions` | Video views | Whole number |
| `video_watched_2s` | `sanidi_videowatched2s` | 2-second video views | Whole number |
| `video_watched_6s` | `sanidi_videowatched6s` | 6-second video views | Whole number |
| `video_views_p25` | `sanidi_videoviewsp25` | Video views at 25% | Whole number |
| `video_views_p50` | `sanidi_videoviewsp50` | Video views at 50% | Whole number |
| `video_views_p75` | `sanidi_videoviewsp75` | Video views at 75% | Whole number |
| `video_views_p100` | `sanidi_videoviewsp100` | Video views at 100% | Whole number |
| `average_video_play` | `sanidi_averagevideoplay` | Average play time per video view | Decimal |
| `average_video_play_per_user` | `sanidi_averagevideoplayperuser` | Average play time per user | Decimal |
| `engaged_view` | `sanidi_engagedview` | 6-second focused views | Whole number |
| `paid_engaged_view` | `sanidi_paidengagedview` | 6-second focused views (paid views) | Whole number |
| `paid_engagement_engaged_view` | `sanidi_paidengagementengagedview` | 6-second focused views (paid interactions) | Whole number |
| `engaged_view_15s` | `sanidi_engagedview15s` | 15-second focused views | Whole number |
| `paid_engaged_view_15s` | `sanidi_paidengagedview15s` | 15-second focused views (paid views) | Whole number |
| `paid_engagement_engaged_view_15s` | `sanidi_paidengagementengagedview15s` | 15-second focused views (paid interactions) | Whole number |

## Engagement (9)

| Metric | Column | Label | Type |
|---|---|---|---|
| `engagements` | `sanidi_engagements` | Clicks (all) | Whole number |
| `engagement_rate` | `sanidi_engagementrate` | CTR (all) | Decimal (%) |
| `clicks_on_music_disc` | `sanidi_clicksonmusicdisc` | Sound clicks | Whole number |
| `duet_clicks` | `sanidi_duetclicks` | Duet button clicks | Whole number |
| `stitch_clicks` | `sanidi_stitchclicks` | Stitch button clicks | Whole number |
| `sound_usage_clicks` | `sanidi_soundusageclicks` | Use sound button clicks | Whole number |
| `anchor_clicks` | `sanidi_anchorclicks` | Anchor clicks | Whole number |
| `anchor_click_rate` | `sanidi_anchorclickrate` | Anchor click rate | Decimal (%) |
| `clicks_on_hashtag_challenge` | `sanidi_clicksonhashtagchallenge` | Hashtag clicks | Whole number |

## Social (11)

| Metric | Column | Label | Type |
|---|---|---|---|
| `follows` | `sanidi_follows` | Paid follows | Whole number |
| `likes` | `sanidi_likes` | Paid likes | Whole number |
| `comments` | `sanidi_comments` | Paid comments | Whole number |
| `shares` | `sanidi_shares` | Paid shares | Whole number |
| `profile_visits` | `sanidi_profilevisits` | Paid profile visits | Whole number |
| `profile_visits_rate` | `sanidi_profilevisitsrate` | Paid profile visit rate | Decimal (%) |
| `tt_playlist_visit` | `sanidi_ttplaylistvisit` | Playlist page visit | Whole number |
| `tt_playlist_visit_rate` | `sanidi_ttplaylistvisitrate` | Playlist page visit rate | Decimal (%) |
| `cost_per_consideration` | `sanidi_costperconsideration` | Cost per consideration | Currency |
| `new_consideration_rate` | `sanidi_newconsiderationrate` | New consideration rate | Decimal (%) |
| `new_consideration_size` | `sanidi_newconsiderationsize` | New consideration size | Whole number |

## Website Conversions (109)

| Metric | Column | Label | Type |
|---|---|---|---|
| `complete_payment_roas` | `sanidi_completepaymentroas` | Purchase ROAS (website) | Decimal |
| `complete_payment` | `sanidi_completepayment` | Purchases (website) | Whole number |
| `cost_per_complete_payment` | `sanidi_costpercompletepayment` | Cost per purchase (website) | Currency |
| `complete_payment_rate` | `sanidi_completepaymentrate` | Unique purchase rate (website) (%) | Decimal (%) |
| `value_per_complete_payment` | `sanidi_valuepercompletepayment` | Value per purchase (website) | Currency |
| `total_complete_payment_rate` | `sanidi_totalcompletepaymentrate` | Purchase value (website) | Currency |
| `total_landing_page_view` | `sanidi_totallandingpageview` | Landing page views (website) | Whole number |
| `cost_per_landing_page_view` | `sanidi_costperlandingpageview` | Cost per landing page view (website) | Currency |
| `landing_page_view_rate` | `sanidi_landingpageviewrate` | Landing page view rate (website) | Decimal (%) |
| `total_pageview` | `sanidi_totalpageview` | Page views (website) | Whole number |
| `cost_per_pageview` | `sanidi_costperpageview` | Cost per page view (website) | Currency |
| `pageview_rate` | `sanidi_pageviewrate` | Page view rate (website) (%) | Decimal (%) |
| `avg_value_per_pageview` | `sanidi_avgvalueperpageview` | Value per page view (website) | Currency |
| `total_value_per_pageview` | `sanidi_totalvalueperpageview` | Total page view value (website) | Currency |
| `page_browse_view` | `sanidi_pagebrowseview` | Page Browse | Whole number |
| `cost_per_page_browse_view` | `sanidi_costperpagebrowseview` | Cost per Page Browse | Currency |
| `page_browse_view_rate` | `sanidi_pagebrowseviewrate` | Page Browse Rate (%) | Decimal (%) |
| `total_page_browse_view_value` | `sanidi_totalpagebrowseviewvalue` | Total Page Browse Value | Currency |
| `value_per_page_browse_view` | `sanidi_valueperpagebrowseview` | Value per Page Browse | Currency |
| `button_click` | `sanidi_buttonclick` | Button clicks (website) | Whole number |
| `cost_per_button_click` | `sanidi_costperbuttonclick` | Cost per button click (website) | Currency |
| `button_click_rate` | `sanidi_buttonclickrate` | Unique button click rate (website) | Decimal (%) |
| `value_per_button_click` | `sanidi_valueperbuttonclick` | Value per button click (website) | Currency |
| `total_button_click_value` | `sanidi_totalbuttonclickvalue` | Button click value (website) | Currency |
| `online_consult` | `sanidi_onlineconsult` | Contacts (website) | Whole number |
| `cost_per_online_consult` | `sanidi_costperonlineconsult` | Cost per contact (website) | Currency |
| `online_consult_rate` | `sanidi_onlineconsultrate` | Unique contact rate (website) | Decimal (%) |
| `value_per_online_consult` | `sanidi_valueperonlineconsult` | Value per contact (website) | Currency |
| `total_online_consult_value` | `sanidi_totalonlineconsultvalue` | Contact value (website) | Currency |
| `user_registration` | `sanidi_userregistration` | Registrations (website) | Whole number |
| `cost_per_user_registration` | `sanidi_costperuserregistration` | Cost per registration (website) | Currency |
| `user_registration_rate` | `sanidi_userregistrationrate` | Unique registration rate (website) (%) | Decimal (%) |
| `value_per_user_registration` | `sanidi_valueperuserregistration` | Value per registration (website) | Currency |
| `total_user_registration_value` | `sanidi_totaluserregistrationvalue` | Registration value (website) | Currency |
| `page_content_view_events` | `sanidi_pagecontentviewevents` | Content views (website) | Whole number |
| `cost_per_page_content_view_event` | `sanidi_costperpagecontentviewevent` | Cost per content view (website) | Currency |
| `page_content_view_event_rate` | `sanidi_pagecontentvieweventrate` | Unique content view rate (website) (%) | Decimal (%) |
| `value_per_page_content_view_event` | `sanidi_valueperpagecontentviewevent` | Value per content view (website) | Currency |
| `total_page_view_content_events_value` | `sanidi_totalpageviewcontenteventsvalue` | Content view value (website) | Currency |
| `product_details_page_browse` | `sanidi_productdetailspagebrowse` | Product Details Page Browse | Whole number |
| `cost_per_product_details_page_browse` | `sanidi_costperproductdetailspagebrowse` | Product Details Page Browse Cost | Currency |
| `product_details_page_browse_rate` | `sanidi_productdetailspagebrowserate` | Product Details Page Browse Rate (%) | Decimal (%) |
| `value_per_product_details_page_browse` | `sanidi_valueperproductdetailspagebrowse` | Value per Product Details Page Browse | Currency |
| `total_product_details_page_browse_value` | `sanidi_totalproductdetailspagebrowsevalue` | Total Product Details Page Browse Value | Currency |
| `web_event_add_to_cart` | `sanidi_webeventaddtocart` | Adds to cart (website) | Whole number |
| `cost_per_web_event_add_to_cart` | `sanidi_costperwebeventaddtocart` | Cost per add to cart (website) | Currency |
| `web_event_add_to_cart_rate` | `sanidi_webeventaddtocartrate` | Unique add to cart rate (website) (%) | Decimal (%) |
| `value_per_web_event_add_to_cart` | `sanidi_valueperwebeventaddtocart` | Value per add to cart (website) | Currency |
| `total_web_event_add_to_cart_value` | `sanidi_totalwebeventaddtocartvalue` | Add to cart value (website) | Currency |
| `on_web_order` | `sanidi_onweborder` | Orders placed (website) | Whole number |
| `cost_per_on_web_order` | `sanidi_costperonweborder` | Cost per order placed (website) | Currency |
| `on_web_order_rate` | `sanidi_onweborderrate` | Unique orders placed rate (website) (%) | Decimal (%) |
| `value_per_on_web_order` | `sanidi_valueperonweborder` | Value per order placed (website) | Currency |
| `total_on_web_order_value` | `sanidi_totalonwebordervalue` | Orders placed value (website) | Currency |
| `initiate_checkout` | `sanidi_initiatecheckout` | Checkouts initiated (website) | Whole number |
| `cost_per_initiate_checkout` | `sanidi_costperinitiatecheckout` | Cost per checkout initiated (website) | Currency |
| `initiate_checkout_rate` | `sanidi_initiatecheckoutrate` | Unique checkout initiation rate (website) (%) | Decimal (%) |
| `value_per_initiate_checkout` | `sanidi_valueperinitiatecheckout` | Value per checkout initiated (website) | Currency |
| `total_initiate_checkout_value` | `sanidi_totalinitiatecheckoutvalue` | Checkout initiation value (website) | Currency |
| `add_billing` | `sanidi_addbilling` | Payment info added (website) | Whole number |
| `cost_per_add_billing` | `sanidi_costperaddbilling` | Cost per payment info added (website) | Currency |
| `add_billing_rate` | `sanidi_addbillingrate` | Unique payment info added rate (%) (website) | Decimal (%) |
| `value_per_add_billing` | `sanidi_valueperaddbilling` | Value per payment info added (website) | Currency |
| `total_add_billing_value` | `sanidi_totaladdbillingvalue` | Add payment info value (website) | Currency |
| `page_event_search` | `sanidi_pageeventsearch` | Searches (website) | Whole number |
| `cost_per_page_event_search` | `sanidi_costperpageeventsearch` | Cost per search (website) | Currency |
| `page_event_search_rate` | `sanidi_pageeventsearchrate` | Unique search rate (website) (%) | Decimal (%) |
| `value_per_page_event_search` | `sanidi_valueperpageeventsearch` | Value per search (website) | Currency |
| `total_page_event_search_value` | `sanidi_totalpageeventsearchvalue` | Search value (website) | Currency |
| `form` | `sanidi_form` | Form submissions (website) | Whole number |
| `cost_per_form` | `sanidi_costperform` | Cost per form submitted (website) | Currency |
| `form_rate` | `sanidi_formrate` | Unique form submission rate (website) (%) | Decimal (%) |
| `value_per_form` | `sanidi_valueperform` | Value per form submitted (website) | Currency |
| `total_form_value` | `sanidi_totalformvalue` | Form submission value (website) | Currency |
| `download_start` | `sanidi_downloadstart` | Downloads (website) | Whole number |
| `cost_per_download_start` | `sanidi_costperdownloadstart` | Cost per download (website) | Currency |
| `download_start_rate` | `sanidi_downloadstartrate` | Unique download rate (website) (%) | Decimal (%) |
| `value_per_download_start` | `sanidi_valueperdownloadstart` | Value per download (website) | Currency |
| `total_download_start_value` | `sanidi_totaldownloadstartvalue` | Download value (website) | Currency |
| `on_web_add_to_wishlist` | `sanidi_onwebaddtowishlist` | Adds to wishlist (website) | Whole number |
| `cost_per_on_web_add_to_wishlist` | `sanidi_costperonwebaddtowishlist` | Cost per add to wishlist (website) | Currency |
| `on_web_add_to_wishlist_per_click` | `sanidi_onwebaddtowishlistperclick` | Unique add to wishlist rate (website) (%) | Decimal (%) |
| `value_per_on_web_add_to_wishlist` | `sanidi_valueperonwebaddtowishlist` | Value per add to wishlist (website) | Currency |
| `total_on_web_add_to_wishlist_value` | `sanidi_totalonwebaddtowishlistvalue` | Add to wishlist value (website) | Currency |
| `on_web_subscribe` | `sanidi_onwebsubscribe` | Subscriptions (website) | Whole number |
| `cost_per_on_web_subscribe` | `sanidi_costperonwebsubscribe` | Cost per subscription (website) | Currency |
| `on_web_subscribe_per_click` | `sanidi_onwebsubscribeperclick` | Unique subscription rate (website) (%) | Decimal (%) |
| `value_per_on_web_subscribe` | `sanidi_valueperonwebsubscribe` | Value per subscription (website) | Currency |
| `total_on_web_subscribe_value` | `sanidi_totalonwebsubscribevalue` | Subscription value (website) | Currency |
| `website_total_find_location` | `sanidi_websitetotalfindlocation` | Total find location | Whole number |
| `website_cost_per_find_location` | `sanidi_websitecostperfindlocation` | Cost per find location | Currency |
| `website_find_location_rate` | `sanidi_websitefindlocationrate` | Find location rate | Decimal (%) |
| `website_value_per_find_location` | `sanidi_websitevalueperfindlocation` | Value per find location | Currency |
| `website_total_find_location_value` | `sanidi_websitetotalfindlocationvalue` | Total find location value | Currency |
| `website_total_schedule` | `sanidi_websitetotalschedule` | Total schedule | Whole number |
| `website_cost_per_schedule` | `sanidi_websitecostperschedule` | Cost per schedule | Currency |
| `website_schedule_rate` | `sanidi_websiteschedulerate` | Schedule rate | Decimal (%) |
| `website_value_per_schedule` | `sanidi_websitevalueperschedule` | Value per schedule | Currency |
| `website_total_schedule_value` | `sanidi_websitetotalschedulevalue` | Total schedule value | Currency |
| `website_total_customize_product` | `sanidi_websitetotalcustomizeproduct` | Total customize product | Whole number |
| `website_cost_per_customize_product` | `sanidi_websitecostpercustomizeproduct` | Cost per customize product | Currency |
| `website_customize_product_rate` | `sanidi_websitecustomizeproductrate` | Customize product rate | Decimal (%) |
| `website_value_per_customize_product` | `sanidi_websitevaluepercustomizeproduct` | Value per customize product | Currency |
| `website_total_customize_product_value` | `sanidi_websitetotalcustomizeproductvalue` | Total customize product value | Currency |
| `custom_page_events` | `sanidi_custompageevents` | Custom events (website) | Whole number |
| `cost_per_custom_page_event` | `sanidi_costpercustompageevent` | Cost per custom event (website) | Currency |
| `custom_page_event_rate` | `sanidi_custompageeventrate` | Custom event rate (website) (%) | Decimal (%) |
| `value_per_custom_page_event` | `sanidi_valuepercustompageevent` | Value per custom event (website) | Currency |
| `custom_page_events_value` | `sanidi_custompageeventsvalue` | Custom event value (website) | Currency |

## Attribution (30)

| Metric | Column | Label | Type |
|---|---|---|---|
| `vta_conversion` | `sanidi_vtaconversion` | VTA conversions | Whole number |
| `cost_per_vta_conversion` | `sanidi_costpervtaconversion` | Cost per VTA conversion | Currency |
| `cta_conversion` | `sanidi_ctaconversion` | CTA conversions | Whole number |
| `cost_per_cta_conversion` | `sanidi_costperctaconversion` | Cost per CTA conversion | Currency |
| `engaged_view_through_conversions` | `sanidi_engagedviewthroughconversions` | EVTA conversions | Whole number |
| `cost_per_engaged_view_through_conversion` | `sanidi_costperengagedviewthroughconversion` | Cost per EVTA conversion | Currency |
| `vta_app_install` | `sanidi_vtaappinstall` | VTA app installs | Whole number |
| `cost_per_vta_app_install` | `sanidi_costpervtaappinstall` | Cost per VTA app install | Currency |
| `cta_app_install` | `sanidi_ctaappinstall` | CTA app installs | Whole number |
| `cost_per_cta_app_install` | `sanidi_costperctaappinstall` | Cost per CTA app install | Currency |
| `evta_app_install` | `sanidi_evtaappinstall` | EVTA app installs | Whole number |
| `cost_per_evta_app_install` | `sanidi_costperevtaappinstall` | Cost per EVTA app install | Currency |
| `vta_registration` | `sanidi_vtaregistration` | VTA registrations | Whole number |
| `cost_per_vta_registration` | `sanidi_costpervtaregistration` | Cost per VTA registration | Currency |
| `cta_registration` | `sanidi_ctaregistration` | CTA registrations | Whole number |
| `cost_per_cta_registration` | `sanidi_costperctaregistration` | Cost per CTA registration | Currency |
| `evta_registration` | `sanidi_evtaregistration` | EVTA registrations | Whole number |
| `cost_per_evta_registration` | `sanidi_costperevtaregistration` | Cost per EVTA registration | Currency |
| `vta_purchase` | `sanidi_vtapurchase` | VTA purchases (app) | Whole number |
| `cost_per_vta_purchase` | `sanidi_costpervtapurchase` | Cost per VTA purchase (app) | Currency |
| `cta_purchase` | `sanidi_ctapurchase` | CTA purchases (app) | Whole number |
| `cost_per_cta_purchase` | `sanidi_costperctapurchase` | Cost per CTA purchase (app) | Currency |
| `evta_purchase` | `sanidi_evtapurchase` | EVTA purchases (app) | Whole number |
| `cost_per_evta_purchase` | `sanidi_costperevtapurchase` | Cost per EVTA purchase (app) | Currency |
| `vta_complete_payment` | `sanidi_vtacompletepayment` | VTA purchases (website) | Whole number |
| `cost_per_vta_payments_completed` | `sanidi_costpervtapaymentscompleted` | Cost per VTA purchase (website) | Currency |
| `evta_payments_completed` | `sanidi_evtapaymentscompleted` | EVTA purchases (website) | Whole number |
| `cost_per_evta_payments_completed` | `sanidi_costperevtapaymentscompleted` | Cost per EVTA purchase (website) | Currency |
| `vta_complete_payment_value` | `sanidi_vtacompletepaymentvalue` | VTA purchase value | Currency |
| `vta_complete_payment_roas` | `sanidi_vtacompletepaymentroas` | VTA purchase ROAS | Decimal |

Totals: 204 metrics: 92 currency, 67 whole number, 35 percentage, 10 decimal.
