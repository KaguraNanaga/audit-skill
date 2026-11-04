"""Renderer 8: explicit OCR provenance, while renderers 1–7 remain frozen."""
from . import reporting_v7
from .derived import WARNING


def render(work, project=None, **kwargs):
    result = reporting_v7.render(work, project, **kwargs)
    attempts = [r for r in work['records'].values() if r['kind'] == 'OCRAttempt']
    if attempts:
        lines = ['', '## OCR 定位层', '', WARNING + '。OCR不改变原页读取状态，不证明视觉事实。', '']
        for r in attempts:
            lines.append('- ' + r['id'] + '；引擎=' + r['engine'] + '；版本=' + str(r.get('version')) + '；状态=' + r['state'] + '；定位单元=' + str(len(r['unit_ids'])) + '；错误=' + str(r['errors']))
        section = '\n'.join(lines) + '\n'
        result['review.md'] += section; result['handoff.md'] += section
    return result


def export_portable(project, ledger, api):
    return reporting_v7.export_portable(project, ledger, api, renderer=render, renderer_version=8)
