# Tutorial-video master templates: three approved references
> When a request looks like a tutorial / walkthrough / feature / system-explainer video,
> START HERE. These 3 CapCut projects are the gold standard (brand films are separate — see the [style DNA](style-dna.md)).
> Decoded from the finished, approved timelines themselves. Real project titles, products and people are withheld; each master is named by what it is.

**Deep Claude-facing recipe:** [capcut-tutorial-templates.md](capcut-tutorial-templates.md).
Use that page when the task is to recreate the style or pre-build a CapCut skeleton.

## The 3 masters (exact final timelines)
| Master | Final timeline | Approved range | Style |
|---|---|---|---|
| **1. Short walkthrough** (an internal web tool) | main draft | 00:00:00.967 → 00:01:02.600 (61.6s) | screen-rec walkthrough, 7 scenes |
| **2. Feature tour** (a business phone app) | main export range / Timeline 02 content | 00:16:46.367 → 00:20:06.467 (200.1s) | feature tour, fast-cut |
| **3. Long training** (an HR process module) | main export range | 01:44:31.100 → 01:53:54.967 (563.9s) | animated-explainer base, adjusted in CapCut |

## The two pacing modes (choose by content type)
**A. Screen-rec / feature style** (masters 1 and 2):
- median cut **4.0s**, text-dense (~1 text element per 2s), lower-thirds + captions
- VO per line ("SubBlock" pattern = [`sa_vo.py`](../tools/sa_vo.py) output), UI zoom to hide chrome
**B. Animation / animated-explainer style** (master 3):
- median scene **8.0s**, text-LIGHT (animation carries its own text)
- music re-enters every ~3.5min as section markers

## Invariants (every final, no exceptions)
- **Bg music enters exactly at the in-point** (proven on both: music start == export_range start)
- **The logo outro closes** (landscape white-background version for 16:9, portrait version for 9:16)
- Transitions: Slow Fade default, Camera Glow for polish, Blur = the one effect (per the edit-DNA report)
- 1920×1080 for tutorials; never replace old projects — new experiments = new drafts

## The workflow when a similar request lands
**Standing rule:** never generate a voiceover by default. The editor's projects are NOT all the same shape —
storytelling, screen-recorded system training, HR process, app feature tours, tribute/farewell montage (see the [style DNA](style-dna.md)) — each has different needs, and
several (e.g. tribute montages) use NO voice at all, music-only. Only run [`sa_vo.py`](../tools/sa_vo.py) when the editor explicitly asks
for a voiceover. Default to asking or waiting, not assuming VO is part of the job.
1. Brief arrives → identify which style this is (tutorial A/B, brand film, tribute montage, other) → write scene plan
2. VO only if requested → `sa_vo.py` (confirm the voice; the last approved voice is the starting point)
3. If screens needed: get raw capture → describe it locally with [`sa_see.py`](../tools/sa_see.py) → map timecodes to scenes (cut sheet)
4. Remotion renders branded overlays if wanted (lower-thirds/end cards)
5. **Write the CapCut draft directly** (skeleton: clips + VO-if-any + music-from-in-point + titles-if-any + outro placed; CapCut CLOSED while writing; backup draft_info.json first; donor schemas copied from an existing working draft — see [CapCut draft format](capcut-draft-format.md))
6. The editor opens CapCut → taste pass only.

## Where the deep data lives
- Per-project stats: an edit-DNA report regenerated from every draft with [`sa_capcut.py`](../tools/sa_capcut.py) (`python3 tools/sa_capcut.py -o EDIT_DNA.md`); anonymised numbers per style (the tutorial and training styles among them) are in [EDIT_DNA_STATS.json](../Reference/EDIT_DNA_STATS.json)
- Master 1 assets/cut sheet: kept in its own project folder (ASSEMBLY.md, title_cards.md, VO folders)
- Draft-writing technique: [CapCut draft format](capcut-draft-format.md) (editing a CapCut draft directly)

Related: [CapCut hub](capcut.md) · [style DNA](style-dna.md) · [tutorial recipe for Claude](capcut-tutorial-templates.md) · [CapCut live eyes](capcut-live-eyes.md)
