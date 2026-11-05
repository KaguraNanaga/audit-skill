"""OFD declared pages and TextObject/TextCode layer; no page rendering."""
from pathlib import PurePosixPath
import re
import zipfile

from .xml_reader import indexed_elements, parse_xml

TEXT_ONLY = '仅文本层；未完成原页视觉核对；text layer only, not a rendered page'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def member_path(base, reference):
    reference = reference.strip()
    if not reference or '\\' in reference or '\x00' in reference or reference.startswith('//') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', reference):
        raise ValueError('Unsupported external/invalid package reference: ' + reference)
    pieces = [] if reference.startswith('/') else list(PurePosixPath(base).parent.parts)
    for piece in PurePosixPath(reference.lstrip('/')).parts:
        if piece == '..':
            if not pieces:
                raise ValueError('Package reference escapes archive root')
            pieces.pop()
        elif piece != '.':
            pieces.append(piece)
    if not pieces:
        raise ValueError('Empty package reference')
    return '/'.join(pieces)


def package_xml(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 32 * 1024 * 1024:
        raise ValueError('XML part exceeds 32 MiB local reader limit')
    return parse_xml(archive.read(info))


def check_package(archive):
    names = archive.namelist()
    if len(names) > 10000 or len(set(names)) != len(names):
        raise ValueError('Too many or duplicate package members')
    for name in names:
        if name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe archive member name')


def read(path, cache):
    from .readers import unit
    rows = []
    physical = 0
    with zipfile.ZipFile(path) as archive:
        check_package(archive)
        root = package_xml(archive, 'OFD.xml')
        if local(root.tag) != 'OFD':
            raise ValueError('OFD.xml root is not OFD')
        documents = [el.text for body in root if local(body.tag) == 'DocBody'
                     for el in body if local(el.tag) == 'DocRoot' and el.text]
        if not documents:
            raise ValueError('OFD.xml has no Document reference')
        for document_number, reference in enumerate(documents, 1):
            document = member_path('OFD.xml', reference)
            try:
                tree = package_xml(archive, document)
                pages = [page for container in tree if local(container.tag) == 'Pages'
                         for page in container if local(page.tag) == 'Page']
                if not pages:
                    raise ValueError('Document contains no declared pages')
            except Exception as exc:
                rows.append(unit({'unit': 'file', 'part': document}, state='failed', errors=[str(exc)], limitations=[TEXT_ONLY]))
                continue
            for page in pages:
                physical += 1
                loc = {'unit': 'page', 'physical_page': physical, 'document': document_number,
                       'ofd_page_id': page.get('ID')}
                try:
                    content = member_path(document, page.get('BaseLoc', ''))
                    page_tree = package_xml(archive, content)
                    if local(page_tree.tag) != 'Page':
                        raise ValueError('OFD page content root is not Page')
                    rows.append(unit(loc, state='manual_check', limitations=[TEXT_ONLY,
                                     'No page image created by text extraction; register an actual renderer for visual review']))
                    for element, anchor in indexed_elements(page_tree):
                        if local(element.tag) != 'TextObject':
                            continue
                        codes = [dict(text=code.text or '', attributes=dict(sorted(code.attrib.items())))
                                 for code in element.iter() if local(code.tag) == 'TextCode']
                        rows.append(unit(dict(loc, unit='block', part=content, object_path=anchor,
                                              object_id=element.get('ID'), boundary=element.get('Boundary')),
                                         ''.join(code['text'] for code in codes),
                                         text_codes=codes, object_attributes=dict(sorted(element.attrib.items())),
                                         limitations=[TEXT_ONLY, 'Declared object order and coordinates retained; visual reading order is not inferred']))
                except Exception as exc:
                    rows.append(unit(loc, state='failed', errors=[str(exc)], limitations=[TEXT_ONLY]))
    return rows
