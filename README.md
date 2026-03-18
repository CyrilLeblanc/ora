# 🔊 Ora

**Ora** is a text-to-speech (TTS) application for Linux, built with GTK3 and [Piper](https://github.com/rhasspy/piper) — 100% offline, open-source, neural.

---

## Features

- Neural text-to-speech via Piper
- 30+ languages available (French, English, German, Spanish…)
- Voice models downloaded automatically on first use — no manual setup
- Voices already downloaded are marked with ✓ in the selector
- Offline mode: if no internet connection, only installed voices are shown
- Clipboard read in one click
- Speed control (×0.5 to ×2)
- Last audio replayed instantly if text/voice/speed haven't changed (no re-synthesis)
- UI language auto-detected from system locale (French / English)
- All settings persisted across restarts: language, voice, speed, text
- Discrete download progress bar (bottom right)
- Dark theme

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
python3 ora.py
```

---

## Usage

1. **Select a language** — the voice list updates automatically.
2. **Select a voice** — voices marked ✓ are already installed. Others are downloaded automatically when you click **▶ Play**.
3. **Type or paste text**, then click **▶ Play**.
4. **📋 Clipboard** pastes and reads clipboard content in one action.
5. **⏹ Stop** interrupts playback at any time.
6. Clicking **▶ Play** again without changing anything replays the last audio immediately.

---

## Data & config

All files are stored in `~/.local/share/ora/`:

| File | Description |
|------|-------------|
| `models/` | Downloaded voice models (`.onnx` + `.onnx.json`) |
| `config.json` | Persisted settings (language, voice, speed, text) |
| `last_audio.raw` | Cached raw PCM for instant replay |

---

## Recommended French voices

| Voice | Gender | Quality |
|-------|--------|---------|
| `fr_FR-siwis-medium` | Female | ★★★★☆ |
| `fr_FR-mls-medium` | Female | ★★★☆☆ |
| `fr_FR-tom-medium` | Male | ★★★★☆ |

Models are downloaded from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) on HuggingFace.

---

## Project structure

```
ora/
├── ora.py       # Main application
└── README.md
```

---

## License

MIT
