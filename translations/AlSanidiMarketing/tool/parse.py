import xml.etree.ElementTree as ET, json, sys
ns={'ss':'urn:schemas-microsoft-com:office:spreadsheet'}
S='{urn:schemas-microsoft-com:office:spreadsheet}'
root=ET.parse(sys.argv[1]).getroot()
out={}
for ws in root.findall('ss:Worksheet',ns):
    name=ws.get(S+'Name'); rows=[]
    for r in ws.find('ss:Table',ns).findall('ss:Row',ns):
        cells=[];idx=0
        for c in r.findall('ss:Cell',ns):
            i=c.get(S+'Index')
            if i: 
                while len(cells)<int(i)-1: cells.append('')
            d=c.find('ss:Data',ns); cells.append(d.text if d is not None and d.text else '')
        rows.append(cells)
    out[name]=rows
json.dump(out,open(sys.argv[2],'w'),ensure_ascii=False)
for k,v in out.items(): print(k,len(v),v[:2])
