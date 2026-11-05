"""Local deterministic table selection; results are derived data, never audit conclusions."""
import copy
from datetime import date, datetime
from decimal import Decimal, localcontext
import itertools
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile

from . import ledger as L
from . import readers

VERSION = 'table-query-1.0'
WARNING = '表查询派生结果；范围由查询规格限定，不能代替原件与业务核查'


def line(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'


def number(value):
    L.require(isinstance(value,str) and len(value)<=100 and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value,flags=re.ASCII), 'Numeric value requires an explicit decimal string; empty/commas/currency are not silently normalized')
    result=Decimal(value)
    L.require(result.is_finite() and abs(result.as_tuple().exponent)<=100 and abs(result.adjusted())<=100, 'Decimal outside supported range')
    return result


def exact_add(a,b):
    with localcontext() as context:
        context.prec=max(a.adjusted(),b.adjusted())-min(a.as_tuple().exponent,b.as_tuple().exponent)+3
        return a+b


def iso_date(value):
    L.require(isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value), 'Date must be YYYY-MM-DD; no locale guessing')
    return date.fromisoformat(value)


def specification(spec):
    L.require(isinstance(spec,dict) and not set(spec)-{'sheet','header_row','filters','group_by','aggregates'}, 'Unknown table query specification fields')
    spec=copy.deepcopy(spec)
    spec.setdefault('header_row',1);spec.setdefault('filters',[]);spec.setdefault('group_by',[]);spec.setdefault('aggregates',[])
    L.require(type(spec['header_row']) is int and spec['header_row']>0, 'header_row must be a positive record/worksheet row')
    L.require(isinstance(spec['filters'],list) and isinstance(spec['group_by'],list) and isinstance(spec['aggregates'],list), 'Query lists required')
    L.require(all(isinstance(c,str) and c for c in spec['group_by']) and len(set(spec['group_by']))==len(spec['group_by']), 'Unique group-by columns required')
    aliases=set()
    for f in spec['filters']:
        L.require(isinstance(f,dict) and f.get('op') in {'eq','contains','number_range','date_range'} and isinstance(f.get('column'),str), 'Invalid filter')
        allowed={'column','op','value'} if f['op'] in {'eq','contains'} else {'column','op','min','max'}
        L.require(not set(f)-allowed,'Unknown filter fields')
        if f['op'] in {'eq','contains'}:L.require(isinstance(f.get('value'),str),'Text comparison requires string value')
        else:
            L.require('min' in f or 'max' in f,'Range requires min or max')
            convert=number if f['op']=='number_range' else iso_date
            for key in ('min','max'):
                if key in f:convert(f[key])
            if 'min' in f and 'max' in f:L.require(convert(f['min'])<=convert(f['max']),'Reversed interval')
    for a in spec['aggregates']:
        L.require(isinstance(a,dict) and not set(a)-{'op','column','as'} and a.get('op') in {'sum','count'},'Invalid aggregate')
        L.require(isinstance(a.get('as'),str) and bool(a['as']) and a['as'] not in aliases|set(spec['group_by']), 'Unique aggregate alias required')
        aliases.add(a['as'])
        if a['op']=='sum':L.require(isinstance(a.get('column'),str),'Sum column required')
        else:L.require('column' not in a,'count counts matched rows, not nonempty cells')
    L.require(not spec['group_by'] or spec['aggregates'],'group_by requires aggregates')
    return spec


def raw_xlsx_rows(path,sheet):
    """Stream original numeric lexemes beside openpyxl; floats are never decimal inputs."""
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rel_ns='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    with zipfile.ZipFile(path) as archive:
        workbook=ET.fromstring(archive.read('xl/workbook.xml'))
        selected=next((s for s in workbook.findall('s:sheets/s:sheet',ns) if s.get('name')==sheet),None)
        L.require(selected is not None,'Unknown worksheet')
        rels=ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        rel=next((r for r in rels if r.get('Id')==selected.get(rel_ns)),None)
        L.require(rel is not None and rel.get('TargetMode')!='External','Worksheet must be an internal package part')
        target=rel.get('Target','');part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
        L.require(not PurePosixPath(part).is_absolute() and '..' not in PurePosixPath(part).parts and ':' not in part,'Worksheet part escapes archive')
        with archive.open(part) as stream:
            for event,el in ET.iterparse(stream,events=('end',)):
                if el.tag=='{'+ns['s']+'}row':
                    row={}
                    for cell in el:
                        value=cell.find('s:v',ns)
                        row[cell.get('r')]=dict(raw=value.text if value is not None else None,type=cell.get('t','n'))
                    yield int(el.get('r')),row
                    el.clear()


def table_rows(project,work,vid,spec):
    version=work['records'][vid];fmt=version['format'];units=work['units'][vid]
    if fmt in {'.csv','.tsv'}:
        L.require('sheet' not in spec,'CSV/TSV has no worksheet')
        for unit in units:
            if unit['locator'].get('unit')=='row' and unit['state']=='extracted':
                yield unit['locator']['record_number'],list(unit['cells']),dict(unit['locator']),[unit['id']]
        return
    L.require(fmt=='.xlsx','table-query supports extracted CSV/TSV/XLSX versions only')
    L.require(isinstance(spec.get('sheet'),str) and bool(spec['sheet']),'XLSX requires explicit sheet')
    import openpyxl
    path=project/version['local_snapshot']
    wb=openpyxl.load_workbook(path,read_only=True,data_only=True,keep_links=False)
    raw=raw_xlsx_rows(path,spec['sheet'])
    cell_units={u['locator'].get('cell_range'):u['id'] for u in units if u['locator'].get('unit')=='cell' and u['locator'].get('sheet')==spec['sheet']}
    try:
        L.require(spec['sheet'] in wb.sheetnames,'Unknown worksheet')
        current=next(raw,None)
        for row_no,cells in enumerate(wb[spec['sheet']].iter_rows(),1):
            while current and current[0]<row_no:current=next(raw,None)
            raw_cells=current[1] if current and current[0]==row_no else {}
            values=[];ids=[]
            for col,cell in enumerate(cells,1):
                coordinate=openpyxl.utils.get_column_letter(col)+str(row_no)
                v=cell.value;literal=raw_cells.get(coordinate,{})
                if v is not None and cell.data_type=='n':
                    v=literal.get('raw')
                    L.require(v is not None,'Numeric XLSX cell lacks original decimal lexeme: '+coordinate)
                elif hasattr(v,'isoformat'):v=v.isoformat()
                elif v is not None:v=str(v)
                values.append(v)
                if coordinate in cell_units:ids.append(cell_units[coordinate])
            yield row_no,values,dict(unit='row',sheet=spec['sheet'],record_number=row_no,cell_range=f'A{row_no}:{openpyxl.utils.get_column_letter(len(cells))}{row_no}'),ids
    finally:
        raw.close();wb.close()


def execute(project,work,vid,spec,folder,limit):
    columns=None;groups={};preview=[];scanned=matched=0
    rows_path=folder/'rows.jsonl';groups_path=folder/'groups.jsonl'
    with rows_path.open('x',encoding='utf-8',newline='\n') as output:
        for row_no,values,locator,ids in table_rows(project,work,vid,spec):
            if row_no==spec['header_row']:
                L.require(values and all(isinstance(v,str) and v for v in values) and len(values)==len(set(values)), 'Header must contain unique nonempty names; choose the actual header_row')
                columns=values
                wanted={f['column'] for f in spec['filters']}|set(spec['group_by'])|{a['column'] for a in spec['aggregates'] if a['op']=='sum'}
                L.require(wanted<=set(columns),'Query cites unknown columns: '+str(sorted(wanted-set(columns))))
                continue
            if row_no<spec['header_row']:continue
            L.require(columns is not None,'Header row not found')
            if not any(v not in (None,'') for v in values):continue
            L.require(len(values)<=len(columns) or all(v in (None,'') for v in values[len(columns):]),'Data extends beyond declared header')
            data=dict(zip(columns,values[:len(columns)]+[None]*max(0,len(columns)-len(values))))
            scanned+=1
            keep=True
            # Validate every filter, even if a prior predicate failed; no hidden invalid amounts.
            for f in spec['filters']:
                v=data[f['column']];op=f['op']
                if op=='eq':ok=v==f['value']
                elif op=='contains':ok=isinstance(v,str) and f['value'] in v
                else:
                    convert=number if op=='number_range' else iso_date
                    if op=='date_range' and isinstance(v,str) and 'T' in v:
                        parsed=datetime.fromisoformat(v).date()
                    else: parsed=convert(v)
                    ok=('min' not in f or parsed>=convert(f['min'])) and ('max' not in f or parsed<=convert(f['max']))
                keep=keep and ok
            if not keep:continue
            L.require(bool(ids),'Matched row has no previously extracted original locator')
            matched+=1;key=tuple(data[c] for c in spec['group_by'])
            row=dict(index=matched,values=data,locator=locator,unit_ids=ids,group_key=list(key))
            output.write(line(row))
            if len(preview)<limit:preview.append(row)
            if spec['aggregates']:
                agg=groups.setdefault(key,{a['as']:Decimal(0) if a['op']=='sum' else 0 for a in spec['aggregates']})
                for a in spec['aggregates']:
                    agg[a['as']]=exact_add(agg[a['as']],number(data[a['column']])) if a['op']=='sum' else agg[a['as']]+1
    L.require(columns is not None,'Header row not found')
    if spec['aggregates'] and not spec['group_by'] and not groups:
        groups[()]={a['as']:Decimal(0) if a['op']=='sum' else 0 for a in spec['aggregates']}
    group_preview=[]
    with groups_path.open('x',encoding='utf-8',newline='\n') as output:
        for index,(key,agg) in enumerate(sorted(groups.items(),key=lambda item:line(item[0])),1):
            row=dict(index=index,values=dict(zip(spec['group_by'],key),**{k:str(v) for k,v in agg.items()}))
            output.write(line(row))
            if len(group_preview)<limit:group_preview.append(row)
    summary=dict(scanned_rows=scanned,matched_rows=matched,group_count=len(groups),columns=columns,header_row=spec['header_row'])
    L.atomic_json(folder/'summary.json',summary);L.atomic_json(folder/'spec.json',spec)
    files={name:dict(path=(folder/name).relative_to(project).as_posix(),sha256=readers.digest(folder/name)) for name in ('spec.json','rows.jsonl','groups.jsonl','summary.json')}
    return summary,files,preview,group_preview


def run(args,api):
    project=args.project.resolve();spec=specification(api.load(args.spec))
    L.require(0<=args.limit<=100,'Preview limit must be 0..100')
    with L.lock(project):
        work=api.get_work(project);L.require(args.version in work['units'],'Unknown table source version')
        api.check_files(project,work)
        version=work['records'][args.version]
        L.require(version['format'] in {'.csv','.tsv','.xlsx'},'table-query supports extracted CSV/TSV/XLSX only')
        qid=L.uid();folder=project/'queries'/qid;folder.mkdir(parents=True)
        record=dict(source_version_id=args.version,source_sha256=version['sha256'],spec=spec,spec_sha256=L.checksum(spec),
                    tool=VERSION,created_run_id=work['run']['id'],created_at=L.now(),state='failed',errors=[],files={},limitations=[WARNING])
        work['run']['table_queries_version']=1
        try:
            summary,files,preview,groups=execute(project,work,args.version,spec,folder,args.limit)
            record.update(state='completed',summary=summary,files=files,result_fingerprint=L.checksum({name:info["sha256"] for name,info in files.items()}))
        except Exception as exc:
            record['errors']=[f'{type(exc).__name__}: {exc}'];preview=[];groups=[]
        L.add(work,'TableQuery',record,qid);api.save_work(project,work)
        return dict(query_id=qid,state=record['state'],summary=record.get('summary'),preview=preview,group_preview=groups,
                    result_directory=str(folder),files=record['files'],errors=record['errors'],warning=WARNING,reviewed=False)


def result_value(project,query,selector):
    L.require(query.get('state')=='completed','Failed query cannot be cited')
    L.require(isinstance(selector,dict) and not set(selector)-{'kind','index','field'} and selector.get('kind') in {'row','group','summary'} and isinstance(selector.get('field'),str),'Invalid query result locator')
    kind=selector['kind'];key={'row':'rows.jsonl','group':'groups.jsonl','summary':'summary.json'}[kind]
    info=query['files'][key];path=(project/info['path']).resolve()
    L.require(path.is_relative_to(project.resolve()) and path.is_file() and readers.digest(path)==info['sha256'],'Query result missing/changed or escaping project')
    if kind=='summary':
        L.require('index' not in selector,'Summary selector has no row index')
        values=json.loads(path.read_text(encoding='utf-8'))
    else:
        L.require(type(selector.get('index')) is int and selector['index']>0,'Query result index must be positive')
        values=None
        with path.open(encoding='utf-8') as stream:
            for index,text in enumerate(stream,1):
                if index==selector['index']:values=json.loads(text)['values'];break
        L.require(values is not None,'Query result index outside saved results')
    L.require(selector['field'] in values,'Unknown query result field')
    value=values[selector['field']]
    L.require(isinstance(value,(str,int)) and not isinstance(value,bool),'Query reference must select one nonempty scalar')
    return str(value)


def bind(work,item,project):
    if not item.get('query_id'):return
    L.require(project is not None,'Query references require the project-aware CLI')
    query=work['records'].get(item['query_id']);L.require(query and query['kind']=='TableQuery','Unknown table query reference')
    value=result_value(Path(project),query,item.get('result_locator'))
    vid=query['source_version_id'];selector=item['result_locator']
    uid=str(uuid.uuid5(uuid.NAMESPACE_URL,item['query_id']+line(selector)))
    for key,expected in [('source_version_id',vid),('unit_id',uid)]:
        L.require(key not in item or item[key]==expected,'Query source/unit reference mismatch');item[key]=expected
    if not any(u['id']==uid for u in work['units'][vid]):
        loc=dict(unit='table_query_derived',query_id=query['id'],result_locator=copy.deepcopy(selector))
        read=L.add(work,'ReadRecord',dict(source_version_id=vid,unit_id=uid,locator=loc,state='extracted',method=VERSION,render_version=None,errors=[],limitations=[WARNING]))
        work['units'][vid].append(readers.unit(loc,value,id=uid,read_id=read,limitations=[WARNING],derived_from=dict(query_id=query['id'],source_version_id=vid,source_sha256=query['source_sha256'],result_locator=copy.deepcopy(selector))))
    if 'raw_value' in item:L.require(item['raw_value']==value,'Calculation raw_value differs from selected query result')
    if 'value' in item:L.require(number(item['value'])==number(value),'Calculation value differs from selected query result; normalize with a separate documented calculation')
    item.setdefault('limitations',[])
    if WARNING not in item['limitations']:item['limitations'].append(WARNING)


def validate(work,project=None):
    queries={r['id']:r for r in work['records'].values() if r['kind']=='TableQuery'}
    for query in queries.values():
        L.require(work['run'].get('table_queries_version')==1,'TableQuery requires versioned query schema')
        version=work['records'].get(query.get('source_version_id'),{})
        L.require(version.get('kind')=='SourceVersion' and query.get('source_sha256')==version.get('sha256'),'Query source fingerprint mismatch')
        L.require(query.get('tool')==VERSION and query.get('spec_sha256')==L.checksum(specification(query.get('spec'))),'Query specification/version mismatch')
        L.require(query.get('state') in {'completed','failed'},'Invalid query state')
        if query['state']=='failed':L.require(bool(query.get('errors')) and not query.get('files'),'Failed query cannot claim result files')
        else:
            L.require(set(query.get('files',{}))=={'spec.json','rows.jsonl','groups.jsonl','summary.json'} and query.get('result_fingerprint')==L.checksum({name:info['sha256'] for name,info in query['files'].items()}),'Query result fingerprint mismatch')
            if project is not None:
                for info in query['files'].values():
                    path=(project/info['path']).resolve()
                    L.require(path.is_relative_to(project.resolve()) and path.is_file() and readers.digest(path)==info['sha256'],'Query result missing/changed or escaping project')
                L.require(json.loads((project/query['files']['spec.json']['path']).read_text(encoding='utf-8'))==query['spec'],'Saved query spec differs')
                L.require(json.loads((project/query['files']['summary.json']['path']).read_text(encoding='utf-8'))==query['summary'],'Saved query summary differs')
    index={(v,u['id']):u for v,units in work['units'].items() for u in units}
    for (vid,uid),unit in index.items():
        if unit['locator'].get('unit')!='table_query_derived':continue
        origin=unit.get('derived_from',{});query=queries.get(origin.get('query_id'))
        L.require(query and query['state']=='completed' and query['source_version_id']==vid and origin.get('source_sha256')==query['source_sha256'] and origin.get('source_version_id')==vid,'Query unit lineage mismatch')
        L.require(unit['locator'].get('query_id')==query['id'] and unit['locator'].get('result_locator')==origin.get('result_locator') and WARNING in unit.get('limitations',[]),'Query unit locator/limitations mismatch')
        if project is not None:L.require(unit['text']==result_value(project,query,origin['result_locator']),'Query unit differs from saved result')
    for record in work['records'].values():
        for item in ([record] if record['kind'] in {'Evidence','ReadRecord'} else record.get('inputs',[]) if record['kind']=='Calculation' else []):
            unit=index.get((item.get('source_version_id'),item.get('unit_id')))
            if unit and unit['locator'].get('unit')=='table_query_derived':
                L.require(item.get('state')!='viewed' and item.get('verification_state')!='original_viewed','Query result cannot be marked original-viewed')
                if record['kind']!='ReadRecord':L.require(item.get('query_id')==unit['locator']['query_id'] and item.get('result_locator')==unit['locator']['result_locator'],'Query citation needs matching query_id and result_locator')
