"""Creates the patch, the global Month / Weekday choices, the 26 insight tables with their columns, alternate keys and
parent lookups (spec.py), in English and Arabic.

  python3 deploy_tables.py                     # dry run
  python3 deploy_tables.py --apply             # create what is missing, then publish
  python3 deploy_tables.py --apply --only=sanidi_metacampaigndailyinsight

Safe to re-run: existing components are skipped (never changed or deleted). Metric columns copy the parent's
column (spec.parent_columns()): type, precision, range, choices, and the English and Arabic labels; descriptions say
"Daily / Monthly insights" instead of "Insights (all time)".
"""
import sys
import time
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402

EN, AR = 1033, 1025
REQ_NONE = {"Value": "None", "CanBeChanged": True, "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}

# Arabic labels of the columns every insight table has (glossary of translations/AlSanidiMarketing).
COMMON_AR = {
    "sanidi_name": "الاسم", "sanidi_platformid": "معرّف المنصة", "sanidi_date": "التاريخ", "sanidi_day": "اليوم",
    "sanidi_month": "الشهر", "sanidi_year": "السنة", "sanidi_weekday": "يوم الأسبوع",
    "sanidi_periodclosed": "الفترة مغلقة", "sanidi_nodata": "لا توجد بيانات", "sanidi_insightkey": "مفتاح المؤشر",
    "sanidi_lastsyncedon": "تاريخ آخر مزامنة", "sanidi_rawpayload": "البيانات الخام",
}
COMMON_DESC_AR = {
    "sanidi_platformid": "معرّف الحملة / المجموعة الإعلانية / الإعلان على المنصة.",
    "sanidi_date": {"daily": "يوم الإحصائيات (حسب المنطقة الزمنية للحساب الإعلاني).",
                    "monthly": "اليوم الأول من شهر الإحصائيات (حسب المنطقة الزمنية للحساب الإعلاني)."},
    "sanidi_day": "يوم الشهر (1-31).", "sanidi_month": "شهر الإحصائيات (1 = يناير).",
    "sanidi_year": "سنة الإحصائيات.", "sanidi_weekday": "يوم الأسبوع (1 = الأحد).",
    "sanidi_periodclosed": {"daily": "نعم عندما ينتهي اليوم ويُحدَّث بعد انتهائه. قد تعدّل المنصة الأرقام القديمة "
                                     "(التحويلات، الإسناد)، ويلتقط ذلك التحديث الأسبوعي.",
                            "monthly": "نعم عندما ينتهي الشهر ويُحدَّث بعد انتهائه. قد تعدّل المنصة الأرقام القديمة "
                                       "(التحويلات، الإسناد)، ويلتقط ذلك التحديث الأسبوعي."},
    "sanidi_nodata": {"daily": "نعم عندما لا تُرجع المنصة أي إحصائيات لهذا اليوم.",
                      "monthly": "نعم عندما لا تُرجع المنصة أي إحصائيات لهذا الشهر: يوجد السجل حتى لا يغيب الشهر "
                                 "عن التقارير."},
    "sanidi_insightkey": {"daily": "مفتاح فريد: <معرّف المنصة>_YYYYMMDD. يُستخدم لتحديث السجل.",
                          "monthly": "مفتاح فريد: <معرّف المنصة>_YYYYMM. يُستخدم لتحديث السجل."},
    "sanidi_lastsyncedon": "وقت آخر كتابة لهذا السجل بواسطة المزامنة.",
    "sanidi_rawpayload": "السجل الأصلي من المنصة (JSON).",
}
PERIOD_AR = {"daily": "مؤشرات الأداء اليومية", "monthly": "مؤشرات الأداء الشهرية"}
DESC_PREFIX = {"daily": ("Daily insights: ", "مؤشرات الأداء اليومية: "),
               "monthly": ("Monthly insights: ", "مؤشرات الأداء الشهرية: ")}
ALL_TIME = ("Insights (all time): ", "مؤشرات الأداء (طوال المدة): ")


def label(en, ar=None):
    labels = [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": en, "LanguageCode": EN}]
    if ar:
        labels.append({"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": ar, "LanguageCode": AR})
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": labels}


def per_period(value, period):
    return value[period] if isinstance(value, dict) else value


def solution_name(dv):
    s = dv.first(f"solutions?$select=uniquename&$filter=friendlyname eq '{spec.PATCH['displayname']}'")
    return s["uniquename"] if s else None


def ensure_patch(dv, apply):
    name = solution_name(dv)
    if name:
        print(f"patch: {name} exists")
        return name
    print(f"patch: create '{spec.PATCH['displayname']}' {spec.PATCH['version']} of {spec.PATCH['parent']}")
    if not apply:
        return None
    dv.request("POST", "CloneAsPatch", {"ParentSolutionUniqueName": spec.PATCH["parent"],
                                        "DisplayName": spec.PATCH["displayname"],
                                        "VersionNumber": spec.PATCH["version"]})
    name = solution_name(dv)
    print(f"  created {name}")
    return name


def ensure_global_choices(dv, solution, apply):
    arabic = {"sanidi_month": spec.MONTHS_AR, "sanidi_weekday": spec.WEEKDAYS_AR}
    labels_ar = {"sanidi_month": ("الشهر", "الشهر الميلادي (1 = يناير)."),
                 "sanidi_weekday": ("يوم الأسبوع", "يوم الأسبوع (1 = الأحد).")}
    for name, (display, description, values) in spec.GLOBAL_CHOICES.items():
        if _global_exists(dv, name):
            print(f"choice {name}: exists")
            continue
        print(f"choice {name}: create ({len(values)} values)")
        if not apply:
            continue
        dv.request("POST", "GlobalOptionSetDefinitions", {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata", "Name": name, "IsGlobal": True,
            "OptionSetType": "Picklist", "DisplayName": label(display, labels_ar[name][0]),
            "Description": label(description, labels_ar[name][1]),
            "Options": [{"Value": i, "Label": label(v, arabic[name][i - 1])} for i, v in enumerate(values, 1)]},
            solution=solution)


def _global_exists(dv, name):
    try:
        dv.get(f"GlobalOptionSetDefinitions(Name='{name}')?$select=Name")
        return True
    except RuntimeError as e:
        if "404" in str(e) or "not found" in str(e).lower() or "does not exist" in str(e).lower():
            return False
        raise


def common_metadata(t, col):
    name, display, kind, description = col
    period = t["period"]
    base = {"SchemaName": name, "RequiredLevel": REQ_NONE,
            "DisplayName": label(display, COMMON_AR[name]),
            "Description": label(description, per_period(COMMON_DESC_AR[name], period))}
    if kind in ("text100", "text150"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", **base,
                "MaxLength": 100 if kind == "text100" else 150, "FormatName": {"Value": "Text"}}
    if kind == "dateonly":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", **base,
                "Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}}
    if kind == "datetime":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", **base,
                "Format": "DateAndTime", "DateTimeBehavior": {"Value": "UserLocal"}}
    if kind == "day":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", **base,
                "Format": "None", "MinValue": 1, "MaxValue": 31}
    if kind == "year":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", **base,
                "Format": "None", "MinValue": 2000, "MaxValue": 2100}
    if kind in ("month", "weekday"):
        return {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata", **base,
                "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions(Name='sanidi_{kind}')"}
    if kind == "bool":
        return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", **base, "DefaultValue": False,
                "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                              "TrueOption": {"Value": 1, "Label": label("Yes", "نعم")},
                              "FalseOption": {"Value": 0, "Label": label("No", "لا")}}}
    if kind == "memo":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", **base,
                "MaxLength": 100000, "Format": "TextArea"}
    raise ValueError(kind)


def metric_description(text, lang, period):
    prefix = DESC_PREFIX[period][0 if lang == EN else 1]
    old = ALL_TIME[0 if lang == EN else 1]
    if text.startswith(old):
        return prefix + text[len(old):]
    return text


def metric_metadata(t, c):
    en, ar = c["label"].get(str(EN)), c["label"].get(str(AR))
    d_en = metric_description(c["description"].get(str(EN), ""), EN, t["period"])
    d_ar = c["description"].get(str(AR))
    d_ar = metric_description(d_ar, AR, t["period"]) if d_ar else None
    base = {"SchemaName": c["schema"], "RequiredLevel": REQ_NONE, "DisplayName": label(en, ar),
            "Description": label(d_en, d_ar)}
    kind = c["type"]
    if kind == "IntegerType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", **base,
                "Format": c.get("Format") or "None", "MinValue": c["MinValue"], "MaxValue": c["MaxValue"]}
    if kind == "DecimalType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata", **base,
                "Precision": c["Precision"], "MinValue": c["MinValue"], "MaxValue": c["MaxValue"]}
    if kind == "DoubleType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DoubleAttributeMetadata", **base,
                "Precision": c["Precision"], "MinValue": c["MinValue"], "MaxValue": c["MaxValue"]}
    if kind == "MoneyType":
        m = {"@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata", **base,
             "PrecisionSource": c["PrecisionSource"], "MinValue": c["MinValue"], "MaxValue": c["MaxValue"]}
        if c["PrecisionSource"] == 0:
            m["Precision"] = c["Precision"]
        return m
    if kind == "StringType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", **base,
                "MaxLength": c["MaxLength"], "FormatName": c.get("FormatName") or {"Value": "Text"}}
    if kind == "MemoType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", **base,
                "MaxLength": c["MaxLength"], "Format": "TextArea"}
    if kind == "DateTimeType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", **base,
                "Format": c["Format"], "DateTimeBehavior": c["DateTimeBehavior"]}
    if kind == "PicklistType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata", **base,
                "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata", "IsGlobal": False,
                              "OptionSetType": "Picklist",
                              "Options": [{"Value": v, "Label": label(l.get(str(EN)), l.get(str(AR)))}
                                          for v, l in c["options"]]}}
    if kind == "BooleanType":
        return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", **base, "DefaultValue": False,
                "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                              "TrueOption": {"Value": 1, "Label": label("Yes", "نعم")},
                              "FalseOption": {"Value": 0, "Label": label("No", "لا")}}}
    raise ValueError(kind)


def parent_labels(dv, parent):
    e = dv.get(f"EntityDefinitions(LogicalName='{parent}')?$select=DisplayName,DisplayCollectionName,ObjectTypeCode")
    get = lambda lbl, lang: next((l["Label"] for l in lbl["LocalizedLabels"] if l["LanguageCode"] == lang), None)
    return {"ar": get(e["DisplayName"], AR), "ar_plural": get(e["DisplayCollectionName"], AR)}


def entity_metadata(t, parent_ar):
    word_ar = PERIOD_AR[t["period"]]
    ar = f"{parent_ar['ar']} - {word_ar}" if parent_ar["ar"] else None
    ar_plural = f"{parent_ar['ar_plural']} - {word_ar}" if parent_ar["ar_plural"] else None
    desc_ar = (f"إحصائيات {parent_ar['ar']} كما تُبلغ عنها المنصة "
               + ("لكل يوم." if t["period"] == "daily" else "لكل شهر (غير مجمّعة من الأيام).")) if parent_ar["ar"] else None
    name_desc = ("<item name> · YYYY-MM-DD" if t["period"] == "daily" else "<item name> · YYYY-MM")
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata", "SchemaName": t["schema"],
            "DisplayName": label(t["display"], ar), "DisplayCollectionName": label(t["plural"], ar_plural),
            "Description": label(t["description"], desc_ar), "OwnershipType": "UserOwned",
            "HasActivities": False, "HasNotes": False, "IsActivity": False, "ChangeTrackingEnabled": True,
            "Attributes": [{"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                            "SchemaName": "sanidi_Name", "IsPrimaryName": True, "RequiredLevel": REQ_NONE,
                            "DisplayName": label("Name", COMMON_AR["sanidi_name"]),
                            "Description": label(name_desc, name_desc), "MaxLength": 450,
                            "FormatName": {"Value": "Text"}}]}


def add_attribute(dv, logical, metadata, solution):
    """Metadata writes run one at a time per environment; retry transient failures after checking."""
    path = f"EntityDefinitions(LogicalName='{logical}')/Attributes"
    for attempt in range(5):
        try:
            dv.request("POST", path, metadata, solution=solution)
            return
        except (RuntimeError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            text = str(e).lower()
            transient = (not isinstance(e, RuntimeError) or "unexpected error" in text
                         or "cannot start another" in text or "timeout" in text)
            if attempt == 4 or not transient:
                raise
            time.sleep(10 * (attempt + 1))
            if dv.first(f"{path}?$select=LogicalName&$filter=LogicalName eq '{metadata['SchemaName'].lower()}'"):
                return


def ensure_lookup(dv, t, solution, apply, existing):
    if t["lookup"] in existing:
        return
    print(f"  lookup {t['lookup']} -> {t['parent']}")
    if not apply:
        return
    parent_ar = parent_labels(dv, t["parent"])["ar"]
    body = {"@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata", "SchemaName": t["relationship"],
            "ReferencedEntity": t["parent"], "ReferencingEntity": t["schema"],
            "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
                                     "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade",
                                     "RollupView": "NoCascade"},
            "Lookup": {"@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata", "SchemaName": t["lookup"],
                       "DisplayName": label(t["lookup_display"], parent_ar), "RequiredLevel": REQ_NONE,
                       "Description": label(f"The {t['lookup_display']} these statistics belong to.",
                                            f"{parent_ar} الذي تخصه هذه الإحصائيات." if parent_ar else None)}}
    for attempt in range(5):
        try:
            dv.request("POST", "RelationshipDefinitions", body, solution=solution)
            return
        except RuntimeError as e:
            if attempt == 4 or "cannot start another" not in str(e).lower():
                raise
            time.sleep(15 * (attempt + 1))


def ensure_key(dv, t, solution, apply):
    keys = dv.get(f"EntityDefinitions(LogicalName='{t['schema']}')/Keys?$select=LogicalName")["value"]
    if any(k["LogicalName"] == t["key_name"] for k in keys):
        return
    print(f"  alternate key {t['key_name']} (sanidi_insightkey)")
    if not apply:
        return
    dv.request("POST", f"EntityDefinitions(LogicalName='{t['schema']}')/Keys", {
        "SchemaName": t["key_name"], "DisplayName": label("Insight Key", COMMON_AR["sanidi_insightkey"]),
        "KeyAttributes": ["sanidi_insightkey"]}, solution=solution)


def main(apply, only=None):
    dv = Dataverse()
    solution = ensure_patch(dv, apply) or spec.SOLUTION
    ensure_global_choices(dv, solution, apply)
    tables = spec.check()
    done = []
    for logical, t in tables.items():
        if only and logical not in only:
            continue
        exists = dv.first(f"EntityDefinitions?$select=LogicalName&$filter=LogicalName eq '{logical}'")
        have = set()
        if exists:
            have = {a["LogicalName"] for a in dv.get(
                f"EntityDefinitions(LogicalName='{logical}')/Attributes?$select=LogicalName")["value"]}
        todo = [("common", c) for c in t["common"] if c[0] not in have]
        todo += [("metric", c) for c in t["metrics"] if c["name"] not in have]
        print(f"{logical}: table {'exists' if exists else 'create'}; {len(todo)} columns to add")
        if not apply:
            ensure_lookup(dv, t, solution, False, have)
            continue
        if not exists:
            dv.request("POST", "EntityDefinitions", entity_metadata(t, parent_labels(dv, t["parent"])),
                       solution=solution)
            print(f"  created table {logical}")
            time.sleep(20)  # a brand-new table rejects columns for a short while
        for i, (kind, c) in enumerate(todo, 1):
            md = common_metadata(t, c) if kind == "common" else metric_metadata(t, c)
            add_attribute(dv, logical, md, solution)
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} columns")
        ensure_lookup(dv, t, solution, True, have)
        ensure_key(dv, t, solution, True)
        done.append(logical)
    if apply and done:
        xml = "".join(f"<entity>{t}</entity>" for t in done)
        dv.request("POST", "PublishXml", idempotent=True,
                   body={"ParameterXml": f"<importexportxml><entities>{xml}</entities></importexportxml>"})
        print(f"published {len(done)} tables")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    main("--apply" in sys.argv, only[0].split(",") if only else None)
