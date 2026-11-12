"""Moves the Daily & Monthly Insights build from UAT to Production as managed solutions (PLAN.md §3.6).

  python3 deploy_prod.py connectors     # UAT Connectors -> version 1.0.1, export managed, import into Production
  python3 deploy_prod.py patch          # UAT patch (1.0.3.0) export managed, import into Production

Exports land in the scratchpad (SCRATCH env var, default ./exports). Imports run asynchronously (ImportSolutionAsync)
and are polled until done; the import job's result is printed.
"""
import base64
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dv import Dataverse  # noqa: E402

UAT = "https://operations-alsenidiuat.crm4.dynamics.com"
PROD = "https://operations-alsanidi.crm4.dynamics.com"
OUT = Path(os.environ.get("SCRATCH", Path(__file__).parent / "exports"))
SOLUTIONS = {"connectors": ("AlSanidiMarketingConnectors", "1.0.1"),
             "patch": ("AlSanidiMarketing_Patch_14289281", None)}


def connect(url):
    os.environ["DATAVERSE_URL"] = url
    return Dataverse()


def export(uat, name, version):
    sol = uat.get(f"solutions?$select=solutionid,version&$filter=uniquename eq '{name}'")["value"][0]
    if version and sol["version"] != version:
        uat.request("PATCH", f"solutions({sol['solutionid']})", {"version": version})
        print(f"{name}: version {sol['version']} -> {version}")
    # Everything in UAT is published already; ExportSolutionAsync avoids the 5-minute request limit.
    body, _ = uat.request("POST", "ExportSolutionAsync", {"SolutionName": name, "Managed": True})
    op, export_id = body["AsyncOperationId"], body["ExportJobId"]
    while True:
        time.sleep(15)
        a = uat.get(f"asyncoperations({op})?$select=statecode,statuscode,message")
        if a["statecode"] == 3:
            break
    if a["statuscode"] != 30:
        raise SystemExit(f"{name}: export failed: {a.get('message')}")
    body, _ = uat.request("POST", "DownloadSolutionExportData", {"ExportJobId": export_id})
    data = base64.b64decode(body["ExportSolutionFile"])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}_managed.zip"
    path.write_bytes(data)
    print(f"{name}: exported managed, {len(data) // 1024} KB -> {path}")
    return data


def import_(prod, name, data):
    job = str(uuid.uuid4())
    body, _ = prod.request("POST", "ImportSolutionAsync", {
        "CustomizationFile": base64.b64encode(data).decode(), "OverwriteUnmanagedCustomizations": True,
        "PublishWorkflows": True, "ImportJobId": job})
    op = body["AsyncOperationId"]
    print(f"{name}: import started (job {job})", flush=True)
    while True:
        time.sleep(30)
        a = prod.get(f"asyncoperations({op})?$select=statecode,statuscode,message,friendlymessage")
        if a["statecode"] == 3:  # completed
            break
    j = prod.get(f"importjobs({job})?$select=progress,completedon")
    print(f"{name}: async status {a['statuscode']} (30 = succeeded), import progress {j.get('progress')}")
    if a["statuscode"] != 30:
        print("ERROR:", (a.get("friendlymessage") or a.get("message") or "")[:3000])
        raise SystemExit(1)
    s = prod.get(f"solutions?$select=version,ismanaged&$filter=uniquename eq '{name}'")["value"][0]
    print(f"{name}: in Production version {s['version']}, managed {s['ismanaged']}")


def main(step):
    name, version = SOLUTIONS[step]
    data = export(connect(UAT), name, version)
    import_(connect(PROD), name, data)


if __name__ == "__main__":
    main(sys.argv[1])
