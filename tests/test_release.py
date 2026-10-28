import hashlib

import pytest

from scripts import release


@pytest.mark.parametrize('tag', ['v9.9.9', '0.1.0', '../v0.1.0'])
def test_release_rejects_tag_version_mismatch(tag):
    with pytest.raises(ValueError, match='不一致'):
        release.release_version(tag)


def test_release_uses_one_version_and_renders_installer_instructions():
    from s7sim import __version__
    assert release.release_version(f'v{__version__}') == __version__
    notes = release.release_notes(__version__)
    assert '@VERSION@' not in notes and '@CHANGES@' not in notes
    assert '移到废纸篓' in notes
    assert 'xattr -dr com.apple.quarantine "/Applications/S7 Studio.app"' in notes
    for name in release.expected_assets(__version__):
        assert name in notes or name.endswith('.zip')


@pytest.mark.parametrize('machine', ['AMD64', 'x86_64', 'x64'])
def test_windows_architecture_names_are_normalized(machine):
    assert release.package_prefix('1.2.3', 'win32', machine) == 'S7Studio-v1.2.3-windows-x64'


@pytest.mark.parametrize('system,machine', [('linux', 'x64'), ('win32', 'arm64'), ('darwin', 'i386')])
def test_unsupported_build_architectures_fail(system, machine):
    with pytest.raises(ValueError):
        release.package_prefix('1.2.3', system, machine)


def make_artifacts(folder):
    for name in release.expected_assets('1.2.3'):
        data = name.encode('utf-8')
        (folder / name).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        (folder / f'{name}.sha256').write_text(f'{digest}  {name}\n', encoding='utf-8')


def test_complete_release_requires_all_platforms_and_generates_checksums(tmp_path):
    make_artifacts(tmp_path)
    names = release.verify_assets(tmp_path, '1.2.3')
    assert len(names) == 6
    checksums = (tmp_path / 'SHA256SUMS.txt').read_text(encoding='utf-8')
    assert len(checksums.splitlines()) == 6
    assert all(name in checksums for name in names)
    # Re-running validation can recover a draft publication without changing packages.
    assert release.verify_assets(tmp_path, '1.2.3') == names


def test_partial_or_mixed_versions_cannot_be_published(tmp_path):
    make_artifacts(tmp_path)
    missing = tmp_path / 'S7Studio-v1.2.3-windows-x64-setup.exe'
    missing.unlink()
    with pytest.raises(ValueError, match='不完整'):
        release.verify_assets(tmp_path, '1.2.3')
    missing.write_bytes(b'restored')
    (tmp_path / 'S7Studio-v0.0.1-macos-arm64.zip').write_bytes(b'old')
    with pytest.raises(ValueError, match='额外'):
        release.verify_assets(tmp_path, '1.2.3')


def test_corrupted_package_cannot_be_published(tmp_path):
    make_artifacts(tmp_path)
    (tmp_path / 'S7Studio-v1.2.3-macos-arm64.dmg').write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='SHA256'):
        release.verify_assets(tmp_path, '1.2.3')
