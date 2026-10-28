from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from s7sim.storage import default_directory, project_filename, suggested_path
from s7sim.models import demo_project


def test_default_uses_documents_not_working_directory(tmp_path, monkeypatch):
    from s7sim import storage
    monkeypatch.setattr(storage.QStandardPaths, 'writableLocation', lambda _: str(tmp_path / 'Documents'))
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    assert default_directory(settings) == tmp_path / 'Documents/S7 Studio'


def test_unicode_spaces_custom_directory_and_no_overwrite(tmp_path):
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    folder = tmp_path / '测试 Projects'
    settings.setValue('files/default_directory', str(folder))
    settings.sync()
    reloaded = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    first = suggested_path(reloaded, 'CON')
    assert first.name == '_CON.s7sim.json'
    first.write_text('original')
    second = suggested_path(reloaded, 'CON')
    assert second != first
    assert first.read_text() == 'original'
    project = demo_project()
    project.save(second)
    assert second.parent == folder


@pytest.mark.parametrize('name', ['CON', 'NUL', 'COM1', 'LPT9', 'a:b/c\\d?*', '../test', ''])
def test_portable_filenames(name):
    filename = project_filename(name)
    assert filename.endswith('.s7sim.json')
    assert not any(c in filename for c in '<>:"/\\|?*')
