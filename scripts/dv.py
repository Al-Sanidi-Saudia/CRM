"""Minimal Dataverse Web API client for deployment scripts.

Signs in with the same service principal as scripts/dataverse-mcp.sh (DATAVERSE_URL,
DATAVERSE_TENANT_ID, DATAVERSE_CLIENT_ID, DATAVERSE_CLIENT_SECRET). Writes made with
`solution=` go into that solution (MSCRM.SolutionUniqueName header).
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def _env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        raise SystemExit(f"{name} must be set")
    return v.strip().rstrip(",").strip('"')


class Dataverse:
    def __init__(self):
        self.url = _env("DATAVERSE_URL", "https://operations-alsenidiuat.crm4.dynamics.com").rstrip("/")
        form = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": _env("DATAVERSE_CLIENT_ID"),
            "client_secret": _env("DATAVERSE_CLIENT_SECRET"),
            "scope": self.url + "/.default",
        }).encode()
        tenant = _env("DATAVERSE_TENANT_ID")
        with urllib.request.urlopen(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", form) as r:
            self.token = json.load(r)["access_token"]

    def request(self, method, path, body=None, solution=None, headers=None):
        url = path if path.startswith("https://") else (
            self.url + "/api/data/v9.2/" + urllib.parse.quote(path, safe="/?$=&(),'@:"))
        h = {"Authorization": "Bearer " + self.token, "Accept": "application/json",
             "OData-Version": "4.0", "OData-MaxVersion": "4.0", "Content-Type": "application/json; charset=utf-8"}
        if solution:
            h["MSCRM.SolutionUniqueName"] = solution
        h.update(headers or {})
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    text = r.read().decode()
                    entity = r.headers.get("OData-EntityId")
                    return (json.loads(text) if text else {}), entity
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 3:
                    time.sleep(int(e.headers.get("Retry-After") or 2 ** (attempt + 1)))
                    continue
                self._raise(method, path, e)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                # Network blips: only reads are retried, a write may already have been applied.
                if method != "GET" or attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))

    @staticmethod
    def _raise(method, path, e):
        detail = e.read().decode()
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError):
            pass
        raise RuntimeError(f"{method} {path.split('?')[0]} -> {e.code}: {detail}") from None

    def get(self, path):
        return self.request("GET", path)[0]

    def first(self, path):
        rows = self.get(path).get("value", [])
        return rows[0] if rows else None
