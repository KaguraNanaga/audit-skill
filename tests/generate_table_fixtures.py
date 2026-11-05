#!/usr/bin/env python3
"""Generate only new synthetic stage-4 fixtures; existing frozen inputs are untouched."""
import csv,hashlib,io,json
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'tests/table-fixtures';folder.mkdir(parents=True,exist_ok=True)
    header=['id','date','category','amount']
    small=[['a','2031-01-02','A','1.2300'],['b','2031-01-03','B','2.0000'],['c','2031-01-04','A','-0.0300'],['d','2031-01-05','A','12345678901234567890.1234567890']]
    for suffix,delimiter in [('csv',','),('tsv','\t')]:
        with (folder/('small.'+suffix)).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream,delimiter=delimiter,lineterminator='\n');writer.writerows([header,*small])
    count=total=0
    with (folder/'synthetic-ledger-50000.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(header)
        for i in range(1,50001):
            cents=i%2001-1000;day=i%28+1
            amount=('-' if cents<0 else '')+f'{abs(cents)//100}.{abs(cents)%100:02d}00'
            writer.writerow([str(i),f'2031-01-{day:02d}',f'G{i%3}',amount])
            if i%3==1 and 10<=day<=20 and cents>=0:count+=1;total+=cents
    # Minimal OOXML from original code: fixed ZIP timestamps and raw numeric lexemes.
    rows=[]
    for rowno,values in enumerate([header,*small,['formula','2031-01-06','A',None]],1):
        cells=[]
        for col,value in zip('ABCD',values):
            coord=col+str(rowno)
            if value is None:cell=f'<c r="{coord}"><f>SUM(D2:D4)</f><v/></c>'
            elif col=='D' and rowno>1:cell=f'<c r="{coord}" t="n"><v>{value}</v></c>'
            else:cell=f'<c r="{coord}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            cells.append(cell)
        rows.append(f'<row r="{rowno}">'+''.join(cells)+'</row>')
    parts={
        '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ledger" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:D6"/><sheetData>'+''.join(rows)+'</sheetData></worksheet>'}
    with zipfile.ZipFile(folder/'small.xlsx','w',compression=zipfile.ZIP_STORED) as archive:
        for name,content in sorted(parts.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,5,0,0,0));info.create_system=3;info.external_attr=0o600 << 16;info.compress_type=zipfile.ZIP_STORED;archive.writestr(info,content.encode())
    expected=ROOT/'tests/expected/table-query.json';expected.parent.mkdir(exist_ok=True)
    expected.write_text(json.dumps(dict(large_matched=count,large_sum_cents=total),indent=2)+'\n',encoding='utf-8',newline='\n')
    files=[*folder.iterdir(),expected]
    (ROOT/'tests/input-sha256-stage4.json').write_text(json.dumps(dict(frozen_on='2026-11-05',synthetic=True,files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}),indent=2)+'\n',encoding='utf-8',newline='\n')
if __name__=='__main__':main()
