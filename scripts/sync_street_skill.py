#!/usr/bin/env python3
"""Bundle license-safe derived street-design Skill data for app runtime use."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

FILES = (
    "rules.jsonl",
    "knowledge-cards.jsonl",
    "manuals.json",
    "terms.json",
    "pdf-sources.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path.home()
        / ".codex"
        / "skills"
        / "design-human-centered-streets",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "knowledge_base"
        / "street_skill",
    )
    args = parser.parse_args()

    references = args.skill_dir.expanduser().resolve() / "references"
    output = args.output_dir.expanduser().resolve()
    missing = [name for name in FILES if not (references / name).is_file()]
    if missing:
        raise SystemExit(
            "Skill references are incomplete: " + ", ".join(missing)
        )

    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bundle_version": "1.0.0",
        "synced_on": datetime.now(timezone.utc).date().isoformat(),
        "source_skill": "design-human-centered-streets",
        "license_note": (
            "Derived structured facts and metadata only; no source PDFs or "
            "copyrighted figure images are bundled."
        ),
        "files": {},
    }
    for name in FILES:
        source = references / name
        destination = output / name
        shutil.copyfile(source, destination)
        manifest["files"][name] = {
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        }

    (output / "bundle-meta.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Synced {len(FILES)} derived files to {output}")


if __name__ == "__main__":
    main()
