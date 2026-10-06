#!/usr/bin/env python3
"""Safe launcher for the Claude Video plugin: native captions/frames, no cloud Whisper."""
import pathlib
import subprocess
import sys

from sa_security import gate

WATCH = pathlib.Path.home() / ".claude/plugins/cache/claude-video/watch/0.2.0/skills/watch/scripts/watch.py"


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: sa_watch.py URL_OR_PUBLIC_FILE [watch options]")
    source = sys.argv[1]
    is_url = source.startswith(("https://", "http://"))
    result = gate(source, "local-caption-extraction", "PUBLIC" if is_url else None)
    if not result["allowed"]:
        raise SystemExit("BLOCKED: " + result["reason"])
    if not is_url and result["data_class"] != "PUBLIC":
        raise SystemExit("BLOCKED: local /watch files require explicit PUBLIC classification; use the local video tools instead")
    if not WATCH.exists():
        raise SystemExit("Claude Video plugin not found at pinned 0.2.0 path")
    args = [sys.executable, str(WATCH), *sys.argv[1:]]
    if "--no-whisper" not in args:
        args.append("--no-whisper")
    raise SystemExit(subprocess.run(args).returncode)


if __name__ == "__main__":
    main()
