# Media-operations field notes

The unglamorous half of production: slowing footage down properly, rescuing a broken download, copying camera cards without losing anything, cleaning storage without breaking a single project, and culling hours of rushes with AI agents. Each recipe came from real work. The commands are the ones that worked, and the numbers were measured, not remembered.

The tools linked here were written by AI coding agents (Claude Code and Codex) under my direction and review: [`sa_compress.py`](../tools/sa_compress.py), [`sa_dedupe.py`](../tools/sa_dedupe.py), [`sa_refmap.py`](../tools/sa_refmap.py), [`sa_organize.py`](../tools/sa_organize.py), [`sa_capcut_writer.py`](../tools/sa_capcut_writer.py), [`sa_event_motionmap.py`](../tools/sa_event_motionmap.py), [`sa_frames.py`](../tools/sa_frames.py), [`sa_extract.py`](../tools/sa_extract.py) and [`media_kit.py`](../tools/media_kit.py). Related playbooks: the [CapCut hub](capcut.md) and [draft format](capcut-draft-format.md), [local AI on a Mac](local-ai-on-a-mac.md) and [orchestrating agent fleets](orchestrating-agent-fleets.md).

| # | Recipe | Maturity | Evidence |
|---|---|---|---|
| 1 | Slow motion that isn’t choppy | **Pilot** – used on one reel’s clips | 10 of 10 clips came out 120 frames, 4.00 s, 0 duplicate frames |
| 2 | Rescuing a truncated zip download | **Pilot** – one real recovery | 35 of 36 files carved back; the snippet below was retested on synthetic zips |
| 3 | Camera cards: copy, verify, image | **Built, in use** – a standing checklist | Card-root database folders, ghost mounts and write speed were all measured on real cards |
| 4 | When “0 files” means “not allowed to look” | **Built, in use** – a standing rule | A protected cloud folder read as empty when it wasn’t |
| 5 | Choosing a donor project for generated CapCut projects | **Built, in use** – enforced in the writer | A crash traced to cloud-only media inside a donor |
| 6 | Clearing an editor’s caches, and other safe space-saving | **Built, in use** | Every project checked for references before and after |
| 7 | Cloud sync that undoes your clean-up | **Built, in use** – a standing rule | A full account restored every deletion and move |
| 8 | Culling hours of rushes with parallel AI agents | **Pilot** – used on two large shoots | About 90 clips (28 min of 4K) culled to their best windows |

---

## 1. Slow motion that isn’t choppy

**First, ask whether you need interpolation at all.** Real frames per output second = source frame rate × speed. If that number is at least the timeline’s frame rate, every output frame is a real camera frame and optical flow adds nothing:

| Source | Speed | Real frames per second | 25 fps timeline | 30 fps export |
|---|---|---|---|---|
| 50 fps | 0.75× | 37.5 | No interpolation needed | No interpolation needed |
| 50 fps | 0.6× | 30 | No interpolation needed | Borderline |
| 50 fps | 0.5× | 25 | Borderline | Needs interpolation |
| 100 fps | 0.3× | 30 | No interpolation needed | Borderline |

The slowest speed without invented frames is *timeline fps ÷ source fps*. Interpolation invents in-between frames, and invented frames warp and shimmer on fine reflective detail such as facets, chrome and small type. For product footage that has to stay faithful, slow down only as far as real frames allow ([photo-fidelity-retouching.md](photo-fidelity-retouching.md)).

**When you do need it,** for example to stretch a slow camera move on a short clip to 4 s, this is the ffmpeg chain that works:

```bash
ffmpeg -i in.mp4 -vf "setpts=PTS*FACTOR,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:search_param=32" \
       -t 4.0 -c:v libx264 -crf 17 -preset medium out.mp4
```

| Flag | Why |
|---|---|
| `mi_mode=mci` | Motion-compensated interpolation: it synthesises genuinely new in-between frames. This is the whole difference between slow motion and stutter |
| `mc_mode=aobmc` | Overlapped block motion compensation, which removes block artefacts |
| `me_mode=bidir` | Searches for motion both forwards and backwards, giving better vectors |
| `vsbmc=1` | Variable-size blocks, which handle edges better |
| `search_param=32` | A wider motion search for larger movements |

What *doesn’t* work: `setpts` alone just holds each frame longer, so it looks choppy, and `tblend` or `framerate` blending gives ghosting.

**Gotcha 1 – overshoot the stretch.** `minterpolate` drops boundary frames, so a factor worked out for exactly 4.0 s comes up short. On the original clips it landed at about 3.77 s. Overshoot the target by about 0.25 s, *FACTOR = (target + 0.25) ÷ source duration*, then hard-trim with `-t`. A re-test for this page on a low-frame-rate 2 s test clip needed more: factor 2.0 gave 3.63 s, 2.125 gave 3.83 s and 2.25 gave exactly 4.00 s. Always check the output’s duration and frame count, and raise the factor until it lands.

**Gotcha 2 – it’s slow.** Expect about 45 s per 4 s clip at 1080×1920. Run three at a time.

**Verify it actually interpolated.** A duplicate-frame count tells you instantly:

```bash
ffmpeg -i out.mp4 -vf mpdecimate -loglevel debug -f null - 2>&1 | grep -c ' drop '
```

0 drops means every frame is unique. Lots of drops means held frames, and it will look choppy. In the same re-test, a plain `setpts` stretch showed 100 drops out of 120 frames; the `minterpolate` version showed 1.

It stays clean when camera movement between frames is small. Stretch factors from 2.0× to 3.75× were all clean on slow camera moves. Fast action is where interpolation falls apart.

**In CapCut,** optical flow is a setting in the app. None of my saved projects has ever used it, so its key in the project file is unknown. Set it in the UI; never write it into the file.

---

## 2. Rescuing a truncated zip download

A 16 GB folder download from a cloud drive failed to open in Archive Utility with “Error 0 – Undefined error: 0”.

**Diagnose before you re-download.**

1. `file big.zip` said it was a valid zip, but `unzip -l big.zip` said “cannot find zipfile directory”.
2. Check free disk space first, and rule it out.
3. Look at both ends of the file. A healthy zip *starts* with a local file header and *ends* with an end-of-central-directory record:

```bash
python3 - big.zip <<'EOF'
import os, sys
p = sys.argv[1]; size = os.path.getsize(p)
with open(p, "rb") as f:
    head = f.read(4); f.seek(max(0, size - (1 << 20))); tail = f.read()
print("starts with a local header:", head == b"PK\x03\x04")
for sig, what in [(b"PK\x05\x06", "end of central directory"), (b"PK\x06\x06", "zip64 end record"),
                  (b"PK\x06\x07", "zip64 locator"), (b"PK\x01\x02", "central directory entry")]:
    print(f"{what} in the last 1 MB:", sig in tail)
EOF
```

A valid head with **all four** tail signatures missing means a truncated download, not corruption. The data is still there; only the index at the end is gone.

**Carve the entries out.** Folder downloads from that cloud drive are zipped with **compression method 0 (stored)**: every entry is raw bytes, so it can be cut straight out of the file. Find each local header, skip its 30 fixed bytes plus the name and extra field, and treat the *next* header’s offset as the end. Every entry except the last is complete. The original recovery used exactly that logic. The snippet below adds three safeguards: it drops the data descriptor that streamed zips put after each entry, it skips chance matches of the 4-byte signature inside media data, and it refuses paths that would escape the output folder. It was written for this page by an AI coding agent and tested on synthetic stored zips, with and without data descriptors, truncated mid-entry. It was not run on the original download.

```python
"""Carve stored (method 0) entries out of a zip whose central directory is missing."""
import mmap, pathlib, struct, sys

LOCAL, DESCRIPTOR = b"PK\x03\x04", b"PK\x07\x08"

def carve(zip_path, out_dir):
    out = pathlib.Path(out_dir)
    with open(zip_path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        heads, i = [], m.find(LOCAL)
        while i != -1:
            flags, method = struct.unpack_from("<HH", m, i + 6)
            nlen, elen = struct.unpack_from("<HH", m, i + 26)
            name = m[i + 30:i + 30 + nlen]
            if method == 0 and 0 < nlen < 1024 and b"\x00" not in name:  # skip chance matches inside data
                heads.append((i, flags, i + 30 + nlen + elen, name.decode("utf-8", "replace")))
            i = m.find(LOCAL, i + 4)
        for n, (start, flags, begin, name) in enumerate(heads):
            end = heads[n + 1][0] if n + 1 < len(heads) else len(m)
            if flags & 0x08:                 # streamed entry: drop the data descriptor
                for size in (24, 16):        # zip64 descriptor, then the ordinary one
                    if m[end - size:end - size + 4] == DESCRIPTOR:
                        end -= size
                        break
            if name.endswith("/") or name.startswith("/") or ".." in name.split("/"):
                continue                     # folder entry, or a path that escapes out_dir
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as w:
                for pos in range(begin, end, 64 << 20):  # copy in 64 MB chunks
                    w.write(m[pos:min(pos + (64 << 20), end)])
            tail = "  <- last entry, probably truncated" if n + 1 == len(heads) else ""
            print(f"{end - begin:>15,}  {name}{tail}")

if __name__ == "__main__":
    carve(sys.argv[1], sys.argv[2])
```

**Check one file before carving the rest.** Run `ffprobe` on the first carved clip before committing to all of them. The real recovery got 35 of 36 files back; the 36th was the one the download had cut off.

**Prevention.** Don’t pull very large folders through the browser. Use the cloud drive’s desktop sync client, or download in subfolder batches. Two earlier browser downloads had died the same way.

---

## 3. Camera cards: copy, verify, image

**The card root holds more than clips.** On the cards I copy (Sony AVCHD), two database folders sit at the root: `AVF_INFO/` and `AVF_ESCP/`. The second is a backup copy of the same data. They hold files such as `AVIN0001.BNP`, `.INP`, `.INT` and `PRV00001.BIN`. A Finder drag-copy often skips them. The `.MTS` clips still play on their own, but losing the database costs clip metadata and **spanned-clip stitching**. Long takes are split into roughly 4 GB chunks on the card. With the database, an editor’s media browser joins them back into one clip; without it, they arrive as separate pieces. Copy the whole card root, not just the clip folder, and check those folders made it before you format the card.

**The verification blind spot.** Comparing *size + file name* lists between card and destination works, but it ignores folders. Duplicate file names in different subfolders then show up as “missing” when they aren’t. Before declaring anything missing, run `find <card> <copy> -name '<file>'` and read the full paths on both sides.

**For irreplaceable footage, image the card.** A disk image is byte-for-byte, with hidden and system files intact, which a Finder copy is not. On macOS: find the card with `diskutil list`, then build the image with `hdiutil create -srcdevice /dev/diskN …` (see `man hdiutil` for the format options). Mount the image with `hdiutil attach` and compare file counts against the card before you format it.

**Ghost mounts.** Re-inserting a card can leave two mounts: `/Volumes/CARD` and `/Volumes/CARD 1`, holding different file counts. Check every mount before calling a backup complete.

**The card sets the speed, not the connection.** Copying about 67 GB of clips *to* a card ran at 51 MB/s through the camera over USB. In the laptop’s built-in SD slot it was still 51 MB/s (measured with `iostat`). That card was a Class 10 / UHS-I card, and 51 MB/s is its maximum write speed, so changing the connection changes nothing. To go faster, use a UHS-II V60 or V90 card.

**Resuming a stopped copy.** Finder deletes the half-copied file when you press stop. To resume, compare file sizes on both sides and copy only the missing clips (`ditto` keeps metadata).

---

## 4. When “0 files” means “not allowed to look”

An agent counting files in a protected cloud-sync folder got **0** and reported the folder as empty. It wasn’t. macOS privacy protection had refused access (“Operation not permitted”), and the count command had thrown its error output away:

```bash
find "$FOLDER" -type f 2>/dev/null | wc -l     # prints 0 – and hides why
find "$FOLDER" -type f | wc -l                 # prints the permission error too
```

The rules that came out of it:

- **Never discard error output when counting.** A count of zero is a claim, and it needs its errors shown.
- **Report three states, never two:** *missing*, *unverifiable* (I can’t read it) and *unmounted* (the drive isn’t attached). During one reference repair, 284 references sat in a folder the agent couldn’t read. They were reported as unverifiable, not lost.
- **Hand protected-folder checks to a human.** The person runs a one-line Terminal command with their own permissions. Removable cards and network volumes read fine.

More on running automation within macOS’s permission model: [local-ai-on-a-mac.md](local-ai-on-a-mac.md).

---

## 5. Choosing a donor project for generated CapCut projects

My CapCut writer builds new projects from a *donor*: an existing project used as a skeleton, because CapCut has no public project API ([capcut-draft-format.md](capcut-draft-format.md)). A donor that referenced footage held only in cloud storage made every generated project crash CapCut on open. Stripping the donor’s tracks didn’t help, because its media list still carried the missing paths.

**Check all three before building:**

1. **Every media path is on disk.** Every `path` in the donor’s video, audio and image materials must exist on disk: 0 missing.
2. **The canvas is already the target shape.** A 16:9 donor silently makes a 16:9 reel.
3. **It has the fewest tracks and segments.** Less donor baggage to strip.

Scan your projects with those three filters rather than trusting a default donor. The clean vertical donor I settled on had one track and nothing missing.

**And the rules around it:**

- **Never copy a project folder wholesale.** Three copies kept the original’s internal timeline folder and main timeline ID, so four projects shared one timeline identity, and the original then wouldn’t open. That is the likely cause rather than a proven one, because the editor’s logs are encrypted. Every generated project gets new IDs. [`sa_capcut_writer.py`](../tools/sa_capcut_writer.py) builds from a donor skeleton, skips the donor’s `Timelines/` folder and writes a fresh one under a new ID.
- **Write both timeline copies, then read them back.** Newer CapCut keeps the live timeline in `Timelines/<main_timeline_id>/draft_info.json`; the root `draft_info.json` is legacy. Writing only the root reports success while the project opens on the donor’s timeline. The writer asserts that the two copies are byte-identical and that exactly one timeline is listed. This applies to single-timeline projects; on a project with several timelines the root copy is the parent video and must be left alone (see [capcut-draft-format.md](capcut-draft-format.md)).
- **Never edit the editor’s own project index** (`root_meta_info.json`).
- **Check that the editor is closed properly.** `pgrep -x CapCut` doesn’t find CapCut. List process names with `ps -axo comm` instead, and remember that a `grep` for “capcut” also matches its own command line.

---

## 6. Clearing an editor’s caches, and other safe space-saving

**Editor caches.** CapCut keeps projects and caches in separate folders under `~/Movies/CapCut/User Data/`. Some cache folders are regenerable scratch; others hold material that projects point to. The method:

1. Close CapCut, and confirm it is closed (section 5).
2. Search **every** project JSON for paths into the cache. Project files are plain-text JSON, so the search is a valid test.
3. **Keep** every folder that any project references. In my case those were `effect`, `music`, `artistEffect`, `onlineMaterial` and `ObjectLocked`, plus the app’s own `ressdk_db` and `cloudDraft`.
4. **Clear the contents of the unreferenced folders, but keep the folders themselves.** These were `SmartCrop` (auto-reframe analysis), `agencycache` (proxy copies), `prerender` (preview renders), `frameThumbnail` and `audioWave`.
5. Search a second time for zero references to the cleared folders, then confirm that the project count and project folder size are unchanged afterwards.

CapCut rebuilds the cleared caches on demand, so the first open of an old project is slower while thumbnails and proxies come back.

**Before moving any footage,** find out who uses it. Every editor stores media as an absolute path, so a moved file reopens as missing media. [`sa_refmap.py`](../tools/sa_refmap.py) maps every media reference in the editing projects on the Mac, and `sa_refmap.py free <dir>` lists files that nothing references. [`sa_organize.py`](../tools/sa_organize.py) tidies loose files only and writes an undo journal.

**Reported size isn’t reclaimable size.** A package-manager cache reported about six times more space than deleting it actually freed, because the environments built from it share those blocks on disk. Measure free space before and after rather than trusting a folder’s size.

**Lossless compression, with a record.** [`sa_compress.py`](../tools/sa_compress.py) uses macOS’s transparent APFS compression (`ditto --hfsCompression`). Files stay where they are and open exactly as before. It skips anything open in an app, changed in the last 7 days, or saving under 10%, and it records every file in a manifest. Undo for one file is `ditto --nohfsCompression F F.tmp && mv F.tmp F`. It pays off on text-like data such as transcripts, logs and JSON. When tested, camera RAW files and TIFF masters gained nothing (they are already compressed inside), so they are on the skip list. Video masters and approved edits are never re-encoded to save space.

**Deleting is a human job.** The agents clear regenerable caches and quarantine duplicates. Emptying the bin, and any hard delete of my own files, I do myself.

---

## 7. Cloud sync that undoes your clean-up

With the cloud account at 100% of its quota, I deleted a quarantine of confirmed duplicates through the Mac’s synced folder. Every file came back. A later *move* of other duplicates was undone too: spot checks found 25 of 25 files back in their original place, and the destination folder gone. The client couldn’t sync local changes to a full account, so it restored the server’s state. Nothing was lost, and nothing was freed.

- **When the account is full, act on the server side,** on the provider’s website, not through the synced folder.
- **Verify before claiming space saved.** Check that the files are really gone and that the recycle bin has filled. Quota only comes back once the recycle bin is emptied.
- **Expect the mass-delete warning.** The client asks for confirmation above roughly 200 items.
- **Exporting into a synced folder still needs local space** until the file has uploaded and been made online-only.

**Finding duplicates without downloading anything.** [`sa_dedupe.py`](../tools/sa_dedupe.py) matches on name and size from metadata alone, so online-only files are never downloaded. With `--hash` it fingerprints the contents of files that are already local. It moves duplicates into a quarantine folder rather than deleting them, and never removes the last copy. Before anything is finally deleted, each file is re-checked: it is still present at the expected size, and its twin outside the quarantine is present at the same size. Every deletion is logged with the path of the copy that stays. A name-and-size match is a strong candidate, not proof. For irreplaceable files, compare content hashes first.

---

## 8. Culling hours of rushes with parallel AI agents

About 90 raw clips, 28 minutes of 4K, culled to the best window in each:

1. **Sample.** Take one frame every 2 s at 384 px wide, and rename the frames `t000`, `t002`, `t004`… so that **the file name is the source timecode**:
   ```bash
   ffmpeg -i clip.mp4 -vf "fps=0.5,scale=384:-2" frames/f%03d.jpg   # then rename f001 -> t000, f002 -> t002 …
   ```
2. **Make one labelled contact sheet per clip** (`media_kit.sheet()` in [`media_kit.py`](../tools/media_kit.py)). [`sa_frames.py`](../tools/sa_frames.py) does the same job with timecode burned into every frame.
3. **Fan out.** Twelve vision-capable agents each took batches of eight sheets. Each returned a structured verdict per clip: `category`, `best_start_s`, `best_end_s`, `quality` (1–5) and a one-line `desc`, plus any job-specific flags. A schema-validated return means the results can be merged without anyone reading prose.
4. **Trim** each best window with a **0.3 s handle** on both sides. Name the outputs `NN_qN_category_clip` so the best sort first, and add a shot list and a contact sheet of the picks.

Two workflow gotchas from that run:

- **Parse defensively.** The batch arguments reached the workflow script as a JSON *string*, not an array, and every parallel item failed. Always `JSON.parse` arguments that might arrive as text.
- **Read the right output.** The run’s journal didn’t carry the agents’ return values; the full results were in the task’s output file. Read the output before concluding the agents returned nothing.

**For event footage, gate on camera motion before choosing anything.** Long takes (over about 30 s) are continuous recordings: read the whole clip and pick the right chunk, not the first usable seconds. [`sa_event_motionmap.py`](../tools/sa_event_motionmap.py) samples each clip at 10 fps, fits the frame-to-frame motion, and labels every 0.5 s:

| Label | What it detects | Verdict |
|---|---|---|
| `lens_zoom` | Scale changing with a clean rigid fit, so an optical zoom with no parallax | Reject |
| `push` | Scale changing *with* parallax: the camera walking in or out | Usable move |
| `whip` | A fast pan, over about 45% of the frame width per second | Cut point only |
| `shake` | Jerky, high-frequency motion | Reject |
| `focus_hunt` | Sharpness dipping more than 45% below its local median while the camera is near-still | Reject |
| `exposure` | Mean brightness jumping more than 18 levels in 0.5 s while near-still | Reject |
| `stable` | None of the above | Usable |

The thresholds were calibrated by eye on one shoot. Retune them for each camera. The gate came out of a mistake. On an earlier pass, five parallel editor agents logged 137 verified candidate windows from 52 minutes of event footage in about 20 minutes. Fast, but a window with the lens zooming still reached the cut, so now every candidate passes the motion map before planning. How the windows then become a cut is in [event films: measure the approved reference before cutting](learning-an-editors-style.md#10-event-films-measure-the-approved-reference-before-cutting).

**Privacy.** Screen frames never go to generation services, and other work media goes to one only with approval for that project. Routine checks run locally and upload nothing; large one-off passes like this cull used AI coding agents ([security-and-data-policy.md](security-and-data-policy.md)).

---

**Related:** [capcut.md](capcut.md) · [capcut-draft-format.md](capcut-draft-format.md) · [local-ai-on-a-mac.md](local-ai-on-a-mac.md) · [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md) · [learning-an-editors-style.md](learning-an-editors-style.md) · [photo-fidelity-retouching.md](photo-fidelity-retouching.md) · [security-and-data-policy.md](security-and-data-policy.md) · [six-months-timeline.md](six-months-timeline.md)
