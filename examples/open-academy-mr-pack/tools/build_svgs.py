#!/usr/bin/env python3
"""Per-concept SVG runner, validator, and idempotent in-place YAML injector."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from academy_check import validate_svg_block


SVG_FENCE_BLOCK_RE = re.compile(
    r"^(?P<ind>[ \t]*)```svg([^\r\n]*)\r?\n(?P<body>[\s\S]*?)^(?P=ind)```",
    re.IGNORECASE | re.MULTILINE,
)


def load_svg_module(mod_path: Path) -> tuple[dict[str, Callable[[], str]], dict[str, str]]:
    svgs_dir = mod_path.parent
    if str(svgs_dir) not in sys.path:
        sys.path.insert(0, str(svgs_dir))
    spec = importlib.util.spec_from_file_location(f"mr_svg_{mod_path.stem.replace('-', '_')}", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load SVG module {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    kp_svgs = getattr(mod, "KP_SVGS", {})
    legacy_files = getattr(mod, "LEGACY_FILES", {})
    return kp_svgs, legacy_files


def normalize_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.strip().splitlines()]


def locate_kp_slice(raw: str, kp_id: str) -> tuple[int, int]:
    start_re = re.compile(rf"^(?P<ind>[ \t]*)-\s+id:\s*{re.escape(kp_id)}\s*(?:#.*)?$", re.MULTILINE)
    m = start_re.search(raw)
    if not m:
        raise ValueError(f'KP "{kp_id}" not found in lesson YAML')
    start = m.start()
    ind = m.group("ind")
    after = m.end()
    next_kp_re = re.compile(rf"^{re.escape(ind)}-\s+id:\s+", re.MULTILINE)
    top_key_re = re.compile(r"^(?:final|summary)\s*:", re.MULTILINE)
    end_candidates = [len(raw)]
    nk = next_kp_re.search(raw, after)
    if nk:
        end_candidates.append(nk.start())
    tk = top_key_re.search(raw, after)
    if tk:
        end_candidates.append(tk.start())
    return start, min(end_candidates)


def dedent_fence_body(body: str, indent: str) -> list[str]:
    lines: list[str] = []
    for line in body.splitlines():
        if indent and line.startswith(indent):
            lines.append(line[len(indent) :].rstrip())
        else:
            lines.append(line.rstrip())
    while lines and not lines[-1]:
        lines.pop()
    return lines


def process_concept(pack_dir: Path, cid: str, mod_path: Path, check_only: bool) -> bool:
    kp_svgs, legacy_files = load_svg_module(mod_path)
    lesson_path = pack_dir / "lessons" / f"{cid}.yaml"
    if not lesson_path.is_file():
        raise FileNotFoundError(f"Missing lesson file for SVG module: {lesson_path}")

    raw = lesson_path.read_text(encoding="utf-8")
    updated = raw
    out_dir = pack_dir / "tools" / "_generated_svgs"
    if not check_only:
        out_dir.mkdir(exist_ok=True)

    all_ok = True
    for kp_id, fn in kp_svgs.items():
        clean_lines = normalize_lines(fn())
        clean_svg = "\n".join(clean_lines)
        err = validate_svg_block(clean_svg)
        print(f"{cid}/{kp_id}: validate -> {'OK' if err is None else err}")
        if err:
            all_ok = False
            continue

        start, end = locate_kp_slice(updated, kp_id)
        block = updated[start:end]
        fm = SVG_FENCE_BLOCK_RE.search(block)
        if not fm:
            print(f"{cid}/{kp_id}: ERROR missing ```svg``` fenced block in {lesson_path.name}")
            all_ok = False
            continue

        indent = fm.group("ind")
        existing_lines = dedent_fence_body(fm.group("body"), indent)
        if check_only:
            if existing_lines != clean_lines:
                print(f"{cid}/{kp_id}: DRIFT detected between {mod_path.name} and {lesson_path.name}")
                all_ok = False
            else:
                print(f"{cid}/{kp_id}: YAML sync -> OK")
        else:
            indented = "\n".join((indent + ln if ln else "") for ln in clean_lines) + "\n"
            if fm.group("body") != indented:
                abs_s = start + fm.start("body")
                abs_e = start + fm.end("body")
                updated = updated[:abs_s] + indented + updated[abs_e:]
                print(f"{cid}/{kp_id}: injected updated SVG into {lesson_path.name}")
            else:
                print(f"{cid}/{kp_id}: YAML already up-to-date")

            fname = legacy_files.get(kp_id) or f"{cid}__{kp_id}.svg"
            svg_out = out_dir / fname
            svg_text = clean_svg + "\n"
            if not svg_out.is_file() or svg_out.read_text(encoding="utf-8") != svg_text:
                svg_out.write_text(svg_text, encoding="utf-8", newline="\n")

    if not check_only and all_ok and updated != raw:
        lesson_path.write_text(updated, encoding="utf-8", newline="\n")
    return all_ok


def discover_modules(svgs_dir: Path, concept_filter: str | None) -> list[tuple[str, Path]]:
    mods: list[tuple[str, Path]] = []
    for p in sorted(svgs_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        cid = p.stem
        if concept_filter and cid != concept_filter:
            continue
        mods.append((cid, p))
    if concept_filter and not mods:
        raise SystemExit(f'No SVG module found for concept "{concept_filter}" in {svgs_dir}')
    return mods


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/check per-concept SVGs and inject into lesson YAMLs.")
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parent.parent, help="Path to course pack root")
    parser.add_argument("--concept", type=str, default=None, help="Only process a single concept SVG module")
    parser.add_argument("--check", action="store_true", help="Verify lesson YAMLs match per-concept SVG modules without writing")
    args = parser.parse_args()

    pack_dir = args.pack.resolve()
    svgs_dir = Path(__file__).resolve().parent / "svgs"
    modules = discover_modules(svgs_dir, args.concept)
    ok = True
    for cid, mod_path in modules:
        if not process_concept(pack_dir, cid, mod_path, check_only=args.check):
            ok = False
    if not ok:
        return 1
    mode = "verified (check-only)" if args.check else f"saved/synced to {pack_dir / 'tools' / '_generated_svgs'}"
    print(f"All {len(modules)} concept SVG modules {mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
