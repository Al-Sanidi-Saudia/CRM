"""Sync Control changes for the Daily & Monthly Insights (PLAN.md §3.3), saved in the patch.

  python3 deploy_synccontrol.py                       # dry run
  python3 deploy_synccontrol.py --apply               # columns + choice values, then the page
  python3 deploy_synccontrol.py --apply --only=page   # only the page

- Integration Platform: Full Load From (Date Only).
- Integration Sync Request: Sync Type values Day & Month to Date / All Time / Scheduled Daily (05:00) / Scheduled
  Intraday; Status value Skipped; columns Triggered By (Button / Schedule), Include Data, Weekly Run, Steps Log.
- The page (sync-control/page/sync-control.tsx): compiled the way pac compiles generative pages (runtime types +
  page, TypeScript ES5 / ESNext modules / React JSX) and written to the page's files (src/pages/page.tsx,
  src/pages/page.compiled); the page is added to the patch. Needs node and the TypeScript compiler (npm install
  typescript in a scratch folder; set TSC_DIR to it).
The dispatcher flow is updated by sync-control/scripts/update_dispatcher.py.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402
from deploy_tables import label, REQ_NONE, add_attribute  # noqa: E402

SOLUTION = spec.SOLUTION
PAGE_ID = "fbb9c7b0-bb45-4583-997d-6b32b0e5d29b"
PAGE_DIR = HERE.parent / "sync-control" / "page"

COLUMNS = {
    "sanidi_integrationplatform": [
        {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", "SchemaName": "sanidi_FullLoadFrom",
         "DisplayName": label("Full Load From", "التحميل الكامل من"), "RequiredLevel": REQ_NONE,
         "Description": label("First day loaded by Update All Time (daily and monthly insights). Empty = the "
                              "platform's maximum history.",
                              "أول يوم يُحمَّل عند التحديث الكامل (مؤشرات الأداء اليومية والشهرية). فارغ = أقصى سجل "
                              "تتيحه المنصة."),
         "Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}},
    ],
    "sanidi_integrationsyncrequest": [
        {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata", "SchemaName": "sanidi_TriggeredBy",
         "DisplayName": label("Triggered By", "طريقة التشغيل"), "RequiredLevel": REQ_NONE,
         "Description": label("Button: started from the Sync Control page. Schedule: created by the Social Media - "
                              "Scheduled Sync flow.",
                              "زر: بدأ من صفحة التحكم بالمزامنة. جدولة: أنشأه مسار المزامنة المجدولة لوسائل التواصل."),
         "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata", "IsGlobal": False,
                       "OptionSetType": "Picklist",
                       "Options": [{"Value": 100000000, "Label": label("Button", "زر")},
                                   {"Value": 100000001, "Label": label("Schedule", "جدولة")}]}},
        {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", "SchemaName": "sanidi_IncludeData",
         "DisplayName": label("Include Data", "تشمل البيانات"), "RequiredLevel": REQ_NONE, "DefaultValue": False,
         "Description": label("Yes: the data sync (campaigns down to the ads) runs first.",
                              "نعم: تعمل مزامنة البيانات (من الحملات حتى الإعلانات) أولاً."),
         "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                       "TrueOption": {"Value": 1, "Label": label("Yes", "نعم")},
                       "FalseOption": {"Value": 0, "Label": label("No", "لا")}}},
        {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", "SchemaName": "sanidi_WeeklyRun",
         "DisplayName": label("Weekly Run", "تشغيل أسبوعي"), "RequiredLevel": REQ_NONE, "DefaultValue": False,
         "Description": label("Yes on Friday's 05:00 run: the last 28 days (Google Ads 90) and the previous month are "
                              "reloaded.",
                              "نعم في تشغيل الجمعة الساعة 05:00: يُعاد تحميل آخر 28 يومًا (Google Ads: ‏90) والشهر "
                              "السابق."),
         "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                       "TrueOption": {"Value": 1, "Label": label("Yes", "نعم")},
                       "FalseOption": {"Value": 0, "Label": label("No", "لا")}}},
        {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", "SchemaName": "sanidi_StepsLog",
         "DisplayName": label("Steps Log", "سجل الخطوات"), "RequiredLevel": REQ_NONE, "MaxLength": 100000,
         "Format": "TextArea",
         "Description": label("One line per step of the Run Sync flow: status, counts and time.",
                              "سطر لكل خطوة من مسار التشغيل: الحالة والأعداد والوقت.")},
    ],
}
OPTIONS = [
    ("sanidi_integrationsyncrequest", "sanidi_synctype", 100000002, "Day & Month to Date", "اليوم والشهر حتى تاريخه"),
    ("sanidi_integrationsyncrequest", "sanidi_synctype", 100000003, "All Time", "كل الفترة"),
    ("sanidi_integrationsyncrequest", "sanidi_synctype", 100000004, "Scheduled Daily (05:00)", "مجدول يومي (05:00)"),
    ("sanidi_integrationsyncrequest", "sanidi_synctype", 100000005, "Scheduled Intraday", "مجدول خلال اليوم"),
    ("sanidi_integrationsyncrequest", "sanidi_status", 100000004, "Skipped", "تم التخطي"),
]


def columns(dv, apply):
    for table, cols in COLUMNS.items():
        have = {a["LogicalName"] for a in dv.get(f"EntityDefinitions(LogicalName='{table}')/Attributes?$select=LogicalName")["value"]}
        for c in cols:
            name = c["SchemaName"].lower()
            print(f"{table}.{name}: {'exists' if name in have else 'add'}")
            if apply and name not in have:
                add_attribute(dv, table, c, SOLUTION)
    for table, column, value, en, ar in OPTIONS:
        attr = dv.get(f"EntityDefinitions(LogicalName='{table}')/Attributes(LogicalName='{column}')"
                      "/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$expand=OptionSet($select=Options)")
        have = {o["Value"] for o in attr["OptionSet"]["Options"]}
        print(f"{table}.{column} {value} {en}: {'exists' if value in have else 'add'}")
        if apply and value not in have:
            for attempt in range(10):
                try:
                    dv.request("POST", "InsertOptionValue", {
                        "EntityLogicalName": table, "AttributeLogicalName": column, "Value": value,
                        "Label": label(en, ar), "SolutionUniqueName": SOLUTION})
                    break
                except RuntimeError as e:
                    if attempt == 9 or "cannot start" not in str(e).lower():
                        raise
                    time.sleep(30)
    if apply:
        xml = "".join(f"<entity>{t}</entity>" for t in COLUMNS)
        dv.request("POST", "PublishXml", idempotent=True,
                   body={"ParameterXml": f"<importexportxml><entities>{xml}</entities></importexportxml>"})
        print("published")


def compile_page():
    """page.tsx + RuntimeTypes.ts -> page.compiled, like pac (checked against the live page: same page code)."""
    tsc_dir = os.environ.get("TSC_DIR")
    if not tsc_dir:
        raise SystemExit("Set TSC_DIR to a folder where `npm install typescript` was run.")
    script = """
const ts = require('typescript'); const fs = require('fs');
const [,, typesFile, pageFile, outFile] = process.argv;
const opts = { compilerOptions: { target: ts.ScriptTarget.ES5, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.React } };
const types = ts.transpileModule(fs.readFileSync(typesFile, 'utf8'), opts).outputText;
const page = ts.transpileModule(fs.readFileSync(pageFile, 'utf8'), opts).outputText;
fs.writeFileSync(outFile, '// --- BEGIN GENERATED RUNTIME TYPES ---\\n' + types + '// --- END GENERATED RUNTIME TYPES ---\\n\\n' + page);
"""
    with tempfile.TemporaryDirectory() as tmp:
        js, out = Path(tmp) / "compile.js", Path(tmp) / "page.compiled"
        js.write_text(script)
        env = dict(os.environ, NODE_PATH=str(Path(tsc_dir) / "node_modules"))
        subprocess.run(["node", str(js), str(PAGE_DIR / "RuntimeTypes.ts"), str(PAGE_DIR / "sync-control.tsx"), str(out)],
                       check=True, env=env)
        return out.read_bytes()


def page(dv, apply):
    files = {f["filename"]: f["uxagentprojectfileid"] for f in dv.get(
        f"uxagentprojectfiles?$filter=_uxagentprojectid_value eq {PAGE_ID}&$select=filename,uxagentprojectfileid")["value"]}
    source = (PAGE_DIR / "sync-control.tsx").read_bytes()
    compiled = compile_page()
    print(f"page: page.tsx {len(source)} bytes, page.compiled {len(compiled)} bytes")
    if not apply:
        return
    for name, data in (("src/pages/page.tsx", source), ("src/pages/page.compiled", compiled)):
        url = f"{dv.url}/api/data/v9.2/uxagentprojectfiles({files[name]})/filecontent"
        req = urllib.request.Request(url, data=data, method="PATCH", headers={
            "Authorization": "Bearer " + dv.token, "Content-Type": "application/octet-stream",
            "x-ms-file-name": name.split("/")[-1]})
        with urllib.request.urlopen(req, timeout=300) as r:
            print(f"  wrote {name} ({r.status})")
    dv.request("POST", "AddSolutionComponent", {
        "ComponentId": PAGE_ID, "ComponentType": 17053, "SolutionUniqueName": SOLUTION,
        "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}, idempotent=True)
    print("  page added to the patch")


if __name__ == "__main__":
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    apply = "--apply" in sys.argv
    dv = Dataverse()
    if only in (None, "columns"):
        columns(dv, apply)
    if only in (None, "page"):
        page(dv, apply)
