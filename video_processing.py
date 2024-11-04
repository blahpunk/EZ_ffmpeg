import subprocess
import os
import shlex
import tempfile
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, QObject
import threading
from queue import Queue, Empty
from table_widgets import NumericTableWidgetItem
import shutil
import time

class VideoProcessor(QObject):
    length_detected = pyqtSignal(int, str)
    mb_per_min_detected = pyqtSignal(int, float)
    status_updated = pyqtSignal(int, str)
    progress_updated = pyqtSignal(float)
    speed_updated = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        # Set up a cache folder named 'ez_ffmpeg' in the system's temporary directory
        self.cache_folder = os.path.join(tempfile.gettempdir(), "ez_ffmpeg")
        os.makedirs(self.cache_folder, exist_ok=True)  # Ensure cache folder exists

    def get_video_length(self, file_path):
        normalized_file_path = os.path.normpath(file_path)
        quoted_file_path = shlex.quote(normalized_file_path)
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {quoted_file_path}'
        try:
            result = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                error_message = result.stderr.strip()
                print(f"Error getting video length: {error_message}")
                return None
        except Exception as e:
            print(f"Exception getting video length: {e}")
            return None

    def format_length(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def calculate_mb_per_min(self, size_mb, length_seconds):
        minutes = length_seconds / 60
        return size_mb / (minutes if minutes else 1)

    def enqueue_output(self, out, queue):
        try:
            for line in iter(out.readline, ''):
                queue.put(line)
        except Exception as e:
            print(f"Error in enqueue_output: {e}")
        finally:
            out.close()

    def delete_cached_file(self, cached_file_path):
        """Retry deleting the cached file if access is initially denied."""
        retries = 3
        delay = 1  # seconds
        for attempt in range(retries):
            try:
                if os.path.exists(cached_file_path):
                    os.chmod(cached_file_path, 0o666)  # Set permissions if necessary
                    os.remove(cached_file_path)
                    print(f"Deleted cached file: {cached_file_path}")
                    break
            except PermissionError as e:
                print(f"Attempt {attempt + 1}: Permission denied while deleting {cached_file_path}. Retrying...")
                time.sleep(delay)  # Wait a bit before retrying
            except Exception as e:
                print(f"Error deleting cached file {cached_file_path}: {e}")
                break

    def process_video(self, row, file_path, size):
        process = None
        cached_file_path = os.path.join(self.cache_folder, os.path.basename(file_path))
        try:
            # Copy file to local cache folder in the 'ez_ffmpeg' temp directory
            if not os.path.exists(cached_file_path):
                shutil.copy2(file_path, cached_file_path)
                print(f"Copied {file_path} to cache as {cached_file_path}")

            self.status_updated.emit(row, "Detecting video length")
            length_seconds = self.get_video_length(cached_file_path)
            if length_seconds is not None:
                self.status_updated.emit(row, "Calculating MB/min")
                length_formatted = self.format_length(length_seconds)
                mb_per_min_before = self.calculate_mb_per_min(size, length_seconds)

                # Update MB/min before column immediately at the start of processing
                self.main_window.file_table.setItem(row, 3, NumericTableWidgetItem(mb_per_min_before))
                self.length_detected.emit(row, length_formatted)

                if self.main_window.convert_checkbox.isChecked():
                    mb_min_target = self.main_window.mb_min_slider.value()
                    threshold = float(self.main_window.threshold_input.text())
                    if mb_per_min_before < (mb_min_target + threshold):
                        self.status_updated.emit(row, "Skipped")
                        self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(size))
                        self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_before))
                        self.delete_cached_file(cached_file_path)
                        return

                    output_file = os.path.join(self.cache_folder, os.path.splitext(os.path.basename(file_path))[0] + '_processed' + os.path.splitext(file_path)[1])
                    target_bitrate = (mb_min_target * 1024 * 1024 * 8) / 60 * 0.9
                    audio_bitrate = 192 * 1024
                    video_bitrate = target_bitrate - audio_bitrate

                    cmd = [
                        'ffmpeg', '-i', cached_file_path,
                        '-map', '0:v', '-map', '0:a', '-map', '0:s?',
                        '-c:v', 'libx265', '-b:v', f'{int(video_bitrate / 1000)}k',
                        '-maxrate', f'{int(video_bitrate / 1000)}k',
                        '-bufsize', f'{int(video_bitrate / 500)}k',
                        '-c:a', 'libmp3lame', '-b:a', '192k',
                        '-c:s', 'copy',
                        '-y', output_file
                    ]

                    if self.main_window.normalize_checkbox.isChecked():
                        cmd.extend(['-af', 'dynaudnorm'])
                    if self.main_window.stereo_checkbox.isChecked():
                        cmd.extend(['-ac', '2'])

                    self.status_updated.emit(row, "Processing")
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                    q = Queue()
                    threading.Thread(target=self.enqueue_output, args=(process.stderr, q)).start()

                    while True:
                        try:
                            line = q.get_nowait()
                        except Empty:
                            if process and process.poll() is not None:
                                break
                        else:
                            if "time=" in line:
                                try:
                                    time_index = line.find("time=")
                                    progress_str = line[time_index:].split(' ')[0]
                                    progress_time = progress_str.split('=')[1]
                                    h, m, s = map(float, progress_time.split(':'))
                                    progress_seconds = int(h * 3600 + m * 60 + s)
                                    progress = (progress_seconds / length_seconds) * 100
                                    self.progress_updated.emit(progress)
                                    self.status_updated.emit(row, "Processing")
                                except (ValueError, IndexError):
                                    self.progress_updated.emit(0)
                                    self.status_updated.emit(row, "Calculating...")

                            if "speed=" in line:
                                speed_index = line.find("speed=")
                                speed = line[speed_index:].split(' ')[0].split('=')[1]
                                self.speed_updated.emit(speed)
                                self.status_updated.emit(row, "Processing")

                            print(line.strip())
                            QApplication.processEvents()

                    process.wait()
                    if process.returncode == 0:
                        self.status_updated.emit(row, "Finalizing")
                        output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                        mb_per_min_after = self.calculate_mb_per_min(output_size_mb, length_seconds)

                        length_check = abs(self.get_video_length(output_file) - length_seconds) <= 8
                        mb_check = output_size_mb < size
                        mb_per_min_check = mb_per_min_after < (mb_min_target + threshold)

                        if not (length_check and mb_check and mb_per_min_check):
                            os.remove(output_file)
                            error_message = f"Error: Processing failed for file {file_path} due to "
                            error_message += "length mismatch, " if not length_check else ""
                            error_message += "size mismatch, " if not mb_check else ""
                            error_message += "MB/min threshold mismatch" if not mb_per_min_check else ""
                            self.status_updated.emit(row, error_message.strip(", "))
                            self.delete_cached_file(cached_file_path)
                            return

                        self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(output_size_mb))
                        self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_after))

                        if self.main_window.replace_checkbox.isChecked():
                            self.status_updated.emit(row, "Replacing")
                            self.replace_file(file_path, output_file, row)
                            self.delete_cached_file(cached_file_path)  # Delete cached copy after replacement
                        self.status_updated.emit(row, "Completed")
                    else:
                        error_message = process.stderr.read().strip()
                        self.status_updated.emit(row, f"Error: {error_message}")
                        print(f"Error processing file: {error_message}")
                        self.delete_cached_file(cached_file_path)

                else:
                    self.status_updated.emit(row, "Skipped")
                    self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(size))
                    self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_before))
                    self.delete_cached_file(cached_file_path)

            else:
                self.length_detected.emit(row, "Error")
                self.mb_per_min_detected.emit(row, 0.0)
                self.status_updated.emit(row, "Error")
        except Exception as e:
            self.status_updated.emit(row, f"Exception: {e}")
            print(f"Exception occurred: {e}")
        finally:
            if process:
                process.stdout.close()
                process.stderr.close()

    def replace_file(self, original_path, new_path, row):
        try:
            if not os.access(original_path, os.W_OK):
                os.chmod(original_path, 0o666)

            if os.name == 'nt':
                import ctypes
                FILE_ATTRIBUTE_ARCHIVE = 0x20
                current_attributes = ctypes.windll.kernel32.GetFileAttributesW(original_path)
                if current_attributes & FILE_ATTRIBUTE_ARCHIVE:
                    ctypes.windll.kernel32.SetFileAttributesW(original_path, current_attributes & ~FILE_ATTRIBUTE_ARCHIVE)

            shutil.move(new_path, original_path)
            self.status_updated.emit(row, "File replaced successfully")
        except Exception as e:
            print(f"Error replacing file {original_path}: {e}")
            self.status_updated.emit(row, f"Error: Failed to replace file {original_path}")
