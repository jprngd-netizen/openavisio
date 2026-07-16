#!/usr/bin/env python3
"""A/B-compare extraction models on real documents via the aiservice.

For each input file: OCR once (shared), then run /extract-entities with every
given model and write the JSONs next to each other for diffing. Deterministic
since aiservice runs temperature=0, so differences are model differences.

Usage (run where the aiservice is reachable, e.g. on the deployment host):
    python3 scripts/ab-extract.py --url http://localhost:8000 \
        --models medgemma:27b gemma4:26b --language de doc1.pdf doc2.pdf

Inside the compose network the aiservice listens on http://aiservice:8000.
Results land in ./ab-results/<file>/<model>.json plus a summary table.
"""
import argparse
import json
import mimetypes
import sys
import urllib.request
import uuid
from pathlib import Path


def post_json(url: str, payload: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def post_file(url: str, path: Path, timeout: int = 600) -> dict:
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: {ctype}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def entity_counts(extraction: dict) -> dict:
    entities = extraction.get("entities") or extraction
    return {k: len(v) for k, v in entities.items() if isinstance(v, list)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--url", default="http://localhost:8000", help="aiservice base URL")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--language", default="de")
    ap.add_argument("--out", type=Path, default=Path("ab-results"))
    args = ap.parse_args()

    for f in args.files:
        print(f"\n=== {f.name} ===")
        ocr = post_file(f"{args.url}/ocr", f)
        text = ocr.get("text", "")
        print(f"OCR: {len(text)} chars, confidence {ocr.get('confidence')}")
        if not text.strip():
            print("  no text — skipping")
            continue

        outdir = args.out / f.stem
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "_ocr.txt").write_text(text)

        for model in args.models:
            print(f"  {model} …", end="", flush=True)
            result = post_json(
                f"{args.url}/extract-entities",
                {"text": text, "model": model, "language": args.language},
            )
            (outdir / f"{model.replace(':', '_').replace('/', '_')}.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False)
            )
            print(" ", entity_counts(result))

    print(f"\nJSONs in {args.out}/ — diff them per file to judge quality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
