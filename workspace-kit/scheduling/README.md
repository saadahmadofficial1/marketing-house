# Scheduling: unattended overnight runs on macOS

The two property lists in this folder run the workspace’s heavy local work in the small hours and check at 07:00 that it actually finished. The reason they look odd – the job opens an *app* rather than running a script – is macOS privacy control: a `launchd` job that runs `bash` on a script under `~/Documents` is silently refused. The step-by-step recipe, with a full example plist, is in [the macOS nightly recipe](../../playbooks/templates/macos-nightly-launchd.md); this page explains the two files that ship here.

---

## The problem

Since macOS Catalina, `~/Documents`, `~/Desktop` and `~/Downloads` are protected folders (TCC). A launch agent that runs `/bin/bash ~/Documents/<workspace>/Tools/nightly.sh` gets “Operation not permitted” or exit code 126 – and because nobody is watching at 2 am, the job simply never happens. My own brain-backup job died that way for weeks before the health check noticed.

## The fix: a frozen applet with Full Disk Access

Build a tiny AppleScript applet **once**, whose only content is “run the nightly shell script”, and grant that applet Full Disk Access a single time in System Settings → Privacy & Security → Full Disk Access:

```bash
osacompile -o ~/Library/<Name>/Nightly.app -e 'do shell script "$HOME/<workspace>/Tools/sa_nightly.sh"'
```

The plist then runs `/usr/bin/open -W -a ~/Library/<Name>/Nightly.app` instead of `bash`. The privacy grant belongs to the applet, so the script it launches can read the workspace.

**Never re-save the applet.** Re-compiling or editing it can invalidate the grant. Every later change goes into the shell script, which the applet merely calls.

The evidence that this is the fix, from the same machine on the same night: the applet-wrapped nightly job’s last exit code is 0, while the 07:00 checker – which still runs `/bin/bash` directly on a script in `~/Documents` – last exited with 126. It was smoke-tested in August; by mid-September, after a Full Disk Access regression, it was being refused. **Give the checker the same applet treatment** (a second applet, or move the check into the first) if you want it to survive a permissions reset.

---

## The files

| File | What it does |
|---|---|
| [`nightly.plist`](nightly.plist) | Runs the applet at 01:12 every night. `KeepAlive` with `SuccessfulExit = false` asks `launchd` to relaunch the job if it exits with an error; `EnvironmentVariables` sets an explicit `PATH`, because `launchd` starts jobs with an almost empty one and tools such as `ffmpeg` would not be found. |
| [`nightcheck.plist`](nightcheck.plist) | The 07:00 dead-man switch: runs the checker, which reads the last-success marker. |
| [`../../tools/sa_nightly.sh`](../../tools/sa_nightly.sh) | The one overnight entry point. Each finished step is appended to a per-day ledger, so a crash or a second run that day resumes at the first unfinished step instead of restarting. If the editor app is open it skips only the step that reads editing projects, never the whole night. It writes `Sessions/_nightly/last_success` as its very last act. |
| [`../../tools/sa_nightcheck.sh`](../../tools/sa_nightcheck.sh) | If `last_success` is older than 10 hours: a macOS notification, plus a line in `Sessions/_nightly/attention.md`, which the agent reads at Step 0 of the next session – so a dead night is the first thing the next session sees. |

Edit both plists before loading them: the label (`com.example.nightly`-style, your own reverse-domain name), the applet path and the checker path. Validate with `plutil -lint <file>.plist`.

---

## Install, test, remove

```bash
cp nightly.plist nightcheck.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/nightly.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/nightcheck.plist

launchctl kickstart -k gui/$(id -u)/<label>          # run it now, to test
launchctl print gui/$(id -u)/<label> | grep "last exit code"

launchctl bootout gui/$(id -u)/<label>               # unload
```

Two behaviours to know:

- **`SuccessfulExit` implies run-at-load.** The job also runs whenever it is loaded – at login, or after a restart – which is why my logs show some mid-morning runs. The ledger makes that harmless: finished steps are skipped.
- **`open -W` reports whether the applet launched, not necessarily how your script ended.** I have not seen the `KeepAlive` retry fire in practice; treat the ledger plus the next night’s run as the real retry. Make the script record failures in its own log and still exit cleanly, so the applet never stops on an error dialog.

## Heavy work belongs in the small hours

Large local-model batches make the machine stutter while someone is working, so they run between 1 and 6 am. The marker is written only after the last step, so one runaway step means “did not finish” every morning: one checking step once ran about ten hours and starved everything after it, and I paused it. A per-step time limit, or heavy steps placed last, is the better fix.

**Optional extras:** `sudo pmset repeat wakeorpoweron MTWRFSU 00:55:00` wakes a sleeping Mac just before the run; wrapping a heavy step in `caffeinate -im` stops it sleeping mid-step.

**The other route:** Claude scheduled tasks already have file access and need no applet – but check their output, not their status. One of mine reported “succeeded” in under five seconds on three separate days while writing nothing; the health check caught it because it demands the job’s own success line plus a fresh output file. Prompt patterns for those jobs are in [scheduled-agent prompts](../../playbooks/templates/scheduled-agent-prompts.md).

## Maturity

| Piece | Status |
|---|---|
| Applet-wrapped nightly runner with resume ledger | **Built, in use** – runs to completion nightly; the logs run from August into October 2026 |
| 07:00 dead-man checker | **Built** – smoke-tested in August and wrote a dead-man note when a night failed; currently refused by the permissions regression described above |
| Optional cloud-text morning note inside the runner | **Experimental** – it has logged “skipped/failed” on most nights since mid-August; the run treats it as optional, so it does not block the clean-exit marker |

---

Related: [macOS nightly recipe](../../playbooks/templates/macos-nightly-launchd.md) · [scheduled-agent prompts](../../playbooks/templates/scheduled-agent-prompts.md) · [running two AI agents](../../playbooks/running-two-ai-agents.md) · [`sa_doctor.py`](../../tools/sa_doctor.py) (the health check that reads the traces)
