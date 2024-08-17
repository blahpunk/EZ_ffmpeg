import subprocess
import os
import shlex
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, QObject
import shutil
import threading
from queue import Queue, Empty
from table_widgets import NumericTableWidgetItem

class VideoProcessor(QObject):
    length_detected = pyqtSignal(int, str)
    mb_per_min_detected = pyqtSignal(int, float)
    status_updated = pyqtSignal(int, str)
<<<<<<< HEAD
    progress_updated = pyqtSignal(int, float)  # Signal for progress updates
    speed_updated = pyqtSignal(str)  # Signal for speed updates
    console_output = pyqtSignal(str)  # Signal for console output
=======
    console_output = pyqtSignal(str)
>>>>>>> origin/main

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
<<<<<<< HEAD
=======
        self.console_output.connect(self.main_window.update_console)
>>>>>>> origin/main

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
<<<<<<< HEAD
=======
                print(f"Error getting video length: {error_message}")
>>>>>>> origin/main
                self.console_output.emit(f"Error getting video length: {error_message}")
                return None
        except Exception as e:
            error_message = f"Exception getting video length: {e}"
<<<<<<< HEAD
=======
            print(error_message)
>>>>>>> origin/main
            self.console_output.emit(error_message)
            return None

    def format_length(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def enqueue_output(self, out, queue):
        try:
            for line in iter(out.readline, ''):
                queue.put(line)
        except Exception as e:
<<<<<<< HEAD
=======
            print(f"Error in enqueue_output: {e}")
>>>>>>> origin/main
            self.console_output.emit(f"Error in enqueue_output: {e}")
        finally:
            out.close()

    def process_video(self, row, file_path, size):
        try:
            self.status_updated.emit(row, "Detecting video length")
<<<<<<< HEAD
            self.console_output.emit(f"Processing file: {file_path}")
=======
            print(f"Processing file: {file_path}")
>>>>>>> origin/main

            length_seconds = self.get_video_length(file_path)
            if length_seconds is not None:
                self.status_updated.emit(row, "Calculating MB/min")
                length_formatted = self.format_length(length_seconds)
                minutes = length_seconds / 60
                mb_per_min_before = size / (minutes if minutes else 1)
                self.length_detected.emit(row, length_formatted)
                self.mb_per_min_detected.emit(row, mb_per_min_before)

<<<<<<< HEAD
                if self.main_window.convert_checkbox.isChecked():
                    mb_min_target = self.main_window.mb_min_slider.value()
                    threshold = float(self.main_window.threshold_input.text())
                    if mb_per_min_before < (mb_min_target + threshold):
                        self.status_updated.emit(row, "Skipped")
                        self.console_output.emit(f"File skipped: {file_path}")
                        return

                    output_file = os.path.splitext(file_path)[0] + '_processed' + os.path.splitext(file_path)[1]
                    target_bitrate = (mb_min_target * 1024 * 1024 * 8) / 60  # Convert MB/min to bits/second
                    audio_bitrate = 192 * 1024  # 192 kbps in bits/sec
                    video_bitrate = target_bitrate - audio_bitrate  # Subtract audio bitrate from target

                    cmd = [
                        'ffmpeg', '-i', file_path,
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

                    self.status_updated.emit(row, "Compressing")
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                    q = Queue()
                    threading.Thread(target=self.enqueue_output, args=(process.stderr, q)).start()

                    while True:
                        try:
                            line = q.get_nowait()
                        except Empty:
                            if process.poll() is not None:
                                break
                        else:
                            if "time=" in line:
                                time_str = line.split("time=")[-1].split(" ")[0]
                                time_parts = time_str.split(":")
                                elapsed_seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + float(time_parts[2])
                                
                                # Correct progress calculation
                                progress = (elapsed_seconds / length_seconds) * 100
                                
                                self.progress_updated.emit(row, round(progress, 1))  # Emit progress rounded to 1 decimal place
                                self.console_output.emit(f"Progress: {round(progress, 1)}%")

                            if "speed=" in line:
                                speed_str = line.split("speed=")[-1].split(" ")[0].strip()
                                self.speed_updated.emit(speed_str)

                            self.console_output.emit(line)
                            QApplication.processEvents()

                    process.wait()
                    if process.returncode == 0:
                        self.status_updated.emit(row, "Finalizing")
                        output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                        mb_per_min_after = output_size_mb / (minutes if minutes else 1)

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
                            self.console_output.emit(error_message.strip(", "))
                            return

                        self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(output_size_mb))
                        self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_after))

                        if self.main_window.replace_checkbox.isChecked():
                            self.status_updated.emit(row, "Replacing")
                            self.replace_file(file_path, output_file)
                        self.status_updated.emit(row, "Completed")
                    else:
                        error_message = process.stderr.read().strip()
                        self.status_updated.emit(row, f"Error: {error_message}")
                        self.console_output.emit(f"Error processing file: {error_message}")
                else:
                    # Handle non-conversion case
                    if self.main_window.normalize_checkbox.isChecked() or self.main_window.stereo_checkbox.isChecked():
                        output_file = os.path.splitext(file_path)[0] + '_processed' + os.path.splitext(file_path)[1]
                        cmd = ['ffmpeg', '-i', file_path, '-map', '0:v', '-map', '0:a', '-map', '0:s?', '-c:s', 'copy', '-y', output_file]
                        if self.main_window.normalize_checkbox.isChecked():
                            cmd.extend(['-af', 'dynaudnorm'])
                        if self.main_window.stereo_checkbox.isChecked():
                            cmd.extend(['-ac', '2'])

                        self.status_updated.emit(row, "Processing Audio")
                        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                        q = Queue()
                        threading.Thread(target=self.enqueue_output, args=(process.stderr, q)).start()

                        while True:
                            try:
                                line = q.get_nowait()
                            except Empty:
                                if process.poll() is not None:
                                    break
                            else:
                                self.console_output.emit(line)
                                QApplication.processEvents()

                        process.wait()
                        if process.returncode == 0:
                            self.status_updated.emit(row, "Finalizing")
                            length_check = abs(self.get_video_length(output_file) - length_seconds) <= 8

                            if not length_check:
                                os.remove(output_file)
                                error_message = f"Error: Processing failed for file {file_path} due to length mismatch."
                                self.status_updated.emit(row, error_message)
                                self.console_output.emit(error_message)
                                return

                            if self.main_window.replace_checkbox.isChecked():
                                self.status_updated.emit(row, "Replacing")
                                self.replace_file(file_path, output_file)
                            self.status_updated.emit(row, "Completed")
                        else:
                            error_message = process.stderr.read().strip()
                            self.status_updated.emit(row, f"Error: {error_message}")
                            self.console_output.emit(f"Error processing file: {error_message}")
                    else:
                        # If Convert, Normalize, and Stereo are all unchecked, just skip processing
                        self.status_updated.emit(row, "Skipped")
                        self.console_output.emit(f"File skipped (no processing required): {file_path}")
=======
                mb_min_target = self.main_window.mb_min_slider.value()
                threshold = float(self.main_window.threshold_input.text())
                if mb_per_min_before < (mb_min_target + threshold):
                    self.status_updated.emit(row, "Skipped")
                    print(f"File skipped: {file_path}")
                    return

                output_file = os.path.splitext(file_path)[0] + '_processed' + os.path.splitext(file_path)[1]
                target_bitrate = (mb_min_target * 1024 * 1024 * 8) / 60  # Convert MB/min to bits/second
                audio_bitrate = 192 * 1024  # 192 kbps in bits/sec
                video_bitrate = target_bitrate - audio_bitrate  # Subtract audio bitrate from target

                cmd = [
                    'ffmpeg', '-i', file_path,
                    '-map', '0:v', '-map', '0:a', '-map', '0:s?',
                    '-c:v', 'libx265', '-b:v', f'{int(video_bitrate / 1000)}k', '-maxrate', f'{int(video_bitrate / 1000)}k', '-bufsize', f'{int(video_bitrate / 500)}k',
                    '-c:a', 'libmp3lame', '-b:a', '192k', '-c:s', 'copy',
                    '-y', output_file
                ]

                self.status_updated.emit(row, "Compressing")
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                q = Queue()
                threading.Thread(target=self.enqueue_output, args=(process.stderr, q)).start()

                while True:
                    try:
                        line = q.get_nowait()
                    except Empty:
                        if process.poll() is not None:
                            break
                    else:
                        self.console_output.emit(line)
                        print(f"Console output: {line.strip()}")
                        QApplication.processEvents()

                process.wait()
                if process.returncode == 0:
                    self.status_updated.emit(row, "Finalizing")
                    output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                    mb_per_min_after = output_size_mb / (minutes if minutes else 1)

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
                        print(error_message.strip(", "))
                        self.console_output.emit(error_message.strip(", "))
                        return

                    self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(output_size_mb))
                    self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_after))

                    if self.main_window.replace_checkbox.isChecked():
                        self.status_updated.emit(row, "Replacing")
                        self.replace_file(file_path, output_file)
                    self.status_updated.emit(row, "Completed")
                else:
                    error_message = process.stderr.read().strip()
                    self.status_updated.emit(row, f"Error: {error_message}")
                    print(f"Error processing file: {error_message}")
                    self.console_output.emit(f"Error processing file: {error_message}")
>>>>>>> origin/main
                self.length_detected.emit(row, length_formatted)
                self.mb_per_min_detected.emit(row, mb_per_min_before)
                QApplication.processEvents()
            else:
                self.length_detected.emit(row, "Error")
                self.mb_per_min_detected.emit(row, 0.0)  # Emit 0.0 if length detection fails
                self.status_updated.emit(row, "Error")
        except Exception as e:
            self.status_updated.emit(row, f"Exception: {e}")
<<<<<<< HEAD
            self.console_output.emit(f"Exception occurred: {e}")
=======
            error_message = f"Exception occurred: {e}"
            print(error_message)
            self.console_output.emit(error_message)
>>>>>>> origin/main

    def replace_file(self, original_path, new_path):
        try:
            if not os.access(original_path, os.W_OK):
<<<<<<< HEAD
                self.console_output.emit(f"Removing read-only attribute from {original_path}")
=======
                print(f"Removing read-only attribute from {original_path}")
>>>>>>> origin/main
                os.chmod(original_path, 0o666)
            shutil.move(new_path, original_path)
        except Exception as e:
            error_message = f"Error replacing file {original_path}: {e}"
<<<<<<< HEAD
=======
            print(error_message)
>>>>>>> origin/main
            self.console_output.emit(error_message)
