# ora/app.py
# Main application window — wires together all core modules and the UI.
#
# OraApp owns one instance of each core module and is the single place where
# callbacks between modules are connected.  GTK widget construction is done
# in _build_ui() and its sub-methods, grouped by window section.
#
# Playback state machine:
#   IDLE    → speak()  → PLAYING
#   PLAYING → pause()  → PAUSED
#   PAUSED  → resume() → PLAYING
#   PLAYING | PAUSED → stop() → IDLE

import threading
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from .constants import CSS, LANG_NAMES
from .i18n import _
from . import config as cfg
from .core.cache import CacheManager
from .core.voices import VoiceManager
from .core.tts import TTSEngine
from .core.clipboard import ClipboardWatcher
from .ui.settings_dialog import SettingsDialog


class OraApp(Gtk.Window):
    """Main Ora application window."""

    def __init__(self) -> None:
        super().__init__(title="Ora")
        self.set_default_size(700, 540)
        self.connect("destroy", Gtk.main_quit)

        # ── Apply dark theme CSS ───────────────────────────────────────────────
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # ── Core modules ──────────────────────────────────────────────────────
        initial_cfg = cfg.load()
        self._cfg = initial_cfg

        self._cache = CacheManager(max_mb=initial_cfg.get("cache_max_mb", 200))
        self._voices = VoiceManager()
        self._tts = TTSEngine(self._cache)
        self._clipboard_watcher = None  # type: Optional[ClipboardWatcher]  # created after window shown

        # Wire TTS callbacks
        self._tts.on_speaking_changed = self._on_speaking_changed
        self._tts.on_chunk_progress   = self._on_chunk_progress
        self._tts.on_done             = self._on_tts_done
        self._tts.on_status           = self._set_status
        self._tts.on_error            = self._show_error

        # ── Build and show UI ─────────────────────────────────────────────────
        self._build_ui()
        self.show_all()
        self.dl_progress.hide()

        # ── Deferred initialisation ───────────────────────────────────────────
        # Fetch the voice catalogue in the background; populate UI when done
        threading.Thread(
            target=self._voices.fetch_catalogue,
            args=(
                lambda: GLib.idle_add(self._populate_languages, False),
                lambda: GLib.idle_add(self._populate_languages, True),
            ),
            daemon=True,
        ).start()

        # Auto-start clipboard watcher if configured
        if initial_cfg.get("clipboard_autostart", False):
            GLib.idle_add(self._start_clipboard_watcher)

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        root.pack_start(self._build_title_bar(), False, False, 0)
        root.pack_start(self._build_text_area(), True, True, 0)
        root.pack_start(self._build_chunk_progress(), False, False, 0)
        root.pack_start(self._build_button_row(), False, False, 0)
        root.pack_start(self._build_speed_row(), False, False, 0)
        root.pack_start(self._build_status_bar(), False, False, 0)

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _build_title_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.get_style_context().add_class("title-bar")
        bar.set_border_width(4)

        title = Gtk.Label(label=_("app_title"))
        title.get_style_context().add_class("title-label")
        title.set_halign(Gtk.Align.START)
        bar.pack_start(title, True, True, 0)

        btn_settings = Gtk.Button(label=_("btn_settings"))
        btn_settings.get_style_context().add_class("btn-settings")
        btn_settings.connect("clicked", self._on_open_settings)
        bar.pack_end(btn_settings, False, False, 0)

        return bar

    # ── Text area ─────────────────────────────────────────────────────────────

    def _build_text_area(self) -> Gtk.ScrolledWindow:
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_border_width(8)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        self.textview.set_top_margin(12)
        self.textview.set_bottom_margin(12)
        self.textview.get_buffer().connect("changed", lambda _: self._autosave_text())

        scroll.add(self.textview)
        return scroll

    # ── Chunk progress bar ────────────────────────────────────────────────────

    def _build_chunk_progress(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.set_border_width(4)
        row.set_margin_start(8)
        row.set_margin_end(8)

        self.chunk_progress = Gtk.ProgressBar()
        self.chunk_progress.get_style_context().add_class("chunk-progress")
        self.chunk_progress.set_fraction(0.0)
        self.chunk_progress.set_show_text(True)
        self.chunk_progress.set_text("")

        row.pack_start(self.chunk_progress, True, True, 0)
        return row

    # ── Button row ────────────────────────────────────────────────────────────

    def _build_button_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_border_width(8)

        # Restart / back-to-start
        self.btn_restart = Gtk.Button(label=_("btn_restart"))
        self.btn_restart.get_style_context().add_class("btn-secondary")
        self.btn_restart.connect("clicked", self._on_restart)
        self.btn_restart.set_sensitive(False)

        # Pause/Resume toggle — label changes based on state
        self.btn_pause = Gtk.Button(label=_("btn_pause"))
        self.btn_pause.get_style_context().add_class("btn-pause")
        self.btn_pause.connect("clicked", self._on_pause_resume)
        self.btn_pause.set_sensitive(False)

        # Stop
        self.btn_stop = Gtk.Button(label=_("btn_stop"))
        self.btn_stop.get_style_context().add_class("btn-stop")
        self.btn_stop.connect("clicked", self._on_stop)
        self.btn_stop.set_sensitive(False)

        # Read clipboard into text area and play
        self.btn_clip_read = Gtk.Button(label=_("btn_clipboard_read"))
        self.btn_clip_read.get_style_context().add_class("btn-secondary")
        self.btn_clip_read.connect("clicked", self._on_read_clipboard)

        # Clear text area
        btn_clear = Gtk.Button(label=_("btn_clear"))
        btn_clear.get_style_context().add_class("btn-icon")
        btn_clear.connect("clicked", lambda _: self.textview.get_buffer().set_text(""))

        # Play (hidden while playing; shown in IDLE state via _on_speaking_changed)
        self.btn_play = Gtk.Button(label=_("btn_play"))
        self.btn_play.get_style_context().add_class("btn-play")
        self.btn_play.connect("clicked", self._on_play)

        row.pack_start(self.btn_play,     True,  True,  0)
        row.pack_start(self.btn_restart,  False, False, 0)
        row.pack_start(self.btn_pause,    True,  True,  0)
        row.pack_start(self.btn_stop,     True,  True,  0)
        row.pack_start(self.btn_clip_read, False, False, 0)
        row.pack_start(btn_clear,         False, False, 0)

        return row

    # ── Speed row ─────────────────────────────────────────────────────────────

    def _build_speed_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.get_style_context().add_class("control-row")

        lbl = Gtk.Label(label=_("lbl_speed"))
        lbl.get_style_context().add_class("speed-label")
        row.pack_start(lbl, False, False, 0)

        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.0, 0.1)
        self.speed_scale.set_value(self._cfg.get("speed", 1.0))
        self.speed_scale.set_size_request(200, -1)
        self.speed_scale.set_draw_value(True)
        self.speed_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.speed_scale.add_mark(0.5, Gtk.PositionType.BOTTOM, "×0.5")
        self.speed_scale.add_mark(1.0, Gtk.PositionType.BOTTOM, "×1")
        self.speed_scale.add_mark(2.0, Gtk.PositionType.BOTTOM, "×2")
        self.speed_scale.connect("value-changed", lambda _: self._autosave_speed())
        row.pack_start(self.speed_scale, True, True, 0)

        return row

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.get_style_context().add_class("status-bar")

        # Clipboard indicator dot — clicking toggles the watcher
        self.clipboard_dot = Gtk.Button(label=_("clipboard_off"))
        self.clipboard_dot.get_style_context().add_class("clipboard-dot-off")
        self.clipboard_dot.set_relief(Gtk.ReliefStyle.NONE)
        self.clipboard_dot.set_tooltip_text(_("settings_clipboard_section"))
        self.clipboard_dot.connect("clicked", self._on_clipboard_dot_clicked)
        bar.pack_start(self.clipboard_dot, False, False, 0)

        # Installed-voice quick-switch dropdown
        self.status_voice_combo = Gtk.ComboBoxText()
        self.status_voice_combo.set_tooltip_text(_("lbl_voice"))
        self.status_voice_combo.connect("changed", self._on_status_voice_changed)
        bar.pack_start(self.status_voice_combo, False, False, 0)

        # Status message
        self.status_lbl = Gtk.Label(label=_("loading"))
        self.status_lbl.get_style_context().add_class("status-label")
        self.status_lbl.set_halign(Gtk.Align.START)
        bar.pack_start(self.status_lbl, True, True, 0)

        # Download progress bar (hidden by default)
        self.dl_progress = Gtk.ProgressBar()
        self.dl_progress.get_style_context().add_class("dl-progress")
        self.dl_progress.set_size_request(120, -1)
        self.dl_progress.set_valign(Gtk.Align.CENTER)
        self.dl_progress.set_no_show_all(True)
        bar.pack_end(self.dl_progress, False, False, 8)

        return bar

    # =========================================================================
    # Voice catalogue population
    # =========================================================================

    def _populate_languages(self, offline: bool) -> None:
        """Populate the status-bar voice combo with installed voices.

        Called from GLib.idle_add after catalogue fetch completes.
        """
        self._populate_status_voice_combo()

        # Restore previously selected voice
        saved_voice = self._cfg.get("voice", "")
        if saved_voice:
            self.status_voice_combo.set_active_id(saved_voice)

        # Restore text
        if self._cfg.get("text"):
            self.textview.get_buffer().set_text(self._cfg["text"])
            # Suppress the save triggered by set_text (nothing actually changed)

        if offline:
            self._set_status(_("offline"))
        else:
            self._set_status(_("ready"))

    def _populate_status_voice_combo(self) -> None:
        """Rebuild the status-bar voice dropdown from installed voices."""
        # Block the signal temporarily to avoid spurious voice-change callbacks
        self.status_voice_combo.handler_block_by_func(self._on_status_voice_changed)
        self.status_voice_combo.remove_all()

        installed = self._voices.installed_voices()
        for v in installed:
            meta = self._voices.voices_data.get(v, {})
            display = f"{v}  [{meta.get('quality','')}]" if meta else v
            self.status_voice_combo.append(v, display)

        if not installed:
            self.status_voice_combo.append("none", "—")
            self.status_voice_combo.set_active(0)

        self.status_voice_combo.handler_unblock_by_func(self._on_status_voice_changed)

    # =========================================================================
    # TTS callbacks
    # =========================================================================

    def _on_speaking_changed(self, speaking: bool) -> None:
        """Update button states to reflect playback state."""
        if speaking:
            self.btn_play.set_sensitive(False)
            self.btn_play.set_no_show_all(True)
            self.btn_play.hide()

            self.btn_pause.set_sensitive(True)
            self.btn_pause.set_label(_("btn_pause"))
            self.btn_pause.set_no_show_all(False)
            self.btn_pause.show()

            self.btn_stop.set_sensitive(True)
            self.btn_restart.set_sensitive(True)
        else:
            # Back to IDLE
            self.btn_pause.set_sensitive(False)
            self.btn_stop.set_sensitive(False)
            self.btn_restart.set_sensitive(False)

            self.btn_play.set_no_show_all(False)
            self.btn_play.show()
            self.btn_play.set_sensitive(True)

    def _on_chunk_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.chunk_progress.set_fraction(done / total)
            self.chunk_progress.set_text(_("chunk_progress", done, total))

    def _on_tts_done(self) -> None:
        self.chunk_progress.set_fraction(0.0)
        self.chunk_progress.set_text("")
        self._set_status(_("ready"))

    # =========================================================================
    # Button callbacks
    # =========================================================================

    def _on_play(self, _btn: Gtk.Button) -> None:
        text = self._get_text()
        if not text:
            self._set_status(_("no_text"))
            return
        model = self._resolve_model_for_play()
        if model is None:
            return
        speed = self.speed_scale.get_value()
        self._tts.speak(text, model, speed)

    def _on_pause_resume(self, _btn: Gtk.Button) -> None:
        if self._tts.is_paused:
            self._tts.resume()
            self.btn_pause.set_label(_("btn_pause"))
            self.btn_pause.get_style_context().remove_class("btn-play")
            self.btn_pause.get_style_context().add_class("btn-pause")
        else:
            self._tts.pause()
            self.btn_pause.set_label(_("btn_resume"))
            self.btn_pause.get_style_context().remove_class("btn-pause")
            self.btn_pause.get_style_context().add_class("btn-play")

    def _on_stop(self, _btn: Gtk.Button) -> None:
        self._tts.stop()
        self.chunk_progress.set_fraction(0.0)
        self.chunk_progress.set_text("")
        self._set_status(_("stopped"))

    def _on_restart(self, _btn: Gtk.Button) -> None:
        model = self._resolve_model_for_play()
        if model is None:
            return
        self._tts.restart(model, self.speed_scale.get_value())

    def _on_read_clipboard(self, _btn: Gtk.Button) -> None:
        """Read clipboard text into the text area and start playback."""
        cb = Gtk.Clipboard.get_default(self.get_display())
        text = cb.wait_for_text()
        if not text or not text.strip():
            self._set_status(_("clipboard_empty"))
            return
        self.textview.get_buffer().set_text(text)
        self._on_play(None)

    def _on_open_settings(self, _btn: Gtk.Button) -> None:
        dlg = SettingsDialog(
            parent=self,
            cache=self._cache,
            voices=self._voices,
            on_voice_changed=self._on_settings_voice_changed,
            on_lang_changed=self._on_settings_lang_changed,
            on_clipboard_toggled=self._on_settings_clipboard_toggled,
        )
        dlg.run()
        dlg.destroy()
        # Refresh status voice combo after any changes in settings
        self._populate_status_voice_combo()
        saved_voice = cfg.load().get("voice", "")
        if saved_voice:
            self.status_voice_combo.set_active_id(saved_voice)

    def _on_status_voice_changed(self, combo: Gtk.ComboBoxText) -> None:
        voice_key = combo.get_active_id()
        if not voice_key or voice_key == "none":
            return
        self._cfg["voice"] = voice_key
        cfg.save(self._cfg)
        if self._voices.is_installed(voice_key):
            self._set_status(_("voice_ready", voice_key))
        else:
            key = "not_installed_offline" if self._voices.offline else "not_installed_online"
            self._set_status(_(key))

    def _on_clipboard_dot_clicked(self, _btn: Gtk.Button) -> None:
        """Toggle the clipboard watcher on/off."""
        if self._clipboard_watcher and self._clipboard_watcher.is_running():
            self._stop_clipboard_watcher()
        else:
            self._start_clipboard_watcher()

    # ── Settings dialog callbacks ─────────────────────────────────────────────

    def _on_settings_voice_changed(self, voice_key: str) -> None:
        self._cfg["voice"] = voice_key
        cfg.save(self._cfg)
        self.status_voice_combo.set_active_id(voice_key)
        if self._voices.is_installed(voice_key):
            self._set_status(_("voice_ready", voice_key))

    def _on_settings_lang_changed(self, lang: str) -> None:
        self._cfg["lang"] = lang
        cfg.save(self._cfg)
        # Rebuild status voice combo so it reflects voices for the new language
        self._populate_status_voice_combo()

    def _on_settings_clipboard_toggled(self, enabled: bool) -> None:
        self._cfg["clipboard_enabled"] = enabled
        cfg.save(self._cfg)
        if enabled:
            self._start_clipboard_watcher()
        else:
            self._stop_clipboard_watcher()

    # =========================================================================
    # Clipboard watcher helpers
    # =========================================================================

    def _start_clipboard_watcher(self) -> None:
        if self._clipboard_watcher is None:
            self._clipboard_watcher = ClipboardWatcher(
                display=self,
                on_new_text=self._on_clipboard_new_text,
            )
        self._clipboard_watcher.start()
        self._update_clipboard_dot(active=True)

    def _stop_clipboard_watcher(self) -> None:
        if self._clipboard_watcher:
            self._clipboard_watcher.stop()
        self._update_clipboard_dot(active=False)

    def _on_clipboard_new_text(self, text: str) -> None:
        """Triggered by the clipboard watcher when new content is detected.

        Interrupts current playback and starts fresh with the clipboard text.
        This runs in the GTK main thread (via GLib.timeout_add).
        """
        self.textview.get_buffer().set_text(text)
        self._set_status(_("clipboard_triggered"))
        # Brief toast: revert status after 2 seconds
        GLib.timeout_add(2000, lambda: self._set_status(_("ready")) or False)

        model = self._resolve_model_for_play()
        if model is None:
            return
        speed = self.speed_scale.get_value()
        self._tts.speak(text, model, speed)

    def _update_clipboard_dot(self, active: bool) -> None:
        ctx = self.clipboard_dot.get_style_context()
        if active:
            ctx.remove_class("clipboard-dot-off")
            ctx.add_class("clipboard-dot-on")
        else:
            ctx.remove_class("clipboard-dot-on")
            ctx.add_class("clipboard-dot-off")

    # =========================================================================
    # Model resolution & download
    # =========================================================================

    def _resolve_model_for_play(self):
        """Return the model Path for the currently selected voice.

        If the model is not installed and we are online, download it in a
        background thread and return None (playback will not start yet).
        Download completion will call _on_model_downloaded.
        """
        voice_key = self.status_voice_combo.get_active_id()
        if not voice_key or voice_key == "none":
            self._show_error(_("no_voice"))
            return None

        model_path = self._voices.is_installed(voice_key)
        if model_path:
            return model_path

        if self._voices.offline:
            self._show_error(_("not_installed_offline"))
            return None

        # Kick off a background download
        self._set_status(_("downloading_voice"))
        threading.Thread(
            target=self._voices.download_voice,
            args=(
                voice_key,
                lambda: GLib.idle_add(self._set_status, _("downloading_onnx")),
                lambda: GLib.idle_add(self._set_status, _("downloading_config")),
                lambda frac: GLib.idle_add(self._on_download_progress, frac),
                lambda path: GLib.idle_add(self._on_model_downloaded, voice_key, path),
                lambda exc: GLib.idle_add(self._on_download_error, exc),
            ),
            daemon=True,
        ).start()
        GLib.idle_add(self.dl_progress.set_fraction, 0.0)
        GLib.idle_add(self.dl_progress.show)
        return None

    def _on_download_progress(self, frac: float) -> None:
        self.dl_progress.set_fraction(frac)

    def _on_model_downloaded(self, voice_key: str, model_path) -> None:
        self.dl_progress.hide()
        self._set_status(_("installed", voice_key))
        self._populate_status_voice_combo()
        self.status_voice_combo.set_active_id(voice_key)

    def _on_download_error(self, exc: Exception) -> None:
        self.dl_progress.hide()
        self._set_status(_("dl_error", exc))

    # =========================================================================
    # Utilities
    # =========================================================================

    def _get_text(self) -> str:
        buf = self.textview.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip()

    def _set_status(self, msg: str) -> None:
        self.status_lbl.set_text(msg)

    def _show_error(self, msg: str) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=msg,
        )
        dlg.run()
        dlg.destroy()

    def _autosave_text(self) -> None:
        self._cfg["text"] = self._get_text()
        cfg.save(self._cfg)

    def _autosave_speed(self) -> None:
        self._cfg["speed"] = self.speed_scale.get_value()
        cfg.save(self._cfg)
