# Second-Machine CapCut Findings – Personal Mac Style Data

> Companion pages: [learning an editor’s style from finished timelines](learning-an-editors-style.md) · [the full editing style](editing-style-full.md) · [Style DNA](style-dna.md) · [the CapCut hub](capcut.md) · [editing technique, observed](editing-technique-observed.md). Project, client, and brand names are excluded; this page records structural patterns and empirical rules only.

**Updated:** October 2026  
**Status:** Measured reference corpus (17 active timelines). Targets available for planning.

| Part | Status | Notes |
|---|---|---|
| Second-machine draft scan | **Measured** | 25 draft folders scanned; 17 active timelines analysed |
| Cut rhythm and vertical reel targets | **In use** | Empirical targets for 9:16 vertical edits |
| Cross-corpus comparison | **Documented** | Compared against published office style baselines |

---

## 1. What was measured and how

This page records the editing patterns measured from CapCut desktop projects on a secondary machine (a personal MacBook Air). The aim was to capture cut rhythm, layer architecture, and styling habits across a broader collection of personal, experimental, and long-form projects, complementing the primary office corpus.

The measurement was entirely read-only and extracted patterns only:

- **Non-destructive inspection:** A standalone Python script (`python3 -I`) inspected `draft_info.json` project by project. It never wrote to the CapCut folders and decoded no source media, video frames, thumbnails, audio waveforms, or exported files.
- **Metrics extracted per project:** Canvas dimensions, total duration, track counts by type, video-segment count, median and 90th percentile (p90) shot lengths on the busiest video track, count of speed-altered segments, transitions used (type and frequency), text layer count, median on-screen text duration, font size, audio track and segment counts, keyframes, animation materials, visual effects, colour filter and adjustment tracks, balance of stills against video clips, and filesystem modification timestamps.
- **Timeline dates:** Dates derive from filesystem modification times (`mtime`) because CapCut folder names follow an `MMDD` naming format without a year. Because file copies, backups, and re-saves alter modification timestamps, these dates are treated strictly as indicative hints.
- **Cut rate measurement:** Shot lengths are calculated from the single busiest video track. On complex vertical reels stacking 5 to 20 video tracks, this metric reflects primary clip length rather than the perceived composite cut rate.
- **Corpus yield:** Of 25 draft folders scanned, 22 were structurally readable and 17 contained populated timelines. Five folders were empty stubs (zero duration, no tracks), and three drafts were unreadable because they use newer encrypted draft schemas.

---

## 2. Edit families on the second machine

Across the 17 populated timelines, projects group naturally into six distinct editing families spanning vertical and landscape formats.

### Summary of structural findings

- **Vertical 9:16 dominance (11 of 17 projects):** The majority of timelines are vertical. The designed reels cut at a 1.4–1.8 s median and hold text cards for a consistent **~1.85 s at font size ~15**. Stills, keyframes, layered tracks, and selective transitions are used heavily.
- **Landscape work splits in two:** Fast-cut montage cuts at a brisk 1.2 s median with almost no transitions. By contrast, long-form or screen-led timelines run at 4.0–10.4 s medians with extended holds and dense text or audio structures.
- **Restrained speed changes:** Speed modifications are sparse, appearing on only 7–9% of shots in the three designed reels and the single montage that use them, and on isolated clips in a few others.
- **Gap in mid-2026 coverage:** No readable draft dates from June–July 2026. Three folders touched in early June 2026 use encrypted draft schemas and could not be decoded. Experimental workflows from that window are therefore unrepresented in this dataset.

### Per-family metrics (17 readable projects)

| Family | n | Canvas | Duration | Video segs | Shot median / p90 (s) | Transitions | Speed segs | Text (count, on-screen, size) | Audio tracks / segs | Keyframes | Filter + adjust tracks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A. Designed vertical reels** | 3 | 1080×1920 | 86–125 s (median 110) | 22–43 | 1.4 / 1.9, 4.1 / 6.5, 1.8 / 5.0 | 11, 7, 0 (Delay Zoom, Camera Glow, Pull in, Film Erase) | 3, 3, 0 | 60, 38, 15; 1.83–1.87 s; size ~15 | 0, 8/30, 4/15 | 56, 47, 8 | 2–3 |
| **B. Short vertical clips** | 6 | 1080×1920 (one 886 wide, one 1072 wide) | 5–38 s (median 10) | 1–3 | No cuts (single holds of 5–36 s) | 0 (one "Mix") | 0–1 | 0 (one card, 10 s) | 0–1 | 0 (one clip has 9) | 0 (one clip has 2) |
| **C. Vertical voice-led or stills-led** | 2 | 1080×1920 | 61 s, 286 s | 12, 1 | 3.7 / 54.7, 75 (one long hold) | 0 | 0 | 6 cards at 2.6 s, size 16; 1 caption spanning 75 s | 1/1, 18/46 | 0 | 0 |
| **D. Landscape fast-cut montage** | 1 | 1920×1080 | 165 s | 53 | 1.2 / 2.9 | 2 (Blur) | 4 | 4 cards; 5.6 s; size 7 | 3/3 | 1 | 2 |
| **E. Landscape long-form or screen-led** | 3 | 1920×1080 (one 1920×1075) | 473 s, 509 s, 2885 s | 15–34 | 10.4 / 45, 5.5 / 20, 4.0 / 10.7 | 0 | 0 | 88 at 2.1 s (size 10); 0; 34 at 11 s (size 5) | 0, 0, 12/44 | 0 | 3, 0, 0 |
| **F. Landscape snippets** | 2 | 1920×1080 | 21 s, 35 s | 5–7 | 5.1 / 7.1, one 35 s hold | 0 | 0–1 | 2 at 21 s; 0 | 3/3; 0 | 0 | 0 |

### Additional asset patterns

- **Stills against video:** Family A contains 20 stills to 77 video segments (roughly 1 in 5). Family C’s stills-led reel contains 9 stills to 3 video clips. In Family E, the longest project balances 17 stills against 17 video segments.
- **Animation materials:** Concentrated heavily on multi-track compositions: 95, 68, and 31 in Family A; 100 in the 88-text landscape build; 54 in the longest project.
- **Effects utilisation:** 39 visual effects in the 88-text landscape project; 14 on one vertical clip; 6–7 on typical vertical reels.
- **Excluded folders:** Five empty drafts (0 duration, no tracks; 20% of scanned folders) and three encrypted drafts.

---

## 3. Comparison with the office style data

Comparing these figures with the office baseline documented in [learning an editor’s style](learning-an-editors-style.md), [the full editing style](editing-style-full.md), and [Style DNA](style-dna.md) highlights consistent personal habits alongside format-specific variations.

### Matches

- **Hard cuts as the governing default:** The landscape montage (Family D) uses transitions on only 2 of 53 cuts (4%), matching the office event recap figure of 7 of 59 (12%). Furthermore, the appearance of "Camera Glow" across two vertical reels matches the approved transition catalogue for chapter markings.
- **Cut rhythm continuity:** Montage D’s 1.2 s median sits squarely within the office’s 0.9–1.8 s premium-reel window. The designed vertical reels (Family A) at 1.4–1.8 s occupy the deliberate end of the same range.
- **Text display holds:** Text cards held for ~1.85–2.1 s match the office standard call-out hold of ~2.1 s.
- **Restrained speed ramps:** Speed changes are applied sparingly, matching the practice in tribute edits where gentle slowing (around 0.8×) emphasises emotion without distorting motion.

### Differences

- **Transition density in designed reels:** Family A projects carry transitions on 16–26% of joins (11 of 43 cuts on the busiest reel), well above the office event default of under 12%. This reflects the distinction noted in [editing-style-full.md](editing-style-full.md): commemorative and designed occasion pieces sustain more transitions and graphic overlays.
- **Vertical multi-track complexity:** Vertical reels lean heavily on keyframed stills, animation materials, and up to 20 stacked video tracks. In the office documentation, this depth of layering was primarily reserved for AI-generated or commemorative assemblies rather than general event coverage.
- **Extended holds on screen-led work:** Long landscape timelines hold shots far longer (4.0–10.4 s median) than event reels. This aligns closely with the [training-video production](training-video-production.md) guidance, where dense interfaces require holds of 6 seconds or more for visual comprehension.
- **Non-standard canvas shapes:** Three projects inherit source dimensions (886×1920, 1072×1920, and 1920×1075) rather than conforming to rigid 1080×1920 or 1920×1080 boundaries.

### New observations from this machine

- **Single-clip inspection stubs:** A sizeable proportion of vertical projects are short, uncut clips (5–38 s). These serve as review trims or checks for source and generated media rather than multi-clip narrative assemblies.
- **Multi-track audio beds:** Deep audio layering emerges in two timelines (18 tracks / 46 segments, and 12 tracks / 44 segments), combining multiple short ambient and sound-design pieces under a single visual take.
- **Structured call-out architecture:** One landscape timeline features 88 distinct text layers averaging 2.1 s each, representing a dedicated subtitle or structured call-out pass.
- **Format encryption:** Newer CapCut desktop releases encrypt draft metadata (affecting 3 of 25 folders), requiring updated tooling to inspect modern projects.

---

## 4. Ten editing rules learned from the second machine

These ten empirical rules reflect patterns measured across the 17 timelines and can be adopted directly by editing agents and automated planning tools:

1. **Vertical reel text cards: hold ~1.85 s at font size ~15.**  
   *Evidence:* 3 of 3 vertical reels with text (113 text layers; project medians of 1.83 s, 1.83 s, and 1.87 s).
2. **Cut fast vertical reels at a 1.4–1.8 s median with p90 under 2.0 s when pace is the objective.**  
   *Evidence:* 2 of 3 reels (1.37 s and 1.83 s medians). The third reel (4.07 s) represents an overlay-heavy, slower-paced composition.
3. **Cap transitions at about 25% of joins on designed reels and about 5% on raw montages.**  
   *Evidence:* Reels 11 of 43 and 7 of 32 joins; montage 2 of 53 joins. Hard cuts must constitute the remaining 75–95% of edits.
4. **Keep speed changes to 10% of timeline segments or fewer.**  
   *Evidence:* 5 of 5 projects using speed ramps (3/43, 3/32, 4/53, plus single clips).
5. **Use stills and keyframes as part of vertical reels, with an animation on each still.**  
   *Evidence:* Stills in 9 of 17 projects; keyframes in 4 of 5 multi-clip vertical projects and 0 of 8 landscape projects.
6. **Grade at timeline level with a filter plus adjust pair (2–3 tracks) instead of per clip.**  
   *Evidence:* 6 of 17 projects apply a global filter plus adjustment pair across separate tracks, avoiding fragmented clip-level adjustments.
7. **Layer audio in pieces for voice-led or long-take projects, and keep the layers on separate tracks.**  
   *Evidence:* 3 projects with 8–18 audio tracks across 30–46 segments to build layered soundscapes beneath extended takes.
8. **Set the output canvas explicitly (1080×1920 or 1920×1080) rather than inheriting the first clip’s shape.**  
   *Evidence:* 3 of 17 projects inherited irregular source resolutions (886×1920, 1072×1920, 1920×1075).
9. **For long landscape work, hold shots 4–10 s and use text cards of ~2.1 s or longer holds on dense screens.**  
   *Evidence:* 3 of 3 long-form projects (medians 4.0 s, 5.5 s, 10.4 s).
10. **Housekeeping: skip empty drafts and flag encrypted ones during automated ingest.**  
    *Evidence:* 5 empty stubs and 3 encrypted drafts out of 25 scanned folders.

---

## 5. Limits of the dataset

To maintain appropriate confidence boundaries, several constraints on this dataset must be noted:

- **Sample size:** 17 populated timelines provide a focused rather than exhaustive sample. Family A rules rest on 3 projects, Family D on 1 montage, and Family E on 3 long-form edits.
- **Draft versus export state:** Scanned timelines represent working drafts. Muted tracks, inactive B-roll, and experimental cuts may remain in the project file and differ from the final delivered export.
- **Modification dates as hints:** Filesystem timestamps (`mtime`) serve as proxies for project chronology; file moves and re-saves make them indicative hints rather than definitive dates.
- **Track-level cut rate bias:** Shot durations are derived from the busiest video track. On complex multi-track reels with heavy B-roll layering, this overstates clip duration relative to visual cut frequency.
- **Qualitative omissions:** The scan analysed structure and metadata only. Audio fidelity, source video composition, narrative rhythm, and text copy were not evaluated.
- **Unread encrypted projects:** Three draft folders use encrypted schemas that could not be decoded, leaving experimental work from June–July 2026 unmeasured.
- **Pattern-only reporting:** Some projects appear to be commercial or client work (notably the 48-minute timeline and the 88-text build, judged by timeline shape only). They are described strictly by pattern and structural metrics, with all identifying names and media references excluded.
