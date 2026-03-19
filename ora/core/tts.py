# ora/core/tts.py
# TTS synthesis engine: text chunking, producer/consumer queue, Piper subprocess.
#
# Architecture (producer/consumer):
#   - speak() splits text into sentence-level chunks, then launches two threads:
#   - Producer: iterates chunks, checks cache, synthesizes with Piper if not cached,
#               pushes PCM paths into a bounded queue.
#   - Consumer: drains the queue, plays each PCM file via aplay sequentially.
#
# Pause/Resume: SIGSTOP/SIGCONT sent to the current aplay subprocess.
# Stop: terminates aplay and the current piper subprocess, drains the queue,
#       and sends a sentinel so any running consumer exits before a new session starts.
# Restart: calls stop() then speak() again from the same chunk list.

import os
import queue
import re
import time
import shutil
import signal
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

from ..constants import APLAY_RATE, APLAY_FORMAT, CHUNK_MIN_LEN, CHUNK_MIN_GAP
from .cache import CacheManager


class TTSEngine:
    """Manages TTS synthesis and chunked audio playback.

    All callbacks (on_status, on_chunk_progress, etc.) are invoked from
    background threads — callers must wrap UI updates in GLib.idle_add.
    """

    def __init__(self, cache: CacheManager) -> None:
        self._cache = cache

        # Shared subprocess handles (accessed from multiple threads, but only
        # written by the thread that owns them; reads are benign races)
        self._current_aplay: Optional[subprocess.Popen] = None
        self._current_piper: Optional[subprocess.Popen] = None

        self._stop_event = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=4)  # replaced each session

        self._speaking = False
        self._paused = False
        self._chunks: list[str] = []

        # ── Callbacks wired by the app ────────────────────────────────────────
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_chunk_progress: Optional[Callable[[int, int], None]] = None
        self.on_done: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_speaking_changed: Optional[Callable[[bool], None]] = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    @property
    def is_paused(self) -> bool:
        return self._paused

    def speak(self, text: str, model_path: Path, speed: float) -> None:
        """Split text into chunks and start producer+consumer threads.

        Stops any current playback first so only one utterance plays at a time.
        """
        self.stop()

        self._chunks = split_chunks(text)
        if not self._chunks:
            return

        self._stop_event.clear()
        self._paused = False
        self._speaking = True
        self._notify_speaking(True)

        total = len(self._chunks)
        q: queue.Queue = queue.Queue(maxsize=4)
        self._queue = q

        threading.Thread(
            target=self._producer,
            args=(list(self._chunks), model_path, speed, total, q),
            daemon=True,
            name="tts-producer",
        ).start()
        threading.Thread(
            target=self._consumer,
            args=(total, q),
            daemon=True,
            name="tts-consumer",
        ).start()

    def pause(self) -> None:
        """Pause playback by sending SIGSTOP to the current aplay process."""
        if not self._speaking or self._paused:
            return
        self._paused = True
        self._signal_process(self._current_aplay, signal.SIGSTOP)
        self._signal_process(self._current_piper, signal.SIGSTOP)

    def resume(self) -> None:
        """Resume playback by sending SIGCONT to the current aplay process."""
        if not self._speaking or not self._paused:
            return
        self._paused = False
        # Resume piper first so it can keep producing audio for the queue
        self._signal_process(self._current_piper, signal.SIGCONT)
        self._signal_process(self._current_aplay, signal.SIGCONT)

    def stop(self) -> None:
        """Stop playback immediately and drain the internal queue."""
        self._stop_event.set()
        self._paused = False
        # Resume processes first so they can receive the terminate signal
        self._signal_process(self._current_piper, signal.SIGCONT)
        self._signal_process(self._current_aplay, signal.SIGCONT)
        self._terminate_process(self._current_aplay)
        self._terminate_process(self._current_piper)
        # Drain the queue, then send a sentinel so any running consumer exits
        # cleanly before a new session's consumer starts (prevents two consumers
        # from competing on the same queue when chunks are cached).
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(None)

    def restart(self, model_path: Path, speed: float) -> None:
        """Restart playback from the first chunk using the stored chunk list."""
        if not self._chunks:
            return
        text = " ".join(self._chunks)  # reconstruct — good enough for restart
        self.speak(text, model_path, speed)

    # ── Producer thread ───────────────────────────────────────────────────────

    def _producer(
        self, chunks: list[str], model_path: Path, speed: float, total: int,
        q: queue.Queue,
    ) -> None:
        piper = _get_piper_bin()
        if not piper:
            self._emit("on_error", "no_piper")
            q.put(None)
            return

        for chunk in chunks:
            if self._stop_event.is_set():
                break

            cache_key = self._cache.make_key(chunk, model_path, speed)
            pcm_path = self._cache.get(cache_key)

            if pcm_path is None:
                self._emit("on_status", "synthesizing")
                pcm_data = self._synthesize(chunk, model_path, speed, piper)
                if pcm_data and not self._stop_event.is_set():
                    pcm_path = self._cache.put(cache_key, pcm_data)

            if pcm_path and not self._stop_event.is_set():
                # Block if the consumer is slow (bounded queue provides back-pressure)
                q.put(pcm_path)

        q.put(None)  # sentinel: producer is done

    # ── Consumer thread ───────────────────────────────────────────────────────

    def _consumer(self, total: int, q: queue.Queue) -> None:
        done = 0
        chunk_end: Optional[float] = None
        while True:
            item = q.get()
            if item is None:
                break  # sentinel received

            # Enforce minimum gap between chunks. chunk_end marks when the
            # previous chunk finished. q.get() already waited for synthesis,
            # so we only sleep the time still remaining up to CHUNK_MIN_GAP.
            if chunk_end is not None:
                remaining = CHUNK_MIN_GAP - (time.monotonic() - chunk_end)
                if remaining > 0:
                    self._stop_event.wait(timeout=remaining)
            if self._stop_event.is_set():
                break

            pcm_path: Path = item
            self._play_pcm(pcm_path)
            chunk_end = time.monotonic()
            done += 1

            if self.on_chunk_progress:
                from gi.repository import GLib
                GLib.idle_add(self.on_chunk_progress, done, total)

        # Mark as no longer speaking once consumer finishes
        self._speaking = False
        self._notify_speaking(False)

        if not self._stop_event.is_set() and self.on_done:
            from gi.repository import GLib
            GLib.idle_add(self.on_done)

    # ── Synthesis & playback helpers ──────────────────────────────────────────

    def _synthesize(
        self, text: str, model_path: Path, speed: float, piper: str
    ) -> Optional[bytes]:
        """Run piper for a single chunk and return raw PCM bytes, or None on failure."""
        cmd = [
            piper,
            "--model", str(model_path),
            "--output-raw",
            "--length-scale", f"{1.0 / speed:.4f}",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._current_piper = proc
            stdout, _ = proc.communicate(text.encode("utf-8"))
            self._current_piper = None
            return stdout if proc.returncode == 0 else None
        except Exception:
            self._current_piper = None
            return None

    def _play_pcm(self, pcm_path: Path) -> None:
        """Play a raw PCM file via aplay, blocking until done (or stopped/paused)."""
        if self._stop_event.is_set():
            return
        cmd = [
            "aplay",
            "-r", str(APLAY_RATE),
            "-f", APLAY_FORMAT,
            "-t", "raw",
            str(pcm_path),
        ]
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
            self._current_aplay = proc
            proc.wait()  # SIGSTOP pauses this wait; SIGCONT resumes it
            self._current_aplay = None
        except Exception:
            self._current_aplay = None

    # ── Utility helpers ───────────────────────────────────────────────────────

    def _notify_speaking(self, state: bool) -> None:
        if self.on_speaking_changed:
            from gi.repository import GLib
            GLib.idle_add(self.on_speaking_changed, state)

    def _emit(self, cb_name: str, i18n_key: str) -> None:
        """Emit a callback with a translated string via GLib.idle_add."""
        cb = getattr(self, cb_name, None)
        if cb:
            from gi.repository import GLib
            from ..i18n import _
            GLib.idle_add(cb, _(i18n_key))

    @staticmethod
    def _signal_process(proc: Optional[subprocess.Popen], sig: int) -> None:
        if proc is not None:
            try:
                os.kill(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    @staticmethod
    def _terminate_process(proc: Optional[subprocess.Popen]) -> None:
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass


# ── Module-level helpers ──────────────────────────────────────────────────────

def split_chunks(text: str, min_len: int = CHUNK_MIN_LEN) -> list[str]:
    """Split text into sentence-level chunks for Piper.

    Splits after sentence-ending punctuation (.!?) or on paragraph breaks
    (two or more consecutive newlines).  Short fragments (< min_len chars)
    are merged into the preceding chunk to avoid synthesizing isolated words,
    which would sound choppy and waste cache space.

    The sentence-ending punctuation is kept with its chunk — Piper uses it for
    prosody (intonation and pauses), so stripping it would degrade audio quality.
    """
    # Split on sentence boundaries, preserving the punctuation in the left part
    raw_parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)

    chunks: list[str] = []
    buffer = ""
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        buffer = f"{buffer} {part}".strip() if buffer else part
        if len(buffer) >= min_len:
            chunks.append(buffer)
            buffer = ""

    # Flush any remaining text (even if shorter than min_len)
    if buffer:
        if chunks:
            chunks[-1] = f"{chunks[-1]} {buffer}"
        else:
            chunks.append(buffer)

    return chunks


def _get_piper_bin() -> Optional[str]:
    """Locate the piper binary, checking PATH and common install locations."""
    candidates = [
        "piper",
        str(Path.home() / ".local" / "bin" / "piper"),
    ]
    for candidate in candidates:
        if shutil.which(candidate) or Path(candidate).is_file():
            return candidate
    return None
