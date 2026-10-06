# Recipe: unattended nightly runs on macOS

A recipe for running heavy local work overnight on a Mac whose workspace sits in `~/Documents`, where macOS privacy controls (TCC) silently refuse a `launchd` job that runs a shell script. A launchd job of mine died that way for weeks before anything noticed. The fix is to wrap the script once in an AppleScript applet, grant the applet Full Disk Access one time, and have `launchd` open the applet – plus a 07:00 dead-man check and a resume ledger so a dead night is impossible to miss. The working files are [`sa_nightly.sh`](../../tools/sa_nightly.sh), [`sa_nightcheck.sh`](../../tools/sa_nightcheck.sh) and the two plists in [`workspace-kit/scheduling/`](../../workspace-kit/scheduling/README.md).

**Maturity:** **Built, in use.** After a heavy step was paused in mid-September the runner was unblocked and has completed nightly since; see [the scheduling page](../../workspace-kit/scheduling/README.md#maturity) for the per-piece status, including the checker’s own permissions problem.

---

## 1. Why the obvious way fails

`launchd` runs `/bin/bash /Users/you/Documents/Workspace/Tools/nightly.sh`. Since macOS Catalina, `~/Documents`, `~/Desktop` and `~/Downloads` are privacy-protected, and `bash` launched by `launchd` has no grant to read them. The job exits with “Operation not permitted” or code 126. Nothing pops up; nobody is awake. Cron fails the same way.

Granting Full Disk Access to `/bin/bash` itself would work, and would also hand every script on the machine that access. Don’t.

## 2. The fix: a frozen applet

Build a one-line applet **once**:

```bash
mkdir -p ~/Library/Nightly
osacompile -o ~/Library/Nightly/Nightly.app -e 'do shell script "$HOME/Documents/Workspace/Tools/sa_nightly.sh"'
```

Then System Settings → Privacy & Security → Full Disk Access → **+** → `~/Library/Nightly/Nightly.app`. That is the only manual step, and it happens once.

**Never re-save the applet.** Recompiling or editing it can drop the grant. All future changes go into `sa_nightly.sh`; the applet only calls it. Write that rule where the next agent will read it, because “just tweak the applet” is the obvious wrong move.

## 3. The nightly plist

Save as `~/Library/LaunchAgents/com.example.nightly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.nightly</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/open</string><string>-W</string><string>-a</string>
    <string>/Users/you/Library/Nightly/Nightly.app</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>1</integer><key>Minute</key><integer>12</integer></dict>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
</dict></plist>
```

| Key | Why |
|---|---|
| `open -W -a <applet>` | Launches the applet through Launch Services so its privacy grant applies; `-W` waits until it has finished. |
| `StartCalendarInterval` 01:12 | Inside the 1–6 am window, off the hour so it doesn’t collide with other scheduled jobs. |
| `KeepAlive` → `SuccessfulExit = false` | Asks `launchd` to relaunch on a non-zero exit. It also implies run-at-load, so the job runs whenever the plist is loaded (login, restart). |
| `EnvironmentVariables` → `PATH` | `launchd` starts jobs with a near-empty `PATH`; without this, `ffmpeg`, Homebrew Python and friends are “not found”. The script also exports its own `PATH` as a second line of defence. |

Load, test and inspect:

```bash
plutil -lint ~/Library/LaunchAgents/com.example.nightly.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.nightly.plist
launchctl kickstart -k gui/$(id -u)/com.example.nightly      # run now
launchctl print gui/$(id -u)/com.example.nightly | grep "last exit code"
launchctl bootout gui/$(id -u)/com.example.nightly           # unload
```

**Retry, honestly.** `open -W` tells `launchd` whether the applet launched, not necessarily how your script ended, and I have not seen the `KeepAlive` relaunch fire in practice. The retry that actually works is the ledger below plus the next night’s run. Make the script record failures in its own log and still exit cleanly, so an applet never stops on an error dialog at 3 am.

## 4. Resume, don’t restart: the step ledger

Each finished step is appended to a per-day ledger; a re-run skips anything already there. A crash costs one step, not the night, and the run-at-load behaviour becomes harmless.

```bash
LEDGER="$STATE_DIR/$(date +%F).ledger"
done_step() { grep -qx "$1" "$LEDGER" 2>/dev/null; }
run_step() {                                   # run_step <name> <command...>
  local name="$1"; shift
  if done_step "$name"; then note "skip $name (already done)"; return 0; fi
  note "start $name"
  if "$@" >> "$LOG" 2>&1; then echo "$name" >> "$LEDGER"; note "ok $name"
  else note "FAIL $name (exit $?) — will retry on next run"; return 1; fi
}
...
date +%s > "$STATE_DIR/last_success"           # the very last line
```

The full runner is [`sa_nightly.sh`](../../tools/sa_nightly.sh). Two rules it learnt the hard way:

- **Skip the step, not the night.** It used to exit when the video editor was left open, which silently skipped everything – the catalogue, the morning note and the clean-exit marker – and tripped the dead-man check every morning. Now only the step that reads editing projects is skipped.
- **One runaway step starves the rest.** A checking step once ran about ten hours, so the marker was never written. Put heavy steps last, or give each step a time limit.

## 5. The 07:00 dead-man check

A suspended 3 am job looks identical to a finished one unless something checks. A second plist runs the checker at 07:00:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.nightcheck</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/open</string><string>-W</string><string>-a</string>
    <string>/Users/you/Library/Nightly/Nightcheck.app</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
</dict></plist>
```

[`sa_nightcheck.sh`](../../tools/sa_nightcheck.sh) reads `last_success`; if it is older than 10 hours it posts a macOS notification and appends a line to `Sessions/_nightly/attention.md`. Every agent session reads that file at Step 0, so a dead night is the first thing the next session says.

Note that this example wraps the checker in its own applet (`Nightcheck.app`, built with the same `osacompile` line). My own checker plist ran `/bin/bash` directly; it was smoke-tested in August and, after a Full Disk Access regression in September, has been refused with exit 126 – the very failure this recipe exists to avoid. Wrap both.

## 6. Optional extras

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 00:55:00    # wake the Mac before the run
caffeinate -im /bin/bash heavy_step.sh               # keep it awake during a heavy step
```

## 7. The other route: Claude scheduled tasks

Scheduled tasks inside Claude already have file access, so they need no applet; my brain backup moved there after its `launchd` job died. They come with their own failure mode: they run only while the app is open, catch-up runs can stamp “ran” with no output, and one reported “succeeded” in under five seconds on three days while writing nothing. Judge them by their output and a heartbeat line, never by their status – the prompt patterns are in [scheduled-agent prompts](scheduled-agent-prompts.md).

---

Related: [workspace-kit scheduling](../../workspace-kit/scheduling/README.md) · [scheduled-agent prompts](scheduled-agent-prompts.md) · [how I engineer with AI coding agents](../ai-engineering-method.md) · [`sa_doctor.py`](../../tools/sa_doctor.py) · [`sa_nightly.sh`](../../tools/sa_nightly.sh) · [`sa_nightcheck.sh`](../../tools/sa_nightcheck.sh)
