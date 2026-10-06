---
name: fish-voice
description: "Generate spoken audio in the user's own cloned voice through Fish Audio, in any language including Arabic. Use for ANY task involving: making a voice-over, narrating a script, speaking lines of text aloud, regenerating a line that sounded wrong, cloning the user's own voice from a reference recording, or checking which cloned voices and how much credit the Fish Audio account has. Clone only the user's own voice, or one whose owner has given explicit permission or a licence. Also use when the user says a generated line is too fast, too slow, choppy, or mispronounced."
---

# Fish voice kit

A folder-based tool that turns a text file into one audio file per line, spoken in the
user's own cloned voice, using Fish Audio's **free** S2.1 Pro model.

**Consent comes first.** Clone only a voice that belongs to the user, or one whose owner
has given them explicit permission or a licence to use it. If asked to clone anyone
else's voice, ask for that permission before doing anything; without it, do not clone.

The kit lives wherever the user unzipped it — usually `~/Downloads/Fish Voice Kit`. Find
it before doing anything else; do not assume the path.

```bash
cd "<kit folder>"
./.venv/bin/python3 fish_voice.py --list                 # voices on the account + ids
./.venv/bin/python3 fish_voice.py --credit               # balance
./.venv/bin/python3 fish_voice.py                        # speak everything in lines.txt
./.venv/bin/python3 fish_voice.py --say "one sentence"
./.venv/bin/python3 fish_voice.py --speed 0.95
./.venv/bin/python3 fish_voice.py --clone reference.wav --title "My voice"
```

Audio lands in `output/`, one mp3 per line, already trimmed and level-matched.

## Setup, if it has not been done

`SETUP.command` installs ffmpeg and `requests` into a private `.venv` inside the folder,
then creates a plain-text file for the user to fill in:

- `fish_key.txt` — the Fish Audio API key, from fish.audio → Developer → API Keys

The voice is **not** configured by hand. On the first generate the tool reads the user's
own account, shows the voices actually on it, and remembers the one they pick in
`my_voice.txt`. **Never write a voice id into that file from a directory search or from
memory** — a public voice can be found by anyone, but that proves only that it exists,
not that it is the one this person works with, and a private voice cannot be found that
way at all. The account's key is the only complete answer. If the file already holds an
id that is not on the account, the tool says so and re-asks.

**Never ask the user to paste an API key into the chat.** Open the file for them
(`open -e fish_key.txt`) and let them paste it there. It is chmod 600, stays in the kit
folder and is sent only to Fish Audio, with each request. Never print it, echo it or
read it back into the conversation.

## The things that actually go wrong

**Speed is the most common complaint, and it is not a matter of taste — measure it.**
When the user says a line is too slow or too fast, do not guess a number and do not copy
whatever value happens to be sitting in the fish.audio web panel; that is where they
started, not what they approved. Instead measure the words-per-second of work they have
already approved, and match it:

```bash
# words per second of an existing approved recording
python3 -c "
import subprocess,sys
d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
 '-of','default=nw=1:nk=1',sys.argv[1]],capture_output=True,text=True).stdout)
print(len(sys.argv[2].split())/d,'words/sec')" approved.mp3 "the words that were spoken"
```

Then set `--speed` so the new lines land on that figure. Fish's default of 1.0 is a
starting point, not an answer.

**Initialisms pause in the middle.** Fish reads spaced single capitals as separate
phrases — "Q and A" comes out "Q… and A…". Bind them with hyphens: "Q-and-A". This is
engine-specific; a spelling that behaved on a different speech engine proves nothing here. Read the
output back before handing it over.

**In Arabic voice-overs, pronunciation is the problem that wastes the most time. Treat
it as the main job, not a detail.**

The cure is never to re-record or re-roll the line until it happens to come out right.
It is to respell the word the way it should *sound* and add it to `pronunciation.txt`,
which is applied to every line from then on:

```
<the word as written> => <the same word with its tashkeel>
2026 => <the number written as Arabic words>
Acme => <the brand name written in Arabic letters>
HR => <the letter names written in Arabic script>
```

**A word only has to be wrong once.** Every fix is permanent and helps every future
script. When the user says a word came out wrong, do not just regenerate — add the line.

The four causes, in the order they actually occur:

1. **No vowel marks.** Undiacritised Arabic is ambiguous — the same consonants are
   several different words (*ʿilm*, “knowledge”, and *ʿalam*, “flag”, share their letters),
   and the model picks one. Add the tashkeel to the specific
   word to force the reading. This is the single most common cause.
2. **Numbers and dates** — read digit by digit, or in the wrong language. Write them as
   Arabic words.
3. **Latin names inside Arabic** — the voice switches accent mid-sentence. Write the name
   in Arabic letters.
4. **Initials** — read as separate phrases with pauses between. Spell them out
   as letter names in Arabic script.

**Build the list from the user's existing work before generating anything new.** On the
first session, ask for the scripts and audio they have already made and go through them
together: play back what they flagged, get the word, add the entry. That turns past
frustration into a list that stops it recurring, instead of starting from an empty file.

**The read-back check cannot help on a free account.** Fish's speech-to-text (`/v1/asr`)
is billed against API credit, which the free model does not include — a free account gets
402 and the tool says so and carries on. So the pronunciation list is built from *the
user's ear*, not from an automatic check. Ask them which word was wrong; do not guess from
the text. (If faster-whisper happens to be installed on the machine, transcribing locally
is a legitimate way to shortlist suspect lines — but their judgement still decides.)

**Several keys are fine — one per team member or language.** Each goes in
`fish_key.txt` on its own line, labelled (`arabic:` / `english:`). The kit pools the
voices and routes each generation to the key that owns the chosen voice — never ask the
user to work out which key to use.

Filenames fall back to `line_03.mp3` for non-Latin text; that is intentional, a row of
underscores helps nobody.

**The free model can be refused.** The tool defaults to `s2.1-pro-free` and, if that is
rejected, falls back to the paid `s2.1-pro` while printing a loud warning. If you see
that warning, stop and tell the user before generating a whole batch — it is their money.

**Generate two or three takes of an important line and let the user choose.** The model
varies between takes. Re-running the same line on the free model costs nothing.

## Verification is not optional

A tool printing "Done" proves a file was written, not that it says the right words.
Before handing anything over, check the output actually exists, is not silent, and runs
for a sensible length:

```bash
for f in output/*.mp3; do
  ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" | \
    xargs -I{} echo "$f {}s"
done
```

A file under half a second, or one whose length does not fit the number of words, is a
failed generation — regenerate it rather than shipping it.
