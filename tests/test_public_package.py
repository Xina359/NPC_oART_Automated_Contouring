"""English-only release hygiene and filename-independent input regressions."""
from pathlib import Path
import json
import shutil

import pytest
from oart_analysis.release_hygiene import scan_public_tree, main
from oart_analysis.io import sha256


def test_english_text_and_mathematical_symbols_are_accepted(tmp_path):
    (tmp_path/'README.md').write_text('DSC mean \u00b1 SD; interval \u2264 0.05.\n', encoding='utf-8')
    report = scan_public_tree(tmp_path, strict=True)
    assert report['passed'] and report['checked_files'] == 1


@pytest.mark.parametrize('point', [0x4E2D, 0x6587, 0x3400, 0xF900, 0x20000, 0x3002])
def test_direct_restricted_text_is_rejected(tmp_path, point):
    (tmp_path/'example.txt').write_text(chr(point), encoding='utf-8')
    report = scan_public_tree(tmp_path, strict=True)
    assert not report['passed']
    assert report['issues'][0]['kind'] == 'restricted_east_asian_text'


@pytest.mark.parametrize('encoded', ['escaped', 'percent'])
def test_encoded_restricted_text_is_rejected(tmp_path, encoded):
    from urllib.parse import quote
    text = (chr(92) + 'u' + '4e2d') if encoded == 'escaped' else quote(chr(0x4E2D))
    (tmp_path/'example.txt').write_text(text, encoding='utf-8')
    assert not scan_public_tree(tmp_path, strict=True)['passed']


def test_localized_readme_name_is_rejected(tmp_path):
    (tmp_path/('README.' + 'zh' + '-CN.md')).write_text('English text', encoding='utf-8')
    assert not scan_public_tree(tmp_path, strict=True)['passed']


def test_non_ascii_release_filename_is_rejected(tmp_path):
    (tmp_path/('r' + chr(0xE9) + 'sum.txt')).write_text('English', encoding='utf-8')
    report = scan_public_tree(tmp_path, strict=True)
    assert any(item['kind'] == 'non_ascii_path' for item in report['issues'])


def test_numbered_source_reference_is_rejected(tmp_path):
    name = 'Source_data' + '(' + '1' + ').xlsx'
    (tmp_path/'README.md').write_text(name, encoding='utf-8')
    assert any(item['kind'] == 'numbered_source_filename'
               for item in scan_public_tree(tmp_path, strict=True)['issues'])


def test_strict_mode_checks_generated_directories_too(tmp_path):
    output = tmp_path/'outputs'; output.mkdir()
    (output/'local.txt').write_text(chr(0x4E2D), encoding='utf-8')
    assert scan_public_tree(tmp_path)['passed']
    assert not scan_public_tree(tmp_path, strict=True)['passed']


def test_binary_resource_is_not_silently_treated_as_english(tmp_path):
    (tmp_path/'private.dat').write_bytes(b'\x00\x01')
    assert not scan_public_tree(tmp_path, strict=True)['passed']


def test_hygiene_cli_reports_json(tmp_path, capsys):
    (tmp_path/'README.md').write_text('English', encoding='utf-8')
    assert main(['--root', str(tmp_path), '--strict']) == 0
    assert json.loads(capsys.readouterr().out)['passed'] is True


def test_identical_bytes_have_same_hash_after_filename_change(tmp_path):
    original = tmp_path/'original.xlsx'
    original.write_bytes(b'filename-independent-hash-fixture')
    canonical = tmp_path/'Source_data.xlsx'
    shutil.copyfile(original, canonical)
    assert sha256(original) == sha256(canonical)
