"""Check release identity and the complete declared source-file inventory."""
from pathlib import Path
import hashlib
import json
import re
import tomllib

GENERATED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
             '.mypy_cache', '.ruff_cache', '.tox', 'build', 'dist', 'outputs', 'local_data'}


def verify_release(root, *, strict=False):
    root = Path(root).resolve()
    manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    version = manifest['release_version']
    declared = manifest['files']
    failures = []
    for name, expected in declared.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            failures.append(f'missing/unsafe: {name}')
            continue
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            failures.append(f'invalid checksum: {name}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f'hash mismatch: {name}')
    actual = set()
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if not strict and any(p in GENERATED or p.endswith('.egg-info') for p in rel.parts):
            continue
        if path.is_symlink():
            failures.append(f'unsupported symlink: {rel.as_posix()}')
        elif path.is_file() and rel.as_posix() != 'RELEASE_MANIFEST.json':
            actual.add(rel.as_posix())
    failures += [f'undeclared file: {name}' for name in sorted(actual - set(declared))]
    identities = {
        'pyproject.toml': tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version'],
        'oart_analysis/data/manifest.json': json.loads((root/'oart_analysis/data/manifest.json').read_text(encoding='utf-8'))['dataset_version'],
        'oart_analysis/data/source_profile.json': json.loads((root/'oart_analysis/data/source_profile.json').read_text(encoding='utf-8'))['code_version'],
    }
    module = (root/'oart_analysis/__init__.py').read_text(encoding='utf-8')
    found = re.search(r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]', module, re.M)
    identities['oart_analysis/__init__.py'] = found.group(1) if found else None
    failures += [f'version mismatch: {name}' for name, value in identities.items() if value != version]
    return {'release_version': version, 'checked_files': len(declared),
            'strict': strict, 'failures': failures, 'passed': not failures}
