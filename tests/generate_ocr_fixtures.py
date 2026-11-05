#!/usr/bin/env python3
"""Construct an original bitmap fixture with a small code-defined glyph alphabet."""
import hashlib,json,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GLYPHS={
'S':['01111','10000','10000','01110','00001','00001','11110'],
'Y':['10001','10001','01010','00100','00100','00100','00100'],
'N':['10001','11001','11001','10101','10011','10011','10001'],
'T':['11111','00100','00100','00100','00100','00100','00100'],
'H':['10001','10001','10001','11111','10001','10001','10001'],
'E':['11111','10000','10000','11110','10000','10000','11111'],
'I':['11111','00100','00100','00100','00100','00100','11111'],
'C':['01111','10000','10000','10000','10000','10000','01111'],
'A':['01110','10001','10001','11111','10001','10001','10001'],
'M':['10001','11011','10101','10101','10001','10001','10001'],
'O':['01110','10001','10001','10001','10001','10001','01110'],
'U':['10001','10001','10001','10001','10001','10001','01110'],
'1':['00100','01100','00100','00100','00100','00100','01110'],
'2':['01110','10001','00001','00010','00100','01000','11111'],
'3':['11110','00001','00001','01110','00001','00001','11110'],
'4':['00010','00110','01010','10010','11111','00010','00010'],
'5':['11111','10000','10000','11110','00001','00001','11110'],
'.':['00000']*5+['00100','00100'],' ':['00000']*7}

def main():
 folder=ROOT/'tests/ocr-fixtures';folder.mkdir(exist_ok=True)
 width,height,scale=900,140,5;pixels=[bytearray([255])*width for _ in range(height)]
 for index,ch in enumerate('SYNTHETIC AMOUNT 123.45'):
  for y,row in enumerate(GLYPHS[ch]):
   for x,bit in enumerate(row):
    if bit=='1':
     for dy in range(scale): pixels[50+y*scale+dy][30+index*6*scale+x*scale:30+index*6*scale+x*scale+scale]=bytes(scale)
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+row for row in pixels)))+chunk(b'IEND',b'')
 (folder/'synthetic.png').write_bytes(png)
 (folder/'blocks.json').write_text(json.dumps([dict(text='SYNTHETIC AMOUNT 123.45',confidence=0.9,bbox=[[30,50],[690,50],[690,85],[30,85]],frame=1)],sort_keys=True,indent=2)+'\n')
 manifest=dict(frozen_on='2026-11-05',synthetic=True,files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()})
 (ROOT/'tests/input-sha256-stage3.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
