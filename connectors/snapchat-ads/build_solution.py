"""Builds an unmanaged solution package that adds the Snap connector, with the
publisher-prefixed internal name sanidi_snap, to the "AlSanidi | Marketing" solution.

`pac connector create` always names the connector with the Default Publisher's prefix
(new_snap); importing this package is how the connector gets the solution's prefix.

Run:   python3 build_solution.py [--client-id <snap client id>] [--out SnapConnector.zip]
Then:  pac solution import --path SnapConnector.zip --environment <env url>

The package contains only the connector, so importing it leaves every other component
of the solution untouched. Re-importing updates the same connector (stable ID).
"""
import argparse
import json
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).parent

SOLUTION_UNIQUE_NAME = "AlSanidiMarketing"
SOLUTION_DISPLAY_NAME = "AlSanidi | Marketing"
SOLUTION_VERSION = "1.0.0"
PUBLISHER_UNIQUE_NAME = "AlSanidiDevelopment"
PUBLISHER_DISPLAY_NAME = "AlSanidi Development"
PREFIX = "sanidi"
OPTION_VALUE_PREFIX = "10000"

CONNECTOR_NAME = f"{PREFIX}_snap"
CONNECTOR_DISPLAY_NAME = "Snap"
CONNECTOR_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"alsanidi/connectors/{CONNECTOR_NAME}"))

XSI = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'


def solution_xml():
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml version="9.2" SolutionPackageVersion="9.2" languagecode="1033" generatedBy="CrmLive" {XSI}>
  <SolutionManifest>
    <UniqueName>{SOLUTION_UNIQUE_NAME}</UniqueName>
    <LocalizedNames>
      <LocalizedName description="{SOLUTION_DISPLAY_NAME}" languagecode="1033" />
    </LocalizedNames>
    <Descriptions />
    <Version>{SOLUTION_VERSION}</Version>
    <Managed>0</Managed>
    <Publisher>
      <UniqueName>{PUBLISHER_UNIQUE_NAME}</UniqueName>
      <LocalizedNames>
        <LocalizedName description="{PUBLISHER_DISPLAY_NAME}" languagecode="1033" />
      </LocalizedNames>
      <Descriptions />
      <EMailAddress xsi:nil="true"></EMailAddress>
      <SupportingWebsiteUrl xsi:nil="true"></SupportingWebsiteUrl>
      <CustomizationPrefix>{PREFIX}</CustomizationPrefix>
      <CustomizationOptionValuePrefix>{OPTION_VALUE_PREFIX}</CustomizationOptionValuePrefix>
      <Addresses />
    </Publisher>
    <RootComponents>
      <RootComponent type="372" id="{{{CONNECTOR_ID}}}" schemaName="{CONNECTOR_NAME}" behavior="0" />
    </RootComponents>
    <MissingDependencies />
  </SolutionManifest>
</ImportExportXml>
"""


def customizations_xml(description):
    empty = "".join(f"\n  <{t} />" for t in [
        "Entities", "Roles", "Workflows", "FieldSecurityProfiles", "Templates", "EntityMaps",
        "EntityRelationships", "OrganizationSettings", "optionsets", "CustomControls", "EntityDataProviders"])
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml {XSI}>{empty}
  <Connectors>
    <Connector>
      <connectorid>{CONNECTOR_ID}</connectorid>
      <description>{description}</description>
      <displayname>{CONNECTOR_DISPLAY_NAME}</displayname>
      <iconbrandcolor>#FFFC00</iconbrandcolor>
      <name>{CONNECTOR_NAME}</name>
      <connectortype>1</connectortype>
      <openapidefinition>/Connector/{CONNECTOR_NAME}_openapidefinition.json</openapidefinition>
      <connectionparameters>/Connector/{CONNECTOR_NAME}_connectionparameters.json</connectionparameters>
      <policytemplateinstances>/Connector/{CONNECTOR_NAME}_policytemplateinstances.json</policytemplateinstances>
    </Connector>
  </Connectors>
  <Languages>
    <Language>1033</Language>
  </Languages>
</ImportExportXml>
"""


CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/octet-stream" />
  <Default Extension="json" ContentType="application/octet-stream" />
</Types>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", help="Snap OAuth app client ID (can also be set later on the Security tab)")
    ap.add_argument("--out", default=str(HERE / "SnapConnector.zip"))
    args = ap.parse_args()

    definition = json.loads((HERE / "apiDefinition.swagger.json").read_text())
    props = json.loads((HERE / "apiProperties.json").read_text())["properties"]
    params = props["connectionParameters"]
    if args.client_id:
        params["token"]["oAuthSettings"]["clientId"] = args.client_id

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("solution.xml", solution_xml())
        z.writestr("customizations.xml", customizations_xml(definition["info"]["description"]))
        z.writestr(f"Connector/{CONNECTOR_NAME}_openapidefinition.json", json.dumps(definition, indent=2))
        z.writestr(f"Connector/{CONNECTOR_NAME}_connectionparameters.json", json.dumps(params, indent=2))
        z.writestr(f"Connector/{CONNECTOR_NAME}_policytemplateinstances.json", "[]")
    print(f"Wrote {args.out} (connector {CONNECTOR_NAME}, id {CONNECTOR_ID})")


if __name__ == "__main__":
    main()
