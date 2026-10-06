#!/usr/bin/env python3
"""Peek at an image locally (zero Claude tokens) — describe via Ollama.
  sa_peek.py                # newest screenshot/image on Desktop
  sa_peek.py path.png       # specific file
Prints a text description Claude can read instead of the pixels.
"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sa_visualmem  # reuse its Ollama vision call

EXT = ("*.png", "*.jpg", "*.jpeg", "*.webp")

def newest_desktop():
    d = os.path.expanduser("~/Desktop")
    files = [f for p in EXT for f in glob.glob(os.path.join(d, p))]
    if not files:
        sys.exit("no image found on Desktop")
    return max(files, key=os.path.getmtime)

if __name__ == "__main__":
    path = os.path.expanduser(sys.argv[1]) if len(sys.argv) > 1 else newest_desktop()
    print(f"[{os.path.basename(path)}]")
    print(sa_visualmem.ask(path))
