# ora/core/voices.py
# Voice model management: fetching the remote voices.json catalogue,
# downloading .onnx models, and listing locally installed voices.
#
# VoiceManager is purely about model files — no GTK code here.
# The app wires up the callbacks to update the UI.

import json
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from ..constants import VOICES_JSON_URL, HF_BASE, MODELS_DIR


class VoiceManager:
    """Fetches/stores the Piper voice catalogue and manages model files.

    Callbacks are called from background threads; callers must use
    GLib.idle_add if they need to update GTK widgets.
    """

    def __init__(self) -> None:
        self.voices_data: dict = {}      # key → metadata from voices.json
        self.offline: bool = False
        self.catalogue_loaded: bool = False

    # ── Catalogue ─────────────────────────────────────────────────────────────

    def fetch_catalogue(
        self,
        on_success: Callable[[], None],
        on_offline: Callable[[], None],
    ) -> None:
        """Fetch voices.json from HuggingFace (runs synchronously — call in a thread)."""
        try:
            with urllib.request.urlopen(VOICES_JSON_URL, timeout=10) as r:
                self.voices_data = json.loads(r.read().decode())
            self.offline = False
            self.catalogue_loaded = True
            on_success()
        except Exception:
            self.offline = True
            self._load_offline()
            self.catalogue_loaded = True
            on_offline()

    def _load_offline(self) -> None:
        """Populate voices_data from locally installed .onnx files."""
        for p in MODELS_DIR.glob("*.onnx"):
            if not p.with_suffix(".onnx.json").exists():
                continue
            key = p.stem
            parts = key.split("-")
            self.voices_data[key] = {
                "name": parts[1] if len(parts) >= 2 else key,
                "quality": parts[2] if len(parts) >= 3 else "",
                "files": {},
            }

    # ── Model access ──────────────────────────────────────────────────────────

    def model_path(self, voice_key: str) -> Path:
        return MODELS_DIR / f"{voice_key}.onnx"

    def is_installed(self, voice_key: str) -> Optional[Path]:
        """Return the model Path if both .onnx and .onnx.json exist, else None."""
        p = self.model_path(voice_key)
        if p.exists() and p.with_suffix(".onnx.json").exists():
            return p
        return None

    def installed_voices(self) -> list[str]:
        """Return list of voice keys that are installed locally."""
        result = []
        for p in MODELS_DIR.glob("*.onnx"):
            if p.with_suffix(".onnx.json").exists():
                result.append(p.stem)
        return sorted(result)

    def delete_voice(self, voice_key: str) -> None:
        """Remove the .onnx and .onnx.json files for a voice."""
        p = self.model_path(voice_key)
        for f in (p, p.with_suffix(".onnx.json")):
            if f.exists():
                f.unlink()

    # ── Download ──────────────────────────────────────────────────────────────

    def download_voice(
        self,
        voice_key: str,
        on_onnx_start: Callable[[], None],
        on_json_start: Callable[[], None],
        on_progress: Callable[[float], None],
        on_done: Callable[[Path], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Download a voice model (runs synchronously — call in a thread).

        Calls progress callback with a fraction 0.0–1.0 as each file
        downloads; calls on_done with the .onnx path on success.
        """
        def make_hook():
            def hook(blocknum: int, blocksize: int, totalsize: int) -> None:
                if totalsize > 0:
                    on_progress(min(blocknum * blocksize / totalsize, 1.0))
            return hook

        try:
            onnx_url, json_url = self._resolve_urls(voice_key)

            dest_onnx = self.model_path(voice_key)
            dest_json = dest_onnx.with_suffix(".onnx.json")

            on_onnx_start()
            urllib.request.urlretrieve(onnx_url, dest_onnx, make_hook())

            on_json_start()
            on_progress(0.0)
            urllib.request.urlretrieve(json_url, dest_json, make_hook())

            on_done(dest_onnx)

        except Exception as exc:
            on_error(exc)

    def _resolve_urls(self, voice_key: str) -> tuple[str, str]:
        """Resolve the ONNX and JSON download URLs for a voice key."""
        meta = self.voices_data.get(voice_key, {})
        files = meta.get("files", {})

        onnx_url = json_url = None
        for path in files:
            if path.endswith(".onnx") and not path.endswith(".json"):
                onnx_url = f"{HF_BASE}/{path}"
            elif path.endswith(".onnx.json"):
                json_url = f"{HF_BASE}/{path}"

        if not onnx_url:
            # Fall back to conventional path structure when files dict is empty
            parts = voice_key.split("-")
            lang_region, name, quality = parts[0], parts[1], parts[2]
            lang_code = lang_region.split("_")[0]
            base = f"{lang_code}/{lang_region}/{name}/{quality}/{voice_key}"
            onnx_url = f"{HF_BASE}/{base}.onnx"
            json_url = f"{HF_BASE}/{base}.onnx.json"

        return onnx_url, json_url
