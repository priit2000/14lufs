#!/usr/bin/env python3
import sys
from pathlib import Path

FORBIDDEN = set(range(0x80, 0x110000))  # any non-ASCII codepoint

def check_file(path: Path) -> int:
    bad = 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        print(f"Skip (read error): {path}: {e}")
        return 0
    for ln, line in enumerate(text, 1):
        for ch in line:
            if ord(ch) in FORBIDDEN:
                bad += 1
                # show a compact preview
                preview = line
                if len(preview) > 120:
                    preview = preview[:117] + '...'
                safe = preview.encode('ascii', 'backslashreplace').decode('ascii')
                print(f"{path}:{ln}: non-ASCII char U+{ord(ch):04X}: {safe}")
                break
    return bad


def main(argv: list[str]) -> int:
    roots = [Path('.')] if len(argv) == 1 else [Path(a) for a in argv[1:]]
    files = []
    for r in roots:
        if r.is_file():
            files.append(r)
        else:
            for p in r.rglob('*'):
                if ".git" in p.parts:
                    continue
                if p.is_file() and p.suffix.lower() in {'.py', '.md', '.txt', '.json', '.yml', '.yaml'}:
                    files.append(p)
    total_bad = 0
    for f in files:
        total_bad += check_file(f)
    if total_bad:
        print(f"Found {total_bad} non-ASCII issues.")
        return 1
    else:
        print("ASCII clean.")
        return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
