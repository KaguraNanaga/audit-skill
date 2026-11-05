"""Optional external OFD adapter; actual page files and diagnostic attempts only."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from . import ledger as L
from .converters import run_tool
from .readers import digest


def render(args, project, work, folder):
    version = work['records'][args.version]
    source = project / version['local_snapshot']
    units = work['units'][args.version]
    known = {u['locator']['physical_page']: u for u in units if u['locator'].get('unit') == 'page'}
    pages = sorted(set(args.pages or known))
    L.require(bool(pages) and set(pages) <= set(known), 'OFD pages must be declared physical page numbers')
    attempt = dict(stage='ofd-render', source_version_id=args.version, parent_sha256=version['sha256'],
                   pages=pages, state='failed', tool=None, version=None, parameters=[], timeout_seconds=120)
    artifacts = []
    try:
        renderer = Path(args.ofd_renderer).expanduser().resolve() if args.ofd_renderer else None
        if renderer is None or not renderer.is_file():
            attempt['state'] = 'tool_unavailable'
            raise FileNotFoundError('Pass an available local Python adapter with --ofd-renderer; no page image was generated')
        attempt.update(tool=str(renderer), tool_sha256=digest(renderer), python=sys.version)
        output, _ = run_tool([sys.executable, renderer, '--version'], timeout=10)
        L.require(bool(output.strip()), 'OFD adapter must report its actual renderer/version with --version')
        attempt['version'] = output.strip()[:2000]
        with tempfile.TemporaryDirectory(prefix='evidence-ofd-render-') as temporary:
            argv = [sys.executable, str(renderer), str(source), '--output_dir', temporary,
                    '--pages', *map(str, pages)]
            attempt['parameters'] = argv[1:]
            run_tool(argv, timeout=120)
            for page in pages:
                image = Path(temporary) / f'page-{page}.png'
                if not image.is_file() or image.is_symlink():
                    raise ValueError(f'OFD adapter did not create regular page-{page}.png')
                with image.open('rb') as stream:
                    header = stream.read(24)
                if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or not all(struct.unpack('>II', header[16:24])):
                    raise ValueError(f'OFD adapter returned invalid PNG for page {page}')
            # Publish only after every requested page exists. No pretend partial success.
            for page in pages:
                image = Path(temporary) / f'page-{page}.png'
                output = folder / image.name
                shutil.copyfile(image, output)
                sha = digest(output)
                # Exact locators retain the existing per-unit observation guard. An
                # observation on one object does not mark the other objects viewed.
                for item in units:
                    if item['locator'].get('physical_page') != page or item['locator'].get('unit') not in {'page', 'block'}:
                        continue
                    artifacts.append(dict(id=L.uid(), source_version_id=args.version, locator=item['locator'],
                        path=output.relative_to(project).as_posix(), sha256=sha,
                        method='External OFD renderer; original page rendition',
                        provenance=dict(attempt, state='rendered')))
        work['artifacts'].extend(artifacts)
        return {'state': 'rendered', 'pages': pages, 'artifacts': artifacts, 'viewed': False}
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as exc:
        attempt['error'] = f'{type(exc).__name__}: {exc}'
        work['run']['errors'].append(attempt)
        shutil.rmtree(folder, ignore_errors=True)
        return {'state': attempt['state'], 'error': attempt['error'], 'artifacts': [], 'viewed': False}
