# AlSanidi | Marketing — Arabic (Saudi Arabia, 1025) translations

Arabic labels for the `AlSanidiMarketing` solution: tables, columns, choices, forms
(tabs, sections, labels), views, the app, site map, environment variables and
flow/business-rule names.

Imported into **UAT** (`operations-alsenidiuat.crm4.dynamics.com`) on 2026-10-11 and
published. A re-export afterwards matched the imported file exactly.

**2026-10-21, TikTok:** the TikTok tables, columns, choices, forms, views, site map group, environment variables
and flows, the new Campaign / Advertisement lookups, Sync Control's *Connection Active* column, the cost roll-up
flows, and Campaign / Advertisement labels that were still empty. Texts added for TikTok never replace existing
Arabic on other components. Imported into UAT and published; `changes_ar-SA_tiktok.csv` lists every label.

**2026-10-29, TikTok patch:** the 8 columns and 6 choice values added after the live check, and the patch's name
(`TRANSLATION_SOLUTION=AlSanidiMarketing_Patch_5b266c1a python3 tool/uat.py export ...`). 24 labels, none changed;
`changes_ar-SA_tiktok_patch.csv`, `files/CrmTranslations_ar-SA_TikTokPatch.zip`.

**2026-10-22, Season Calendar:** the new `sanidi_seasoncalendar` table (see `seasons/README.md`). Its table,
column, form and site map labels were created in Arabic by `seasons/deploy.py`. This round added the names
Dataverse generates (views, forms, Advanced Find, …) and aligned its system column labels with the glossary.
Only Season Calendar labels changed. Imported into UAT and published; `changes_ar-SA_seasons.csv` lists every label.

## Contents

| Path | What it is |
|---|---|
| `files/CrmTranslations_ar-SA.zip` | The translation file that was imported. Import it into another environment (e.g. production) with **Solutions → AlSanidi \| Marketing → Translations → Import translations**, then **Publish all customizations**. |
| `files/CrmTranslations_original_export.zip` | The export taken before any change (rollback / reference). |
| `files/CrmTranslations_before_tiktok_export.zip` | The export taken before the TikTok round (rollback / reference). |
| `files/CrmTranslations_before_seasons_export.zip` | The export taken before the Season Calendar round (rollback / reference). |
| `changes_ar-SA_seasons.csv` | Labels added or changed in the Season Calendar round. |
| `changes_ar-SA_tiktok.csv` | Labels added or changed in the TikTok round. |
| `changes_ar-SA.csv` | Every label that was added or changed: English, previous Arabic, new Arabic (opens in Excel). |
| `tool/` | Glossary and build script used to produce the file (see below). |

## Scope

- **Translated:** all components of the solution, including AlSanidi's own columns on
  the standard Product table (`GM`, `L CM`, `Classification Level 1`, …).
- **Left as is:** Microsoft's own Arabic on the standard Product table and its ribbon.
- **TikTok:** `dict_tiktok.py` (labels) and `dict_tiktok_caps.py` (choice values).
- **Season Calendar:** `dict_seasons.py` (names Dataverse generates from the table name).
- **Skipped (retired tables):** `sanidi_meta_*`, `sanidi_snap_*`, `sanidi_google_*`
  (the underscore set). The tables in use are `sanidi_metacampaign`,
  `sanidi_metaadset`, `sanidi_metaadvertisement`, `sanidi_snapcampaign`,
  `sanidi_snapadsquad`, `sanidi_snapadvertisement` and `sanidi_googleads*`.

## Conventions

- **Platform/brand names stay in English:** `حملة Meta`, `مجموعة إعلانية في Snap`,
  `حملات Google Ads`, `TikTok`, `Instagram`.
- **Abbreviations:** the Arabic term followed by the abbreviation in parentheses, e.g.
  `تكلفة النقرة (CPC)`, `تكلفة الألف ظهور (CPM)`, `عائد الإنفاق الإعلاني (ROAS)`,
  `العائد على الاستثمار (ROI)`, `الوزن بالجرام (GM)`, `الطول بالسنتيمتر (L CM)`.
- **Technical descriptions** that only name an API field (e.g.
  `Google Ads: metrics.clicks.`, `Snap: pacing_level`) keep the field reference in English
  so administrators can trace it to the API.
- **AlSanidi website terms** (alsanidi.com.sa/ar): product categories are `الأقسام`
  (Product Category → `قسم المنتجات`, Parent Category → `القسم الرئيسي`). Online store is
  `المتجر الإلكتروني` and branches are `الفروع`.

## Key glossary

| English | Arabic |
|---|---|
| Campaign | الحملة |
| Advertisement / Ad | إعلان |
| Ad Set (Meta) / Ad Squad (Snap) / Ad Group (Google) | المجموعة الإعلانية |
| Asset Group / Asset | مجموعة مواد العرض / مادة العرض |
| Creative | التصميم الإعلاني |
| Influencer | المؤثر |
| Organic / Paid | عضوي / مدفوع |
| Awareness | الوعي بالعلامة التجارية |
| Objective | الهدف |
| Impressions | مرات الظهور |
| Reach | الوصول |
| Frequency | معدل التكرار |
| Clicks | النقرات |
| CTR | نسبة النقر إلى الظهور (CTR) |
| CPC / CPM / CPA / CPV / CPP | تكلفة النقرة (CPC) / تكلفة الألف ظهور (CPM) / تكلفة الإجراء (CPA) / تكلفة المشاهدة (CPV) / تكلفة الوصول لكل ألف شخص (CPP) |
| ROAS / ROI | عائد الإنفاق الإعلاني (ROAS) / العائد على الاستثمار (ROI) |
| Spend | الإنفاق |
| Budget (Daily / Lifetime) | الميزانية (اليومية / طوال المدة) |
| Bid / Bidding / Bid Strategy | عرض السعر / عروض الأسعار / استراتيجية عروض الأسعار |
| Conversion(s) | التحويلات |
| Engagement | التفاعل |
| Landing Page | الصفحة المقصودة |
| Swipe (Snap) | السحب |
| Targeting | الاستهداف |
| Placement | موضع الإعلان |
| Delivery | عرض الإعلانات |
| Pacing | وتيرة الإنفاق |
| Attribution | الإسناد |
| Headline / Description | العنوان الرئيسي / الوصف |
| Call to Action | عبارة الحث على اتخاذ إجراء |
| Insights | مؤشرات الأداء |
| Sync | المزامنة |
| Integration Platform | منصة التكامل |
| Performance Max | الأداء الأقصى (Performance Max) |
| Demand Gen | زيادة الطلب (Demand Gen) |
| (Base) — currency columns | (العملة الأساسية) |
| (State) — rollup columns | (حالة الاحتساب) |

## Re-running after new customizations

1. Export translations for the solution (Solutions → AlSanidi | Marketing → Translations →
   Export translations) and unzip it.
2. Add any new English texts to `tool/dict*.py`. `tool/templates.py` already covers labels
   Dataverse generates on its own (`X (Base)`, `My X`, `Status of the X`, …).
3. `python tool/build_text.py CrmTranslations.xml out/CrmTranslations.xml`. Any text with
   no translation is reported as `missing` and left unchanged.
4. Zip `out/CrmTranslations.xml` with the exported `[Content_Types].xml`, import it, then
   publish all customizations.

`tool/uat.py export <zip>` / `tool/uat.py import <zip>` do steps 1 and 4 (import + publish) through the
Organization service with the service principal (`DATAVERSE_*` variables).

`tool/build.py <in.xml> <scratch.xml> <changes.csv>` writes the change report (CSV) only.
Always import the output of `build_text.py`, which keeps the exported file's layout exactly as it was.
