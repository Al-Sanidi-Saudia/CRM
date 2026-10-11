import json, re, sys, csv
import xml.etree.ElementTree as ET
sys.path.insert(0, '.')
from templates import TEMPLATES, TECH, SNAKE, CAPS
from dict1 import D as D1
from dict2 import D as D2
from dict3 import D as D3
from dict_caps import D as DC
from dict4 import D as D4

DICT = {}
for d in (DC, D1, D2, D3, D4):  # later wins
    DICT.update(d)
LOWER = {k.lower(): v for k, v in DICT.items()}

SKIP = re.compile(r'^sanidi_(meta|snap|google)_')
KEEP_MS = {'product', 'RibbonCustomization'}   # keep Microsoft Arabic where present
LATIN = re.compile(r'[A-Za-z]')

# singular entity names read better without the definite article
ENTITY_SINGULAR = {
    'Campaign': 'حملة', 'Influencer': 'مؤثر', 'City': 'مدينة', 'Product': 'منتج',
    'Product Category - sinidi': 'قسم منتجات', 'Product Category': 'قسم منتجات',
    'Advertisement Item': 'بند إعلان', 'Campaign Product': 'منتج حملة',
    'Integration Platform': 'منصة تكامل', 'Integration Sync Request': 'طلب مزامنة تكامل',
}
# (entity, column, english) -> arabic, for labels whose English is ambiguous
CONTEXT = {
    ('new_city', 'LocalizedCollectionName', 'City'): 'المدن',
}

# AlSanidi's own columns on the standard Product table (fix poor manual translations)
PRODUCT_CUSTOM = {
    'GM': 'الوزن بالجرام (GM)',
    'L CM': 'الطول بالسنتيمتر (L CM)',
    'Classification Level 1': 'التصنيف - المستوى 1',
}

missing = set()

def T(en, existing=None):
    s = en.strip()
    if en in DICT: return DICT[en]
    if s in DICT: return DICT[s]
    for rx, f in TEMPLATES:
        m = rx.match(s)
        if m: return f(m, T)
    for rx, f in TECH:
        m = rx.match(s)
        if m: return f(m)
    if SNAKE.match(s):
        title = s.replace('_', ' ').strip().lower()
        if title in LOWER: return LOWER[title]
    if s.lower() in LOWER: return LOWER[s.lower()]
    if existing and not LATIN.search(existing): return existing
    missing.add(s)
    return None

def resolve(entity, col, en, ar):
    if entity == 'product' and en in PRODUCT_CUSTOM: return PRODUCT_CUSTOM[en]
    if entity in KEEP_MS and ar.strip(): return None
    if (entity, col, en) in CONTEXT: return CONTEXT[(entity, col, en)]
    if col == 'LocalizedName' and en in ENTITY_SINGULAR: return ENTITY_SINGULAR[en]
    return T(en, ar.strip() or None)

NS = 'urn:schemas-microsoft-com:office:spreadsheet'
S = '{%s}' % NS

def main(src, dst, report):
    for p, u in [('', NS), ('o', 'urn:schemas-microsoft-com:office:office'),
                 ('x', 'urn:schemas-microsoft-com:office:excel'), ('ss', NS),
                 ('html', 'http://www.w3.org/TR/REC-html40')]:
        ET.register_namespace(p, u)
    tree = ET.parse(src)
    rows_out = []
    stats = {'filled': 0, 'changed': 0, 'kept': 0, 'skipped_table': 0}
    for ws in tree.getroot().findall(S + 'Worksheet'):
        if ws.get(S + 'Name') != 'Localized Labels': continue
        for i, row in enumerate(ws.find(S + 'Table').findall(S + 'Row')):
            if i == 0: continue
            cells = row.findall(S + 'Cell')
            vals = [(c.find(S + 'Data').text or '') if c.find(S + 'Data') is not None else '' for c in cells]
            entity, oid, col, en = vals[0], vals[1], vals[2], vals[3]
            ar = vals[4] if len(vals) > 4 else ''
            if not en.strip(): continue
            if SKIP.match(entity):
                stats['skipped_table'] += 1; continue
            new = resolve(entity, col, en, ar)
            if new is None: continue
            new = new.replace('‏', '').replace('‬', '').strip()
            if new == ar: stats['kept'] += 1; continue
            stats['filled' if not ar.strip() else 'changed'] += 1
            cells[4].find(S + 'Data').text = new
            rows_out.append([entity, oid, col, en, ar, new, 'New' if not ar.strip() else 'Updated'])
    tree.write(dst, encoding='utf-8', xml_declaration=True)
    with open(report, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Table / Component', 'Object ID', 'Label Type', 'English', 'Previous Arabic', 'New Arabic', 'Change'])
        w.writerows(rows_out)
    print(stats)
    print('missing', len(missing))
    for m in sorted(missing): print('  ', repr(m))

if __name__ == '__main__':
    main(*sys.argv[1:4])
