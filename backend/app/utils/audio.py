from pathlib import Path
from typing import Tuple

import librosa
import numpy as np


def load_mono(path: Path, sample_rate: int = 44100) -> Tuple[np.ndarray, int]:
    y, sr = librosa.load(path.as_posix(), sr=sample_rate, mono=True)
    return y, sr
