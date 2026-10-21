"""Exports / imports the AlSanidi | Marketing translations through the Organization service (SOAP),
signed in with the service principal from scripts/dataverse-mcp.sh (DATAVERSE_* variables).

  python3 uat.py export <out.zip>            # Export translations (same file as the maker portal's)
  python3 uat.py import <CrmTranslations.zip> # Import translations, then publish all customizations
"""
import base64
import re
import sys
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from dv import Dataverse  # noqa: E402

SOLUTION = "AlSanidiMarketing"
XS = 'xmlns:c="http://www.w3.org/2001/XMLSchema"'


def execute(dv, request_name, params_xml, timeout=1800):
    envelope = (
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
        '<Execute xmlns="http://schemas.microsoft.com/xrm/2011/Contracts/Services" '
        'xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
        '<request xmlns:a="http://schemas.microsoft.com/xrm/2011/Contracts" '
        'xmlns:b="http://schemas.datacontract.org/2004/07/System.Collections.Generic">'
        f'<a:Parameters>{params_xml}</a:Parameters><a:RequestId i:nil="true"/>'
        f'<a:RequestName>{request_name}</a:RequestName></request></Execute></s:Body></s:Envelope>')
    req = urllib.request.Request(dv.url + "/XRMServices/2011/Organization.svc/web", data=envelope.encode(),
                                 method="POST", headers={
                                     "Authorization": "Bearer " + dv.token, "Content-Type": "text/xml; charset=utf-8",
                                     "SOAPAction": "http://schemas.microsoft.com/xrm/2011/Contracts/Services/"
                                                   "IOrganizationService/Execute"})
    try:
        return urllib.request.urlopen(req, timeout=timeout).read().decode()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{request_name} failed: {e.code} {e.read().decode()[:2000]}")


def param(key, type_, value):
    return (f'<a:KeyValuePairOfstringanyType><b:key>{key}</b:key>'
            f'<b:value i:type="c:{type_}" {XS}>{value}</b:value></a:KeyValuePairOfstringanyType>')


if __name__ == "__main__":
    action, path = sys.argv[1], Path(sys.argv[2])
    dv = Dataverse()
    if action == "export":
        out = execute(dv, "ExportTranslation", param("SolutionName", "string", SOLUTION))
        data = re.search(r"<b:key>ExportTranslationFile</b:key><b:value[^>]*>([^<]+)</b:value>", out).group(1)
        path.write_bytes(base64.b64decode(data))
        print(f"exported {path} ({path.stat().st_size} bytes)")
    elif action == "import":
        data = base64.b64encode(path.read_bytes()).decode()
        job = str(uuid.uuid4())
        execute(dv, "ImportTranslation", param("TranslationFile", "base64Binary", data) +
                param("ImportJobId", "guid", job).replace('xmlns:c="http://www.w3.org/2001/XMLSchema"',
                                                          'xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/"'))
        print(f"imported {path} (import job {job})")
        execute(dv, "PublishAllXml", "")
        print("published all customizations")
    else:
        raise SystemExit(__doc__)
