"""Updates the Meta and Snap connectors for the daily / monthly insights (definitions in connectors/meta-ads and
connectors/snapchat-ads). The TikTok connector is updated by connectors/tiktok-ads/deploy_dataverse.py connector.

  python3 deploy_connectors.py            # dry run
  python3 deploy_connectors.py --apply

Only the definition (and Meta's custom code) changes; the connection settings (OAuth app, secrets) are kept. The
connectors live in the "AlSanidi | Marketing | Connectors" solution (imported before the main solution), so the
changes are saved there.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from dv import Dataverse  # noqa: E402

CONNECTOR_SOLUTION = "AlSanidiMarketingConnectors"
CONNECTORS = HERE.parent / "connectors"


def update(dv, name, folder, script_operations, apply):
    swagger = (CONNECTORS / folder / "apiDefinition.swagger.json").read_text()
    body = {"openapidefinition": swagger}
    if script_operations:
        body["customcodeblobcontent"] = (CONNECTORS / folder / "script.csx").read_text()
        body["scriptoperations"] = json.dumps(script_operations)
    row = dv.first(f"connectors?$select=connectorid&$filter=name eq '{name}'")
    ops = sum(1 for p in json.loads(swagger)["paths"].values() for o in p.values() if isinstance(o, dict))
    print(f"{name}: update {row['connectorid']}; {ops} operations"
          + (f", custom code for {', '.join(script_operations)}" if script_operations else ""))
    if apply:
        dv.request("PATCH", f"connectors({row['connectorid']})", body, solution=CONNECTOR_SOLUTION)
        print("  updated")


def main(apply):
    dv = Dataverse()
    sys.path.insert(0, str(CONNECTORS / "meta-ads"))
    from build_definition import SCRIPT_OPERATIONS  # noqa: E402
    update(dv, "sanidi_meta", "meta-ads", SCRIPT_OPERATIONS, apply)
    update(dv, "sanidi_snap", "snapchat-ads", None, apply)


if __name__ == "__main__":
    main("--apply" in sys.argv)
