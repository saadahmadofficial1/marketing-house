#!/usr/bin/env python3
"""Write an auditable provenance manifest for a creative output."""
import argparse
import datetime
import hashlib
import json
import pathlib


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(raw):
    path = pathlib.Path(raw).expanduser().resolve()
    return {"path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() and path.is_file() else None,
            "sha256": sha256(path) if path.exists() and path.is_file() else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--tool", action="append", default=[])
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--data-class", choices=["PUBLIC", "INTERNAL", "CONFIDENTIAL", "CLIENT_RESTRICTED"], default="INTERNAL")
    parser.add_argument("--external-service", action="append", default=[])
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    manifest = {"schema_version": "1.0", "project": args.project,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "data_class": args.data_class, "inputs": [describe(x) for x in args.input],
                "outputs": [describe(x) for x in args.output], "tools": args.tool,
                "models": args.model, "external_services": args.external_service,
                "data_left_machine": bool(args.external_service), "warnings": args.warning,
                "human_approval": {"approved": False, "approved_at": None}}
    out = pathlib.Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix + ".tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temp.replace(out)
    print(out)


if __name__ == "__main__":
    main()
