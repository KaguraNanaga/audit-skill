#!/usr/bin/env python3
"""Validate the selected public files and their SHA-256 manifest; no network access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
ROOT_FILES = {
    "README.md", "README.zh-CN.md", "LICENSE", "requirements.txt", ".gitignore",
    "RELEASE_NOTES.md", "VALIDATION.md", "RELEASE_MANIFEST.json",
}
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".txt"}
PRIVATE_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/|[A-Za-z]:\\Users\\[^\\]+\\")
KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}")


def release_files():
    files, errors = [], []
    candidates = []
    for base, dirs, names in os.walk(ROOT, followlinks=False):
        for name in list(dirs):
            p = Path(base) / name
            if name == ".git":
                dirs.remove(name)
            elif p.is_symlink():
                errors.append(f"symlink is not a release input: {p.relative_to(ROOT)}")
                dirs.remove(name)
        candidates.extend(Path(base) / name for name in names if name != ".git")
    for p in sorted(candidates):
        rel = p.relative_to(ROOT)
        if p.is_symlink():
            errors.append(f"symlink is not a release input: {rel}")
            continue
        if not p.is_file():
            continue
        s = rel.as_posix()
        allowed = (
            (len(rel.parts) == 1 and s in ROOT_FILES)
            or s == "evidence-reviewer/SKILL.md"
            or s == "evidence-reviewer/LICENSE"
            or s == "evidence-reviewer/agents/openai.yaml"
            or (rel.parent.as_posix() == "evidence-reviewer/scripts" and p.suffix == ".py")
            or (rel.parent.as_posix() == "evidence-reviewer/references" and p.suffix == ".md")
            or (rel.parent.as_posix() == "tools" and p.suffix == ".py")
            or (rel.parts[0] == "tests" and p.suffix in TEXT_SUFFIXES | {".pdf", ".png", ".xlsx", ".docx"})
        )
        if not allowed or any(part in {"__pycache__", ".git", "outputs", "ledger", "cache"} for part in rel.parts):
            errors.append(f"unlisted release input: {s}")
        if p != MANIFEST:
            files.append(p)
    return files, errors


def inspected_texts(p):
    if p.suffix in {".xlsx", ".docx"}:
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.endswith((".xml", ".rels")):
                    yield name, z.read(name).decode("utf-8", errors="replace")
    else:
        # Binary metadata is scanned where decodable; this does not replace visual review.
        yield "", p.read_bytes().decode("utf-8", errors="ignore")


def check_files(files):
    errors = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        for member, text in inspected_texts(p):
            if PRIVATE_PATH.search(text) or KEY_PATTERN.search(text):
                errors.append(f"review possible private path/key: {rel} {member}")
        if p.suffix != ".md":
            continue
        for target in re.findall(r"\]\(([^\n)]+)\)", p.read_text(encoding="utf-8")):
            target = target.strip().strip("<>")
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            dest = (p.parent / target).resolve()
            if not dest.is_relative_to(ROOT) or not dest.exists():
                errors.append(f"broken or nonportable local link: {rel} -> {target}")
    return errors


def hashes(files):
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true", help="create a fresh manifest after reviewing the release inputs")
    args = parser.parse_args()
    files, errors = release_files()
    errors.extend(check_files(files))
    if not (ROOT / "evidence-reviewer/SKILL.md").is_file() or not (ROOT / "LICENSE").is_file():
        errors.append("missing skill entry or license")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    current = hashes(files)
    if args.write_manifest:
        MANIFEST.write_text(json.dumps({
            "package_version": "0.4.0-beta.1", "engine_version": "0.3.1",
            "scope": "Selected public package; manifest excludes itself. No authenticity or audit-accuracy guarantee.",
            "files": current,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        if not MANIFEST.exists():
            print("Missing RELEASE_MANIFEST.json", file=sys.stderr)
            return 1
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
        changed = sorted(k for k in set(expected) | set(current) if expected.get(k) != current.get(k))
        if changed:
            print(json.dumps({"ok": False, "changed_or_missing": changed}, ensure_ascii=False, indent=2))
            return 1
    print(json.dumps({"ok": True, "files": len(files), "manifest_written": args.write_manifest,
                      "limits": "Heuristic scan and integrity check; not a complete confidentiality or business review."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
