# P:\_Functional Tools\EZ_ffmpeg\0.4\table_widgets.py

from PyQt5.QtWidgets import QTableWidgetItem

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, value, display_text=None, empty_sort_value=float("-inf")):
        if value is None:
            super().__init__("" if display_text is None else display_text)
            self.value = empty_sort_value
            self.has_numeric_value = False
        else:
            super().__init__(f"{value:.2f}" if display_text is None else display_text)
            self.value = value
            self.has_numeric_value = True

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)
