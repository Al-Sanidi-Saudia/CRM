# Season Calendar

One Dataverse row per day showing which marketing seasons, holidays and paydays fall on it. Built from
AlSanidi's seasons workbook (`source/AlSanidi-Seasons.xlsx`). It is in the **AlSanidi | Marketing** solution
(publisher `AlSanidiDevelopment`, prefix `sanidi_`).

Deployed to **UAT** (`operations-alsenidiuat.crm4.dynamics.com`) on 2026-10-22 with the 365 days of 2026.

## Table `sanidi_seasoncalendar`

**Season Calendar Day / Season Calendar** (يوم في تقويم المواسم / تقويم المواسم). The table is organization
owned. Every label is in English (1033) and Arabic (1025).

| Column | Type | Arabic |
|---|---|---|
| `sanidi_name` (primary) | Text, the day as `yyyy-mm-dd` | الاسم |
| `sanidi_date` | Date only, required, alternate key `sanidi_seasoncalendar_date` | التاريخ |
| `sanidi_year` | Text (4), required, `2026` | السنة |
| 26 season columns | Yes/No, default No | the workbook header without "قائمة" |

| Column | English | Arabic | Column | English | Arabic |
|---|---|---|---|---|---|
| `sanidi_ramadan` | Ramadan | رمضان | `sanidi_firsttermbreak` | First Term Break | إجازة الفصل الأول |
| `sanidi_eidalfitr` | Eid Al-Fitr | عيد الفطر | `sanidi_extraholiday2` | Extra Holiday 2 | إجازة إضافية 2 |
| `sanidi_travel` | Travel | السفر | `sanidi_midyearbreak` | Mid-Year Break | إجازة منتصف العام |
| `sanidi_domestictravel` | Domestic Travel | السفر الداخلي | `sanidi_foundingday` | Founding Day | يوم التأسيس |
| `sanidi_huntingapril` | Hunting (April) | الصيد شهر 4 | `sanidi_eidalfitrschoolholiday` | Eid Al-Fitr School Holiday | إجازة عيد الفطر الدراسية |
| `sanidi_summer` | Summer | الصيفية | `sanidi_eidaladhaschoolholiday` | Eid Al-Adha School Holiday | إجازة عيد الأضحى الدراسية |
| `sanidi_eidaladha` | Eid Al-Adha | الأضحى | `sanidi_endofschoolyearholiday` | End of School Year Holiday | إجازة نهاية العام الدراسي |
| `sanidi_huntingaugust` | Hunting (August) | الصيد شهر 8 | `sanidi_governmentpayday` | Government Payday | صرف الرواتب الحكومية |
| `sanidi_outboundcustomers` | Outbound Customers | العملاء الخارجين | `sanidi_privatesectorpayday` | Private Sector Payday | صرف رواتب الشركات |
| `sanidi_alwasm` | Al-Wasm Season | الوسم | `sanidi_retireespayday` | Retirees & Social Security Payday | صرف المتقاعدين والضمان |
| `sanidi_winter` | Winter | الشتاء | `sanidi_citizenaccount` | Citizen Account Payment | حساب المواطن |
| `sanidi_springbreak` | Spring Break | إجازة الربيع | `sanidi_socialsecuritypayday` | Developed Social Security Payment | صرف الضمان الاجتماعي المطور |
| `sanidi_nationaldayholiday` | National Day Holiday | إجازة اليوم الوطني | | | |
| `sanidi_extraholiday1` | Extra Holiday 1 | إجازة إضافية 1 | | | |

## In the app

- **Site map:** a **Seasons** (المواسم) group at the end of the **General** area of *AlSanidi | Marketing*.
- **Main form "Information":** a **General** tab with the sections Day, Religious & National, Travel & Leisure,
  Paydays and School Holidays.
- **Active view:** Date, Year and all 26 flags, sorted by Date.
- **Role "AlSanidi | Marketing | Manager":** Read, Append and Append To at organization level, the same as on
  the other tables. The role is not in the solution, so this is set per environment.

## Files

| Path | What it is |
|---|---|
| `source/AlSanidi-Seasons.xlsx` | The workbook as received. |
| `spec.py` | Table, columns (English + Arabic), form sections and site map group. |
| `build_data.py` | Turns the workbook into `season_calendar_2026.csv`. |
| `season_calendar_2026.csv` | The 365 rows that were loaded. |
| `deploy.py` | Creates the table, columns, key, form, views, app entry and rows. |

The workbook's dates say **2021**, but its content is the 2026 calendar (Ramadan 18 Feb–19 Mar, Eid Al-Fitr
20–23 Mar). `build_data.py` keeps each day and month and sets the year to 2026. A `*` means Yes and an empty
cell means No.

## Running it

Uses the service principal from `scripts/dataverse-mcp.sh` (`DATAVERSE_*` variables).

```
python3 build_data.py            # workbook -> season_calendar_2026.csv
python3 deploy.py                # dry run
python3 deploy.py --apply        # create what's missing, update form / views / app / rows, publish
```

You can run it again safely. Existing columns are kept, rows are matched on Date, and only changed values are
written. For another year, set `YEAR` in `spec.py` and use a workbook for that year. The rows for the new year
are added next to the 2026 rows.

The Arabic for the labels Dataverse generates itself (view names, form names, …) comes from the translation
round in `translations/AlSanidiMarketing` (`changes_ar-SA_seasons.csv`).
