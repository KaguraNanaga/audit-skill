#!/usr/bin/env python3
"""Check local Markdown links and fragments without fetching external resources."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def prose(text):
    lines=[]; fence=None
    for line in text.splitlines():
        match=re.match(r'^\s{0,3}(`{3,}|~{3,})',line)
        if match:
            marker=match.group(1)
            if fence is None: fence=(marker[0],len(marker))
            elif marker[0]==fence[0] and len(marker)>=fence[1]: fence=None
            continue
        if fence is None: lines.append(re.sub(r'(`+).*?\1','',line))
    return '\n'.join(lines)


def anchors(text):
    result=set();counts={}
    for heading in re.findall(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$',text,re.M):
        heading=re.sub(r'<[^>]+>','',heading).strip().lower()
        slug=re.sub(r'[^\w\- ]','',heading).replace(' ','-')
        number=counts.get(slug,0);counts[slug]=number+1
        result.add(slug+('-'+str(number) if number else ''))
    result.update(re.findall(r'<a\s+[^>]*?(?:id|name)=[\'"]([^\'"]+)',text,re.I))
    return result


def destinations(text):
    text=prose(text)
    inline=r'!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+[\'"][^\n]*?)?\s*\)'
    found=[a or b for a,b in re.findall(inline,text)]
    definitions={key.strip().casefold():a or b for key,a,b in re.findall(r'^\s{0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|([^\s]+))',text,re.M)}
    # Check the definitions themselves, including ones referenced later in a file.
    found.extend(definitions.values())
    missing=[]
    for label,key in re.findall(r'!?\[([^\]\n]+)\]\[([^\]\n]*)\]',text):
        key=(key or label).strip().casefold()
        if key not in definitions: missing.append(key)
    return found,missing


def check_links(root, files=None):
    root=Path(root).resolve(); errors=[];checked=0
    files=list(files) if files is not None else [p for p in root.rglob('*.md') if '.git' not in p.relative_to(root).parts]
    for path in files:
        path=Path(path)
        if path.suffix!='.md': continue
        targets,missing=destinations(path.read_text(encoding='utf-8'))
        label=path.relative_to(root).as_posix()
        errors.extend('Undefined Markdown reference: '+label+' -> '+key for key in missing)
        for target in targets:
            parsed=urlsplit(target)
            if parsed.scheme or parsed.netloc: continue
            name=unquote(parsed.path)
            if Path(name).is_absolute():
                errors.append('Absolute local link: '+label+' -> '+target);continue
            dest=(path.parent/name).resolve() if name else path.resolve()
            checked+=1
            if not dest.is_relative_to(root) or not dest.exists():
                errors.append('Broken or escaping local link: '+label+' -> '+target)
            elif parsed.fragment and dest.is_file() and dest.suffix=='.md':
                if unquote(parsed.fragment) not in anchors(dest.read_text(encoding='utf-8')):
                    errors.append('Missing local fragment: '+label+' -> '+target)
    return dict(ok=not errors,checked_local_links=checked,errors=errors)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();result=check_links(args.root)
    print(json.dumps(result,ensure_ascii=False,indent=2));return int(not result['ok'])


if __name__=='__main__': raise SystemExit(main())
