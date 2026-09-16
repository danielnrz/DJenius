"""DJ reference folders never enter ordinary candidate-song scans by default."""

from pathlib import Path

import numpy as np
import soundfile as sf

from djenius.audio.scanner import scan_directory


def _short_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.zeros(4410, dtype=np.float32), 44100)


def test_recursive_song_scan_excludes_reference_subtrees(tmp_path: Path) -> None:
    normal = tmp_path / "song.wav"
    reference = tmp_path / "fromDJ" / "edit.wav"
    nested_reference = tmp_path / "nested" / "FromDj" / "mix.wav"
    _short_wav(normal)
    _short_wav(reference)
    _short_wav(nested_reference)

    found = scan_directory(str(tmp_path))

    assert {item.filepath for item in found} == {str(normal)}


def test_explicit_reference_scan_and_opt_in_remain_possible(tmp_path: Path) -> None:
    normal = tmp_path / "song.wav"
    reference = tmp_path / "fromDJ" / "edit.wav"
    _short_wav(normal)
    _short_wav(reference)

    direct = scan_directory(str(reference.parent))
    opted_in = scan_directory(str(tmp_path), exclude_reference_material=False)

    assert {item.filepath for item in direct} == {str(reference)}
    assert {item.filepath for item in opted_in} == {str(normal), str(reference)}
