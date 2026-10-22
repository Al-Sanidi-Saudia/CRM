"""Season Calendar: one row per day with a Yes/No flag for each marketing season (source/AlSanidi-Seasons.xlsx).

Columns are listed in the workbook's order. Each flag is (column, English, Arabic, workbook header); the
Arabic label is the workbook header without the "قائمة" prefix.
"""
PREFIX = "sanidi_"
TABLE = "seasoncalendar"
YEAR = 2026

DISPLAY = ("Season Calendar Day", "يوم في تقويم المواسم")
PLURAL = ("Season Calendar", "تقويم المواسم")
DESCRIPTION = ("One row per day with the marketing seasons, holidays and paydays that fall on it.",
               "صف لكل يوم يبيّن المواسم التسويقية والإجازات وأيام صرف الرواتب الواقعة فيه.")

# (column, English, Arabic, description English, description Arabic)
NAME = ("name", "Name", "الاسم", "The day as text (yyyy-mm-dd).", "اليوم كنص (yyyy-mm-dd).")
DATE = ("date", "Date", "التاريخ", "The calendar day.", "اليوم في التقويم.")
YEAR_COL = ("year", "Year", "السنة", "The calendar year of the day.", "السنة التي يقع فيها اليوم.")

FLAGS = [
    ("ramadan", "Ramadan", "رمضان", "قائمة رمضان"),
    ("eidalfitr", "Eid Al-Fitr", "عيد الفطر", "قائمة  عيد الفطر  "),
    ("travel", "Travel", "السفر", "قائمة السفر"),
    ("domestictravel", "Domestic Travel", "السفر الداخلي", "قائمة السفر  الداخلي"),
    ("huntingapril", "Hunting (April)", "الصيد شهر 4", "قائمة الصيد شهر 4"),
    ("summer", "Summer", "الصيفية", "قائمة الصيفية"),
    ("eidaladha", "Eid Al-Adha", "الأضحى", "قائمة الاضحي"),
    ("huntingaugust", "Hunting (August)", "الصيد شهر 8", "قائمة الصيد شهر 8"),
    ("outboundcustomers", "Outbound Customers", "العملاء الخارجين", "قائمة العملاء الخارجين"),
    ("alwasm", "Al-Wasm Season", "الوسم", "قائمة الوسم"),
    ("winter", "Winter", "الشتاء", "قائمة الشتاء"),
    ("springbreak", "Spring Break", "إجازة الربيع", "قائمة  إجازة الربيع"),
    ("nationaldayholiday", "National Day Holiday", "إجازة اليوم الوطني", "قائمة إجازة اليوم الوطني"),
    ("extraholiday1", "Extra Holiday 1", "إجازة إضافية 1", "قائمة إجازة إضافية 1"),
    ("firsttermbreak", "First Term Break", "إجازة الفصل الأول", "قائمة إجازة الفصل الأول"),
    ("extraholiday2", "Extra Holiday 2", "إجازة إضافية 2", "قائمة إجازة إضافية 2"),
    ("midyearbreak", "Mid-Year Break", "إجازة منتصف العام", "قائمة إجازة منتصف العام"),
    ("foundingday", "Founding Day", "يوم التأسيس", "قائمة يوم التأسيس"),
    ("eidalfitrschoolholiday", "Eid Al-Fitr School Holiday", "إجازة عيد الفطر الدراسية",
     "قائمة إجازة عيد الفطر الدراسية"),
    ("eidaladhaschoolholiday", "Eid Al-Adha School Holiday", "إجازة عيد الأضحى الدراسية",
     "قائمة إجازة عيد الأضحى الدراسية"),
    ("endofschoolyearholiday", "End of School Year Holiday", "إجازة نهاية العام الدراسي",
     "قائمة إجازة نهاية العام الدراسي"),
    ("governmentpayday", "Government Payday", "صرف الرواتب الحكومية", "قائمة صرف الرواتب الحكومية"),
    ("privatesectorpayday", "Private Sector Payday", "صرف رواتب الشركات", "قائمة صرف رواتب الشركات"),
    ("retireespayday", "Retirees & Social Security Payday", "صرف المتقاعدين والضمان",
     "قائمة صرف المتقاعدين والضمان"),
    ("citizenaccount", "Citizen Account Payment", "حساب المواطن", "قائمة حساب المواطن"),
    ("socialsecuritypayday", "Developed Social Security Payment", "صرف الضمان الاجتماعي المطور",
     "قائمة صرف الضمان الاجتماعي المطور"),
]


def flag_description(english, arabic):
    return f"Yes when the day is in the {english} list.", f"نعم إذا كان اليوم ضمن قائمة {arabic}."


# Main form: tab "General", one section for the day and one per group of flags.
# (section key, English, Arabic, flag columns)
SECTIONS = [
    ("religious", "Religious & National", "المناسبات الدينية والوطنية",
     ["ramadan", "eidalfitr", "eidaladha", "foundingday", "nationaldayholiday"]),
    ("travel", "Travel & Leisure", "السفر والترفيه",
     ["travel", "domestictravel", "outboundcustomers", "summer", "winter", "alwasm", "huntingapril", "huntingaugust"]),
    ("school", "School Holidays", "الإجازات الدراسية",
     ["springbreak", "midyearbreak", "firsttermbreak", "eidalfitrschoolholiday", "eidaladhaschoolholiday",
      "endofschoolyearholiday", "extraholiday1", "extraholiday2"]),
    ("paydays", "Paydays", "أيام صرف الرواتب",
     ["governmentpayday", "privatesectorpayday", "retireespayday", "citizenaccount", "socialsecuritypayday"]),
]
DAY_SECTION = ("day", "Day", "اليوم")
TAB = ("general", "General", "عام")

# Site map: a new group at the end of the General area.
GROUP = ("group_seasons", "Seasons", "المواسم")

assert sorted(c for s in SECTIONS for c in s[3]) == sorted(f[0] for f in FLAGS)
