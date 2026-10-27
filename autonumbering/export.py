"""Exports the Auto Numbering patch from UAT, managed (for Production) and unmanaged (source backup), and lists
what is in it.

  python3 export.py    # writes solution/AlSanidiMarketing_AutoNumbering_<version>_managed.zip and _unmanaged.zip
"""
import base64
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from deploy import find_patch  # noqa: E402
from dv import Dataverse  # noqa: E402

TYPES = {1: "Table", 2: "Column", 9: "Choice", 60: "Form", 61: "Web resource", 62: "Site map",
         91: "Plug-in assembly", 92: "Plug-in step"}


def main():
    dv = Dataverse()
    _, patch = find_patch(dv)
    if not patch:
        raise SystemExit("patch not found: run deploy.py --apply first")
    solution = dv.first(f"solutions?$select=solutionid&$filter=uniquename eq '{patch['uniquename']}'")
    components = dv.get(f"solutioncomponents?$select=componenttype,objectid,rootcomponentbehavior"
                        f"&$filter=_solutionid_value eq {solution['solutionid']}")["value"]
    counts = {}
    for c in components:
        name = TYPES.get(c["componenttype"], f"type {c['componenttype']}")
        counts[name] = counts.get(name, 0) + 1
    print(f"{patch['uniquename']} {patch['version']}: {len(components)} components "
          f"({', '.join(f'{n} {k}' for k, n in counts.items())})")

    out = HERE / "solution"
    out.mkdir(exist_ok=True)
    version = patch["version"].replace(".", "_")
    for managed in (True, False):
        result = dv.request("POST", "ExportSolution", idempotent=True, body={
            "SolutionName": patch["uniquename"], "Managed": managed})[0]
        path = out / f"AlSanidiMarketing_AutoNumbering_{version}_{'managed' if managed else 'unmanaged'}.zip"
        path.write_bytes(base64.b64decode(result["ExportSolutionFile"]))
        print(f"  {path.relative_to(HERE)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
