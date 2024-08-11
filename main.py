import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QLabel, QSlider, QCheckBox, QPushButton, QTextEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtGui import QPixmap, QPalette, QBrush
from PyQt5.QtCore import Qt
from file_manager import FileManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager(self)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("EZ_ffmpeg")
        self.setGeometry(100, 100, 800, 600)
        self.apply_background()
        self.apply_stylesheet()

        layout = QVBoxLayout()
        central_widget = QWidget(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Folder path label
        self.folder_path_label = QLabel("Folder: ")
        layout.addWidget(self.folder_path_label)

        # Button and checkbox layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Replace checkbox
        self.replace_checkbox = QCheckBox("Replace")
        self.replace_checkbox.setChecked(True)
        button_layout.addWidget(self.replace_checkbox)

        # Monitor checkbox
        self.monitor_checkbox = QCheckBox("Monitor")
        self.monitor_checkbox.setChecked(True)
        button_layout.addWidget(self.monitor_checkbox)

        # MB/min slider
        self.mb_min_slider = QSlider(Qt.Horizontal)
        self.mb_min_slider.setRange(5, 20)
        self.mb_min_slider.setValue(12)
        self.mb_min_slider.valueChanged.connect(self.update_mb_min_label)
        button_layout.addWidget(self.mb_min_slider)

        self.mb_min_label = QLabel(f"MB/min: {self.mb_min_slider.value()}")
        button_layout.addWidget(self.mb_min_label)

        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.on_start_pressed)
        button_layout.addWidget(self.start_button)

        layout.addLayout(button_layout)

        # File table
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Size", "Status"])
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.file_table)

        # Console output
        self.console_output = QTextEdit(self)
        self.console_output.setReadOnly(True)
        self.console_output.setFixedHeight(150)
        layout.addWidget(self.console_output)

        self.show()

    def update_mb_min_label(self, value):
        self.mb_min_label.setText(f"MB/min: {value}")

    def on_start_pressed(self):
        if self.start_button.text() == "Start":
            self.start_button.setText("Stop")
            self.file_manager.process_files()
        else:
            self.start_button.setText("Start")
            self.file_manager.stop_processing()

    def apply_background(self):
        background_path = os.path.join(os.path.dirname(__file__), 'background.png')
        pixmap = QPixmap(background_path)
        if not pixmap.isNull():
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pixmap))
            self.setPalette(palette)
        else:
            print("Failed to load background image")

    def apply_stylesheet(self):
        with open('style.qss', 'r') as f:
            self.setStyleSheet(f.read())

    def update_console(self, text):
        self.console_output.append(text)

def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("Application interrupted. Cleaning up...")
        sys.exit(0)

if __name__ == '__main__':
    main()
