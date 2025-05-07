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

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager(self)
        self.files_list = []
        self.current_speed = ''
        self.initUI()
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

        self.folder_path_label = QLabel("Folder: ")
        self.folder_path_label.setObjectName("folderPathLabel")
        layout.addWidget(self.folder_path_label)

        top_row_layout = QHBoxLayout()

        options_frame = QFrame(self)
        options_frame.setObjectName("optionsFrame")
        options_frame.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px; padding: 10px;")
        grid_layout = QGridLayout(options_frame)

        self.normalize_checkbox = QCheckBox("Normalize")
        self.normalize_checkbox.setChecked(True)
        grid_layout.addWidget(self.normalize_checkbox, 0, 0)

        self.stereo_checkbox = QCheckBox("Stereo")
        self.stereo_checkbox.setChecked(True)
        grid_layout.addWidget(self.stereo_checkbox, 0, 1)

        self.replace_checkbox = QCheckBox("Replace")
        self.replace_checkbox.setChecked(True)
        grid_layout.addWidget(self.replace_checkbox, 1, 0)

        self.convert_checkbox = QCheckBox("Convert")
        self.convert_checkbox.setChecked(True)
        grid_layout.addWidget(self.convert_checkbox, 1, 1)

        top_row_layout.addWidget(options_frame)

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

        stacked_button_layout = QVBoxLayout()
        self.movies_button = QPushButton("Movies")
        self.television_button = QPushButton("Television")
        self.animation_button = QPushButton("Animation")
        button_height = 100 // 3
        self.movies_button.setFixedSize(100, button_height)
        self.television_button.setFixedSize(100, button_height)
        self.animation_button.setFixedSize(100, button_height)
        stacked_button_layout.addWidget(self.movies_button)
        stacked_button_layout.addWidget(self.television_button)
        stacked_button_layout.addWidget(self.animation_button)
        top_row_layout.addLayout(stacked_button_layout)

        self.movies_button.clicked.connect(self.set_movies)
        self.television_button.clicked.connect(self.set_television)
        self.animation_button.clicked.connect(self.set_animation)

        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedSize(100, 100)
        self.browse_button.clicked.connect(self.file_manager.browse_folder)
        top_row_layout.addWidget(self.browse_button)

        self.start_button = QPushButton("Start")
        self.start_button.setFixedSize(100, 100)
        self.start_button.clicked.connect(self.on_start_pressed)
        top_row_layout.addWidget(self.start_button)

        self.calculate_button = QPushButton("Calculate")
        self.calculate_button.setFixedSize(100, 100)
        self.calculate_button.clicked.connect(self.on_calculate_pressed)
        top_row_layout.addWidget(self.calculate_button)

        layout.addLayout(top_row_layout)

        self.file_table = QTableWidget(0, 7)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Status", "MB before", "MB/min before", "Length", "MB after", "MB/min after"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 6):
            self.file_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setFont(QFont("Arial", 10, QFont.Bold))
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSortingEnabled(False)
        layout.addWidget(self.file_table)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
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
            self.progress_bar.setValue(0)
            self.current_speed = ''
            self.progress_bar.setFormat("%p%")
            self.file_manager.process_files()
        else:
            self.start_button.setText("Start")
            self.file_manager.stop_processing()
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")

    def on_calculate_pressed(self):
        if self.calculate_button.text() == "Calculate":
            self.calculate_button.setText("Cancel")
            self.file_manager.calculate_mb_min()
        else:
            self.calculate_button.setText("Calculate")
            self.file_manager.stop_estimation()

    def reset_start_button(self):
        self.start_button.setText("Start")

    def reset_calculate_button(self):
        self.calculate_button.setText("Calculate")

    def update_progress(self, progress):
        speed = self.current_speed if self.current_speed else ''
        self.progress_bar.setFormat(f"{progress:.1f}% {speed}")
        self.progress_bar.setValue(int(progress))

    def update_speed(self, speed):
        self.current_speed = speed

    def apply_background(self):
        background_path = resource_path('background.png')
        pixmap = QPixmap(background_path)
        if not pixmap.isNull():
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pixmap))
            self.setPalette(palette)

    def apply_stylesheet(self):
        style_path = resource_path('style.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())

    def save_settings(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'normalize': self.normalize_checkbox.isChecked(),
            'stereo': self.stereo_checkbox.isChecked(),
            'replace': self.replace_checkbox.isChecked(),
            'convert': self.convert_checkbox.isChecked(),
            'last_folder': getattr(self, 'current_folder', '')
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
            last_folder = settings.get('last_folder', '')
            if os.path.isdir(last_folder):
                self.current_folder = os.path.normpath(last_folder).replace('\\', '/')
                self.folder_path_label.setText(f"Folder: {self.current_folder}")

def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    try:
        app.aboutToQuit.connect(ex.save_settings)
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()
