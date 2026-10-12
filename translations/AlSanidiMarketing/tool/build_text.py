import re, sys, html, csv, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
import build
from xml.sax.saxutils import escape
# usage: python build_text.py <exported CrmTranslations.xml> <output CrmTranslations.xml>
src, dst = ARGS
t = open(src, encoding='utf-8').read()
start = t.index('ss:Name="Localized Labels"')
head, body = t[:start], t[start:]
DATA = re.compile(r'(<Data ss:Type="String">)(.*?)(</Data>)', re.S)
ROW = re.compile(r'<Row\b.*?</Row>', re.S)
n = 0
def fix_row(m):
    global n
    row = m.group(0)
    ds = list(DATA.finditer(row))
    if len(ds) < 5: return row
    v = [html.unescape(d.group(2)) for d in ds[:5]]
    entity, oid, col, en, ar = v
    if not en.strip() or entity == 'Entity name' or build.SKIP.match(entity): return row
    new = build.resolve(entity, col, en, ar)
    if new is None: return row
    new = new.replace('‏', '').replace('‬', '').strip()
    if new == ar: return row
    n += 1
    d = ds[4]
    return row[:d.start(2)] + escape(new) + row[d.end(2):]
body = ROW.sub(fix_row, body)
open(dst, 'w', encoding='utf-8').write(head + body)
print('rows updated', n, 'missing', len(build.missing))
