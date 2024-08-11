# P:\_Functional Tools\EZ_ffmpeg\0.4\table_widgets.py

from PyQt5.QtWidgets import QTableWidgetItem

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, value):
        super().__init__(f"{value:.2f}")
        self.value = value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)
