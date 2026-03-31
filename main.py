import sys
import os
import configparser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QHBoxLayout, QVBoxLayout,
    QWidget, QTableWidget, QHeaderView, QSlider, QCheckBox, QLabel, QFrame, QLineEdit, QGridLayout, QProgressBar,
    QComboBox, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from file_manager import FileManager
from table_columns import TABLE_HEADERS

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class MainWindow(QMainWindow):
    CACHE_FOLDER_NAME = "ez_ffmpeg_cache"
    THEMES = {
        "Light": {
            "WINDOW_BG": "#f5f1e8",
            "CARD_BG": "#fffaf0",
            "CARD_BORDER": "#d4c8b6",
            "TEXT": "#2f2a24",
            "MUTED_TEXT": "#665f55",
            "BUTTON_BG": "#d8863b",
            "BUTTON_HOVER": "#bf7230",
            "BUTTON_PRESSED": "#9c5b25",
            "BUTTON_TEXT": "#fffaf3",
            "INPUT_BG": "#fffdf8",
            "INPUT_BORDER": "#c9baa5",
            "TABLE_BG": "#fffdf9",
            "TABLE_ALT": "#f7efe1",
            "HEADER_BG": "#eadfce",
            "GRID": "#d8cab8",
            "ACCENT": "#d8863b",
            "ACCENT_SOFT": "#f5d9bc",
            "PROGRESS_BG": "#ede2d2",
            "SLIDER_GROOVE": "#d8cab8",
            "SLIDER_HANDLE": "#b66c2d",
        },
        "Dark": {
            "WINDOW_BG": "#171a1f",
            "CARD_BG": "#22262d",
            "CARD_BORDER": "#313844",
            "TEXT": "#f1f3f5",
            "MUTED_TEXT": "#b5bcc8",
            "BUTTON_BG": "#4f8fba",
            "BUTTON_HOVER": "#43789d",
            "BUTTON_PRESSED": "#37627f",
            "BUTTON_TEXT": "#f7fbff",
            "INPUT_BG": "#1d2128",
            "INPUT_BORDER": "#3a4250",
            "TABLE_BG": "#1b1f26",
            "TABLE_ALT": "#232932",
            "HEADER_BG": "#2c3440",
            "GRID": "#37404d",
            "ACCENT": "#4f8fba",
            "ACCENT_SOFT": "#2f4353",
            "PROGRESS_BG": "#232932",
            "SLIDER_GROOVE": "#37404d",
            "SLIDER_HANDLE": "#6ca8cf",
        },
    }

    def __init__(self):
        super().__init__()
        self.file_manager = FileManager(self)
        self.files_list = []
        self.current_speed = ''
        self.current_eta = ''
        self.initUI()
        self.file_manager.video_processor.progress_updated.connect(self.update_progress)
        self.file_manager.video_processor.speed_updated.connect(self.update_speed)
        self.file_manager.video_processor.current_eta_updated.connect(self.update_current_eta)
        self.file_manager.queue_summary_updated.connect(self.update_queue_summary)
        self.file_manager.queue_stats_updated.connect(self.update_queue_stats)
        self.file_manager.processing_complete.connect(self.reset_start_button)
        self.file_manager.analysis_complete.connect(self.reset_analyze_button)

    def initUI(self):
        self.setWindowTitle("EZ_ffmpeg")
        self.setGeometry(100, 100, 800, 600)
        self.apply_stylesheet("Light")

        layout = QVBoxLayout()
        central_widget = QWidget(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.folder_path_label = QLabel("Folder: ")
        self.folder_path_label.setObjectName("folderPathLabel")
        layout.addWidget(self.folder_path_label)

        temp_layout = QHBoxLayout()
        self.temp_folder_label = QLabel("")
        self.temp_folder_label.setObjectName("folderPathLabel")
        self.temp_folder_button = QPushButton("Temp Folder")
        self.temp_folder_button.clicked.connect(self.browse_temp_folder)
        temp_layout.addWidget(self.temp_folder_label)
        temp_layout.addWidget(self.temp_folder_button)
        self.theme_label = QLabel("Theme")
        self.theme_label.setObjectName("folderPathLabel")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.THEMES.keys())
        temp_layout.addWidget(self.theme_label)
        temp_layout.addWidget(self.theme_combo)
        layout.addLayout(temp_layout)

        top_row_layout = QHBoxLayout()

        options_frame = QFrame(self)
        options_frame.setObjectName("optionsFrame")
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

        encoder_frame = QFrame()
        encoder_frame.setObjectName("sliderFrame")
        encoder_layout = QVBoxLayout(encoder_frame)
        self.encoder_label = QLabel("Encoder")
        self.encoder_combo = QComboBox()
        encoder_layout.addWidget(self.encoder_label, alignment=Qt.AlignCenter)
        encoder_layout.addWidget(self.encoder_combo)
        top_row_layout.addWidget(encoder_frame)

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

        self.calculate_button = QPushButton("Analyze")
        self.calculate_button.setFixedSize(100, 100)
        self.calculate_button.clicked.connect(self.on_calculate_pressed)
        top_row_layout.addWidget(self.calculate_button)

        layout.addLayout(top_row_layout)

        self.file_table = QTableWidget(0, len(TABLE_HEADERS))
        self.file_table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.file_table.setColumnWidth(0, 420)
        for i in range(1, len(TABLE_HEADERS)):
            self.file_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setFont(QFont("Arial", 10, QFont.Bold))
        self.file_table.horizontalHeader().setStretchLastSection(False)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSortingEnabled(False)
        self.file_table.setAlternatingRowColors(True)
        layout.addWidget(self.file_table)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.queue_summary_label = QLabel("Current file ETA: -- | Queue remaining: -- | Finish: --")
        self.queue_summary_label.setWordWrap(True)
        layout.addWidget(self.queue_summary_label)

        self.queue_stats_label = QLabel("Queued: 0 | Processing: 0 | Completed: 0 | Skipped: 0 | Failed: 0 | Saved: 0.00 MB")
        self.queue_stats_label.setWordWrap(True)
        layout.addWidget(self.queue_stats_label)

        self.populate_encoder_modes()
        self.update_temp_folder_label()
        self.load_settings()
        self.encoder_combo.currentIndexChanged.connect(self.on_encoder_changed)
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
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

    def populate_encoder_modes(self):
        self.encoder_combo.blockSignals(True)
        self.encoder_combo.clear()
        for encoder_key, encoder_label in self.file_manager.video_processor.get_available_encoder_options():
            self.encoder_combo.addItem(encoder_label, encoder_key)
        self.encoder_combo.blockSignals(False)

    def get_selected_encoder_mode(self):
        return self.encoder_combo.currentData() or 'auto'

    def on_encoder_changed(self):
        self.file_manager.refresh_estimates_for_selected_encoder()

    def get_selected_theme(self):
        if hasattr(self, "theme_combo"):
            return self.theme_combo.currentText() or "Light"
        return "Light"

    def on_theme_changed(self, theme_name):
        self.apply_stylesheet(theme_name)

    def update_temp_folder_label(self):
        self.temp_folder_label.setText(f"Temp: {self.file_manager.video_processor.cache_folder}")

    def set_temp_folder(self, folder_path):
        self.file_manager.video_processor.set_cache_folder(folder_path)
        self.update_temp_folder_label()

    def browse_temp_folder(self):
        if self.file_manager.is_busy():
            QMessageBox.warning(self, "Busy", "Stop the current queue or analysis pass before changing the temp folder.")
            return

        current_temp = os.path.dirname(self.file_manager.video_processor.cache_folder)
        folder_path = QFileDialog.getExistingDirectory(self, "Select Temp Folder Root", current_temp)
        if folder_path:
            self.set_temp_folder(os.path.join(folder_path, self.CACHE_FOLDER_NAME))

    def on_start_pressed(self):
        if self.start_button.text() == "Start":
            self.start_button.setText("Stop")
            self.progress_bar.setValue(0)
            self.current_speed = ''
            self.current_eta = ''
            self.progress_bar.setFormat("%p%")
            self.file_manager.process_files()
        else:
            self.show_stop_dialog()

    def on_calculate_pressed(self):
        if self.calculate_button.text() == "Analyze":
            self.calculate_button.setText("Cancel")
            self.file_manager.calculate_mb_min()
        else:
            self.calculate_button.setText("Analyze")
            self.file_manager.stop_estimation()

    def reset_start_button(self):
        self.start_button.setText("Start")
        self.current_speed = ''
        self.current_eta = ''
        self.refresh_progress_bar_format(self.progress_bar.value())

    def reset_analyze_button(self):
        self.calculate_button.setText("Analyze")

    def update_progress(self, progress):
        self.refresh_progress_bar_format(progress)

    def update_speed(self, speed):
        self.current_speed = speed
        self.refresh_progress_bar_format(self.progress_bar.value())

    def update_current_eta(self, eta):
        self.current_eta = eta
        self.refresh_progress_bar_format(self.progress_bar.value())

    def refresh_progress_bar_format(self, progress):
        details = [f"{progress:.1f}%"]
        if self.current_speed:
            details.append(self.current_speed)
        if self.current_eta and self.current_eta != "--":
            details.append(f"ETA {self.current_eta}")
        self.progress_bar.setFormat(" | ".join(details))
        self.progress_bar.setValue(int(progress))

    def update_queue_summary(self, summary):
        self.queue_summary_label.setText(summary)

    def update_queue_stats(self, stats):
        self.queue_stats_label.setText(stats)

    def show_stop_dialog(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Stop Processing")
        dialog.setText("How do you want to stop the queue?")
        dialog.setInformativeText("You can let the current file finish, abort immediately, or keep processing.")

        finish_button = dialog.addButton("Finish Current File", QMessageBox.AcceptRole)
        abort_button = dialog.addButton("Abort Now", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(finish_button)
        dialog.exec_()

        clicked_button = dialog.clickedButton()
        if clicked_button == finish_button:
            self.file_manager.request_stop_processing(finish_current=True)
        elif clicked_button == abort_button:
            self.file_manager.request_stop_processing(finish_current=False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")
        elif clicked_button == cancel_button:
            self.start_button.setText("Stop")

    def closeEvent(self, event):
        self.file_manager.prepare_for_exit()
        self.save_settings()
        event.accept()

    def apply_stylesheet(self, theme_name=None):
        theme = self.THEMES.get(theme_name or self.get_selected_theme(), self.THEMES["Light"])
        style_path = resource_path('style.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as style_file:
                stylesheet = style_file.read()
            for token, value in theme.items():
                stylesheet = stylesheet.replace(f"__{token}__", value)
            self.setStyleSheet(stylesheet)

    def save_settings(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'normalize': self.normalize_checkbox.isChecked(),
            'stereo': self.stereo_checkbox.isChecked(),
            'replace': self.replace_checkbox.isChecked(),
            'convert': self.convert_checkbox.isChecked(),
            'encoder_mode': self.get_selected_encoder_mode(),
            'theme': self.get_selected_theme(),
            'temp_folder': self.file_manager.video_processor.cache_folder,
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
            encoder_mode = settings.get('encoder_mode', 'auto')
            combo_index = self.encoder_combo.findData(encoder_mode)
            if combo_index >= 0:
                self.encoder_combo.setCurrentIndex(combo_index)
            theme_name = settings.get('theme', 'Light')
            theme_index = self.theme_combo.findText(theme_name)
            if theme_index >= 0:
                self.theme_combo.setCurrentIndex(theme_index)
            self.apply_stylesheet(self.get_selected_theme())
            temp_folder = settings.get('temp_folder', '')
            if temp_folder and os.path.isdir(temp_folder):
                self.set_temp_folder(temp_folder)
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
