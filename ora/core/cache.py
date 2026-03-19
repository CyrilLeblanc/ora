# ora/core/cache.py
# Per-chunk PCM cache with LRU eviction.
#
# Design: each synthesized audio chunk is stored as a raw PCM file named by
# the SHA-256 of (text + model_path + speed + model_version_signature).
# LRU eviction uses file atime — the OS updates atime on each read, so
# "last used" is automatically tracked without extra metadata.
#
# The cache key includes a model version signature (size+mtime of the .onnx.json
# sidecar) so cached entries are automatically invalidated when the model is
# replaced or updated.

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..constants import CACHE_DIR


@dataclass
class CacheEntry:
    name: str       # filename (hash)
    path: Path
    size: int       # bytes
    atime: float    # last-access timestamp (epoch)


class CacheManager:
    """Manages the PCM audio chunk cache on disk.

    Thread-safe for concurrent producer reads/writes and consumer reads,
    because each entry is written atomically (tmp → rename) and reads only
    access existing files.
    """

    def __init__(self, max_mb: int = 200):
        self._dir = CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_mb * 1024 * 1024

    # ── Public API ────────────────────────────────────────────────────────────

    def make_key(self, text: str, model_path: Path, speed: float) -> str:
        """Return a hex digest that uniquely identifies this (text, voice, speed) triple.

        Including the model version signature prevents stale cache hits after
        a voice model is updated on disk.
        """
        version_sig = self._model_version_sig(model_path)
        raw = f"{text}|{model_path}|{speed:.4f}|{version_sig}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Path]:
        """Return the cache file path if it exists, else None.

        Accessing the file updates its atime, which is used for LRU eviction.
        """
        p = self._path_for(key)
        if p.exists() and p.stat().st_size > 0:
            # Touch atime explicitly (some filesystems mount with relatime/noatime)
            os.utime(p, (time.time(), p.stat().st_mtime))
            return p
        return None

    def put(self, key: str, pcm_data: bytes) -> Path:
        """Write PCM data to cache and return the file path.

        Uses atomic write (tmp file → rename) to avoid partial reads by the
        consumer thread while the producer is still writing.
        """
        dest = self._path_for(key)
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(pcm_data)
        tmp.rename(dest)
        self.evict_if_needed()
        return dest

    def delete(self, key: str) -> None:
        """Remove a single cache entry by key."""
        p = self._path_for(key)
        if p.exists():
            p.unlink()

    def list_entries(self) -> list[CacheEntry]:
        """Return all cache entries sorted by atime (oldest first)."""
        entries = []
        for p in self._dir.glob("*.raw"):
            try:
                st = p.stat()
                entries.append(CacheEntry(p.name, p, st.st_size, st.st_atime))
            except OSError:
                pass
        entries.sort(key=lambda e: e.atime)
        return entries

    def total_size(self) -> int:
        """Return total size of all cache files in bytes."""
        return sum(e.size for e in self.list_entries())

    def clear(self) -> None:
        """Delete all cache entries."""
        for p in self._dir.glob("*.raw"):
            try:
                p.unlink()
            except OSError:
                pass

    def evict_if_needed(self) -> None:
        """Evict the oldest (LRU) entries until total size is within max_bytes."""
        entries = self.list_entries()
        total = sum(e.size for e in entries)
        for entry in entries:  # already sorted oldest-first
            if total <= self.max_bytes:
                break
            try:
                entry.path.unlink()
                total -= entry.size
            except OSError:
                pass

    def set_max_mb(self, mb: int) -> None:
        self.max_bytes = mb * 1024 * 1024
        self.evict_if_needed()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _path_for(self, key: str) -> Path:
        return self._dir / f"{key}.raw"

    @staticmethod
    def _model_version_sig(model_path: Path) -> str:
        """Produce a short signature for the model version.

        We use the size and mtime of the companion .onnx.json file rather than
        hashing the large .onnx binary, because the JSON sidecar changes with
        every official model release and is tiny.
        """
        json_path = model_path.with_suffix(".onnx.json")
        if json_path.exists():
            try:
                st = json_path.stat()
                return f"{st.st_size}:{st.st_mtime:.0f}"
            except OSError:
                pass
        return "unknown"
