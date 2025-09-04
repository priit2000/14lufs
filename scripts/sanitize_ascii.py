#!/usr/bin/env python3
import sys
from pathlib import Path

REPLACEMENTS = {
    # Dashes and minus-like
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    # Quotes
    "\u2018": "'", "\u2019": "'",  # single smart quotes
    "\u201C": '"', "\u201D": '"',  # double smart quotes
    # Ellipsis
    "\u2026": "...",
    # Non-breaking space
    "\u00A0": " ",
}

def sanitize_text(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if code < 128:
            out.append(ch)
        elif ch in REPLACEMENTS:
            out.append(REPLACEMENTS[ch])
        else:
            # Drop any other non-ASCII garbage
            # (could also map to '?' if preferred)
            pass
    return "".join(out)


def sanitize_file(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fixed = sanitize_text(raw)
    if fixed != raw:
        path.write_text(fixed, encoding="utf-8", newline="\n")
        return True
    return False


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: sanitize_ascii.py FILE [FILE ...]")
        return 2
    changed_any = False
    for arg in argv[1:]:
        p = Path(arg)
        if not p.exists():
            print(f"Skip: {p} (not found)")
            continue
        changed = sanitize_file(p)
        print(("Sanitized" if changed else "Clean"), p)
        changed_any = changed_any or changed
    return 0 if changed_any else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

