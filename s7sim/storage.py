"""Native user directories and portable project filenames."""
import re
from pathlib import Path
from PySide6.QtCore import QStandardPaths


def default_directory(settings):
    saved = str(settings.value('files/default_directory', '') or '').strip()
    if saved:
        return Path(saved).expanduser()
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return (Path(documents) if documents else Path.home()) / 'S7 Studio'


def project_filename(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip().rstrip('. ') or 'Workspace'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        name = '_' + name
    return name[:100] + '.s7sim.json'


def suggested_path(settings, name):
    directory = default_directory(settings)
    directory.mkdir(parents=True, exist_ok=True)
    filename = project_filename(name)
    path = directory / filename
    n = 2
    while path.exists():
        path = directory / f'{filename[:-11]} ({n}).s7sim.json'
        n += 1
    return path
