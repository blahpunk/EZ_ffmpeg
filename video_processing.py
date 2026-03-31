import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from queue import Empty, Queue

from PyQt5.QtCore import QObject, pyqtSignal


class VideoProcessor(QObject):
    analysis_updated = pyqtSignal(int, object)
    output_updated = pyqtSignal(int, object)
    status_updated = pyqtSignal(int, str)
    progress_updated = pyqtSignal(float)
    speed_updated = pyqtSignal(str)
    current_eta_updated = pyqtSignal(str)
    runtime_updated = pyqtSignal(int, object)
    encoder_updated = pyqtSignal(int, str)

    ENCODER_PROFILES = {
        'auto': {
            'label': 'Auto',
            'default_speed': 0.9,
        },
        'libx265': {
            'label': 'CPU H.265 (libx265)',
            'default_speed': 0.35,
        },
        'h264_nvenc': {
            'label': 'GPU H.264 (h264_nvenc)',
            'default_speed': 2.8,
        },
        'hevc_nvenc': {
            'label': 'GPU H.265 (hevc_nvenc)',
            'default_speed': 2.0,
        },
        'av1_nvenc': {
            'label': 'GPU AV1 (av1_nvenc)',
            'default_speed': 1.2,
        },
    }

    AUTO_PRIORITY = ['hevc_nvenc', 'h264_nvenc', 'av1_nvenc', 'libx265']
    MAX_HISTORY_ITEMS = 200
    TIME_PATTERN = re.compile(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)')
    SPEED_PATTERN = re.compile(r'speed=\s*([0-9.]+)x')

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.cache_folder = ""
        self.history_path = ""
        self.stop_requested = False
        self.current_process = None
        self.current_cached_file_path = None
        self.current_output_file = None
        self.available_encoders = self.detect_available_encoders()
        self.encode_history = []
        self.set_cache_folder(os.path.join(tempfile.gettempdir(), "ez_ffmpeg_cache"))

    def get_available_encoder_options(self):
        options = [('auto', self.get_encoder_label('auto'))]
        for encoder_key in self.AUTO_PRIORITY:
            if encoder_key in self.available_encoders:
                options.append((encoder_key, self.get_encoder_label(encoder_key)))
        if len(options) == 1:
            options.append(('libx265', self.get_encoder_label('libx265')))
        return options

    def set_cache_folder(self, folder_path):
        normalized_path = os.path.abspath(folder_path)
        self.cache_folder = normalized_path
        self.history_path = os.path.join(self.cache_folder, "encode_history.json")
        os.makedirs(self.cache_folder, exist_ok=True)
        self.encode_history = self.load_encode_history()
        self.cleanup_stale_cache()

    def detect_available_encoders(self):
        detected = {'libx265'}
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            for encoder_key in ('h264_nvenc', 'hevc_nvenc', 'av1_nvenc', 'libx265'):
                if encoder_key in output:
                    detected.add(encoder_key)
        except Exception as exc:
            print(f"Unable to detect FFmpeg encoders: {exc}")
        return detected

    def get_encoder_label(self, encoder_key):
        profile = self.ENCODER_PROFILES.get(encoder_key)
        if profile:
            return profile['label']
        return encoder_key

    def resolve_encoder_mode(self, selected_mode):
        if selected_mode and selected_mode != 'auto' and selected_mode in self.available_encoders:
            return selected_mode

        for encoder_key in self.AUTO_PRIORITY:
            if encoder_key in self.available_encoders:
                return encoder_key
        return 'libx265'

    def get_video_length(self, file_path):
        source_info = self.probe_media_info(file_path)
        if source_info:
            return source_info.get('duration_seconds')
        return None

    def probe_media_info(self, file_path):
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v',
                    'error',
                    '-print_format',
                    'json',
                    '-show_format',
                    '-show_streams',
                    file_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                stderr_text = result.stderr.decode('utf-8', errors='replace').strip()
                print(f"Error getting media info: {stderr_text}")
                return None

            stdout_text = result.stdout.decode('utf-8', errors='replace')
            probe_data = json.loads(stdout_text)
            format_info = probe_data.get('format', {})
            streams = probe_data.get('streams', [])
            video_stream = next((stream for stream in streams if stream.get('codec_type') == 'video'), {})
            audio_stream = next((stream for stream in streams if stream.get('codec_type') == 'audio'), {})

            duration_seconds = self._safe_float(
                format_info.get('duration') or video_stream.get('duration') or audio_stream.get('duration')
            )
            width = self._safe_int(video_stream.get('width'))
            height = self._safe_int(video_stream.get('height'))
            audio_channels = self._safe_int(audio_stream.get('channels'))

            return {
                'duration_seconds': duration_seconds,
                'video_codec': video_stream.get('codec_name') or 'Unknown',
                'audio_codec': audio_stream.get('codec_name') or 'None',
                'audio_channels': audio_channels,
                'width': width,
                'height': height,
            }
        except Exception as exc:
            print(f"Exception getting media info: {exc}")
            return None

    def format_seconds(self, seconds):
        if seconds is None:
            return "--"
        total_seconds = max(int(round(seconds)), 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        remaining_seconds = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{remaining_seconds:02}"

    def calculate_mb_per_min(self, size_mb, length_seconds):
        minutes = length_seconds / 60 if length_seconds else 0
        return size_mb / (minutes if minutes else 1)

    def analyze_video(self, record):
        source_info = record.get('source_info') or self.probe_media_info(record['file_path'])
        if not source_info:
            return None

        duration_seconds = source_info.get('duration_seconds')
        if not duration_seconds:
            return None

        resolved_encoder = self.resolve_encoder_mode(self.main_window.get_selected_encoder_mode())
        width = source_info.get('width') or 0
        height = source_info.get('height') or 0
        mb_per_min_before = self.calculate_mb_per_min(record['size_mb'], duration_seconds)
        estimated_seconds = self.estimate_encode_seconds(source_info, resolved_encoder)
        estimated_output_size_mb = self.main_window.mb_min_slider.value() * (duration_seconds / 60.0)
        audio_channels = source_info.get('audio_channels') or 0
        audio_codec = source_info.get('audio_codec') or 'None'

        return {
            **source_info,
            'length_formatted': self.format_seconds(duration_seconds),
            'mb_per_min_before': mb_per_min_before,
            'estimated_seconds': estimated_seconds,
            'estimated_display': self.format_seconds(estimated_seconds),
            'estimated_output_size_mb': estimated_output_size_mb,
            'resolved_encoder': resolved_encoder,
            'encoder_label': self.get_encoder_label(resolved_encoder),
            'video_codec_label': (source_info.get('video_codec') or 'Unknown').upper(),
            'resolution_label': f"{width}x{height}" if width and height else '--',
            'audio_label': f"{audio_codec.upper()} {audio_channels}ch" if audio_channels else audio_codec.upper(),
        }

    def estimate_encode_seconds(self, source_info, encoder_key):
        duration_seconds = source_info.get('duration_seconds')
        if not duration_seconds:
            return None

        speed_multiplier = self.estimate_speed_multiplier(source_info, encoder_key)
        if speed_multiplier <= 0:
            return None
        return duration_seconds / speed_multiplier

    def estimate_speed_multiplier(self, source_info, encoder_key):
        pixels = (source_info.get('width') or 0) * (source_info.get('height') or 0)
        weighted_total = 0.0
        total_weight = 0.0

        for entry in reversed(self.encode_history):
            if entry.get('encoder') != encoder_key:
                continue

            weight = 1.0
            entry_pixels = entry.get('pixels') or 0
            if pixels and entry_pixels:
                similarity = min(pixels, entry_pixels) / max(pixels, entry_pixels)
                weight += similarity
            if entry.get('normalize') == self.main_window.normalize_checkbox.isChecked():
                weight += 0.25
            if entry.get('stereo') == self.main_window.stereo_checkbox.isChecked():
                weight += 0.25

            weighted_total += entry.get('avg_speed', 0.0) * weight
            total_weight += weight

            if total_weight >= 8:
                break

        if total_weight > 0:
            return weighted_total / total_weight

        return self.ENCODER_PROFILES.get(encoder_key, {}).get('default_speed', 1.0)

    def build_output_path(self, file_path):
        base_name, extension = os.path.splitext(os.path.basename(file_path))
        output_name = f"{base_name}_processed{extension}"
        return os.path.join(self.cache_folder, output_name)

    def build_final_output_path(self, file_path):
        source_dir = os.path.dirname(file_path)
        base_name, extension = os.path.splitext(os.path.basename(file_path))
        candidate = os.path.join(source_dir, f"{base_name}_processed{extension}")

        if not os.path.exists(candidate):
            return candidate

        counter = 1
        while True:
            candidate = os.path.join(source_dir, f"{base_name}_processed_{counter}{extension}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def build_ffmpeg_command(self, input_path, output_path, resolved_encoder, video_bitrate):
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-i',
            input_path,
            '-map',
            '-0:d?',
            '-map',
            '0:v:0',
            '-map',
            '0:a?',
            '-map',
            '0:s?',
        ]
        cmd.extend(self.build_video_args(resolved_encoder, video_bitrate))
        cmd.extend(self.build_audio_args())
        cmd.extend(self.build_subtitle_args())
        cmd.extend(['-y', output_path])
        return cmd

    def build_video_args(self, encoder_key, video_bitrate):
        bitrate_kbps = max(int(video_bitrate / 1000), 100)
        buffer_kbps = max(int(video_bitrate / 500), 200)
        return [
            '-c:v',
            encoder_key,
            '-b:v',
            f'{bitrate_kbps}k',
            '-maxrate',
            f'{bitrate_kbps}k',
            '-bufsize',
            f'{buffer_kbps}k',
        ]

    def build_audio_args(self):
        needs_audio_processing = (
            self.main_window.convert_checkbox.isChecked()
            or self.main_window.normalize_checkbox.isChecked()
            or self.main_window.stereo_checkbox.isChecked()
        )

        if not needs_audio_processing:
            return ['-c:a', 'copy']

        args = ['-c:a', 'aac', '-b:a', '192k']
        if self.main_window.normalize_checkbox.isChecked():
            args.extend(['-af', 'dynaudnorm'])
        if self.main_window.stereo_checkbox.isChecked():
            args.extend(['-ac', '2'])
        return args

    def build_subtitle_args(self):
        return ['-c:s', 'copy']

    def enqueue_output(self, stream, queue):
        try:
            for line in iter(stream.readline, ''):
                queue.put(line)
        except Exception as exc:
            print(f"Error in enqueue_output: {exc}")
        finally:
            stream.close()

    def delete_cached_file(self, cached_file_path):
        retries = 3
        for attempt in range(retries):
            try:
                if os.path.exists(cached_file_path):
                    os.chmod(cached_file_path, 0o666)
                    os.remove(cached_file_path)
                    print(f"Deleted cached file: {cached_file_path}")
                    break
            except PermissionError:
                print(f"Attempt {attempt + 1}: Permission denied for {cached_file_path}. Retrying...")
                time.sleep(1)
            except Exception as exc:
                print(f"Error deleting {cached_file_path}: {exc}")
                break

    def cleanup_stale_cache(self):
        if not os.path.isdir(self.cache_folder):
            return

        for entry in os.listdir(self.cache_folder):
            entry_path = os.path.join(self.cache_folder, entry)
            if os.path.abspath(entry_path) == os.path.abspath(self.history_path):
                continue

            try:
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path, ignore_errors=True)
                else:
                    os.remove(entry_path)
            except Exception as exc:
                print(f"Error cleaning cache entry {entry_path}: {exc}")

    def request_stop(self, immediate=False):
        self.stop_requested = immediate

    def abort_active_process(self):
        self.stop_requested = True

        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except Exception as exc:
                print(f"Error terminating active ffmpeg process: {exc}")
                try:
                    self.current_process.kill()
                except Exception as kill_exc:
                    print(f"Error killing active ffmpeg process: {kill_exc}")

        if self.current_output_file and os.path.exists(self.current_output_file):
            try:
                os.remove(self.current_output_file)
            except Exception as exc:
                print(f"Error deleting partial output {self.current_output_file}: {exc}")

        if self.current_cached_file_path:
            self.delete_cached_file(self.current_cached_file_path)

        self.current_process = None
        self.current_output_file = None
        self.current_cached_file_path = None

    def process_video(self, record):
        process = None
        cached_file_path = os.path.join(self.cache_folder, os.path.basename(record['file_path']))
        output_file = self.build_output_path(record['file_path'])
        row = record['row']
        length_seconds = None
        last_speed_multiplier = 0.0
        last_avg_speed_multiplier = 0.0

        try:
            self.stop_requested = False
            self.current_cached_file_path = cached_file_path
            self.current_output_file = output_file
            self.status_updated.emit(row, "Probing")
            analysis = self.analyze_video(record)
            if not analysis:
                self.status_updated.emit(row, "Error analyzing")
                return

            self.analysis_updated.emit(row, analysis)
            length_seconds = analysis['duration_seconds']
            mb_per_min_before = analysis['mb_per_min_before']
            mb_min_target = self.main_window.mb_min_slider.value()
            threshold = float(self.main_window.threshold_input.text())

            self.status_updated.emit(row, "Checking thresholds")
            if mb_per_min_before < (mb_min_target + threshold):
                self.output_updated.emit(
                    row,
                    {
                        'output_size_mb': record['size_mb'],
                        'mb_per_min_after': mb_per_min_before,
                    },
                )
                self.runtime_updated.emit(
                    row,
                    {
                        'eta_seconds': 0.0,
                        'eta_display': '00:00:00',
                        'elapsed_seconds': 0.0,
                        'elapsed_display': '',
                        'avg_speed_multiplier': 0.0,
                        'avg_speed_display': '',
                    },
                )
                self.delete_cached_file(cached_file_path)
                self.status_updated.emit(row, "Skipped")
                return

            if not os.path.exists(cached_file_path):
                self.status_updated.emit(row, "Copying to cache")
                shutil.copy2(record['file_path'], cached_file_path)
                print(f"Copied {record['file_path']} to {cached_file_path}")

            target_bitrate = (mb_min_target * 1024 * 1024 * 8) / 60 * 0.9
            audio_bitrate = 192 * 1024 if self._is_audio_reencoded() else 0
            video_bitrate = max(target_bitrate - audio_bitrate, 100 * 1024)
            resolved_encoder = analysis['resolved_encoder']

            self.encoder_updated.emit(row, self.get_encoder_label(resolved_encoder))
            cmd = self.build_ffmpeg_command(cached_file_path, output_file, resolved_encoder, video_bitrate)
            self.status_updated.emit(row, "Launching encoder")
            self.status_updated.emit(row, "Processing")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self.current_process = process
            queue = Queue()
            threading.Thread(target=self.enqueue_output, args=(process.stderr, queue), daemon=True).start()

            start_time = time.time()
            current_seconds = 0.0

            while True:
                if self.stop_requested:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except Exception as exc:
                        print(f"Error stopping ffmpeg: {exc}")
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    self.delete_cached_file(cached_file_path)
                    self.status_updated.emit(row, "Stopped")
                    self.speed_updated.emit('')
                    self.current_eta_updated.emit('--')
                    return

                try:
                    line = queue.get(timeout=0.1)
                except Empty:
                    if process.poll() is not None:
                        break
                    continue

                parsed_time = self.parse_progress_time(line)
                if parsed_time is not None:
                    current_seconds = parsed_time
                    progress = min((current_seconds / length_seconds) * 100, 100.0)
                    self.progress_updated.emit(progress)

                parsed_speed = self.parse_speed(line)
                if parsed_speed is not None:
                    speed_text, last_speed_multiplier = parsed_speed
                    self.speed_updated.emit(speed_text)

                if current_seconds and length_seconds:
                    elapsed_seconds = max(time.time() - start_time, 0.0)
                    last_avg_speed_multiplier = current_seconds / elapsed_seconds if elapsed_seconds else 0.0
                    eta_seconds = None
                    if last_speed_multiplier > 0:
                        eta_seconds = max((length_seconds - current_seconds) / last_speed_multiplier, 0.0)

                    eta_display = self.format_seconds(eta_seconds)
                    self.current_eta_updated.emit(eta_display)
                    self.runtime_updated.emit(
                        row,
                        {
                            'eta_seconds': eta_seconds,
                            'eta_display': eta_display,
                            'elapsed_seconds': elapsed_seconds,
                            'elapsed_display': self.format_seconds(elapsed_seconds),
                            'avg_speed_multiplier': last_avg_speed_multiplier,
                            'avg_speed_display': self.format_speed(last_avg_speed_multiplier),
                        },
                    )

                print(line.strip())

            process.wait()
            if process.returncode == 0:
                self.status_updated.emit(row, "Finalizing")
                output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                mb_per_min_after = self.calculate_mb_per_min(output_size_mb, length_seconds)
                output_length = self.get_video_length(output_file)
                length_check = output_length is not None and abs(output_length - length_seconds) <= 8
                size_check = output_size_mb < record['size_mb']

                if not (length_check and size_check):
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    error_message = f"Error: Processing failed for {record['file_path']} due to "
                    if not length_check:
                        error_message += "length mismatch, "
                    if not size_check:
                        error_message += "output not smaller"
                    self.status_updated.emit(row, error_message.strip(", "))
                    self.delete_cached_file(cached_file_path)
                    return

                self.output_updated.emit(
                    row,
                    {
                        'output_size_mb': output_size_mb,
                        'mb_per_min_after': mb_per_min_after,
                    },
                )
                self.progress_updated.emit(100.0)
                self.current_eta_updated.emit('--')
                self.runtime_updated.emit(
                    row,
                    {
                        'eta_seconds': 0.0,
                        'eta_display': '00:00:00',
                        'elapsed_seconds': time.time() - start_time,
                        'elapsed_display': self.format_seconds(time.time() - start_time),
                        'avg_speed_multiplier': last_avg_speed_multiplier,
                        'avg_speed_display': self.format_speed(last_avg_speed_multiplier),
                    },
                )

                if self.main_window.replace_checkbox.isChecked():
                    self.status_updated.emit(row, "Replacing")
                    if not self.replace_file(record['file_path'], output_file, row):
                        self.delete_cached_file(cached_file_path)
                        return
                else:
                    self.status_updated.emit(row, "Moving output")
                    final_output_path = self.build_final_output_path(record['file_path'])
                    if not self.move_output_file(output_file, final_output_path, row):
                        self.delete_cached_file(cached_file_path)
                        return

                self.record_encode_history(analysis, resolved_encoder, last_avg_speed_multiplier)
                self.speed_updated.emit('')
                self.status_updated.emit(row, "Completed")
                self.delete_cached_file(cached_file_path)
            else:
                self.status_updated.emit(row, "Error: See log")
                self.speed_updated.emit('')
                self.current_eta_updated.emit('--')
                if os.path.exists(output_file):
                    os.remove(output_file)
                self.delete_cached_file(cached_file_path)

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            self.delete_cached_file(cached_file_path)
            self.speed_updated.emit('')
            self.current_eta_updated.emit('--')
            self.status_updated.emit(row, f"Exception: {exc}")
            print(f"Exception: {exc}")
        finally:
            if process and process.stderr:
                process.stderr.close()
            self.current_process = None
            self.current_output_file = None
            self.current_cached_file_path = None

    def replace_file(self, original_path, new_path, row):
        try:
            if not os.access(original_path, os.W_OK):
                os.chmod(original_path, 0o666)
            if os.path.exists(new_path) and not os.access(new_path, os.W_OK):
                os.chmod(new_path, 0o666)

            if os.name == 'nt':
                import ctypes

                FILE_ATTRIBUTE_ARCHIVE = 0x20
                current_attributes = ctypes.windll.kernel32.GetFileAttributesW(original_path)
                if current_attributes & FILE_ATTRIBUTE_ARCHIVE:
                    ctypes.windll.kernel32.SetFileAttributesW(original_path, current_attributes & ~FILE_ATTRIBUTE_ARCHIVE)

            original_drive = os.path.splitdrive(os.path.abspath(original_path))[0].lower()
            new_drive = os.path.splitdrive(os.path.abspath(new_path))[0].lower()

            if original_drive == new_drive:
                os.replace(new_path, original_path)
            else:
                backup_path = self.build_backup_path(original_path)
                os.replace(original_path, backup_path)
                try:
                    shutil.move(new_path, original_path)
                except Exception:
                    if os.path.exists(backup_path):
                        os.replace(backup_path, original_path)
                    raise
                else:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)

            self.status_updated.emit(row, "File replaced successfully")
            return True
        except Exception as exc:
            print(f"Error replacing file {original_path}: {exc}")
            self.status_updated.emit(row, "Error: Failed to replace file")
            return False

    def build_backup_path(self, original_path):
        base_path = f"{original_path}.ez_ffmpeg_backup"
        if not os.path.exists(base_path):
            return base_path

        counter = 1
        while True:
            candidate = f"{base_path}_{counter}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def move_output_file(self, processed_path, final_path, row):
        try:
            shutil.move(processed_path, final_path)
            self.status_updated.emit(row, f"Saved as {os.path.basename(final_path)}")
            return True
        except Exception as exc:
            print(f"Error moving processed file to {final_path}: {exc}")
            self.status_updated.emit(row, "Error: Failed to move processed file")
            return False

    def record_encode_history(self, source_info, encoder_key, avg_speed_multiplier):
        if avg_speed_multiplier <= 0:
            return

        entry = {
            'encoder': encoder_key,
            'pixels': (source_info.get('width') or 0) * (source_info.get('height') or 0),
            'duration_seconds': source_info.get('duration_seconds'),
            'normalize': self.main_window.normalize_checkbox.isChecked(),
            'stereo': self.main_window.stereo_checkbox.isChecked(),
            'avg_speed': avg_speed_multiplier,
            'timestamp': time.time(),
        }
        self.encode_history.append(entry)
        self.encode_history = self.encode_history[-self.MAX_HISTORY_ITEMS:]
        self.save_encode_history()

    def load_encode_history(self):
        if not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, 'r', encoding='utf-8') as history_file:
                return json.load(history_file)
        except Exception as exc:
            print(f"Unable to load encode history: {exc}")
            return []

    def save_encode_history(self):
        try:
            with open(self.history_path, 'w', encoding='utf-8') as history_file:
                json.dump(self.encode_history, history_file, indent=2)
        except Exception as exc:
            print(f"Unable to save encode history: {exc}")

    def parse_progress_time(self, line):
        match = self.TIME_PATTERN.search(line)
        if not match:
            return None
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def parse_speed(self, line):
        match = self.SPEED_PATTERN.search(line)
        if not match:
            return None
        speed_multiplier = self._safe_float(match.group(1))
        if speed_multiplier <= 0:
            return None
        return f"{speed_multiplier:.2f}x", speed_multiplier

    def format_speed(self, speed_multiplier):
        if not speed_multiplier or speed_multiplier <= 0:
            return ""
        return f"{speed_multiplier:.2f}x"

    def _is_audio_reencoded(self):
        return (
            self.main_window.convert_checkbox.isChecked()
            or self.main_window.normalize_checkbox.isChecked()
            or self.main_window.stereo_checkbox.isChecked()
        )

    def _safe_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
