"""Catch an altered, extra or inconsistently versioned distributed resource."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import os
import pytest
from oart_analysis.release import verify_release


@pytest.fixture
def release(tmp_path):
    files = {
        'pyproject.toml': '[project]\nversion="2.1.0"\n',
        'oart_analysis/__init__.py': '__version__ = "2.1.0"\n',
        'oart_analysis/data/manifest.json': '{"dataset_version":"2.1.0"}',
        'oart_analysis/data/source_profile.json': '{"code_version":"2.1.0"}',
        'data.txt': 'verified source\n',
    }
    hashes = {}
    for name, value in files.items():
        p = tmp_path/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value, encoding='utf-8')
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (tmp_path/'RELEASE_MANIFEST.json').write_text(json.dumps({'release_version':'2.1.0','files':hashes}), encoding='utf-8')
    return tmp_path


def test_pristine_release(release):
    assert verify_release(release, strict=True)['passed']


@pytest.mark.parametrize('change', ['altered', 'extra', 'missing', 'version', 'traversal'])
def test_rejects_release_changes(release, change):
    if change == 'altered':
        (release/'data.txt').write_text('different\n')
    elif change == 'extra':
        (release/'unexpected.py').write_text('# extra\n')
    elif change == 'missing':
        (release/'data.txt').rename(release/'other.txt')
    else:
        p = release/'RELEASE_MANIFEST.json'
        m = json.loads(p.read_text())
        if change == 'version':
            (release/'pyproject.toml').write_text('[project]\nversion="0.0.0"\n')
            m['files']['pyproject.toml'] = hashlib.sha256((release/'pyproject.toml').read_bytes()).hexdigest()
        else:
            m['files']['../outside.txt'] = '0'*64
        p.write_text(json.dumps(m))
    assert not verify_release(release, strict=True)['passed']


def test_strict_rejects_generated_file(release):
    (release/'outputs').mkdir()
    (release/'outputs/log.txt').write_text('local result\n')
    assert verify_release(release)['passed']
    assert not verify_release(release, strict=True)['passed']


@pytest.mark.parametrize('script', ['analyse_data.py', 'evaluate_masks.py'])
def test_legacy_entrypoint_propagates_runtime_failure(tmp_path, script):
    package = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(package/'scripts'/script), '--output', str(tmp_path/'output')]
    if script == 'analyse_data.py':
        source = tmp_path/'invalid.xlsx'
        source.write_text('deliberately invalid OOXML')
        command += ['--source-data', str(source)]
    else:
        command += ['--config', str(tmp_path/'missing.json')]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'ERROR:' in result.stderr


def test_strict_checker_does_not_create_bytecode(release):
    package = Path(__file__).resolve().parents[1]
    for name in ['scripts/verify_release.py', 'oart_analysis/release.py']:
        destination = release/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((package/name).read_bytes())
    manifest_path = release/'RELEASE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'] = {p.relative_to(release).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in release.rglob('*') if p.is_file() and p != manifest_path}
    manifest_path.write_text(json.dumps(manifest))
    environment = dict(os.environ)
    environment.pop('PYTHONDONTWRITEBYTECODE', None)
    result = subprocess.run([sys.executable, str(release/'scripts/verify_release.py'), '--strict'],
                            capture_output=True, text=True, env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(release.rglob('*.pyc'))
