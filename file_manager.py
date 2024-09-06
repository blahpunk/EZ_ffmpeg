import os
import threading
import shutil
from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QObject
import mimetypes
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
        self.estimate_thread = None
        self.file_loader = FileLoader(main_window)
        self.file_loader.file_loaded.connect(self.add_file_to_table)
        self.video_processor = VideoProcessor(main_window)
        self.video_processor.length_detected.connect(self.update_length)
        self.video_processor.mb_per_min_detected.connect(self.update_mb_per_min)
        self.video_processor.status_updated.connect(self.update_status)

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self.main_window, "Select Folder")
        if folder_path:
            self.main_window.current_folder = os.path.normpath(folder_path).replace('\\', '/')
            self.main_window.folder_path_label.setText(f"Folder: {self.main_window.current_folder}")
            self.main_window.file_table.setRowCount(0)
            self.main_window.files_list = []
            self.processed_files.clear()
            print(f"Selected folder: {folder_path}")
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
        
        # When the queue is finished, reset the Start/Stop button
        self.main_window.reset_start_button()

    def stop_processing(self):
        self.stop_requested = True
        print("Stop processing requested")

    def update_length(self, row, length):
        print(f"Updating length for row {row}: {length}")
        self.main_window.file_table.setItem(row, 4, QTableWidgetItem(length))
        self.main_window.file_table.viewport().update()  # Force table update to refresh UI

    def update_mb_per_min(self, row, mb_per_min):
        print(f"Updating MB/min for row {row}: {mb_per_min}")
        self.main_window.file_table.setItem(row, 3, NumericTableWidgetItem(mb_per_min))
        self.main_window.file_table.viewport().update()  # Force table update to refresh UI

    def update_status(self, row, status):
        try:
            print(f"Updating status for row {row}: {status}")
            self.main_window.file_table.setItem(row, 1, QTableWidgetItem(status))
            self.main_window.file_table.viewport().update()  # Force table update to refresh UI
        except Exception as e:
            print(f"Error updating status for row {row}: {e}")

    def estimate_mb_min(self):
        """
        Start the estimation of MB/min for each video file in the queue without processing the file.
        """
        if not self.estimate_thread or not self.estimate_thread.is_alive():
            self.stop_requested = False
            print("Starting estimation thread")
            self.estimate_thread = threading.Thread(target=self._estimate_mb_min)
            self.estimate_thread.start()

    def _estimate_mb_min(self):
        """
        Perform the actual estimation process in a separate thread.
        """
        for row, (file_path, size) in enumerate(self.main_window.files_list):
            if self.stop_requested:
                print("Estimation canceled")
                break
            print(f"Estimating MB/min for file: {file_path}")
            length_seconds = self.video_processor.get_video_length(file_path)
            if length_seconds is not None:
                length_formatted = self.video_processor.format_length(length_seconds)
                minutes = length_seconds / 60
                mb_per_min = size / (minutes if minutes else 1)

                # Update the table with estimated values
                self.update_length(row, length_formatted)
                self.update_mb_per_min(row, mb_per_min)
                self.update_status(row, "Estimated")
            else:
                self.update_status(row, "Error estimating")
            QApplication.processEvents()

        # When estimation is done, reset the Estimate/Cancel button
        self.main_window.reset_estimate_button()

    def stop_estimation(self):
        """
        Stop the estimation process if it's running.
        """
        self.stop_requested = True
        print("Stop estimation requested")
