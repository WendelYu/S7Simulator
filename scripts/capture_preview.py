"""Generate the documentation screenshot using two real loopback S7 clients."""
import os
import socket
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import snap7
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from s7sim.models import demo_project
from s7sim.widgets import STYLE
from s7sim.window import MainWindow

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
project = demo_project()
project.plcs[0].port = port
app = QApplication([])
app.setStyle("Fusion")
app.setFont(QFont("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei", 10))
app.setStyleSheet(STYLE)
window = MainWindow(project)
window.resize(1560, 1120)
window.show()
window.engine.runtime(project.plcs[0]).start()
window.update_tree_status()
window.data_table.setCurrentCell(2, 0)
clients = [snap7.Client() for _ in range(2)]
for client in clients:
    client.connect("127.0.0.1", 0, 1, tcp_port=port)
poll = QTimer()
poll.timeout.connect(lambda: [client.db_read(1, 0, 16) for client in clients])
poll.start(100)


def capture():
    poll.stop()
    folder = ROOT / "docs"
    folder.mkdir(exist_ok=True)
    window.grab().save(str(folder / "workbench.png"))
    window.tabs.setCurrentIndex(1)
    window.refresh()
    window.grab().save(str(folder / "connections.png"))
    for client in clients:
        client.disconnect()
        client.destroy()
    window.dirty = False
    window.close()


QTimer.singleShot(3500, capture)
raise SystemExit(app.exec())
