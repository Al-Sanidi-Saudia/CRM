import sys, json; sys.path.insert(0, sys.argv[1])
import dv

def flows(*pairs): return json.dumps([{"name": n, "id": i} for n, i in pairs])

rows = [
    {"sanidi_name": "Meta", "sanidi_platformkey": "meta", "sanidi_sortorder": 1, "sanidi_isconfigured": True,
     "sanidi_dataflows": flows(("Get Meta Campaigns", "8b6d991c-d3c0-f111-aaaf-70a8a581e673"),
                               ("Get Meta AdSets", "947c3f10-d3c0-f111-aaaf-70a8a581e673"),
                               ("Get Meta Advertisements", "957c3f10-d3c0-f111-aaaf-70a8a581e673")),
     "sanidi_insightsflowname": "Get Meta Insights", "sanidi_insightsflowid": "e30b9610-07c5-f111-aaaf-70a8a581e5c5"},
    {"sanidi_name": "Snap", "sanidi_platformkey": "snap", "sanidi_sortorder": 2, "sanidi_isconfigured": True,
     "sanidi_dataflows": flows(("Get Snap Campaigns", "f0adc814-8c13-5fe3-8ba7-9ad697ea4ea2"),
                               ("Get Snap Ad Squads", "ddb71436-2f06-50ad-b721-146978286924"),
                               ("Get Snap Advertisements", "9c0d86ce-7ccd-5b1e-bb13-55921b643dad")),
     "sanidi_insightsflowname": "Get Snap Insights", "sanidi_insightsflowid": "028e8be8-505f-5f70-acc7-85653b1f859f"},
    {"sanidi_name": "Google Ads", "sanidi_platformkey": "google", "sanidi_sortorder": 3, "sanidi_isconfigured": True,
     "sanidi_dataflows": flows(("Get Google Ads Campaigns", "b10505e5-822c-5641-8499-e8324198b469"),
                               ("Get Google Ads Ad Groups", "3574fbc1-642c-5d29-8757-9521a4b03c8e"),
                               ("Get Google Ads Asset Groups", "5f9e257b-5d19-5fe5-9a1e-974434268472"),
                               ("Get Google Ads Advertisements", "511feda4-57bc-5009-bf26-21dd79bb8fe9")),
     "sanidi_insightsflowname": "Get Google Ads Insights", "sanidi_insightsflowid": "59399b2c-080a-50b0-afcf-b803145237cf"},
    {"sanidi_name": "TikTok", "sanidi_platformkey": "tiktok", "sanidi_sortorder": 4, "sanidi_isconfigured": False,
     "sanidi_dataflows": "[]"},
]
for r in rows:
    st, b, _ = dv.call('POST', 'sanidi_integrationplatforms', r, solution=None)
    print(r["sanidi_name"], st, b.get("sanidi_integrationplatformid") if isinstance(b, dict) else b)
