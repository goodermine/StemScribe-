from functools import lru_cache
from pathlib import Path
from typing import Tuple

import librosa
import numpy as np

from app.config import settings


@lru_cache(maxsize=16)
def _load_cached(path_str: str, sample_rate: int) -> Tuple[np.ndarray, int]:
    y, sr = librosa.load(path_str, sr=sample_rate, mono=True)
    return y, sr


def load_mono(path: Path, sample_rate: int | None = None) -> Tuple[np.ndarray, int]:
    """Load a stem at the analysis sample rate.

    Several stages read the same stem (chords and key both want the harmony
    stems), so decoded audio is cached — decoding a 3-minute WAV repeatedly
    dominates the runtime otherwise. The array is returned read-only to keep
    one caller from mutating another's copy.
    """
    sr_target = sample_rate or settings.sample_rate
    y, sr = _load_cached(path.as_posix(), sr_target)
    view = y.view()
    view.flags.writeable = False
    return view, sr


def clear_audio_cache() -> None:
    _load_cached.cache_clear()


def is_silent(y: np.ndarray, threshold: float = 1e-4) -> bool:
    return not bool(np.any(np.abs(y) > threshold))


def rms_envelope(y: np.ndarray, hop_length: int | None = None) -> np.ndarray:
    hop = hop_length or settings.hop_length
    return librosa.feature.rms(y=y, hop_length=hop)[0]
