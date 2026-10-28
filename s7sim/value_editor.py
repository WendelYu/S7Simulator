"""Type-aware editor shared by the inspector and variable form."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QLineEdit
from .inputs import ChoiceBox


class BoolCombo(ChoiceBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(['false', 'true'])
        self.setAccessibleName('BOOL 值选择')

class ValueEditor(QStackedWidget):
    returnPressed = Signal()

    def __init__(self, text=''):
        super().__init__()
        self.line = QLineEdit(text)
        self.line.setObjectName('valueInput')
        self.boolean = BoolCombo()
        self.addWidget(self.line)
        self.addWidget(self.boolean)
        self.line.returnPressed.connect(self.returnPressed)

    def configure(self, dtype, count=1):
        old = self.text()
        self.setCurrentIndex(1 if dtype == 'BOOL' and count == 1 else 0)
        self.setText(old)
        self.setToolTip('选择 true 或 false，再点击写入' if self.currentIndex() else '数组使用 JSON，例如 [true, false]' if count > 1 else '')

    def text(self):
        return self.boolean.currentText() if self.currentIndex() else self.line.text()

    def setText(self, text):
        self.line.setText(str(text))
        self.boolean.setCurrentText('true' if str(text).lower() in {'true', '1'} else 'false')

    def clear(self):
        self.setText('')

    def setPlaceholderText(self, text):
        self.line.setPlaceholderText(text)
