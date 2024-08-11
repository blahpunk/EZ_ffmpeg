import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QHBoxLayout, QVBoxLayout,
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QCheckBox, QLabel, QFrame, QLineEdit, QTextEdit
)
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QFont
from PyQt5.QtCore import Qt
from file_manager import FileManager, NumericTableWidgetItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager(self)
        self.files_list = []  # List to store file paths
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

        # Add folder path label
        self.folder_path_label = QLabel("Folder: ")
        self.folder_path_label.setObjectName("folderPathLabel")
        layout.addWidget(self.folder_path_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Add space to push buttons to the right

        # Add Replace checkbox
        self.replace_checkbox = QCheckBox("Replace")
        self.replace_checkbox.setChecked(True)
        button_layout.addWidget(self.replace_checkbox)

        # Add Monitor checkbox
        self.monitor_checkbox = QCheckBox("Monitor")
        self.monitor_checkbox.setChecked(True)
        button_layout.addWidget(self.monitor_checkbox)

        # Add MB/min slider
        mb_min_frame = QFrame()
        mb_min_frame.setObjectName("sliderFrame")
        mb_min_frame.setFixedSize(150, 100)  # Set fixed size to match the height of the buttons
        mb_min_layout = QVBoxLayout(mb_min_frame)
        self.mb_min_label = QLabel("MB/min: 12")
        self.mb_min_slider = QSlider(Qt.Horizontal)
        self.mb_min_slider.setObjectName("horizontalSlider")
        self.mb_min_slider.setRange(2, 45)
        self.mb_min_slider.setValue(12)
        self.mb_min_slider.setTickInterval(1)
        self.mb_min_slider.setTickPosition(QSlider.TicksBelow)
        self.mb_min_slider.valueChanged.connect(self.update_mb_min_label)
        mb_min_layout.addWidget(self.mb_min_label, alignment=Qt.AlignCenter)
        mb_min_layout.addWidget(self.mb_min_slider)
        button_layout.addWidget(mb_min_frame)

        # Add Threshold input box
        threshold_frame = QFrame()
        threshold_frame.setObjectName("sliderFrame")
        threshold_frame.setFixedSize(100, 100)  # Set fixed size to match the height of the buttons
        threshold_layout = QVBoxLayout(threshold_frame)
        self.threshold_label = QLabel("Threshold")
        self.threshold_input = QLineEdit()
        self.threshold_input.setObjectName("thresholdInput")
        self.threshold_input.setText("2")
        self.threshold_input.setAlignment(Qt.AlignCenter)
        threshold_layout.addWidget(self.threshold_label, alignment=Qt.AlignCenter)
        threshold_layout.addWidget(self.threshold_input)
        button_layout.addWidget(threshold_frame)

        # Add stacked buttons
        stacked_button_layout = QVBoxLayout()
        self.movies_button = QPushButton("Movies")
        self.television_button = QPushButton("Television")
        self.animation_button = QPushButton("Animation")
        button_height = 100 // 3  # Height of each stacked button
        self.movies_button.setFixedSize(100, button_height)
        self.television_button.setFixedSize(100, button_height)
        self.animation_button.setFixedSize(100, button_height)
        stacked_button_layout.addWidget(self.movies_button)
        stacked_button_layout.addWidget(self.television_button)
        stacked_button_layout.addWidget(self.animation_button)
        button_layout.addLayout(stacked_button_layout)

        # Connect buttons to their respective methods
        self.movies_button.clicked.connect(self.set_movies)
        self.television_button.clicked.connect(self.set_television)
        self.animation_button.clicked.connect(self.set_animation)

        # Add Browse and Start buttons
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedSize(100, 100)
        self.browse_button.clicked.connect(self.file_manager.browse_folder)
        button_layout.addWidget(self.browse_button)

        self.start_button = QPushButton("Start")
        self.start_button.setFixedSize(100, 100)
        self.start_button.clicked.connect(self.on_start_pressed)
        button_layout.addWidget(self.start_button)

        layout.addLayout(button_layout)

        self.file_table = QTableWidget(0, 7)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Status", "MB before", "MB/min before", "Length", "MB after", "MB/min after"])
        
        # Set the section resize mode for the filename column
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 7):
            self.file_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.file_table.horizontalHeader().setFont(QFont("Arial", 10, QFont.Bold))
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSortingEnabled(False)  # Disable manual sorting

        layout.addWidget(self.file_table)

        # Add console output text area
        self.console_output = QTextEdit(self)
        self.console_output.setReadOnly(True)
        self.console_output.setFixedHeight(150)
        layout.addWidget(self.console_output)

        self.show()

    def update_mb_min_label(self, value):
        self.mb_min_label.setText(f"MB/min: {value}")

    def set_movies(self):
        self.mb_min_slider.setValue(10)
        self.threshold_input.setText("2")

    def set_television(self):
        self.mb_min_slider.setValue(12)
        self.threshold_input.setText("2")

    def set_animation(self):
        self.mb_min_slider.setValue(8)
        self.threshold_input.setText("1")

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
        # Perform any necessary cleanup here
        sys.exit(0)

if __name__ == '__main__':
    main()
