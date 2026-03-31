import os
import threading
import mimetypes
import configparser
from datetime import datetime, timedelta

from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QApplication
from PyQt5.QtCore import pyqtSignal, QObject, Qt

from table_columns import (
    COLUMN_AUDIO,
    COLUMN_AVG_SPEED,
    COLUMN_CODEC,
    COLUMN_ELAPSED,
    COLUMN_ENCODER,
    COLUMN_ETA,
    COLUMN_FILENAME,
    COLUMN_LENGTH,
    COLUMN_MB_AFTER,
    COLUMN_MB_BEFORE,
    COLUMN_MB_PER_MIN_AFTER,
    COLUMN_MB_PER_MIN_BEFORE,
    COLUMN_RESOLUTION,
    COLUMN_STATUS,
)
from table_widgets import NumericTableWidgetItem
from video_processing import VideoProcessor


class FileLoader(QObject):
    file_loaded = pyqtSignal(str, float)
    loading_finished = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def list_files(self, folder_path):
        print(f"Listing files in folder: {folder_path}")
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type and mime_type.startswith('video'):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    self.file_loaded.emit(file_path, size_mb)
                    print(f"File loaded: {file_path}, size: {size_mb} MB")
                    QApplication.processEvents()
        self.loading_finished.emit()


class FileManager(QObject):
    queue_summary_updated = pyqtSignal(str)
    queue_stats_updated = pyqtSignal(str)
    processing_complete = pyqtSignal()
    analysis_complete = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.stop_requested = False
        self.processing_thread = None
        self.calculate_thread = None
        self.current_processing_row = None
        self.records_by_row = {}
        self.records_by_path = {}
        self.file_loader = FileLoader(main_window)
        self.file_loader.file_loaded.connect(self.add_file_to_table)
        self.file_loader.loading_finished.connect(self.sort_table_by_size)
        self.video_processor = VideoProcessor(main_window)
        self.video_processor.analysis_updated.connect(self.update_analysis)
        self.video_processor.output_updated.connect(self.update_output)
        self.video_processor.status_updated.connect(self.update_status)
        self.video_processor.runtime_updated.connect(self.update_runtime)
        self.video_processor.encoder_updated.connect(self.update_encoder)

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
            self.records_by_row = {}
            self.records_by_path = {}
            self.current_processing_row = None
            self.stop_requested = False
            self.video_processor.stop_requested = False
            self.queue_summary_updated.emit("Current file ETA: -- | Queue remaining: -- | Finish: --")
            self.queue_stats_updated.emit("Queued: 0 | Processing: 0 | Completed: 0 | Skipped: 0 | Failed: 0 | Saved: 0.00 MB")
            print(f"Selected folder: {folder_path}")

            config = configparser.ConfigParser()
            config.read(config_path)
            if 'Settings' not in config:
                config['Settings'] = {}
            config['Settings']['last_folder'] = self.main_window.current_folder
            with open(config_path, 'w') as configfile:
                config.write(configfile)

            threading.Thread(target=self.file_loader.list_files, args=(self.main_window.current_folder,), daemon=True).start()

    def add_file_to_table(self, file_path, size):
        print(f"Adding file to table: {file_path}, size: {size} MB")
        row = self.main_window.file_table.rowCount()
        self.main_window.file_table.insertRow(row)

        filename_item = QTableWidgetItem(os.path.basename(file_path))
        filename_item.setToolTip(file_path)
        self.main_window.file_table.setItem(row, COLUMN_FILENAME, filename_item)
        self.main_window.file_table.setItem(row, COLUMN_STATUS, QTableWidgetItem("Queued"))
        self.main_window.file_table.setItem(row, COLUMN_ENCODER, QTableWidgetItem(self.video_processor.get_encoder_label(self.main_window.get_selected_encoder_mode())))
        self.main_window.file_table.setItem(row, COLUMN_MB_BEFORE, NumericTableWidgetItem(size))

        for column in (
            COLUMN_CODEC,
            COLUMN_RESOLUTION,
            COLUMN_AUDIO,
            COLUMN_MB_PER_MIN_BEFORE,
            COLUMN_LENGTH,
            COLUMN_ETA,
            COLUMN_ELAPSED,
            COLUMN_AVG_SPEED,
            COLUMN_MB_AFTER,
            COLUMN_MB_PER_MIN_AFTER,
        ):
            self.main_window.file_table.setItem(row, column, QTableWidgetItem(""))

        record = {
            'row': row,
            'file_path': file_path,
            'filename': os.path.basename(file_path),
            'size_mb': size,
            'status': 'Queued',
            'source_info': None,
            'resolved_encoder': self.video_processor.resolve_encoder_mode(self.main_window.get_selected_encoder_mode()),
            'estimated_seconds': None,
            'eta_seconds': None,
            'eta_display': '--',
            'elapsed_seconds': 0.0,
            'elapsed_display': '',
            'avg_speed_multiplier': 0.0,
            'avg_speed_display': '',
            'output_size_mb': None,
        }
        self.main_window.files_list.append(record)
        self.records_by_row[row] = record
        self.records_by_path[file_path] = record
        self.refresh_estimates_for_selected_encoder()

    def process_files(self):
        if not self.processing_thread or not self.processing_thread.is_alive():
            self.sort_table_by_size()
            self.stop_requested = False
            self.video_processor.stop_requested = False
            print("Starting file processing thread")
            self.processing_thread = threading.Thread(target=self._process_files, daemon=True)
            self.processing_thread.start()

    def _process_files(self):
        sorted_files = sorted(self.main_window.files_list, key=lambda record: record['row'])
        try:
            for record in sorted_files:
                if self.stop_requested:
                    print("Stop requested, terminating file processing")
                    break
                if self._is_terminal_status(record['status']):
                    continue
                self.current_processing_row = record['row']
                print(f"Processing file: {record['file_path']}, size: {record['size_mb']} MB")
                self.video_processor.process_video(record)
        finally:
            self.current_processing_row = None
            self.refresh_queue_overview()
            self.processing_complete.emit()

    def stop_processing(self):
        self.request_stop_processing(finish_current=False)

    def request_stop_processing(self, finish_current=True):
        self.stop_requested = True
        self.video_processor.request_stop(immediate=not finish_current)
        if finish_current:
            print("Stop requested after current file")
        else:
            print("Immediate stop requested")

    def is_processing_active(self):
        return bool(self.processing_thread and self.processing_thread.is_alive())

    def is_busy(self):
        return self.is_processing_active() or bool(self.calculate_thread and self.calculate_thread.is_alive())

    def prepare_for_exit(self):
        self.stop_requested = True
        self.video_processor.request_stop(immediate=True)
        self.video_processor.abort_active_process()
        self.video_processor.cleanup_stale_cache()

    def update_analysis(self, row, analysis):
        record = self.records_by_row.get(row)
        if not record:
            return

        print(f"Updating analysis for row {row}: {analysis}")
        record['source_info'] = analysis
        record['resolved_encoder'] = analysis.get('resolved_encoder')
        record['estimated_seconds'] = analysis.get('estimated_seconds')

        self._set_text(row, COLUMN_ENCODER, analysis.get('encoder_label', ''))
        self._set_text(row, COLUMN_CODEC, analysis.get('video_codec_label', ''))
        self._set_text(row, COLUMN_RESOLUTION, analysis.get('resolution_label', ''))
        self._set_text(row, COLUMN_AUDIO, analysis.get('audio_label', ''))
        self._set_text(row, COLUMN_LENGTH, analysis.get('length_formatted', ''))
        self._set_numeric(row, COLUMN_MB_PER_MIN_BEFORE, analysis.get('mb_per_min_before'))

        if not self._is_active_processing_status(record['status']):
            self._set_text(row, COLUMN_ETA, analysis.get('estimated_display', '--'))

        self.main_window.file_table.viewport().update()
        self.refresh_queue_overview()

    def update_output(self, row, output):
        record = self.records_by_row.get(row)
        if not record:
            return

        record['output_size_mb'] = output.get('output_size_mb')
        self._set_numeric(row, COLUMN_MB_AFTER, output.get('output_size_mb'))
        self._set_numeric(row, COLUMN_MB_PER_MIN_AFTER, output.get('mb_per_min_after'))
        self.main_window.file_table.viewport().update()
        self.refresh_queue_overview()

    def update_runtime(self, row, runtime):
        record = self.records_by_row.get(row)
        if not record:
            return

        record['eta_seconds'] = runtime.get('eta_seconds')
        record['eta_display'] = runtime.get('eta_display', '--')
        record['elapsed_seconds'] = runtime.get('elapsed_seconds', 0.0)
        record['elapsed_display'] = runtime.get('elapsed_display', '')
        record['avg_speed_multiplier'] = runtime.get('avg_speed_multiplier', 0.0)
        record['avg_speed_display'] = runtime.get('avg_speed_display', '')

        self._set_text(row, COLUMN_ETA, record['eta_display'])
        self._set_text(row, COLUMN_ELAPSED, record['elapsed_display'])
        self._set_text(row, COLUMN_AVG_SPEED, record['avg_speed_display'])
        self.main_window.file_table.viewport().update()
        self.refresh_queue_overview()

    def update_encoder(self, row, encoder_label):
        self._set_text(row, COLUMN_ENCODER, encoder_label)
        self.refresh_queue_overview()

    def update_status(self, row, status):
        record = self.records_by_row.get(row)
        if record:
            record['status'] = status

        try:
            print(f"Updating status for row {row}: {status}")
            self._set_text(row, COLUMN_STATUS, status)
            self.main_window.file_table.viewport().update()
            self.refresh_queue_overview()
        except Exception as exc:
            print(f"Error updating status for row {row}: {exc}")

    def calculate_mb_min(self):
        if not self.calculate_thread or not self.calculate_thread.is_alive():
            self.stop_requested = False
            self.video_processor.stop_requested = False
            print("Starting analysis thread")
            self.calculate_thread = threading.Thread(target=self._calculate_mb_min, daemon=True)
            self.calculate_thread.start()

    def _calculate_mb_min(self):
        sorted_files = sorted(self.main_window.files_list, key=lambda record: record['size_mb'], reverse=True)
        try:
            for record in sorted_files:
                if self.stop_requested:
                    print("Analysis canceled")
                    break
                row = record['row']
                print(f"Analyzing file: {record['file_path']}, original size: {record['size_mb']} MB")
                analysis = self.video_processor.analyze_video(record)
                if analysis:
                    self.video_processor.analysis_updated.emit(row, analysis)
                    self.video_processor.status_updated.emit(row, "Analyzed")
                else:
                    self.video_processor.status_updated.emit(row, "Error analyzing")
                QApplication.processEvents()
        finally:
            self.analysis_complete.emit()

    def stop_estimation(self):
        self.stop_requested = True
        self.video_processor.stop_requested = True
        print("Stop analysis requested")

    def refresh_estimates_for_selected_encoder(self):
        selected_encoder = self.main_window.get_selected_encoder_mode()
        for record in self.main_window.files_list:
            if not record.get('source_info'):
                self._set_text(
                    record['row'],
                    COLUMN_ENCODER,
                    self.video_processor.get_encoder_label(selected_encoder),
                )
                continue

            if self._is_active_processing_status(record['status']) or self._is_terminal_status(record['status']):
                continue

            resolved_encoder = self.video_processor.resolve_encoder_mode(selected_encoder)
            estimated_seconds = self.video_processor.estimate_encode_seconds(record['source_info'], resolved_encoder)
            record['resolved_encoder'] = resolved_encoder
            record['estimated_seconds'] = estimated_seconds
            self._set_text(record['row'], COLUMN_ENCODER, self.video_processor.get_encoder_label(resolved_encoder))
            self._set_text(record['row'], COLUMN_ETA, self.video_processor.format_seconds(estimated_seconds))

        self.refresh_queue_overview()

    def sort_table_by_size(self):
        if (self.processing_thread and self.processing_thread.is_alive()) or (
            self.calculate_thread and self.calculate_thread.is_alive()
        ):
            return

        if self.main_window.file_table.rowCount() <= 1:
            return

        self.main_window.file_table.sortItems(COLUMN_MB_BEFORE, Qt.DescendingOrder)
        self.records_by_row = {}

        for row in range(self.main_window.file_table.rowCount()):
            filename_item = self.main_window.file_table.item(row, COLUMN_FILENAME)
            if filename_item is None:
                continue

            file_path = filename_item.toolTip()
            record = self.records_by_path.get(file_path)
            if not record:
                continue

            record['row'] = row
            self.records_by_row[row] = record

        self.main_window.file_table.viewport().update()

    def refresh_queue_overview(self):
        total_remaining_seconds = 0.0
        current_eta = '--'
        completed = 0
        skipped = 0
        failed = 0
        processing = 0
        queued = 0
        saved_mb = 0.0

        for record in self.main_window.files_list:
            status = record.get('status', 'Queued')

            if status == "Completed":
                completed += 1
            elif status == "Skipped":
                skipped += 1
            elif status.startswith("Error") or status.startswith("Exception"):
                failed += 1
            elif self._is_active_processing_status(status):
                processing += 1
            else:
                queued += 1

            if record.get('output_size_mb') is not None:
                saved_mb += max(record['size_mb'] - record['output_size_mb'], 0.0)

            if status == "Processing":
                if record.get('eta_seconds') is not None:
                    total_remaining_seconds += record['eta_seconds']
                    current_eta = record.get('eta_display', '--')
                elif record.get('estimated_seconds'):
                    total_remaining_seconds += record['estimated_seconds']
                    current_eta = self.video_processor.format_seconds(record['estimated_seconds'])
            elif not self._is_terminal_status(status):
                estimated_seconds = self._get_record_estimate(record)
                if estimated_seconds:
                    total_remaining_seconds += estimated_seconds

        finish_text = '--'
        if total_remaining_seconds > 0:
            finish_at = datetime.now() + timedelta(seconds=total_remaining_seconds)
            finish_text = finish_at.strftime("%I:%M %p").lstrip('0')

        summary = (
            f"Current file ETA: {current_eta} | "
            f"Queue remaining: {self.video_processor.format_seconds(total_remaining_seconds)} | "
            f"Finish: {finish_text}"
        )
        stats = (
            f"Queued: {queued} | Processing: {processing} | Completed: {completed} | "
            f"Skipped: {skipped} | Failed: {failed} | Saved: {saved_mb:.2f} MB"
        )
        self.queue_summary_updated.emit(summary)
        self.queue_stats_updated.emit(stats)

    def _get_record_estimate(self, record):
        if record.get('eta_seconds') is not None and self._is_active_processing_status(record['status']):
            return record['eta_seconds']

        if record.get('source_info'):
            selected_encoder = self.main_window.get_selected_encoder_mode()
            resolved_encoder = self.video_processor.resolve_encoder_mode(selected_encoder)
            estimate = self.video_processor.estimate_encode_seconds(record['source_info'], resolved_encoder)
            record['resolved_encoder'] = resolved_encoder
            record['estimated_seconds'] = estimate
            return estimate

        return record.get('estimated_seconds')

    def _set_text(self, row, column, text):
        item = self.main_window.file_table.item(row, column)
        if item is None:
            item = QTableWidgetItem("")
            self.main_window.file_table.setItem(row, column, item)
        item.setText(text or "")

    def _set_numeric(self, row, column, value):
        if value is None:
            self._set_text(row, column, "")
            return
        self.main_window.file_table.setItem(row, column, NumericTableWidgetItem(value))

    def _is_active_processing_status(self, status):
        return status in {
            "Probing",
            "Checking thresholds",
            "Copying to cache",
            "Launching encoder",
            "Processing",
            "Finalizing",
            "Replacing",
            "Moving output",
        }

    def _is_terminal_status(self, status):
        return status in {"Completed", "Skipped"}


__all__ = ["FileManager", "NumericTableWidgetItem"]
