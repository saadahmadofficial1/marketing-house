#!/usr/bin/env python3
"""Beat grid + energy peaks for a music track — cut points that land ON the music.

  Tools/venv/bin/python3 Tools/sa_beats.py "/path/to/music.mp3"
  Tools/venv/bin/python3 Tools/sa_beats.py song.wav --out beats.json
  Tools/venv/bin/python3 Tools/sa_beats.py --test

Writes tempo, every beat time, downbeat estimates and energy-peak moments
(drops/hits worth cutting on). sa_timeline plans can snap cut points to the
nearest beat so montage cuts feel musical, matching the tight rhythm_spread
measured in Reference/EDIT_DNA_STATS.json.
Run under Tools/venv (librosa). Keep separate from sa_extract (cv2/av clash).
"""
import json
import pathlib
import sys


def analyse(path):
    import librosa
    import numpy as np
    y, sr = librosa.load(str(path), mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    # energy peaks: onset strength spikes above the 90th percentile = hits/drops
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    times = librosa.times_like(onset, sr=sr)
    threshold = float(np.percentile(onset, 90))
    peaks = [round(float(t), 3) for t, s in zip(times, onset)
             if s >= threshold]
    # collapse peaks closer than 0.4s to the first of the run
    merged = []
    for t in peaks:
        if not merged or t - merged[-1] > 0.4:
            merged.append(t)
    tempo_f = float(tempo if np.isscalar(tempo) else tempo[0])
    return {
        "source": str(path),
        "duration": round(float(len(y) / sr), 2),
        "tempo_bpm": round(tempo_f, 1),
        "beat_interval": round(60.0 / tempo_f, 3) if tempo_f else None,
        "beats": [round(float(b), 3) for b in beats],
        # every 4th beat as a bar/downbeat estimate — strongest cut points
        "downbeats": [round(float(b), 3) for b in beats[::4]],
        "energy_peaks": merged,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    src = pathlib.Path(args[0]).expanduser()
    if not src.exists():
        raise SystemExit("no such file: %s" % src)
    result = analyse(src)
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else src.with_suffix(src.suffix + ".beats.json")
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print("%s — %.1f BPM, %d beats, %d energy peaks -> %s" % (
        src.name, result["tempo_bpm"], len(result["beats"]),
        len(result["energy_peaks"]), out))


def self_test():
    import numpy as np
    import soundfile as sf
    import tempfile
    # synthetic 120 BPM click track: clicks every 0.5s for 8s
    sr = 22050
    y = np.zeros(sr * 8, dtype=np.float32)
    for i in range(0, 16):
        y[int(i * 0.5 * sr):int(i * 0.5 * sr) + 200] = 0.9
    f = tempfile.mktemp(suffix=".wav")
    sf.write(f, y, sr)
    r = analyse(f)
    pathlib.Path(f).unlink()
    assert 110 <= r["tempo_bpm"] <= 130, r["tempo_bpm"]
    assert len(r["beats"]) >= 10
    print("sa_beats self-checks: ok (%.1f BPM detected on 120 BPM click)" % r["tempo_bpm"])


if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
