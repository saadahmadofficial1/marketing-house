#!/usr/bin/env python3
"""Build FINAL_CHECK.html — Saad's per-video pre-export dashboard.

One card per video: status, what to fix, what to glance at, in plain words
with timestamps. Inputs are the two JSON files the checker and the review pass
leave in the series' 5 ADMIN folder:

    final_check_data.json      measurements (sa_videocheck.py)
    final_check_reviews.json   judged findings, one record per video

Local file only: this runs locally and uploads nothing.
"""
import html
import json
import os
import pathlib
import sys

ADMIN = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN"
# optional {tag: module title} map, e.g. {"T03": "Create a quote"}
NAME_FILE = ADMIN / "module_names.json"
NAME = json.loads(NAME_FILE.read_text()) if NAME_FILE.exists() else {}
# optional tag to pin first (e.g. the video being fixed next); its missing outro is a warning
PIN = os.environ.get("FINAL_CHECK_PIN", "")
COL = {"FIX": "#e5484d", "LOOK": "#f5a623", "READY": "#30a46c"}
SEV = {"fix": "#e5484d", "look": "#f5a623", "note": "#8b8d98"}


def mmss(t):
    if t is None:
        return ""
    return f"{int(t // 60)}:{int(t % 60):02d}"


def esc(s):
    return html.escape(str(s or ""))


def chip(label, ok, warn=False):
    c = "#30a46c" if ok else ("#f5a623" if warn else "#e5484d")
    return f'<span class="chip" style="border-color:{c};color:{c}">{esc(label)}</span>'


def card(m, r):
    tag = m["tag"]
    verdict = (r or {}).get("verdict", "LOOK")
    col = COL[verdict]
    dur = m.get("picture_end_s") or 0
    intro = ("on the timeline" if m["intro_on_timeline"]
             else f"gap left ({m['head_s']:.1f}s) — drag it in" if (m.get("head_s") or 0) > 1
             else "in the media panel — no gap yet")
    chips = [
        chip(f"intro: {intro}", m["intro_on_timeline"], warn=True),
        chip("outro placed" if m["outro"]["present"] else "outro: none yet",
             m["outro"]["present"], warn=(tag == PIN)),
        chip("sign-off laid" if m.get("signoff") else "sign-off: not laid",
             bool(m.get("signoff")), warn=True),
    ]
    rows = []
    for f in (r or {}).get("findings", []):
        sev = f.get("severity", "note")
        t = mmss(f.get("t"))
        rows.append(
            f'<div class="f"><span class="sev" style="background:{SEV[sev]}"></span>'
            f'<span class="t">{t}</span><div><b>{esc(f.get("what"))}</b>'
            + (f'<div class="d">{esc(f["detail"])}</div>' if f.get("detail") else "")
            + (f'<div class="d fix">→ {esc(f["fix_hint"])}</div>' if f.get("fix_hint") else "")
            + "</div></div>")
    quick = "".join(f"<li>{esc(q)}</li>" for q in (r or {}).get("quick_look", []))
    unk = "".join(f"<li>{esc(u)}</li>" for u in (r or {}).get("unknowns", []) if u)
    return f"""
<div class="card" id="{tag}">
 <div class="head" style="border-left:6px solid {col}">
   <div><span class="tag">{tag}</span> <span class="nm">{esc(NAME.get(tag, ''))}</span></div>
   <div class="right"><span class="len">{mmss(dur)}</span>
     <span class="verdict" style="background:{col}">{verdict}</span></div>
 </div>
 <div class="chips">{''.join(chips)}</div>
 {'<div class="fs">' + ''.join(rows) + '</div>' if rows else '<div class="clean">Nothing found — matches your reference style.</div>'}
 {f'<div class="quick"><b>30-second glance before export</b><ul>{quick}</ul></div>' if quick else ''}
 {f'<div class="unk"><b>Could not verify</b><ul>{unk}</ul></div>' if unk else ''}
</div>"""


def build():
    data = {m["tag"]: m for m in json.loads((ADMIN / "final_check_data.json").read_text())}
    reviews = {r["tag"]: r for r in json.loads((ADMIN / "final_check_reviews.json").read_text())}
    order = sorted(data, key=lambda t: ({"FIX": 0, "LOOK": 1, "READY": 2}
                   .get((reviews.get(t) or {}).get("verdict", "LOOK"), 1), t))
    # the pinned video (FINAL_CHECK_PIN) goes first
    if PIN in order:
        order.remove(PIN); order.insert(0, PIN)
    counts = {"FIX": 0, "LOOK": 0, "READY": 0}
    for t in data:
        counts[(reviews.get(t) or {}).get("verdict", "LOOK")] += 1
    toc = "".join(
        f'<a href="#{t}" style="color:{COL[(reviews.get(t) or {}).get("verdict","LOOK")]}">{t}</a>'
        for t in order)
    body = "".join(card(data[t], reviews.get(t)) for t in order)
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Training series — final check before export</title><style>
 body{{background:#101114;color:#e8e9ec;font:15px/1.5 -apple-system,system-ui;margin:0;padding:28px 20px 80px;max-width:880px;margin-inline:auto}}
 h1{{font-size:22px;margin:0}} .sub{{color:#8b8d98;margin:4px 0 18px}}
 .totals span{{display:inline-block;margin-right:14px;font-weight:600}}
 .toc{{margin:10px 0 24px;display:flex;flex-wrap:wrap;gap:8px}}
 .toc a{{text-decoration:none;font-weight:600;font-size:13px;border:1px solid #2a2c33;border-radius:6px;padding:2px 8px}}
 .card{{background:#17181c;border:1px solid #24262c;border-radius:12px;margin:14px 0;overflow:hidden}}
 .head{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#1b1d22}}
 .tag{{font-weight:700;font-size:17px}} .nm{{color:#a9abb4;margin-left:6px}}
 .right{{display:flex;gap:10px;align-items:center}} .len{{color:#8b8d98;font-variant-numeric:tabular-nums}}
 .verdict{{color:#0b0c0e;font-weight:800;font-size:12px;border-radius:6px;padding:3px 9px}}
 .chips{{padding:10px 16px 0;display:flex;flex-wrap:wrap;gap:8px}}
 .chip{{border:1px solid;border-radius:20px;padding:2px 10px;font-size:12.5px}}
 .fs{{padding:8px 16px 4px}}
 .f{{display:flex;gap:10px;padding:8px 0;border-top:1px solid #202228}}
 .f:first-child{{border-top:none}}
 .sev{{width:8px;height:8px;border-radius:50%;margin-top:7px;flex:none}}
 .t{{color:#8b8d98;min-width:44px;font-variant-numeric:tabular-nums}}
 .d{{color:#a9abb4;font-size:13.5px}} .fix{{color:#7cc4a0}}
 .clean{{padding:14px 16px;color:#30a46c}}
 .quick,.unk{{margin:10px 16px 14px;padding:10px 14px;background:#1b1d22;border-radius:8px;font-size:13.5px}}
 .quick b{{color:#f5a623}} .unk b{{color:#8b8d98}} ul{{margin:6px 0 0;padding-left:20px}}
</style></head><body>
<h1>Training series — final check</h1>
<div class="sub">Checked against your reference style ·
intro + voice line are in every project's media panel · you place them and export</div>
<div class="totals">
 <span style="color:{COL['FIX']}">{counts['FIX']} to fix</span>
 <span style="color:{COL['LOOK']}">{counts['LOOK']} worth a look</span>
 <span style="color:{COL['READY']}">{counts['READY']} ready</span>
</div>
<div class="toc">{toc}</div>
{body}
</body></html>"""
    aj = ADMIN / "automation_audit.json"
    if aj.exists():
        a = json.loads(aj.read_text())
        li = lambda xs: "".join(f"<li>{esc(x)}</li>" for x in xs)
        page = page.replace("</body>", f"""
<div class="card"><div class="head" style="border-left:6px solid #8b8d98">
 <div><span class="tag">The automation's own record</span>
 <span class="nm">what it wrote, what it got wrong — analysis only, nothing changed</span></div></div>
 <div class="quick" style="margin-top:12px"><b style="color:#30a46c">{esc(a['frozen'])}</b></div>
 <div class="quick"><b>Written this session, re-audited clean</b><ul>{li(a['writes_tonight'])}</ul></div>
 <div class="quick"><b style="color:#e5484d">Errors it made along the way</b><ul>{li(a['errors_made_this_session'])}</ul></div>
 <div class="quick"><b>One interaction to know about</b><ul><li>{esc(a['known_interaction'])}</li></ul></div>
</div></body>""")
    out = ADMIN / "FINAL_CHECK.html"
    out.write_text(page)
    print(f"-> {out}  ({counts})")


if __name__ == "__main__":
    build()
