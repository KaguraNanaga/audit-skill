"""Renderer 9: query-derived values and result files, preserving previous renderers."""
from urllib.parse import quote
from . import reporting_v8,reporting_v7
from .table_query import WARNING


def render(work,project=None,**kwargs):
    result=reporting_v8.render(work,project,**kwargs)
    queries=[r for r in work['records'].values() if r['kind']=='TableQuery']
    if queries:
        root=kwargs.get('relative_root','../..')
        lines=['','## 表查询来源','',WARNING+'。','']
        for q in queries:
            lines.append('- '+q['id']+'；源版本='+q['source_version_id']+'；状态='+q['state']+'；摘要='+str(q.get('summary'))+'；查询规格指纹='+q['spec_sha256'])
            for name,info in q['files'].items():lines.append('  - ['+name+'](<'+quote(root+'/'+info['path'],safe='/.-_~')+'>)；SHA256='+info['sha256'])
            if q['errors']:lines.append('  - 失败原因：'+str(q['errors']))
        section='\n'.join(lines)+'\n'
        result['review.md']+=section;result['handoff.md']+=section
    return result


def export_portable(project,ledger,api):
    def selected(work,**kwargs):
        return render(work,**kwargs) if work['run'].get('table_queries_version') else reporting_v8.render(work,**kwargs)
    return reporting_v7.export_portable(project,ledger,api,renderer=selected,renderer_version=9)
