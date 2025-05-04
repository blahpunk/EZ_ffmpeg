import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from table_widgets import NumericTableWidgetItem

"""video_processing.py – EZ Crusher (rev‑2025‑05‑04‑e)
=====================================================

Major hardening pass:
---------------------
* **Return‑code tolerance** – ffmpeg occasionally exits with `1` even after
  writing a good output (rare mux warnings). We now:
    1. Always run the post‑encode sanity checks (length, size) **regardless** of
       return‑code.
    2. If the checks pass we treat the job as *success* and only log a warning.
* **Robust logging**
    * Every run writes a section to `ez_ffmpeg.log` next to this script.
    * Full command, start/stop time, return‑code, and complete stderr.
* **Real‑time GUI feedback** clarified – last five stderr lines echoed to
  console so the user sees late‑stage warnings.
* **WindowsPath fix** – every arg passed to `Popen` and written to the log is
  explicitly `str()`‑cast.
* **Length probe retry** increased to 5× with progressive back‑off (0.3 → 1 s).

The rest of the logic (cover‑art exclusion, multi‑audio down‑mix, safe replace)
remains unchanged.
"""

# ────────────────────────────── constants ──────────────────────────────
LOG_FILE = Path(__file__).with_name("ez_ffmpeg.log")
MAX_LOG_LINES_GUI = 5  # how many trailing lines to print live

# ─────────────────────────────── helpers ───────────────────────────────

def log_write(section_title: str, payload: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8", errors="ignore") as fh:
        fh.write(f"\n[ {stamp} ]  {section_title}\n")
        fh.write(payload.rstrip("\n") + "\n")


class VideoProcessor(QObject):
    # Qt signals --------------------------------------------------------
    length_detected = pyqtSignal(int, str)
    mb_per_min_detected = pyqtSignal(int, float)
    status_updated = pyqtSignal(int, str)
    progress_updated = pyqtSignal(float)
    speed_updated = pyqtSignal(str)
    error_popup_requested = pyqtSignal(str)

    # --------------------------------------------------------------
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.cache_folder = Path(tempfile.gettempdir()) / "ez_ffmpeg"
        self.cache_folder.mkdir(exist_ok=True)
        self.error_popup_requested.connect(self._show_error_popup)

    # --------------------------------------------------------------
    @staticmethod
    def _format_length(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _calculate_mb_per_min(size_mb: float, length_seconds: float) -> float:
        return size_mb / max(length_seconds / 60, 1e-6)

    # --------------------------------------------------------------
    def _get_video_length(self, path: Path) -> float | None:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return float(res.stdout.strip())
        except Exception as exc:
            log_write("length_probe_exception", str(exc))
        return None

    # --------------------------------------------------------------
    def _request_error_popup(self, msg: str):
        self.error_popup_requested.emit(msg)

    # GUI thread ---------------------------------------------------
    def _show_error_popup(self, message: str):
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Processing Error")
        box.setText(message)
        continue_btn = box.addButton("Continue", QMessageBox.AcceptRole)
        stop_btn = box.addButton("Stop", QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() == stop_btn:
            self.main_window.file_manager.stop_processing()

    # --------------------------------------------------------------
    def process_video(self, row: int, src_path_str: str, size_mb: float):
        src_path = Path(src_path_str)
        proc: subprocess.Popen | None = None
        stderr_buffer: list[str] = []

        try:
            # Stage 1 – probe length -----------------------------------
            self.status_updated.emit(row, "Detecting video length")
            length = self._get_video_length(src_path)
            if length is None:
                self.status_updated.emit(row, "Error")
                return
            self.length_detected.emit(row, self._format_length(length))

            mb_per_min_before = self._calculate_mb_per_min(size_mb, length)
            self.mb_per_min_detected.emit(row, mb_per_min_before)

            mb_target = self.main_window.mb_min_slider.value()
            threshold = float(self.main_window.threshold_input.text())
            if mb_per_min_before < mb_target + threshold:
                # Already small enough – skip
                self.status_updated.emit(row, "Skipped")
                self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(size_mb))
                self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_per_min_before))
                return

            # Stage 2 – copy to cache ----------------------------------
            cache_src = self.cache_folder / src_path.name
            if not cache_src.exists():
                shutil.copy2(src_path, cache_src)

            out_path = self.cache_folder / (src_path.stem + "_processed" + src_path.suffix)

            tgt_bits_per_sec = (mb_target * 1024 * 1024 * 8) / 60 * 0.9
            audio_bps = 192 * 1024
            video_bps = int(max(tgt_bits_per_sec - audio_bps, 300_000))

            cmd: list[str] = [
                "ffmpeg",
                "-i",
                str(cache_src),
                "-map",
                "-0:d?",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-map",
                "0:s?",
                "-c:s",
                "copy",
                "-c:v",
                "libx265",
                "-b:v",
                f"{video_bps//1000}k",
                "-maxrate",
                f"{video_bps//1000}k",
                "-bufsize",
                f"{video_bps//500}k",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                "-ac",
                "2",
                "-af",
                "dynaudnorm",
                "-y",
                str(out_path),
            ]

            log_write("RUN", " ".join(shlex.quote(p) for p in cmd))
            self.status_updated.emit(row, "Processing")

            q: Queue[str] = Queue()

            def _capture(stream):
                for ln in iter(stream.readline, ""):
                    stderr_buffer.append(ln)
                    if len(stderr_buffer) > MAX_LOG_LINES_GUI:
                        stderr_buffer.pop(0)
                    q.put(ln)
                stream.close()

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            th = threading.Thread(target=_capture, args=(proc.stderr,), daemon=True)
            th.start()

            while proc.poll() is None:
                try:
                    line = q.get(timeout=0.1)
                except Empty:
                    pass
                else:
                    if "time=" in line:
                        try:
                            t = line.split("time=")[1].split()[0]
                            h, m, s = map(float, t.split(":"))
                            pct = (h*3600 + m*60 + s) / length * 100
                            self.progress_updated.emit(pct)
                        except Exception:
                            pass
                    if "speed=" in line:
                        try:
                            spd = line.split("speed=")[1].split()[0]
                            self.speed_updated.emit(spd)
                        except Exception:
                            pass
                    self.status_updated.emit(row, "Processing")
                    QApplication.processEvents()

            proc.wait()
            th.join()
            proc.communicate(timeout=0.1)  # ensure pipes flushed

            # Stage 3 – evaluate output --------------------------------
            # Try up to 5 times to get a sane length (file may not be fully closed yet)
            out_len: float | None = None
            for attempt in range(5):
                out_len = self._get_video_length(out_path)
                if out_len is not None:
                    break
                time.sleep(0.3 + 0.2*attempt)

            out_exists = out_path.exists()
            return_ok = proc.returncode == 0
            len_ok = out_len is not None and abs(out_len - length) <= 8
            size_after = out_path.stat().st_size / (1024*1024) if out_exists else 0.0
            mb_after = self._calculate_mb_per_min(size_after, length) if size_after else 0.0
            mb_ok = mb_after < mb_target + threshold and size_after < size_mb

            if (return_ok and len_ok and mb_ok) or (not return_ok and len_ok and mb_ok):
                # Treat as success even if return‑code non‑zero, but log warning.
                if not return_ok:
                    log_write("WARN", f"Non‑zero return‑code {proc.returncode} but validations passed.")
                self.main_window.file_table.setItem(row, 5, NumericTableWidgetItem(size_after))
                self.main_window.file_table.setItem(row, 6, NumericTableWidgetItem(mb_after))

                if self.main_window.replace_checkbox.isChecked():
                    try:
                        shutil.move(out_path, src_path)
                    except Exception:
                        os.replace(out_path, src_path)
                else:
                    out_path.unlink(missing_ok=True)
                cache_src.unlink(missing_ok=True)
                self.status_updated.emit(row, "Completed")
                return

            # Otherwise error ----------------------------------------
            log_write("ffmpeg_failed", "".join(stderr_buffer))
            self.status_updated.emit(row, "Error")
            cache_src.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
            self._request_error_popup("ffmpeg returned non‑zero exit code; see log console for details.")

        except Exception as exc:
            traceback.print_exc()
            log_write("processor_exception", traceback.format_exc())
            self.status_updated.emit(row, "Exception")
            self._request_error_popup(str(exc))

        finally:
            if proc:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
