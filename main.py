# main.py

import sys
import os
import configparser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QHBoxLayout, QVBoxLayout,
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QCheckBox, QLabel, QFrame, QLineEdit, QGridLayout, QProgressBar
)
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QFont
from PyQt5.QtCore import Qt
from file_manager import FileManager, NumericTableWidgetItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager(self)
        self.files_list = []  # List to store file paths
        self.current_speed = ''  # Initialize the current speed display
        self.initUI()

        # Connect the progress_updated signal to the update_progress method
        self.file_manager.video_processor.progress_updated.connect(self.update_progress)
        self.file_manager.video_processor.speed_updated.connect(self.update_speed)

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

        # Create a horizontal layout for the top row
        top_row_layout = QHBoxLayout()

        # Create a frame for the checkboxes and sliders with a dark background
        options_frame = QFrame(self)
        options_frame.setObjectName("optionsFrame")
        options_frame.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px; padding: 10px;")
        grid_layout = QGridLayout(options_frame)

        # Add Normalize checkbox
        self.normalize_checkbox = QCheckBox("Normalize")
        self.normalize_checkbox.setChecked(True)
        grid_layout.addWidget(self.normalize_checkbox, 0, 0)

        # Add Stereo checkbox
        self.stereo_checkbox = QCheckBox("Stereo")
        self.stereo_checkbox.setChecked(True)
        grid_layout.addWidget(self.stereo_checkbox, 0, 1)

        # Add Replace checkbox
        self.replace_checkbox = QCheckBox("Replace")
        self.replace_checkbox.setChecked(True)
        grid_layout.addWidget(self.replace_checkbox, 1, 0)

        # Add Convert checkbox
        self.convert_checkbox = QCheckBox("Convert")
        self.convert_checkbox.setChecked(True)
        grid_layout.addWidget(self.convert_checkbox, 1, 1)

        # Add the options frame to the top row layout
        top_row_layout.addWidget(options_frame)

        # Add MB/min slider
        mb_min_frame = QFrame()
        mb_min_frame.setObjectName("sliderFrame")
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
        top_row_layout.addWidget(mb_min_frame)

        # Add Threshold input box
        threshold_frame = QFrame()
        threshold_frame.setObjectName("sliderFrame")
        threshold_layout = QVBoxLayout(threshold_frame)
        self.threshold_label = QLabel("Threshold")
        self.threshold_input = QLineEdit()
        self.threshold_input.setObjectName("thresholdInput")
        self.threshold_input.setText("2")
        self.threshold_input.setAlignment(Qt.AlignCenter)
        threshold_layout.addWidget(self.threshold_label, alignment=Qt.AlignCenter)
        threshold_layout.addWidget(self.threshold_input)
        top_row_layout.addWidget(threshold_frame)

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
        top_row_layout.addLayout(stacked_button_layout)

        # Connect buttons to their respective methods
        self.movies_button.clicked.connect(self.set_movies)
        self.television_button.clicked.connect(self.set_television)
        self.animation_button.clicked.connect(self.set_animation)

        # Add Browse button
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedSize(100, 100)
        self.browse_button.clicked.connect(self.file_manager.browse_folder)
        top_row_layout.addWidget(self.browse_button)

        # Add Start button
        self.start_button = QPushButton("Start")
        self.start_button.setFixedSize(100, 100)
        self.start_button.clicked.connect(self.on_start_pressed)
        top_row_layout.addWidget(self.start_button)

        # Add the top row layout to the main layout
        layout.addLayout(top_row_layout)

        # File table
        self.file_table = QTableWidget(0, 7)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Status", "MB before", "MB/min before", "Length", "MB after", "MB/min after"])

        # Set the section resize mode for the filename column
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 6):
            self.file_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.file_table.horizontalHeader().setFont(QFont("Arial", 10, QFont.Bold))
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSortingEnabled(False)  # Disable manual sorting

        layout.addWidget(self.file_table)

        # Add a progress bar at the bottom of the layout
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)  # Initialize the progress bar at 0%
        layout.addWidget(self.progress_bar)

        self.load_settings()
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
            self.progress_bar.setValue(0)  # Reset the progress bar to 0%
            self.current_speed = ''  # Reset the speed display
            self.progress_bar.setFormat("%p%")  # Reset the progress bar format
            self.file_manager.process_files()
        else:
            self.start_button.setText("Start")
            self.file_manager.stop_processing()
            self.progress_bar.setValue(0)  # Reset the progress bar to 0%
            self.progress_bar.setFormat("%p%")  # Reset the progress bar format

    def update_progress(self, progress):
        # Update progress with percentage and speed if available
        speed = self.current_speed if self.current_speed else ''
        self.progress_bar.setFormat(f"{progress:.1f}% {speed}")
        self.progress_bar.setValue(int(progress))

    def update_speed(self, speed):
        self.current_speed = speed

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

    def save_settings(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'normalize': self.normalize_checkbox.isChecked(),
            'stereo': self.stereo_checkbox.isChecked(),
            'replace': self.replace_checkbox.isChecked(),
            'convert': self.convert_checkbox.isChecked(),
        }
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)

    def load_settings(self):
        config = configparser.ConfigParser()
        if os.path.exists('settings.ini'):
            config.read('settings.ini')
            settings = config['Settings']
            self.normalize_checkbox.setChecked(settings.getboolean('normalize', True))
            self.stereo_checkbox.setChecked(settings.getboolean('stereo', True))
            self.replace_checkbox.setChecked(settings.getboolean('replace', True))
            self.convert_checkbox.setChecked(settings.getboolean('convert', True))

def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    try:
        app.aboutToQuit.connect(ex.save_settings)
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("Application interrupted. Cleaning up...")
        sys.exit(0)

if __name__ == '__main__':
    main()

# End of main.py
