"""Imports the managed Auto Numbering patch into DATAVERSE_URL and waits for the result.

  DATAVERSE_URL=https://operations-alsanidi.crm4.dynamics.com python3 import_patch.py

Plug-in steps and flows in the patch are turned on. Unmanaged customizations are kept (none existed in
Production on the patched components when this was first run).
"""
import base64
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from dv import Dataverse  # noqa: E402

# Newest managed export in solution/ (the version is in the file name)
PACKAGE = max((HERE / "solution").glob("AlSanidiMarketing_AutoNumbering_*_managed.zip"),
              key=lambda p: [int(n) for n in p.name.split("_")[2:6]])


def main():
    dv = Dataverse()
    print(f"environment: {dv.url}")
    print(f"package: {PACKAGE.name}")
    job_id = str(uuid.uuid4())
    result = dv.request("POST", "ImportSolutionAsync", idempotent=False, body={
        "CustomizationFile": base64.b64encode(PACKAGE.read_bytes()).decode(),
        "OverwriteUnmanagedCustomizations": False, "PublishWorkflows": True, "ImportJobId": job_id})[0]
    operation = result["AsyncOperationId"]
    print(f"import started (async operation {operation}, import job {job_id})")
    while True:
        time.sleep(15)
        op = dv.get(f"asyncoperations({operation})?$select=statecode,statuscode,message,friendlymessage")
        job = dv.first(f"importjobs?$select=progress&$filter=importjobid eq {job_id}")
        print(f"  status {op['statuscode']}, progress {job['progress'] if job else 0:.0f}%")
        if op["statecode"] == 3:
            break
    data = dv.get(f"importjobs({job_id})?$select=data")["data"] or ""
    errors = re.findall(r'result="failure"[^>]*errortext="([^"]*)"', data)
    warnings = re.findall(r'result="warning"[^>]*errortext="([^"]*)"', data)
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  error: {e}")
    if op["statuscode"] != 30 or errors:
        raise SystemExit(f"import failed: {op.get('friendlymessage') or op.get('message')}")
    print("import succeeded")


if __name__ == "__main__":
    main()
