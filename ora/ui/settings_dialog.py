# ora/ui/settings_dialog.py
# Modal settings dialog opened via the ⚙ button in the main window.
#
# All changes take effect immediately and are persisted to config.json on each
# interaction — there is no "Save" button.  The dialog only has a "Close" button.
#
# The dialog communicates back to the app via the on_voice_changed and
# on_lang_changed callbacks so the main window voice dropdown stays in sync.

from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..i18n import _
from ..constants import LANG_NAMES
from ..core.cache import CacheManager
from ..core.voices import VoiceManager
from .. import config as cfg


class SettingsDialog(Gtk.Dialog):
    """Modal settings dialog for Ora.

    Parameters
    ----------
    parent : Gtk.Window
        Transient parent (for window manager placement).
    cache : CacheManager
        Shared cache instance — used to show usage and clear cache.
    voices : VoiceManager
        Shared voice manager — used to list/delete installed voices.
    on_voice_changed : callable
        Called with the new voice_key string whenever the active voice changes.
    on_lang_changed : callable
        Called with the new language code whenever the voice language changes.
    on_clipboard_toggled : callable
        Called with (enabled: bool) when the auto-clipboard checkbox changes.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        cache: CacheManager,
        voices: VoiceManager,
        on_voice_changed: Callable[[str], None],
        on_lang_changed: Callable[[str], None],
        on_clipboard_toggled: Callable[[bool], None],
    ) -> None:
        super().__init__(
            title=_("settings_title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(460, -1)
        self.set_resizable(False)

        self._cache = cache
        self._voices = voices
        self._on_voice_changed = on_voice_changed
        self._on_lang_changed = on_lang_changed
        self._on_clipboard_toggled = on_clipboard_toggled

        self._cfg = cfg.load()
        self._build_ui()
        self.show_all()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        content = self.get_content_area()
        content.set_spacing(0)
        content.set_border_width(0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_border_width(16)
        content.add(main_box)

        # ── Voice language & active voice ─────────────────────────────────────
        main_box.pack_start(self._make_section_label(_("settings_lang")), False, False, 4)
        self._lang_combo = Gtk.ComboBoxText()
        for code, name in sorted(LANG_NAMES.items()):
            self._lang_combo.append(code, name)
        self._lang_combo.set_active_id(self._cfg.get("lang", "fr"))
        self._lang_combo.connect("changed", self._on_lang_changed_internal)
        main_box.pack_start(self._lang_combo, False, False, 4)

        main_box.pack_start(self._make_section_label(_("settings_voice")), False, False, 4)
        voice_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._voice_combo = Gtk.ComboBoxText()
        self._voice_combo.set_hexpand(True)
        self._voice_combo.connect("changed", self._on_voice_changed_internal)
        voice_row.pack_start(self._voice_combo, True, True, 0)
        self._catalogue_spinner = Gtk.Spinner()
        self._catalogue_spinner.set_tooltip_text(_("settings_loading_catalogue"))
        voice_row.pack_start(self._catalogue_spinner, False, False, 0)
        self._populate_voice_combo()
        main_box.pack_start(voice_row, False, False, 8)

        # ── Installed voices list ─────────────────────────────────────────────
        main_box.pack_start(self._make_section_label(_("settings_installed_voices")), False, False, 4)
        self._installed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._rebuild_installed_list()
        main_box.pack_start(self._installed_box, False, False, 8)

        main_box.pack_start(Gtk.Separator(), False, False, 8)

        # ── Cache section ─────────────────────────────────────────────────────
        main_box.pack_start(self._make_section_label(_("settings_cache")), False, False, 4)

        cache_grid = Gtk.Grid(column_spacing=16, row_spacing=6)

        cache_grid.attach(self._make_label(_("settings_cache_max")), 0, 0, 1, 1)
        self._cache_max_combo = Gtk.ComboBoxText()
        for mb in (100, 200, 500, 1024):
            label = _("mb_unit", mb) if mb < 1024 else _("mb_unit", mb)
            # Show "1024 MB" as "1 GB" for readability
            display = "1 Go" if mb == 1024 and _("mb_unit", 1).startswith("1 Mo") else (
                       "1 GB" if mb == 1024 else _("mb_unit", mb))
            self._cache_max_combo.append(str(mb), display)
        self._cache_max_combo.set_active_id(str(self._cfg.get("cache_max_mb", 200)))
        if not self._cache_max_combo.get_active_id():
            self._cache_max_combo.set_active(1)  # default 200 MB
        self._cache_max_combo.connect("changed", self._on_cache_max_changed)
        cache_grid.attach(self._cache_max_combo, 1, 0, 1, 1)

        cache_grid.attach(self._make_label(_("settings_cache_used")), 0, 1, 1, 1)
        self._cache_used_lbl = Gtk.Label(label=self._cache_used_str())
        self._cache_used_lbl.set_halign(Gtk.Align.START)
        cache_grid.attach(self._cache_used_lbl, 1, 1, 1, 1)

        main_box.pack_start(cache_grid, False, False, 4)

        btn_clear = Gtk.Button(label=_("settings_cache_clear"))
        btn_clear.connect("clicked", self._on_cache_clear)
        main_box.pack_start(btn_clear, False, False, 8)

        main_box.pack_start(Gtk.Separator(), False, False, 8)

        # ── Clipboard watcher section ─────────────────────────────────────────
        main_box.pack_start(self._make_section_label(_("settings_clipboard_section")), False, False, 4)

        self._clip_auto_check = Gtk.CheckButton(label=_("settings_clipboard_auto"))
        self._clip_auto_check.set_active(self._cfg.get("clipboard_enabled", False))
        self._clip_auto_check.connect("toggled", self._on_clipboard_auto_toggled)
        main_box.pack_start(self._clip_auto_check, False, False, 2)

        self._clip_startup_check = Gtk.CheckButton(label=_("settings_clipboard_startup"))
        self._clip_startup_check.set_active(self._cfg.get("clipboard_autostart", False))
        self._clip_startup_check.connect("toggled", self._on_clipboard_startup_toggled)
        main_box.pack_start(self._clip_startup_check, False, False, 8)

        # ── Close button ──────────────────────────────────────────────────────
        btn_close = Gtk.Button(label=_("settings_close"))
        btn_close.connect("clicked", lambda _: self.destroy())
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.pack_end(btn_close, False, False, 0)
        main_box.pack_start(btn_box, False, False, 4)

    # ── Voice list helpers ────────────────────────────────────────────────────

    def _populate_voice_combo(self) -> None:
        """Fill the active-voice combo with all catalogue voices for the language."""
        self._voice_combo.remove_all()
        lang = self._cfg.get("lang", "fr")
        installed_set = set(self._voices.installed_voices())

        if not self._voices.catalogue_loaded:
            self._catalogue_spinner.start()
            self._catalogue_spinner.show()
            available = list(installed_set)
        else:
            self._catalogue_spinner.stop()
            self._catalogue_spinner.hide()
            available = [v for v in self._voices.voices_data if v.startswith(lang)]

        if not available:
            self._voice_combo.append("none", _("settings_no_installed"))
            self._voice_combo.set_active(0)
            return
        for v in sorted(available):
            meta = self._voices.voices_data.get(v, {})
            marker = "✓ " if v in installed_set else "⬇ "
            display = f"{marker}{meta.get('name', v)}  [{meta.get('quality','')}]"
            self._voice_combo.append(v, display)
        saved = self._cfg.get("voice", "")
        if not self._voice_combo.set_active_id(saved):
            self._voice_combo.set_active(0)

    def refresh_voice_combo(self) -> None:
        """Called by the app when the catalogue fetch completes."""
        self._populate_voice_combo()

    def _rebuild_installed_list(self) -> None:
        """Rebuild the installed-voice rows (name + size + delete button)."""
        for child in self._installed_box.get_children():
            self._installed_box.remove(child)

        installed = self._voices.installed_voices()
        if not installed:
            lbl = Gtk.Label(label=_("settings_no_installed"))
            lbl.set_halign(Gtk.Align.START)
            self._installed_box.pack_start(lbl, False, False, 0)
            self._installed_box.show_all()
            return

        for v in installed:
            p = self._voices.model_path(v)
            size_mb = (p.stat().st_size // (1024 * 1024)) if p.exists() else 0
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            name_lbl = Gtk.Label(label=v)
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_xalign(0)
            row.pack_start(name_lbl, True, True, 0)

            size_lbl = Gtk.Label(label=_("mb_unit", size_mb))
            size_lbl.get_style_context().add_class("voice-label")
            row.pack_start(size_lbl, False, False, 0)

            del_btn = Gtk.Button(label=_("settings_delete_voice"))
            del_btn.get_style_context().add_class("btn-danger")
            del_btn.connect("clicked", lambda _b, key=v: self._on_delete_voice(key))
            row.pack_start(del_btn, False, False, 0)

            self._installed_box.pack_start(row, False, False, 2)

        self._installed_box.show_all()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_lang_changed_internal(self, combo: Gtk.ComboBoxText) -> None:
        lang = combo.get_active_id()
        if not lang:
            return
        self._cfg["lang"] = lang
        cfg.save(self._cfg)
        self._populate_voice_combo()
        self._on_lang_changed(lang)

    def _on_voice_changed_internal(self, combo: Gtk.ComboBoxText) -> None:
        voice = combo.get_active_id()
        if not voice or voice == "none":
            return
        self._cfg["voice"] = voice
        cfg.save(self._cfg)
        self._on_voice_changed(voice)

    def _on_delete_voice(self, voice_key: str) -> None:
        """Confirm with user, then delete the voice model files."""
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("settings_delete_voice_confirm", voice_key),
        )
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return

        self._voices.delete_voice(voice_key)

        # If the deleted voice was active, switch to the first remaining one
        if self._cfg.get("voice") == voice_key:
            remaining = self._voices.installed_voices()
            new_voice = remaining[0] if remaining else ""
            self._cfg["voice"] = new_voice
            cfg.save(self._cfg)
            if new_voice:
                self._on_voice_changed(new_voice)

        self._rebuild_installed_list()
        self._populate_voice_combo()

    def _on_cache_max_changed(self, combo: Gtk.ComboBoxText) -> None:
        mb_str = combo.get_active_id()
        if mb_str:
            mb = int(mb_str)
            self._cfg["cache_max_mb"] = mb
            cfg.save(self._cfg)
            self._cache.set_max_mb(mb)

    def _on_cache_clear(self, _btn: Gtk.Button) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("settings_cache_clear_confirm"),
        )
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            self._cache.clear()
            self._cache_used_lbl.set_text(self._cache_used_str())

    def _on_clipboard_auto_toggled(self, check: Gtk.CheckButton) -> None:
        enabled = check.get_active()
        self._cfg["clipboard_enabled"] = enabled
        cfg.save(self._cfg)
        self._on_clipboard_toggled(enabled)

    def _on_clipboard_startup_toggled(self, check: Gtk.CheckButton) -> None:
        self._cfg["clipboard_autostart"] = check.get_active()
        cfg.save(self._cfg)

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _cache_used_str(self) -> str:
        mb = self._cache.total_size() // (1024 * 1024)
        return _("mb_unit", mb)

    @staticmethod
    def _make_section_label(text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text.upper())
        lbl.get_style_context().add_class("section-title")
        lbl.set_halign(Gtk.Align.START)
        return lbl

    @staticmethod
    def _make_label(text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        return lbl
