#!/usr/bin/env python3
"""
Ora — TTS avec Piper (neural, offline)
Dépendances :
  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 espeak-ng alsa-utils
  pip install piper-tts pathvalidate --break-system-packages
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

import threading
import subprocess
import json
import os
import locale
import urllib.request
import shutil
from pathlib import Path


# ── Constantes ───────────────────────────────────────────────────────────────

VOICES_JSON_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json"
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
MODELS_DIR = Path.home() / ".local" / "share" / "ora" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE  = Path.home() / ".local" / "share" / "ora" / "config.json"
AUDIO_CACHE  = Path.home() / ".local" / "share" / "ora" / "last_audio.raw"

# ── Langue de l'interface ─────────────────────────────────────────────────────

def _detect_ui_lang():
    for src in (os.environ.get("LANG", ""), os.environ.get("LANGUAGE", ""),
                locale.getlocale()[0] or ""):
        if src.startswith("fr"):
            return "fr"
    return "en"

UI_LANG = _detect_ui_lang()

STRINGS = {
    "lbl_lang":             {"fr": "Langue",                    "en": "Language"},
    "lbl_voice":            {"fr": "Voix",                      "en": "Voice"},
    "lbl_speed":            {"fr": "Vitesse",                   "en": "Speed"},
    "btn_play":             {"fr": "▶  Lire",                   "en": "▶  Play"},
    "btn_clipboard":        {"fr": "📋  Presse-papier",         "en": "📋  Clipboard"},
    "btn_stop":             {"fr": "⏹  Stop",                   "en": "⏹  Stop"},
    "loading":              {"fr": "Chargement…",               "en": "Loading…"},
    "fetching":             {"fr": "Récupération des voix…",    "en": "Fetching voices…"},
    "ready":                {"fr": "Prêt.",                     "en": "Ready."},
    "offline":              {"fr": "⚠ Hors ligne — voix installées uniquement.",
                             "en": "⚠ Offline — installed voices only."},
    "voice_ready":          {"fr": "Voix prête : {}",           "en": "Voice ready: {}"},
    "not_installed_offline":{"fr": "Voix non installée — connexion requise",
                             "en": "Voice not installed — connection required"},
    "not_installed_online": {"fr": "Voix non installée — sera téléchargée à la lecture",
                             "en": "Voice not installed — will be downloaded on play"},
    "downloading_voice":    {"fr": "Téléchargement de la voix…","en": "Downloading voice…"},
    "downloading_onnx":     {"fr": "Téléchargement du modèle ONNX…",
                             "en": "Downloading ONNX model…"},
    "downloading_config":   {"fr": "Téléchargement de la config…",
                             "en": "Downloading config…"},
    "installed":            {"fr": "✓ Voix installée : {}",     "en": "✓ Voice installed: {}"},
    "dl_error":             {"fr": "Erreur téléchargement : {}", "en": "Download error: {}"},
    "synthesizing":         {"fr": "Synthèse en cours…",        "en": "Synthesizing…"},
    "no_text":              {"fr": "Aucun texte à lire.",        "en": "No text to read."},
    "clipboard_empty":      {"fr": "Presse-papier vide.",        "en": "Clipboard is empty."},
    "stopped":              {"fr": "Arrêté.",                   "en": "Stopped."},
    "error":                {"fr": "Erreur : {}",               "en": "Error: {}"},
    "no_voice":             {"fr": "Aucune voix installée.",     "en": "No voice installed."},
    "no_piper":             {
        "fr": "Binaire 'piper' introuvable.\n\nInstallez-le :\n  pip install piper-tts pathvalidate --break-system-packages",
        "en": "Binary 'piper' not found.\n\nInstall it:\n  pip install piper-tts pathvalidate --break-system-packages",
    },
}

def _(key, *args):
    s = STRINGS[key][UI_LANG]
    return s.format(*args) if args else s


# ── Mapping code langue → nom lisible ────────────────────────────────────────

LANG_NAMES = {
    "fr": "Français", "en": "English", "de": "Deutsch", "es": "Español",
    "it": "Italiano", "pt": "Português", "nl": "Nederlands", "pl": "Polski",
    "ru": "Русский", "zh": "中文", "ja": "日本語", "ko": "한국어",
    "ar": "العربية", "cs": "Čeština", "da": "Dansk", "fi": "Suomi",
    "hu": "Magyar", "nb": "Norsk", "ro": "Română", "sk": "Slovenčina",
    "sv": "Svenska", "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
    "ca": "Català", "el": "Ελληνικά", "fa": "فارسی", "is": "Íslenska",
    "ka": "ქართული", "lb": "Lëtzebuergesch", "ne": "नेपाली",
    "sr": "Српски", "sw": "Kiswahili",
}

CSS = b"""
window { background-color: #242424; }
.title-bar { background-color: #1c1c1c; padding: 8px 12px; }
.title-label { color: #ffffff; font-weight: bold; font-size: 15px; }
textview, textview text { background-color: #2e2e2e; color: #e0e0e0; font-size: 13px; }
.control-bar { background-color: #1e1e1e; padding: 8px 12px; }
.status-bar { background-color: #161616; padding: 4px 12px; }
.status-label { color: #888888; font-size: 11px; }
.voice-label { color: #aaaaaa; font-size: 11px; }
.btn-play { background-color: #2d6a4f; color: white; border-radius: 6px; padding: 6px 16px; }
.btn-play:hover { background-color: #40916c; }
.btn-stop { background-color: #7b2d2d; color: white; border-radius: 6px; padding: 6px 16px; }
.btn-stop:hover { background-color: #a33a3a; }
.btn-secondary { background-color: #3a3a3a; color: #dddddd; border-radius: 6px; padding: 6px 12px; }
.btn-secondary:hover { background-color: #4a4a4a; }
.installed-badge { color: #52b788; font-size: 11px; font-weight: bold; }
combobox { background-color: #3a3a3a; color: #dddddd; }
scale trough { background-color: #3a3a3a; }
scale highlight { background-color: #40916c; }
.dl-progress trough { background-color: #2a2a2a; border-radius: 3px; min-height: 5px; }
.dl-progress progress { background-color: #2166a0; border-radius: 3px; min-height: 5px; }
"""


class Ora(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ora")
        self.set_default_size(680, 520)
        self.connect("destroy", Gtk.main_quit)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._speaking = False
        self._proc = None
        self._proc_piper = None
        self._voices_data = {}
        self._current_model = None
        self._offline = False
        self._last_cache_key = None   # (text, model_path, speed)

        self._build_ui()
        self.show_all()

        threading.Thread(target=self._load_voices_json, daemon=True).start()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # Titre
        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_bar.get_style_context().add_class("title-bar")
        lbl = Gtk.Label(label="🔊 Ora")
        lbl.get_style_context().add_class("title-label")
        lbl.set_halign(Gtk.Align.START)
        title_bar.pack_start(lbl, True, True, 0)
        root.pack_start(title_bar, False, False, 0)

        # Barre de contrôle
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        ctrl.get_style_context().add_class("control-bar")

        # Langue
        lang_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lang_lbl = Gtk.Label(label=_("lbl_lang"))
        lang_lbl.get_style_context().add_class("voice-label")
        lang_lbl.set_halign(Gtk.Align.START)
        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append("loading", _("loading"))
        self.lang_combo.set_active(0)
        self.lang_combo.connect("changed", self._on_lang_changed)
        lang_box.pack_start(lang_lbl, False, False, 0)
        lang_box.pack_start(self.lang_combo, False, False, 0)
        ctrl.pack_start(lang_box, False, False, 0)

        # Voix
        voice_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        voice_lbl = Gtk.Label(label=_("lbl_voice"))
        voice_lbl.get_style_context().add_class("voice-label")
        voice_lbl.set_halign(Gtk.Align.START)
        self.voice_combo = Gtk.ComboBoxText()
        self.voice_combo.append("none", "—")
        self.voice_combo.set_active(0)
        self.voice_combo.connect("changed", self._on_voice_changed)
        voice_box.pack_start(voice_lbl, False, False, 0)
        voice_box.pack_start(self.voice_combo, False, False, 0)
        ctrl.pack_start(voice_box, False, False, 0)

        # Vitesse
        speed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        speed_lbl = Gtk.Label(label=_("lbl_speed"))
        speed_lbl.get_style_context().add_class("voice-label")
        speed_lbl.set_halign(Gtk.Align.START)
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.0, 0.1)
        self.speed_scale.set_value(1.0)
        self.speed_scale.set_size_request(160, -1)
        self.speed_scale.set_draw_value(True)
        self.speed_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.speed_scale.add_mark(0.5, Gtk.PositionType.BOTTOM, "×0.5")
        self.speed_scale.add_mark(1.0, Gtk.PositionType.BOTTOM, "×1")
        self.speed_scale.add_mark(2.0, Gtk.PositionType.BOTTOM, "×2")
        self.speed_scale.connect("value-changed", lambda _w: self._save_config())
        speed_box.pack_start(speed_lbl, False, False, 0)
        speed_box.pack_start(self.speed_scale, False, False, 0)
        ctrl.pack_start(speed_box, True, True, 0)

        root.pack_start(ctrl, False, False, 0)

        # Zone texte
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        self.textview.set_top_margin(12)
        self.textview.set_bottom_margin(12)
        self.textview.get_buffer().connect("changed", lambda _w: self._save_config())
        scroll.add(self.textview)
        root.pack_start(scroll, True, True, 0)

        # Boutons action
        btn_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_bar.set_border_width(10)

        self.btn_play = Gtk.Button(label=_("btn_play"))
        self.btn_play.get_style_context().add_class("btn-play")
        self.btn_play.connect("clicked", self._on_play)

        self.btn_clipboard = Gtk.Button(label=_("btn_clipboard"))
        self.btn_clipboard.get_style_context().add_class("btn-secondary")
        self.btn_clipboard.connect("clicked", self._on_clipboard)

        self.btn_stop = Gtk.Button(label=_("btn_stop"))
        self.btn_stop.get_style_context().add_class("btn-stop")
        self.btn_stop.connect("clicked", self._on_stop)
        self.btn_stop.set_sensitive(False)

        self.btn_clear = Gtk.Button(label="🗑")
        self.btn_clear.get_style_context().add_class("btn-secondary")
        self.btn_clear.connect("clicked", lambda _w: self.textview.get_buffer().set_text(""))

        btn_bar.pack_start(self.btn_play, True, True, 0)
        btn_bar.pack_start(self.btn_clipboard, True, True, 0)
        btn_bar.pack_start(self.btn_stop, True, True, 0)
        btn_bar.pack_start(self.btn_clear, False, False, 0)
        root.pack_start(btn_bar, False, False, 0)

        # Statut
        status_bar = Gtk.Box()
        status_bar.get_style_context().add_class("status-bar")
        self.status_lbl = Gtk.Label(label=_("loading"))
        self.status_lbl.get_style_context().add_class("status-label")
        self.status_lbl.set_halign(Gtk.Align.START)
        status_bar.pack_start(self.status_lbl, True, True, 0)

        self.dl_progress = Gtk.ProgressBar()
        self.dl_progress.get_style_context().add_class("dl-progress")
        self.dl_progress.set_size_request(120, -1)
        self.dl_progress.set_valign(Gtk.Align.CENTER)
        self.dl_progress.set_no_show_all(True)
        status_bar.pack_end(self.dl_progress, False, False, 8)

        root.pack_start(status_bar, False, False, 0)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}

    def _save_config(self, lang=None, voice=None):
        try:
            cfg = self._load_config()
            if lang is not None:
                cfg["lang"] = lang
            if voice is not None:
                cfg["voice"] = voice
            cfg["speed"] = self.speed_scale.get_value()
            cfg["text"] = self._get_text()
            CONFIG_FILE.write_text(json.dumps(cfg))
        except Exception:
            pass

    # ── Chargement voices.json ────────────────────────────────────────────────

    def _load_voices_json(self):
        self._set_status(_("fetching"))
        try:
            with urllib.request.urlopen(VOICES_JSON_URL, timeout=10) as r:
                self._voices_data = json.loads(r.read().decode())
            GLib.idle_add(self._populate_languages)
        except Exception:
            self._offline = True
            GLib.idle_add(self._populate_offline)

    def _populate_offline(self):
        for p in MODELS_DIR.glob("*.onnx"):
            if not p.with_suffix(".onnx.json").exists():
                continue
            key = p.stem
            parts = key.split("-")
            name = parts[1] if len(parts) >= 2 else key
            quality = parts[2] if len(parts) >= 3 else ""
            self._voices_data[key] = {"name": name, "quality": quality, "files": {}}
        self._populate_languages()
        self._set_status(_("offline"))

    def _populate_languages(self):
        cfg = self._load_config()
        saved_lang = cfg.get("lang", "fr")
        saved_voice = cfg.get("voice", "")

        langs = set()
        for key in self._voices_data:
            langs.add(key.split("_")[0])

        self.lang_combo.remove_all()
        for code in sorted(langs):
            self.lang_combo.append(code, LANG_NAMES.get(code, code.upper()))

        if not self.lang_combo.set_active_id(saved_lang):
            if not self.lang_combo.set_active_id("fr"):
                self.lang_combo.set_active(0)

        if saved_voice:
            self.voice_combo.set_active_id(saved_voice)

        if "speed" in cfg:
            self.speed_scale.set_value(cfg["speed"])
        if cfg.get("text"):
            self.textview.get_buffer().set_text(cfg["text"])

        if not self._offline:
            self._set_status(_("ready"))

    def _on_lang_changed(self, combo):
        lang_code = combo.get_active_id()
        if not lang_code or not self._voices_data:
            return

        self.voice_combo.remove_all()
        for key, meta in sorted(self._voices_data.items()):
            if key.startswith(lang_code + "_") or key.startswith(lang_code + "-"):
                quality = meta.get("quality", "")
                name = meta.get("name", key)
                marker = "✓  " if self._is_installed(key) else "     "
                self.voice_combo.append(key, f"{marker}{name}  [{quality}]")

        self.voice_combo.set_active(0)

    def _on_voice_changed(self, combo):
        voice_key = combo.get_active_id()
        if not voice_key or not self._voices_data:
            return

        if self._is_installed(voice_key):
            self._current_model = self._is_installed(voice_key)
            self._set_status(_("voice_ready", voice_key))
        else:
            self._current_model = None
            key = "not_installed_offline" if self._offline else "not_installed_online"
            self._set_status(_(key))

        lang = self.lang_combo.get_active_id()
        if lang and voice_key:
            self._save_config(lang, voice_key)

    # ── Gestion modèles ───────────────────────────────────────────────────────

    def _model_path(self, voice_key):
        return MODELS_DIR / f"{voice_key}.onnx"

    def _is_installed(self, voice_key):
        p = self._model_path(voice_key)
        if p.exists() and p.with_suffix(".onnx.json").exists():
            return p
        return None

    def _download_model(self, voice_key):
        def make_hook():
            def hook(blocknum, blocksize, totalsize):
                if totalsize > 0:
                    GLib.idle_add(self.dl_progress.set_fraction,
                                  min(blocknum * blocksize / totalsize, 1.0))
            return hook

        try:
            meta = self._voices_data.get(voice_key, {})
            files = meta.get("files", {})

            onnx_url = json_url = None
            for path in files:
                if path.endswith(".onnx") and not path.endswith(".json"):
                    onnx_url = f"{HF_BASE}/{path}"
                elif path.endswith(".onnx.json"):
                    json_url = f"{HF_BASE}/{path}"

            if not onnx_url:
                parts = voice_key.split("-")
                lang_region, name, quality = parts[0], parts[1], parts[2]
                lang_code = lang_region.split("_")[0]
                base = f"{lang_code}/{lang_region}/{name}/{quality}/{voice_key}"
                onnx_url = f"{HF_BASE}/{base}.onnx"
                json_url = f"{HF_BASE}/{base}.onnx.json"

            dest_onnx = self._model_path(voice_key)
            dest_json = dest_onnx.with_suffix(".onnx.json")

            GLib.idle_add(self.dl_progress.set_fraction, 0.0)
            GLib.idle_add(self.dl_progress.show)

            GLib.idle_add(self._set_status, _("downloading_onnx"))
            urllib.request.urlretrieve(onnx_url, dest_onnx, make_hook())

            GLib.idle_add(self.dl_progress.set_fraction, 0.0)
            GLib.idle_add(self._set_status, _("downloading_config"))
            urllib.request.urlretrieve(json_url, dest_json, make_hook())

            GLib.idle_add(self.dl_progress.hide)
            self._current_model = dest_onnx
            GLib.idle_add(self._set_status, _("installed", voice_key))
            GLib.idle_add(self._refresh_voice_list, voice_key)

        except Exception as e:
            GLib.idle_add(self.dl_progress.hide)
            GLib.idle_add(self._set_status, _("dl_error", e))
            raise

    def _refresh_voice_list(self, select_key=None):
        current = select_key or self.voice_combo.get_active_id()
        self._on_lang_changed(self.lang_combo)
        if current:
            self.voice_combo.set_active_id(current)

    # ── TTS ───────────────────────────────────────────────────────────────────

    def _get_piper_bin(self):
        script_dir = Path(__file__).resolve().parent
        for candidate in [
            "piper",
            str(Path.home() / ".local" / "bin" / "piper"),
            str(script_dir / ".venv" / "bin" / "piper"),
        ]:
            if shutil.which(candidate) or Path(candidate).is_file():
                return candidate
        return None

    def _speak(self, text: str, voice_key: str):
        self._set_speaking(True)

        if not self._current_model and voice_key and not self._offline:
            self._set_status(_("downloading_voice"))
            try:
                self._download_model(voice_key)
            except Exception:
                self._set_speaking(False)
                return

        model = self._current_model
        if not model:
            GLib.idle_add(self._show_error, _("no_voice"))
            self._set_speaking(False)
            return

        self._set_status(_("synthesizing"))

        piper = self._get_piper_bin()
        if not piper:
            GLib.idle_add(self._show_error, _("no_piper"))
            self._set_speaking(False)
            return

        try:
            speed = self.speed_scale.get_value()
            cache_key = (text, str(model), speed)
            cmd_play = ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]

            if cache_key == self._last_cache_key and AUDIO_CACHE.exists():
                # Rejouer le cache directement
                proc_play = subprocess.Popen(
                    cmd_play + [str(AUDIO_CACHE)], stderr=subprocess.PIPE
                )
                self._proc = proc_play
                proc_play.wait()
            else:
                # Synthèse + mise en cache via tee (streaming conservé)
                cmd_piper = [piper, "--model", str(model), "--output-raw",
                             "--length-scale", f"{1.0 / speed:.2f}"]

                proc_piper = subprocess.Popen(
                    cmd_piper, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                proc_tee = subprocess.Popen(
                    ["tee", str(AUDIO_CACHE)], stdin=proc_piper.stdout, stdout=subprocess.PIPE
                )
                proc_play = subprocess.Popen(
                    cmd_play, stdin=proc_tee.stdout, stderr=subprocess.PIPE
                )
                self._proc_piper = proc_piper
                self._proc = proc_play

                proc_piper.stdin.write(text.encode("utf-8"))
                proc_piper.stdin.close()
                proc_piper.wait()
                proc_tee.wait()
                proc_play.wait()
                self._last_cache_key = cache_key

        except Exception as e:
            GLib.idle_add(self._set_status, _("error", e))
        finally:
            self._proc = None
            self._proc_piper = None
            self._set_speaking(False)
            GLib.idle_add(self._set_status, _("ready"))

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _set_status(self, msg):
        GLib.idle_add(self.status_lbl.set_text, msg)

    def _set_speaking(self, state: bool):
        GLib.idle_add(self.btn_play.set_sensitive, not state)
        GLib.idle_add(self.btn_clipboard.set_sensitive, not state)
        GLib.idle_add(self.btn_stop.set_sensitive, state)

    def _get_text(self):
        buf = self.textview.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip()

    def _show_error(self, msg):
        dlg = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg
        )
        dlg.run()
        dlg.destroy()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_play(self, _btn):
        text = self._get_text()
        if not text:
            self._set_status(_("no_text"))
            return
        voice_key = self.voice_combo.get_active_id()
        threading.Thread(target=self._speak, args=(text, voice_key), daemon=True).start()

    def _on_clipboard(self, _btn):
        cb = Gtk.Clipboard.get_default(self.get_display())
        text = cb.wait_for_text()
        if not text or not text.strip():
            self._set_status(_("clipboard_empty"))
            return
        self.textview.get_buffer().set_text(text)
        voice_key = self.voice_combo.get_active_id()
        threading.Thread(target=self._speak, args=(text.strip(), voice_key), daemon=True).start()

    def _on_stop(self, _btn):
        if self._proc:
            self._proc.terminate()
        if self._proc_piper:
            self._proc_piper.terminate()
        self._set_status(_("stopped"))


if __name__ == "__main__":
    app = Ora()
    Gtk.main()
