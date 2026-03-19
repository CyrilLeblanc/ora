# ora/clipboard.py
# Clipboard watcher: polls the system clipboard every 500 ms via GLib.timeout_add.
#
# Design note: Gtk.Clipboard must be accessed from the GTK main thread.
# Instead of a raw Python thread (which would require locking), we use
# GLib.timeout_add to schedule the poll inside the GTK event loop.
# This gives us the "background daemon" feel while staying GTK-safe.
#
# The watcher stores a hash of the last seen clipboard text (not the text
# itself) to avoid keeping large strings in memory.

import hashlib
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..constants import CLIPBOARD_POLL_MS


class ClipboardWatcher:
    """Polls the GTK clipboard at a fixed interval and fires a callback on change.

    Usage:
        watcher = ClipboardWatcher(display, on_new_text=my_callback)
        watcher.start()   # enable polling
        watcher.stop()    # disable polling
    """

    def __init__(
        self,
        display: Gtk.Widget,
        on_new_text: Callable[[str], None],
    ) -> None:
        self._display = display
        self._on_new_text = on_new_text
        self._last_hash: Optional[str] = None
        self._timeout_id: Optional[int] = None
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin polling the clipboard."""
        if self._running:
            return
        self._running = True
        # Seed the last-seen hash so the first tick doesn't trigger immediately
        self._seed_current_content()
        self._timeout_id = GLib.timeout_add(CLIPBOARD_POLL_MS, self._poll)

    def stop(self) -> None:
        """Stop polling the clipboard."""
        self._running = False
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def is_running(self) -> bool:
        return self._running

    # ── Internal polling ──────────────────────────────────────────────────────

    def _poll(self) -> bool:
        """Called by GLib every CLIPBOARD_POLL_MS ms.  Returns True to keep polling."""
        if not self._running:
            return False  # unschedule

        clipboard = Gtk.Clipboard.get_default(self._display.get_display())
        text = clipboard.wait_for_text()

        if text and text.strip():
            h = _text_hash(text)
            if h != self._last_hash:
                self._last_hash = h
                self._on_new_text(text.strip())

        return True  # reschedule

    def _seed_current_content(self) -> None:
        """Capture current clipboard hash so we don't trigger on stale content."""
        try:
            clipboard = Gtk.Clipboard.get_default(self._display.get_display())
            text = clipboard.wait_for_text()
            if text:
                self._last_hash = _text_hash(text)
        except Exception:
            pass


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
