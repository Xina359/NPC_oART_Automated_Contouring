"""Check the public source distribution without reading a workbook or using a network.

This is a deterministic text/path check, not natural-language classification.
The final source ZIP contains UTF-8 text resources only. Development runs may
exclude documented generated directories; use strict mode on an unpacked ZIP.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote

# Numeric Unicode ranges avoid embedding forbidden-language text in this checker.
RESTRICTED_RANGES = (
    (0x2E80, 0x2FFF), (0x3000, 0x303F), (0x3100, 0x312F),
    (0x31A0, 0x31BF), (0x31C0, 0x31EF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF),
    (0x16FE0, 0x18DFF), (0x20000, 0x2FA1F), (0x30000, 0x323AF),
)
GENERATED_DIRS = frozenset({
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', '.tox', 'build', 'dist', 'outputs', 'local_data',
})
UNICODE_ESCAPE = re.compile(r'\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})')
NUMBERED_SOURCE = re.compile(r'Source_data\s*\(\d+\)\.xlsx', re.IGNORECASE)
LOCALIZED_README = re.compile(r'^README[._-]zh(?:[._-]|$)', re.IGNORECASE)


def _restricted(character: str) -> bool:
    value = ord(character)
    return any(low <= value <= high for low, high in RESTRICTED_RANGES)


def _decoded_text(text: str) -> str:
    """Recognize direct, percent-encoded and common escaped Unicode text."""
    value = unquote(text)
    for _ in range(2):
        def replace(match: re.Match[str]) -> str:
            point = int(match.group(1) or match.group(2), 16)
            return chr(point) if point <= 0x10FFFF else match.group(0)
        value = UNICODE_ESCAPE.sub(replace, value)
    return value


def scan_public_tree(root: Path | str, *, strict: bool = False) -> dict[str, Any]:
    """Inspect all distributed paths and their UTF-8 text; never mutate files.

    Strict mode traverses every member, including generated directories. Use it
    on a pristine extraction of the deliverable archive. Non-strict mode excludes
    only the documented local build/cache/output directories for maintainer use.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f'Package root is not a directory: {root}')
    issues: list[dict[str, Any]] = []
    checked_files = 0
    checked_bytes = 0
    excluded = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not strict and any(part in GENERATED_DIRS or part.endswith('.egg-info')
                              for part in relative.parts):
            if path.is_file():
                excluded += 1
            continue
        name = relative.as_posix()
        if not name.isascii():
            issues.append({'path': name, 'kind': 'non_ascii_path'})
        if LOCALIZED_README.search(path.name):
            issues.append({'path': name, 'kind': 'localized_readme_name'})
        if NUMBERED_SOURCE.search(unquote(name)):
            issues.append({'path': name, 'kind': 'numbered_source_filename'})
        if path.is_symlink():
            issues.append({'path': name, 'kind': 'symlink_not_supported'})
            continue
        if not path.is_file():
            continue
        checked_files += 1
        data = path.read_bytes()
        checked_bytes += len(data)
        if b'\x00' in data:
            issues.append({'path': name, 'kind': 'binary_resource_requires_review'})
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            issues.append({'path': name, 'kind': 'not_utf8_text'})
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            decoded = _decoded_text(line)
            points = sorted({f'U+{ord(c):04X}' for c in decoded if _restricted(c)})
            if points:
                # Report code points rather than reproducing disallowed text.
                issues.append({'path': name, 'line': number,
                               'kind': 'restricted_east_asian_text', 'code_points': points})
            if NUMBERED_SOURCE.search(decoded):
                issues.append({'path': name, 'line': number,
                               'kind': 'numbered_source_filename'})
            if re.search(r'README[._-]zh(?:[._-]|$)', decoded, re.IGNORECASE):
                issues.append({'path': name, 'line': number,
                               'kind': 'localized_readme_reference'})
    return {
        'check': 'public-source-package-text-and-path-hygiene',
        'strict': strict,
        'checked_files': checked_files,
        'checked_bytes': checked_bytes,
        'excluded_generated_files': excluded,
        'issues': issues,
        'passed': not issues,
        'scope': 'Text/path scan only; does not certify clinical data or natural-language grammar.',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--strict', action='store_true',
                        help='Scan every member of a pristine extracted public archive.')
    args = parser.parse_args(argv)
    try:
        report = scan_public_tree(args.root, strict=args.strict)
    except (OSError, ValueError) as error:
        parser.exit(1, f'ERROR: {error}\n')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
