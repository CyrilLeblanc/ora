# ora/i18n.py
# UI language detection and all translatable strings.
# Every string shown in the interface must have both "fr" and "en" keys here.
# Use the _() helper everywhere; never hardcode French or English in widget code.

import os
import locale
from typing import Any


def _detect_ui_lang() -> str:
    """Detect UI language from system environment, defaulting to English."""
    for src in (
        os.environ.get("LANG", ""),
        os.environ.get("LANGUAGE", ""),
        locale.getlocale()[0] or "",
    ):
        if src.startswith("fr"):
            return "fr"
    return "en"


UI_LANG: str = _detect_ui_lang()

# ── All UI strings ────────────────────────────────────────────────────────────
# Each key maps to {"fr": ..., "en": ...}.
# Use {} placeholders for format arguments passed to _().

STRINGS: dict[str, dict[str, str]] = {
    # ── Status / general ──────────────────────────────────────────────────────
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
    "no_piper": {
        "fr": "Binaire 'piper' introuvable.\n\nInstallez-le :\n  pip install piper-tts pathvalidate --break-system-packages",
        "en": "Binary 'piper' not found.\n\nInstall it:\n  pip install piper-tts pathvalidate --break-system-packages",
    },
    "chunk_progress":       {"fr": "Morceau {}/{}",             "en": "Chunk {}/{}"},

    # ── Buttons ───────────────────────────────────────────────────────────────
    "btn_play":             {"fr": "▶  Lire",                   "en": "▶  Play"},
    "btn_pause":            {"fr": "⏸  Pause",                  "en": "⏸  Pause"},
    "btn_resume":           {"fr": "▶  Reprendre",              "en": "▶  Resume"},
    "btn_stop":             {"fr": "⏹  Stop",                   "en": "⏹  Stop"},
    "btn_restart":          {"fr": "⏮  Restart",               "en": "⏮  Restart"},
    "btn_clipboard_read":   {"fr": "📋",                        "en": "📋"},
    "btn_clear":            {"fr": "🗑",                        "en": "🗑"},
    "btn_settings":         {"fr": "⚙  Paramètres",            "en": "⚙  Settings"},

    # ── Labels ────────────────────────────────────────────────────────────────
    "lbl_lang":             {"fr": "Langue",                    "en": "Language"},
    "lbl_voice":            {"fr": "Voix",                      "en": "Voice"},
    "lbl_speed":            {"fr": "Vitesse",                   "en": "Speed"},
    "app_title":            {"fr": "🔊 Ora",                    "en": "🔊 Ora"},

    # ── Clipboard watcher ─────────────────────────────────────────────────────
    "clipboard_watching":   {"fr": "● Presse-papier actif",    "en": "● Clipboard active"},
    "clipboard_triggered":  {"fr": "Presse-papier détecté — lecture…",
                             "en": "Clipboard detected — playing…"},
    "clipboard_off":        {"fr": "●",                         "en": "●"},  # dot only, colored by CSS
    "clipboard_on":         {"fr": "●",                         "en": "●"},

    # ── Settings dialog ───────────────────────────────────────────────────────
    "settings_title":              {"fr": "⚙ Paramètres",           "en": "⚙ Settings"},
    "settings_lang":               {"fr": "Langue des voix",         "en": "Voice language"},
    "settings_voice":              {"fr": "Voix active",             "en": "Active voice"},
    "settings_installed_voices":   {"fr": "Voix installées",         "en": "Installed voices"},
    "settings_cache":              {"fr": "Cache",                   "en": "Cache"},
    "settings_cache_max":          {"fr": "Taille max",              "en": "Max size"},
    "settings_cache_used":         {"fr": "Utilisé",                 "en": "Used"},
    "settings_cache_clear":        {"fr": "Vider le cache",          "en": "Clear cache"},
    "settings_cache_clear_confirm":{"fr": "Vider tout le cache PCM ?",
                                    "en": "Clear all PCM cache?"},
    "settings_clipboard_section":  {"fr": "Presse-papier automatique",
                                    "en": "Clipboard watcher"},
    "settings_clipboard_auto":     {"fr": "Activer automatiquement", "en": "Enable automatically"},
    "settings_clipboard_startup":  {"fr": "Lancer au démarrage",    "en": "Start on launch"},
    "settings_close":              {"fr": "Fermer",                  "en": "Close"},
    "settings_delete_voice":       {"fr": "Supprimer",               "en": "Delete"},
    "settings_delete_voice_confirm":{"fr": "Supprimer la voix {} ?",
                                     "en": "Delete voice {}?"},
    "settings_voice_deleted":      {"fr": "Voix supprimée.",         "en": "Voice deleted."},
    "settings_no_installed":       {"fr": "(aucune voix installée)", "en": "(no voices installed)"},
    "confirm_yes":                 {"fr": "Oui",                     "en": "Yes"},
    "confirm_no":                  {"fr": "Non",                     "en": "No"},
    "mb_unit":                     {"fr": "{} Mo",                   "en": "{} MB"},
}


def _(key: str, *args: Any) -> str:
    """Return the translated string for key, with optional format arguments."""
    s = STRINGS[key][UI_LANG]
    return s.format(*args) if args else s
