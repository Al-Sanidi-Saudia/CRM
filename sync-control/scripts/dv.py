import os, json, urllib.request, urllib.parse, ssl, sys
def clean(v): v=(v or '').strip().rstrip(','); return v.strip('"')
URL=clean(os.environ.get('DATAVERSE_URL')).rstrip('/')
ctx=ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')
_tok=None
def token():
    global _tok
    if _tok: return _tok
    d=urllib.parse.urlencode({'client_id':clean(os.environ['DATAVERSE_CLIENT_ID']),'client_secret':clean(os.environ['DATAVERSE_CLIENT_SECRET']),'scope':URL+'/.default','grant_type':'client_credentials'}).encode()
    r=urllib.request.urlopen(urllib.request.Request(f"https://login.microsoftonline.com/{clean(os.environ['DATAVERSE_TENANT_ID'])}/oauth2/v2.0/token",d),context=ctx)
    _tok=json.load(r)['access_token']; return _tok
def call(method, path, body=None, solution='AlSanidiMarketing', extra=None):
    h={'Authorization':'Bearer '+token(),'Accept':'application/json','Content-Type':'application/json; charset=utf-8','OData-Version':'4.0','OData-MaxVersion':'4.0','Prefer':'return=representation'}
    if solution: h['MSCRM.SolutionUniqueName']=solution
    if extra: h.update(extra)
    req=urllib.request.Request(URL+'/api/data/v9.2/'+path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        r=urllib.request.urlopen(req,context=ctx, timeout=300); t=r.read()
        return r.status, (json.loads(t) if t else None), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:2000], {}
