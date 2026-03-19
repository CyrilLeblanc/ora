# 🔊 Ora

**Ora** is a text-to-speech (TTS) application for Linux, built with GTK3 and [Piper](https://github.com/rhasspy/piper) — 100% offline, open-source, neural.

---

## Features

- **Neural TTS** via Piper — high-quality, fully offline after initial voice download
- **30+ languages** (French, English, German, Spanish, and more)
- **Voice auto-download** — models fetched automatically on first use; no manual setup
- **Sentence-level chunking** — text is split into chunks for low-latency start and fine-grained progress reporting
- **Per-chunk PCM cache** with LRU eviction — instant re-playback without re-synthesis
- **Pause / Resume** — SIGSTOP/SIGCONT on the audio subprocess; no quality loss
- **Restart** — jump back to the first chunk without re-typing
- **Clipboard watcher** (opt-in) — auto-reads clipboard every 500 ms and speaks new content
- **Clipboard quick-read** button — paste and play in one click
- **Progress bar** — shows chunk-level progress (e.g. "Chunk 3/7")
- **Voice quick-switch** in the status bar — switch voices without opening Settings
- **Settings dialog** — manage installed voices, cache size, and clipboard watcher
- **Offline mode** — if no internet, only locally installed voices are available
- **Speed control** — ×0.5 to ×2 via a slider
- **UI language** auto-detected from system locale (French / English)
- **All settings persisted** across restarts: language, voice, speed, text, cache limits, clipboard preferences
- **Dark theme**

---

## Requirements

### System

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 espeak-ng alsa-utils
```

Compatible with **Ubuntu 22.04+** and **Linux Mint 21+**.

### Piper

```bash
pip install piper-tts pathvalidate --break-system-packages
```

> If `pip` is not available: `sudo apt install python3-pip`
>
> `pathvalidate` is a dependency of `piper-tts` that is not always installed automatically — without it, no audio is produced.

---

## Installation

```bash
git clone https://github.com/youruser/ora.git
cd ora
python3 -m ora
```

The original `ora.py` top-level shim is kept for backward compatibility:

```bash
python3 ora.py   # equivalent to python3 -m ora
```

---

## Usage

1. **Select a voice** from the status-bar dropdown — voices already downloaded are shown; others are downloaded automatically when you click **▶ Play**.
2. **Type or paste text** in the text area.
3. **▶ Play** — starts synthesis and playback, chunk by chunk.
4. **⏸ Pause / ▶ Resume** — suspends or resumes audio at any point.
5. **⏮ Restart** — restarts playback from the first chunk.
6. **⏹ Stop** — interrupts playback immediately.
7. **📋** — reads clipboard content into the text area and starts playback.
8. **● (clipboard dot)** in the status bar — click to toggle the automatic clipboard watcher.
9. **⚙ Settings** — manage voices, cache, and clipboard preferences.

---

## Data & config

All files are stored in `~/.local/share/ora/`:

| Path | Description |
|------|-------------|
| `models/` | Downloaded voice models (`.onnx` + `.onnx.json`) |
| `cache/` | Per-chunk PCM cache (one `.raw` file per synthesised chunk) |
| `config.json` | Persisted settings (see below) |

### config.json keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `lang` | string | `"fr"` | Active voice language code |
| `voice` | string | `""` | Active voice key (e.g. `fr_FR-tom-medium`) |
| `speed` | float | `1.0` | Playback speed multiplier |
| `text` | string | `""` | Last text in the text area |
| `cache_max_mb` | int | `200` | Maximum PCM cache size in MB |
| `clipboard_enabled` | bool | `false` | Whether the clipboard watcher is active |
| `clipboard_autostart` | bool | `false` | Start the clipboard watcher on launch |

---

## Project structure

```
ora/
├── ora/                     # Python package (main application)
│   ├── __main__.py          # Entry point: python3 -m ora
│   ├── __init__.py
│   ├── app.py               # Main Gtk.Window — wires all modules together
│   ├── constants.py         # Paths, URLs, CSS, defaults
│   ├── config.py            # Config load/save (JSON persistence)
│   ├── i18n.py              # STRINGS dict + _() helper + locale detection
│   ├── core/
│   │   ├── tts.py           # TTSEngine: chunking, queue, synthesis via Piper
│   │   ├── cache.py         # CacheManager: LRU PCM cache
│   │   ├── clipboard.py     # ClipboardWatcher: GLib-based polling
│   │   └── voices.py        # VoiceManager: catalogue fetch, model download
│   └── ui/
│       └── settings_dialog.py  # SettingsDialog (Gtk.Dialog)
├── ora.py                   # Thin backward-compat launcher
├── Makefile                 # .deb packaging target
└── README.md
```

---

## Recommended French voices

| Voice | Gender | Quality |
|-------|--------|---------|
| `fr_FR-siwis-medium` | Female | ★★★★☆ |
| `fr_FR-mls-medium`   | Female | ★★★☆☆ |
| `fr_FR-tom-medium`   | Male   | ★★★★☆ |

Models are downloaded from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) on HuggingFace.

---

## Building a .deb package

```bash
sudo apt install fakeroot dpkg-dev
make deb
sudo dpkg -i ora_1.0.0_all.deb
```

---

## Roadmap

Items that are **not yet implemented** but planned:

- **Word/sentence highlight during playback** — requires Piper to emit per-word timestamps (not yet available in the stable Piper API)
- **Flatpak packaging** — needs a Flatpak manifest and GNOME runtime
- **Systray support** — would allow Ora to run in the background with a tray icon

---

## License

MIT
