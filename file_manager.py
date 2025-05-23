import os
import threading
from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QObject
import mimetypes
import configparser
from table_widgets import NumericTableWidgetItem
from video_processing import VideoProcessor

class FileLoader(QObject):
    file_loaded = pyqtSignal(str, float)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def list_files(self, folder_path):
        print(f"Listing files in folder: {folder_path}")
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type and mime_type.startswith('video'):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    self.main_window.files_list.append((file_path, size_mb))
                    self.file_loaded.emit(file, size_mb)
                    print(f"File loaded: {file_path}, size: {size_mb} MB")
                    QApplication.processEvents()

class FileManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.stop_requested = False
        self.processed_files = set()
        self.processing_thread = None
        self.calculate_thread = None
        self.file_loader = FileLoader(main_window)
        self.file_loader.file_loaded.connect(self.add_file_to_table)
        self.video_processor = VideoProcessor(main_window)
        self.video_processor.length_detected.connect(self.update_length)
        self.video_processor.mb_per_min_detected.connect(self.update_mb_per_min)
        self.video_processor.status_updated.connect(self.update_status)

    def browse_folder(self):
        default_path = ''
        config_path = 'settings.ini'
        if os.path.exists(config_path):
            config = configparser.ConfigParser()
            config.read(config_path)
            default_path = config.get('Settings', 'last_folder', fallback='')

        folder_path = QFileDialog.getExistingDirectory(self.main_window, "Select Folder", default_path)
        if folder_path:
            self.main_window.current_folder = os.path.normpath(folder_path).replace('\\', '/')
            self.main_window.folder_path_label.setText(f"Folder: {self.main_window.current_folder}")
            self.main_window.file_table.setRowCount(0)
            self.main_window.files_list = []
            self.processed_files.clear()
            print(f"Selected folder: {folder_path}")

            config = configparser.ConfigParser()
            config.read(config_path)
            if 'Settings' not in config:
                config['Settings'] = {}
            config['Settings']['last_folder'] = self.main_window.current_folder
            with open(config_path, 'w') as configfile:
                config.write(configfile)

            threading.Thread(target=self.file_loader.list_files, args=(self.main_window.current_folder,)).start()


    def add_file_to_table(self, filename, size):
        print(f"Adding file to table: {filename}, size: {size} MB")
        row = self.main_window.file_table.rowCount()
        self.main_window.file_table.insertRow(row)
        self.main_window.file_table.setItem(row, 0, QTableWidgetItem(filename))
        self.main_window.file_table.setItem(row, 1, QTableWidgetItem("Queued"))
        self.main_window.file_table.setItem(row, 2, NumericTableWidgetItem(size))
        for i in range(3, 7):
            self.main_window.file_table.setItem(row, i, QTableWidgetItem(""))
        self.main_window.file_table.sortItems(2, Qt.DescendingOrder)

    def process_files(self):
        if not self.processing_thread or not self.processing_thread.is_alive():
            self.stop_requested = False
            print("Starting file processing thread")
            self.processing_thread = threading.Thread(target=self._process_files)
            self.processing_thread.start()

    def _process_files(self):
        sorted_files = sorted(self.main_window.files_list, key=lambda x: x[1], reverse=True)
        for row, (file_path, size) in enumerate(sorted_files):
            if self.stop_requested:
                print("Stop requested, terminating file processing")
                break
            if file_path in self.processed_files:
                continue
            print(f"Processing file: {file_path}, size: {size} MB")
            self.processed_files.add(file_path)
            self.video_processor.process_video(row, file_path, size)
        self.main_window.reset_start_button()

    def stop_processing(self):
        self.stop_requested = True
        print("Stop processing requested")

    def update_length(self, row, length):
        print(f"Updating length for row {row}: {length}")
        self.main_window.file_table.setItem(row, 4, QTableWidgetItem(length))
        self.main_window.file_table.viewport().update()

    def update_mb_per_min(self, row, mb_per_min, is_calculation=False):
        print(f"Updating MB/min for row {row}: {mb_per_min}")
        column = 3 if is_calculation else 6
        self.main_window.file_table.setItem(row, column, NumericTableWidgetItem(mb_per_min))
        self.main_window.file_table.viewport().update()

    def update_status(self, row, status):
        try:
            print(f"Updating status for row {row}: {status}")
            self.main_window.file_table.setItem(row, 1, QTableWidgetItem(status))
            self.main_window.file_table.viewport().update()
        except Exception as e:
            print(f"Error updating status for row {row}: {e}")

    def calculate_mb_min(self):
        if not self.calculate_thread or not self.calculate_thread.is_alive():
            self.stop_requested = False
            print("Starting calculation thread")
            self.calculate_thread = threading.Thread(target=self._calculate_mb_min)
            self.calculate_thread.start()

    def _calculate_mb_min(self):
        sorted_files = sorted(self.main_window.files_list, key=lambda x: x[1], reverse=True)
        for row, (file_path, size) in enumerate(sorted_files):
            if self.stop_requested:
                print("Calculation canceled")
                break
            print(f"Calculating MB/min for file: {file_path}, Original size: {size} MB")
            length_seconds = self.video_processor.get_video_length(file_path)
            if length_seconds is not None:
                print(f"Video length: {length_seconds} seconds for file {file_path}")
                length_formatted = self.video_processor.format_length(length_seconds)
                mb_per_min = self.video_processor.calculate_mb_per_min(size, length_seconds)
                print(f"Calculated MB/min: {mb_per_min}")
                self.update_length(row, length_formatted)
                self.update_mb_per_min(row, mb_per_min, is_calculation=True)
                self.update_status(row, "Calculated")
            else:
                self.update_status(row, "Error calculating")
            QApplication.processEvents()
        self.main_window.reset_calculate_button()

    def stop_estimation(self):
        self.stop_requested = True
        print("Stop calculation requested")
