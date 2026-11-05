"""PPTX declared slide order and text anchors, including DPS-derived packages."""
import zipfile

from .ofd_reader import check_package, local, member_path, package_xml
from .xml_reader import indexed_elements

REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def read(path, cache):
    from .readers import unit
    rows = []
    with zipfile.ZipFile(path) as archive:
        check_package(archive)
        presentation = package_xml(archive, 'ppt/presentation.xml')
        relationships = package_xml(archive, 'ppt/_rels/presentation.xml.rels')
        targets = {el.get('Id'): el for el in relationships}
        slides = [el for parent in presentation if local(parent.tag) == 'sldIdLst'
                  for el in parent if local(el.tag) == 'sldId']
        for number, slide in enumerate(slides, 1):
            loc = {'unit': 'page', 'slide': number}
            try:
                rel = targets[slide.get(REL)]
                if rel.get('TargetMode') == 'External':
                    raise ValueError('External slide is not fetched')
                name = member_path('ppt/presentation.xml', rel.get('Target', ''))
                tree = package_xml(archive, name)
                rows.append(unit(loc, state='manual_check', limitations=[
                    'Slide text only; layout, images, charts, notes and animations require separate review']))
                for element, anchor in indexed_elements(tree):
                    if local(element.tag) != 'p':
                        continue
                    text = ''.join(el.text or '' if local(el.tag) == 't' else '\n' if local(el.tag) == 'br' else ''
                                   for el in element.iter())
                    if text:
                        rows.append(unit({'unit': 'block', 'slide': number, 'part': name, 'object_path': anchor}, text,
                                         limitations=['Slide XML text anchor only; not visually verified; notes/master content not extracted']))
            except Exception as exc:
                rows.append(unit(loc, state='failed', errors=[str(exc)], limitations=['Slide extraction failed; other slides continue']))
    return rows
