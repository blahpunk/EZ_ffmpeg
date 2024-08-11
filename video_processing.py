import subprocess
import os
import shlex
import shutil
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, QObject
from table_widgets import NumericTableWidgetItem

class VideoProcessor(QObject):
    length_detected = pyqtSignal(int, str)
    mb_per_min_detected = pyqtSignal(int, float)
    status_updated = pyqtSignal(int, str)
    console_output = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.console_output.connect(self.main_window.update_console)

    def get_video_length(self, file_path):
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {shlex.quote(file_path)}'
        try:
            result = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                self._log_error("Error getting video length", result.stderr)
                return None
        except Exception as e:
            self._log_error("Exception getting video length", str(e))
            return None

    def format_length(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def process_video(self, row, file_path, size):
        try:
            length_seconds = self.get_video_length(file_path)
            if length_seconds:
                length_formatted = self.format_length(length_seconds)
                self.length_detected.emit(row, length_formatted)
                mb_per_min_before = size / (length_seconds / 60)
                self.mb_per_min_detected.emit(row, mb_per_min_before)

                output_file = self._create_output_filename(file_path)
                cmd = self._build_ffmpeg_command(file_path, output_file)
                process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                output_size_mb, mb_per_min_after = self._monitor_process(process, row, file_path, size)

                if process.returncode == 0:
                    self._finalize_video_processing(row, file_path, output_file, output_size_mb, mb_per_min_after)
                else:
                    self._log_error("Error processing file", process.stderr.read())
            else:
                self._handle_length_detection_failure(row)
        except Exception as e:
            self.status_updated.emit(row, f"Exception: {e}")
            self._log_error("Exception occurred during processing", str(e))

    def _create_output_filename(self, file_path):
        base, ext = os.path.splitext(file_path)
        return f"{base}_stereonorm{ext}"

    def _build_ffmpeg_command(self, file_path, output_file):
        return (
            f'ffmpeg -i {shlex.quote(file_path)} -filter_complex "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=summary[out]" '
            f'-map 0:v -map "[out]" -map 0:s? -c:v copy -c:a libmp3lame -b:a 192k -c:s copy {shlex.quote(output_file)}'
        )

    def _monitor_process(self, process, row, file_path, size):
        output_size_mb, mb_per_min_after = None, None
        while True:
            line = process.stdout.readline()
            if line == "" and process.poll() is not None:
                break
            if line:
                self.console_output.emit(line.strip())
            QApplication.processEvents()

        if process.returncode == 0:
            output_size_mb = os.path.getsize(self._create_output_filename(file_path)) / (1024 * 1024)
            length_seconds_after = self.get_video_length(self._create_output_filename(file_path))
            if length_seconds_after:
                mb_per_min_after = output_size_mb / (length_seconds_after / 60)

        return output_size_mb, mb_per_min_after

    def _finalize_video_processing(self, row, file_path, output_file, output_size_mb, mb_per_min_after):
        self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(output_size_mb))
        self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_after))

        if self.main_window.replace_checkbox.isChecked():
            self.status_updated.emit(row, "Replacing")
            self.replace_file(file_path, output_file)
        self.status_updated.emit(row, "Completed")

    def _handle_length_detection_failure(self, row):
        self.length_detected.emit(row, "Error")
        self.mb_per_min_detected.emit(row, 0.0)
        self.status_updated.emit(row, "Error")

    def replace_file(self, original_path, new_path):
        try:
            if not os.access(original_path, os.W_OK):
                os.chmod(original_path, 0o666)
            shutil.move(new_path, original_path)
        except Exception as e:
            self._log_error(f"Error replacing file {original_path}", str(e))

    def _log_error(self, context, message):
        full_message = f"{context}: {message}"
        print(full_message)
        self.console_output.emit(full_message)
