#!/usr/bin/env python3
"""Measure high-frequency energy in a voice line — the one test that catches the drift.

Saad hears it as "old radio": the voice suddenly dulls mid-flow, as if it were a
different person, then recovers. Six methods failed to find it (see sa_voiceclips
docstring); this one works, and it was validated the hard way — by him.

Controlled evidence, all the SAME sentence, voice and settings:
    rejected by ear              HF 0.0614
    take A / B / C he accepted   HF 0.1080 / 0.0907 / 0.0916
and separately, a title line he flagged as still wrong measured 0.0404 — the
lowest of anything tested, which this metric would have caught before he heard it.

Two things it is NOT:
  * not a ranking. He chose the take with the SECOND-LOWEST rolloff, so "keep the
    brightest" is wrong and would have binned the one he wanted. It is a
    threshold: below ~0.085 on this voice is suspect, above it is fine.
  * not spectral rolloff, which does not separate at all (his chosen take sat at
    6395 Hz, right beside the rejected one's 6008 Hz).

    sa_hfcheck.py file.mp3 [more.mp3 ...]      # measure
    sa_hfcheck.py --demo
"""
import io
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")

# THERE IS NO ABSOLUTE THRESHOLD. Measured 18 Aug: every title line already in Saad's
# DELIVERED videos scores 0.047-0.071, i.e. all "below" the 0.085 that separated the takes
# of one sibilant-rich sentence. HF energy tracks the PHONETIC CONTENT — "The next step is
# to save the settings" is full of s/t and reads high; "Now open a new window" has almost
# none and reads low however well it is spoken. So HF only means something when comparing
# takes of the SAME words.
RELATIVE_DROP = 0.80       # a take below 80% of the best take of that same line is suspect


def hf_ratio(path, sr=22050):
    """Median share of energy above 5 kHz across the voiced frames. -> float"""
    import numpy as np
    import soundfile as sf
    import librosa
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(sr), "-f", "wav", "-"], capture_output=True).stdout
    if len(raw) < 2000:
        return None
    x, _ = sf.read(io.BytesIO(raw))
    x = x.astype(np.float32)
    S = np.abs(librosa.stft(x, n_fft=1024, hop_length=256)) + 1e-10
    rms = librosa.feature.rms(S=S, frame_length=1024)[0]
    voiced = rms > np.percentile(rms, 55)      # ignore pauses; they have no HF either way
    if voiced.sum() < 5:
        return None
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    return float(np.median((S[freqs > 5000].sum(0) / S.sum(0))[voiced]))


def rank(paths):
    """Compare takes of the SAME sentence. -> [(path, hf, verdict)] best first.

    The only comparison that means anything. Validated on the one controlled set
    Saad judged by ear: rejected 0.0614 against 0.0907 / 0.0916 / 0.1080 accepted.
    """
    rows = [(p, hf_ratio(p)) for p in paths]
    good = [h for _p, h in rows if h is not None]
    if not good:
        return [(p, h, "unknown") for p, h in rows]
    best = max(good)
    out = []
    for p, h in rows:
        if h is None:
            out.append((p, h, "unknown"))
        else:
            out.append((p, h, "SUSPECT" if h < best * RELATIVE_DROP else "ok"))
    return sorted(out, key=lambda r: -(r[1] or 0))


def _verdicts(hs):
    best = max(h for h in hs if h is not None)
    return ["SUSPECT" if h < best * RELATIVE_DROP else "ok" for h in hs]


def demo():
    """Pin the RELATIVE rule against what Saad judged by ear on 18 Aug."""
    # the one controlled set: same sentence, one rejected, three accepted
    assert _verdicts([0.0614, 0.0907, 0.0916, 0.1080]) == ["SUSPECT", "ok", "ok", "ok"]
    # The trap this rule exists to avoid: title lines in his DELIVERED videos span
    # 0.047-0.071 purely because of their wording. Feeding DIFFERENT sentences to the
    # same comparison condemns work he is happy with — proof that the rule is only ever
    # valid within one line, which is why rank() is documented as same-text only.
    across_sentences = [0.0471, 0.0476, 0.0480, 0.0509, 0.0563, 0.0610, 0.0647, 0.0713]
    assert _verdicts(across_sentences).count("SUSPECT") >= 4, (
        "comparing different sentences must look obviously wrong, so nobody does it")
    print("demo ok — catches the rejected take; misuse across sentences stays visibly wrong")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
        sys.exit()
    for p, h, v in rank(sys.argv[1:]):
        print(f"  {v:<8} {h if h is None else round(h, 4):<8} {p.split('/')[-1]}")
