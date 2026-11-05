"""Local XML text/attributes with namespace-aware, indexed element locators."""
import json
from xml.etree import ElementTree as ET
from xml.parsers import expat


def parse_xml(data):
    # Expat detects declarations even in UTF-16. Reject before ElementTree expands
    # entities; neither parser is given an external resource resolver.
    parser = expat.ParserCreate()

    def reject(*args):
        raise ValueError('DTD/entity declarations are unsupported; external resources are never resolved')

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(data, True)
    return ET.fromstring(data)


def indexed_elements(root):
    def visit(element, path):
        yield element, path
        counts = {}
        for child in element:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            yield from visit(child, path + '/' + child.tag + '[' + str(counts[child.tag]) + ']')
    yield from visit(root, '/' + root.tag + '[1]')


def read(path, cache):
    from .readers import unit
    root = parse_xml(path.read_bytes())
    rows = []
    for element, anchor in indexed_elements(root):
        # Own text/tails only, so child values are not copied into every ancestor.
        text = element.text or ''
        tails = ''.join(child.tail or '' for child in element)
        attributes = dict(sorted(element.attrib.items()))
        if not (text.strip() or tails.strip() or attributes):
            continue
        content = text + tails
        if attributes:
            content += '\n' + json.dumps(attributes, ensure_ascii=False, sort_keys=True)
        rows.append(unit({'unit': 'block', 'element_path': anchor}, content,
                         xml_text=text, xml_child_tails=[child.tail or '' for child in element],
                         xml_attributes=attributes,
                         limitations=['Structured XML values only; authenticity, signatures and business meaning require review']))
    return rows
