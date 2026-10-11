import re
def DEF(x):
    # add the Arabic definite article to a single-word noun (idafa: حالة الإعلان)
    if ' ' not in x and not x.startswith('ال') and re.match(r'^[\u0600-\u06FF]', x): return 'ال' + x
    return x
# Each: (regex, function(match, T) -> arabic) ; T translates a sub-name
TEMPLATES = [
 (r'^(.+) \(Base\)$', lambda m,T: f'{T(m[1])} (العملة الأساسية)'),
 (r'^(.+) \(State\)$', lambda m,T: f'{T(m[1])} (حالة الاحتساب)'),
 (r'^(.+) \(Last Updated On\)$', lambda m,T: f'{T(m[1])} (تاريخ آخر تحديث)'),
 (r'^Value of the (.+) in base currency\.$', lambda m,T: f'قيمة "{T(m[1])}" بالعملة الأساسية.'),
 (r'^State of rollup field (.+)\.$', lambda m,T: f'حالة احتساب الحقل التجميعي "{T(m[1])}".'),
 (r'^Last Updated time of rollup field (.+)\.$', lambda m,T: f'وقت آخر تحديث للحقل التجميعي "{T(m[1])}".'),
 (r'^Status of the (.+)$', lambda m,T: f'حالة {DEF(T(m[1]))}'),
 (r'^Reason for the status of the (.+)$', lambda m,T: f'سبب حالة {DEF(T(m[1]))}'),
 (r'^Active (.+) owned by me$', lambda m,T: f'{T(m[1])} النشطة الخاصة بي'),
 (r'^Quick Find Active (.+)$', lambda m,T: f'بحث سريع - {T(m[1])} النشطة'),
 (r'^(.+) Advanced Find View$', lambda m,T: f'عرض البحث المتقدم - {T(m[1])}'),
 (r'^(.+) Associated View$', lambda m,T: f'العرض المرتبط - {T(m[1])}'),
 (r'^(.+) Lookup View$', lambda m,T: f'عرض البحث - {T(m[1])}'),
 (r'^(.+) Quick Create$', lambda m,T: f'إنشاء سريع - {T(m[1])}'),
 (r'^My (.+)$', lambda m,T: f'{T(m[1])} الخاصة بي'),
 (r'^Inactive (.+)$', lambda m,T: f'{T(m[1])} غير النشطة'),
 (r'^Active (.+)$', lambda m,T: f'{T(m[1])} النشطة'),
]
TEMPLATES=[(re.compile(a),b) for a,b in TEMPLATES]
TECH = [
 (re.compile(r'^Google Ads: linked assets of type (.+)\.$'), lambda m: f'Google Ads: الأصول المرتبطة من النوع {m[1]}.'),
 (re.compile(r'^Google Ads: number of linked assets \((.+)\)\.$'), lambda m: f'Google Ads: عدد الأصول المرتبطة ({m[1]}).'),
 (re.compile(r'^(Google Ads|Snapchat|Snap|Meta|TikTok)( API)?: [A-Za-z0-9_.\[\]]+\.?$'), lambda m: m[0]),
]
SNAKE = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+ ?$|^[a-z]+$')
CAPS = re.compile(r'^[A-Z][A-Z0-9_]+$')
TECH += [
 (re.compile(r'^Meta ad set field ([a-z0-9_]+)( \(JSON\))?$'), lambda m: f'حقل المجموعة الإعلانية في Meta: {m[1]}{m[2] or ""}'),
 (re.compile(r'^Meta ad field ([a-z0-9_]+)( \(JSON\))?$'), lambda m: f'حقل الإعلان في Meta: {m[1]}{m[2] or ""}'),
 (re.compile(r'^Meta campaign field ([a-z0-9_]+)( \(JSON\))?$'), lambda m: f'حقل الحملة في Meta: {m[1]}{m[2] or ""}'),
 (re.compile(r'^All-time Snap stat: ([a-z0-9_]+)$'), lambda m: f'إحصائية Snap (طوال المدة): {m[1]}'),
 (re.compile(r'^All-time Snap stat: ([a-z0-9_]+) / 1,000,000$'), lambda m: f'إحصائية Snap (طوال المدة): {m[1]} / 1,000,000'),
 (re.compile(r'^All-time Snap stat: ([a-z0-9_]+) / 1,000$'), lambda m: f'إحصائية Snap (طوال المدة): {m[1]} / 1,000'),
 (re.compile(r'^Snap: ([a-z0-9_.]+) / 1,000,000$'), lambda m: m[0]),
 (re.compile(r'^Google Ads: [a-z0-9_.]+(, [a-z0-9_.]+)*,? ?[a-z0-9_.]*\.?$'), lambda m: m[0]),
]
