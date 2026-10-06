# Fish Voice Kit

Turn a list of written lines into spoken audio in a cloned voice — your own, or one whose
owner has given you explicit permission or a licence — in any language Fish Audio
supports, Arabic included. It uses Fish Audio’s **free** model through the official API,
so it does not spend your credits; if the free model is ever refused, the kit warns
loudly before it uses the paid one.

**Maturity:** Pilot — built and tested end to end on a real account; the workspace version,
[`sa_fishvo.py`](../../tools/sa_fishvo.py), is the one in use. The code was written
by an AI coding agent under my direction. The full method — route, speed matching,
pronunciation and quality gates — is in
[Fish Audio voice cloning](../../playbooks/fish-audio-voice-cloning.md).

**What goes where.** Your API key stays in this folder (`fish_key.txt`, readable only by
you) and is sent only to Fish Audio, with each request. The lines you generate, and any
recording you clone from, go to Fish Audio — that is how the voice is made. The audio
tidying (trimming and loudness) runs locally with ffmpeg and uploads nothing.

---

## The quickest route: ask Claude Code

If you use Claude Code, install the skill once and then just talk to it:

1. Copy the skill into place — in Terminal, from inside this folder:

   ```bash
   mkdir -p ~/.claude/skills/fish-voice && cp claude-skill/SKILL.md ~/.claude/skills/fish-voice/
   ```

2. Restart Claude Code, then say things like:

   - “Set up the fish voice kit”
   - “Which voices are on my Fish account?”
   - “Say these lines in my voice” *(paste the lines)*
   - “That one is too slow, regenerate it”

Claude reads the skill and runs the tool for you — including the fiddly parts, like
matching the speed to recordings you have already approved.

---

## Or do it by hand — three steps

### 1. Set up, once

Double-click **SETUP.command**.

It installs what is needed and opens one small window:

- **fish_key.txt** — paste your Fish Audio API key, then press Cmd+S.
  Get it from fish.audio → Developer → API Keys. It begins with `sk-fish-`.

**You are not asked for a voice id.** The first time you generate, the kit reads your
own Fish Audio account and shows you the voices that are actually on it — public and
private — and you pick one by number. It remembers your choice after that.

To change voice later, delete **my_voice.txt** and it will ask again. To see the list any
time, double-click **MY_VOICES.command**.

> If it says Homebrew is missing, install it from https://brew.sh first, then run
> SETUP.command again.

### 2. Write your lines

Open **lines.txt** and type what you want spoken. **One line here becomes one audio
file.** Lines beginning with `#` are ignored, so you can leave yourself notes.

### 3. Generate

Double-click **GENERATE.command**. The audio appears in the **output** folder, one mp3
per line, already trimmed and evened out in volume.

---

## Adjusting the result

Open Terminal in this folder and add an option:

| What you want | Command |
|---|---|
| Slower delivery | `./.venv/bin/python3 fish_voice.py --speed 0.9` |
| Faster delivery | `./.venv/bin/python3 fish_voice.py --speed 1.1` |
| Just one sentence | `./.venv/bin/python3 fish_voice.py --say "your sentence"` |
| Clone your own voice (or one you have permission to use) | `./.venv/bin/python3 fish_voice.py --clone recording.wav --title "My voice"` |
| Check your balance | `./.venv/bin/python3 fish_voice.py --credit` |

Re-running a line on the free model costs nothing, so generate an important line two or
three times and keep the take you like best.

---

## When a word is pronounced wrong

This is the thing that wastes the most time, and it has a permanent fix.

**Do not regenerate the line hoping for better.** Open **pronunciation.txt** and write the
word the way it should *sound*:

```
<the word as written> => <the same word with its vowel marks>
2026 => two thousand and twenty-six
Acme => <the brand name written in Arabic letters>
```

From then on, every line you generate says it correctly. **A word only has to be wrong
once.** The file has examples of the four usual causes — missing vowel marks, numbers,
Latin names inside Arabic, and initials. In Arabic the commonest is missing vowel marks:
the same bare letters can spell *ʿilm* (“knowledge”) or *ʿalam* (“flag”), so the right-hand
side is the word written with the tashkeel that forces the reading you mean. Numbers go
on the right as words in the language of the line.

---

## More than one key

Several keys are fine — one per team member or language. Put each one in
**fish_key.txt** on its own line, labelled:

```
arabic: sk-fish-PASTE-KEY
english: sk-fish-PASTE-KEY
```

The kit shows you the voices from every key together and uses the right key
automatically. You never have to think about which key goes with which voice.

---

## Two things worth knowing

**Single capital letters pause.** Written as “Q and A”, the voice says “Q… and A…”. Write
it **“Q-and-A”** and it reads as one word. Same for any initials.

**If you see a warning about the paid model**, stop. The free model was refused and the
next lines would be charged to your account. Check your balance before continuing.

---

## Related

- [Fish Audio voice cloning](../../playbooks/fish-audio-voice-cloning.md) — the full method: the free route, speed measured from approved audio, the pronunciation file and the quality gates.
- [`sa_fishvo.py`](../../tools/sa_fishvo.py) — the workspace version: best-of-N takes, a local Whisper word check, choppiness ranking and loudness matching.
- [`sa_clonevo.py`](../../tools/sa_clonevo.py) — local zero-shot cloning when nothing should go to a cloud service.
- [`sa_voiceref.py`](../../tools/sa_voiceref.py) — picks the best takes from recordings you own or are licensed to clone, to build the reference sample.
- [`sa_voicecheck.py`](../../tools/sa_voicecheck.py) — a transcription-based shortlist of lines that drifted.
- [Training-video production](../../playbooks/training-video-production.md) — where the voice-over fits in a finished video.
