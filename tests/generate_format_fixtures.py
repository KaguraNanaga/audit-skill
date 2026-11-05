#!/usr/bin/env python3
"""Construct minimal OFD/XML/PPTX packages from code, not business materials."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
O = 'http://www.ofdspec.org/2016'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def package(path, parts):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(parts.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 5, 0, 0, 0))
            info.create_system = 0
            archive.writestr(info, content.encode('utf-8') if isinstance(content, str) else content)


def png():
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 0, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b''.join(b'\0' + bytes([255 if y % 2 else 0]) * 8 for y in range(8)))) + chunk(b'IEND', b''))


def ofd_parts():
    return {
        'OFD.xml': f'<ofd:OFD xmlns:ofd="{O}" Version="1.0" DocType="OFD"><ofd:DocBody><ofd:DocInfo><ofd:DocID>00000000000000000000000000000001</ofd:DocID></ofd:DocInfo><ofd:DocRoot>Doc_0/Document.xml</ofd:DocRoot></ofd:DocBody></ofd:OFD>',
        'Doc_0/Document.xml': f'<ofd:Document xmlns:ofd="{O}"><ofd:CommonData><ofd:MaxUnitID>30</ofd:MaxUnitID><ofd:PageArea><ofd:PhysicalBox>0 0 210 297</ofd:PhysicalBox></ofd:PageArea><ofd:PublicRes>PublicRes.xml</ofd:PublicRes><ofd:DocumentRes>DocumentRes.xml</ofd:DocumentRes></ofd:CommonData><ofd:Pages><ofd:Page ID="1" BaseLoc="Pages/Page_0/Content.xml"/><ofd:Page ID="2" BaseLoc="Pages/Page_1/Content.xml"/></ofd:Pages></ofd:Document>',
        'Doc_0/PublicRes.xml': f'<ofd:Res xmlns:ofd="{O}" BaseLoc="Res"><ofd:Fonts><ofd:Font ID="10" FontName="sans-serif"/></ofd:Fonts></ofd:Res>',
        'Doc_0/DocumentRes.xml': f'<ofd:Res xmlns:ofd="{O}" BaseLoc="Res"><ofd:MultiMedias><ofd:MultiMedia ID="20" Type="Image" Format="PNG"><ofd:MediaFile>image.png</ofd:MediaFile></ofd:MultiMedia></ofd:MultiMedias></ofd:Res>',
        'Doc_0/Pages/Page_0/Content.xml': f'<ofd:Page xmlns:ofd="{O}"><ofd:Content><ofd:Layer ID="3"><ofd:TextObject ID="4" Boundary="10 20 100 10" Font="10" Size="4"><ofd:TextCode X="0" Y="4" DeltaX="4 4">合成金额 </ofd:TextCode><ofd:TextCode X="20" Y="4">123.4500</ofd:TextCode></ofd:TextObject><ofd:PageBlock ID="5"><ofd:TextObject ID="6" Boundary="10 40 100 10" Font="10" Size="4"><ofd:TextCode X="0" Y="4">仅用于格式测试</ofd:TextCode></ofd:TextObject></ofd:PageBlock></ofd:Layer></ofd:Content></ofd:Page>',
        'Doc_0/Pages/Page_1/Content.xml': f'<ofd:Page xmlns:ofd="{O}"><ofd:Content><ofd:Layer ID="7"><ofd:ImageObject ID="8" Boundary="0 0 210 297" ResourceID="20"/></ofd:Layer></ofd:Content></ofd:Page>',
        'Doc_0/Res/image.png': png(),
    }


def main():
    folder = ROOT / 'tests/format-fixtures'
    folder.mkdir(parents=True, exist_ok=True)
    package(folder / 'mixed.ofd', ofd_parts())
    (folder / 'invoice.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<Invoice xmlns="urn:synthetic:invoice" currency="CNY"><Line id="A"><Amount>123.4500</Amount></Line><Line id="B"><Amount>0.0100</Amount></Line><Memo>合成材料，非真实业务</Memo></Invoice>\n', encoding='utf-8', newline='\n')
    # Slide filenames intentionally differ from presentation order.
    slides = {}
    for name, text in [('slide9.xml', 'SYNTHETIC FIRST 123.45'), ('slide2.xml', '合成第二页')]:
        slides['ppt/slides/' + name] = f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/><p:sp><p:nvSpPr><p:cNvPr id="2" name="Synthetic text"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    package(folder / 'slides.pptx', dict(slides, **{
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slides/slide9.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/><Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{R}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        'ppt/presentation.xml': f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{R}/slide" Target="slides/slide9.xml"/><Relationship Id="rId2" Type="{R}/slide" Target="slides/slide2.xml"/></Relationships>',
    }))
    manifest = dict(frozen_on='2026-11-05', synthetic=True,
                    files={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(folder.iterdir()) if p.is_file()})
    (ROOT / 'tests/input-sha256-stage2.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
