# Monthly Insights: Data After Empty Months (AlSanidi-UAT)

Analysis of every monthly insight row (3,691 items on the 13 synced tables) as of **3 November 2026**: items that have months with data, then one or more months with **No Data = Yes**, and then data again.

## 1. Result per platform and level

| Platform | Level | Items checked | Items with data after empty months |
|---|---|---|---|
| Meta | Campaign | 19 | 0 |
| Meta | Ad Set | 46 | 0 |
| Meta | Advertisement | 153 | 0 |
| Snapchat | Campaign | 193 | 0 |
| Snapchat | Ad Squad | 363 | 0 |
| Snapchat | Advertisement | 848 | 0 |
| Google Ads | Campaign | 77 | 4 |
| Google Ads | Ad Group | 88 | 2 |
| Google Ads | Advertisement | 118 | 0 |
| Google Ads | Asset Group | 28 | 0 |
| TikTok | Campaign | 134 | 1 |
| TikTok | Ad Group | 237 | 1 |
| TikTok | Advertisement | 1,387 | 0 |
| **Total** | | **3,691** | **8** |

## 2. Campaigns where data resumes after empty months

| Platform | Campaign | Platform ID | Last month with data | Empty months (No Data = Yes) | Data resumes |
|---|---|---|---|---|---|
| Google Ads | C-2026-001-G-03 (Search) | 23070458360 | Oct 2025 | Nov 2025 – Aug 2026 (10 months) | Sep 2026 |
| Google Ads | حملة العروض الحصرية | 20824864711 | Feb 2024 | Mar – Apr 2024 (2 months) | May 2024 |
| Google Ads | حملة موسم الشتاء 2023 | 20668279390 | Dec 2023 | Jan 2024 (1 month) | Feb 2024 |
| Google Ads | Awareness l Search l 110 l Malaka | 21823140710 | Oct 2024 | Nov 2024 (1 month) | Dec 2024 |
| TikTok | fa -Sales | 1850581838815362 | Feb 2026 | Mar – Apr 2026 (2 months) | May 2026 |

## 3. Ad groups with the same pattern

| Platform | Ad Group | Platform ID | Last month with data | Empty months (No Data = Yes) | Data resumes |
|---|---|---|---|---|---|
| Google Ads | Ad group 1 | 189770930361 | Oct 2025 | Nov 2025 – Aug 2026 (10 months) | Sep 2026 |
| Google Ads | Ad group 1 | 155055093496 | Dec 2023 | Jan 2024 (1 month) | Feb 2024 |
| TikTok | Ad Group5 | 1867975995286593 | Jul 2026 | Aug 2026 (1 month) | Sep 2026 |

## Notes

- For every other item, once the first **No Data** month comes, every later month up to the current month is also empty.
- The two Google Ads ad groups match the months of a campaign above (Nov 2025 – Aug 2026, and Jan 2024); they appear to belong to those campaigns.
- These look like campaigns that were paused and restarted: the empty months had no delivery on the platform.
- Every month is fetched from the platform on its own, so a month that gets data later is updated and its **No Data** set back to No.
