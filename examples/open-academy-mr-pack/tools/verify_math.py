#!/usr/bin/env python3
"""Generic per-concept mathematical, worked-example, and exercise verifier for Open Academy packs."""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import math
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import sympy as sp
import yaml


def _within_tol(w_val: float, ans: float, tol: dict[str, Any]) -> bool:
    abs_tol = float(tol.get("abs", 1e-6))
    rel_tol = float(tol.get("rel", 0.0))
    thresh = max(abs_tol, rel_tol * max(abs(w_val), abs(ans)))
    return abs(w_val - ans) <= thresh


def verify_exercises(ex_path: Path) -> int:
    """Validate all exercises (MC, numeric static/template, expression, text) in one YAML file."""
    if not ex_path.is_file():
        raise FileNotFoundError(f"Missing exercises file: {ex_path}")

    edoc = yaml.safe_load(ex_path.read_text(encoding="utf-8"))
    if not isinstance(edoc, dict) or not isinstance(edoc.get("exercises"), list):
        raise ValueError(f"Expected mapping with 'exercises' list in {ex_path}")

    exs = edoc["exercises"]
    print(f"--- Checking {ex_path.name} ({len(exs)} exercises) ---")

    for ex in exs:
        ex_type = ex["type"]
        ex_id = ex["id"]

        if ex_type == "mc":
            n_correct = sum(1 for o in ex["options"] if o.get("correct"))
            assert n_correct == 1, f"MC {ex_id} must have exactly 1 correct option (got {n_correct})"

        elif ex_type == "numeric":
            if "params" in ex:
                param_names = list(ex["params"].keys())
                grids = []
                for k in param_names:
                    spec = ex["params"][k]
                    cur = float(spec["min"])
                    vals = []
                    while cur <= float(spec["max"]) + 1e-9:
                        vals.append(round(cur, 9))
                        cur += float(spec.get("step", 1))
                    grids.append(vals)

                ans_set: set[float] = set()
                valid = 0
                base_tol = ex.get("tolerance") or {"abs": 1e-6}
                for combo in itertools.product(*grids):
                    env = dict(zip(param_names, combo))
                    if not all(
                        eval(c.replace("&&", " and ").replace("||", " or "), {"__builtins__": {}}, env)
                        for c in ex.get("constraints", [])
                    ):
                        continue
                    valid += 1
                    ans = float(sp.N(sp.sympify(ex["answer_expr"].replace("^", "**"), locals=env)))
                    assert math.isfinite(ans), f"Non-finite template answer in {ex_id} for {env}"
                    ans_set.add(round(ans, 9))

                    for cw in ex.get("common_wrong", []):
                        if "answer_expr" in cw:
                            w = float(sp.N(sp.sympify(cw["answer_expr"].replace("^", "**"), locals=env)))
                        elif "answer" in cw:
                            w = float(cw["answer"])
                        else:
                            continue
                        cw_tol = cw.get("tolerance") or base_tol
                        assert not _within_tol(w, ans, cw_tol), (
                            f"Collision in {ex_id} for {env}: common_wrong {w} vs {ans}"
                        )

                assert valid > 0 and len(ans_set) >= 3, f"Template {ex_id} insufficient diversity"
                print(
                    f"[PASS] Template {ex_id}: {valid} combos, {len(ans_set)} distinct answers "
                    f"[{min(ans_set)}, {max(ans_set)}]"
                )
            else:
                ans_raw = ex.get("answer")
                assert isinstance(ans_raw, (int, float)) and not isinstance(ans_raw, bool), (
                    f"Numeric {ex_id} must have numeric 'answer'"
                )
                ans = float(ans_raw)
                base_tol = ex.get("tolerance") or {"abs": 1e-6}
                for cw in ex.get("common_wrong", []):
                    cw_ans = cw.get("answer")
                    if isinstance(cw_ans, (int, float)) and not isinstance(cw_ans, bool):
                        cw_tol = cw.get("tolerance") or base_tol
                        assert not _within_tol(float(cw_ans), ans, cw_tol), (
                            f"Static common_wrong collision in {ex_id}: {cw_ans} vs {ans}"
                        )
                print(f"[PASS] Numeric {ex_id}: answer={ex['answer']}")

        elif ex_type == "expression":
            ans_sym = sp.sympify(ex["answer"].replace("^", "**"))
            vars_spec = ex.get("variables", {})
            assert set(map(str, ans_sym.free_symbols)) == set(vars_spec.keys()), (
                f"Expr {ex_id} symbol mismatch: {ans_sym.free_symbols} vs {vars_spec.keys()}"
            )
            print(f"[PASS] Expression {ex_id}: '{ex['answer']}', vars={list(vars_spec.keys())}")

        elif ex_type == "text":
            rx = re.compile(ex["regex"]) if ex.get("regex") else None
            if rx:
                for acc in ex.get("accept", []):
                    assert rx.match(acc), f"Regex in {ex_id} failed to match accept '{acc}'"
            print(f"[PASS] Text {ex_id}: {len(ex.get('accept', []))} accept patterns validated")

    return len(exs)


def discover_authored_concepts(pack_dir: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Discover all concepts and return authored concept IDs in deterministic course order."""
    concepts_dir = pack_dir / "concepts"
    concepts_by_id: dict[str, dict[str, Any]] = {}
    for cfile in sorted(concepts_dir.glob("*.yaml")):
        cdoc = yaml.safe_load(cfile.read_text(encoding="utf-8")) or {}
        for c in cdoc.get("concepts") or []:
            cid = c["id"]
            if cid in concepts_by_id:
                raise ValueError(f'Duplicate concept id "{cid}" in {cfile}')
            concepts_by_id[cid] = c

    authored_set = {cid for cid, c in concepts_by_id.items() if c.get("status") == "authored"}

    course_order: list[str] = []
    courses_dir = pack_dir / "courses"
    if courses_dir.is_dir():
        for kfile in sorted(courses_dir.glob("*.yaml")):
            kdoc = yaml.safe_load(kfile.read_text(encoding="utf-8")) or {}
            for unit in kdoc.get("units") or []:
                for cid in unit.get("concepts") or []:
                    if cid not in course_order:
                        course_order.append(cid)

    ordered_authored = [cid for cid in course_order if cid in authored_set]
    remaining = sorted(authored_set - set(ordered_authored))
    ordered_authored.extend(remaining)
    return ordered_authored, concepts_by_id


def load_check_module(mod_path: Path) -> ModuleType:
    """Dynamically import a per-concept verification module exporting verify(lesson_path, pack_dir)."""
    checks_dir = str(mod_path.parent)
    if checks_dir not in sys.path:
        sys.path.insert(0, checks_dir)

    spec = importlib.util.spec_from_file_location(f"mr_check_{mod_path.stem.replace('-', '_')}", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load check module {mod_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    verify_fn = getattr(mod, "verify", None)
    if not callable(verify_fn):
        raise RuntimeError(f"Check module {mod_path} must define callable verify(lesson_path, pack_dir)")
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run per-concept symbolic/worked checks and universal exercise verification for an Open Academy pack."
    )
    parser.add_argument("pack_pos", nargs="?", default=None, help="Path to course pack root (optional positional arg)")
    parser.add_argument("--pack", type=Path, default=None, help="Path to course pack root")
    parser.add_argument(
        "--concept",
        action="append",
        default=None,
        help="Verify only the specified authored concept ID (repeatable)",
    )
    parser.add_argument(
        "--require-checks",
        action="store_true",
        help="Fail if any authored concept is missing tools/checks/<concept_id>.py",
    )
    args = parser.parse_args()

    if args.pack is not None:
        pack_dir = args.pack.resolve()
    elif args.pack_pos is not None:
        pack_dir = Path(args.pack_pos).resolve()
    else:
        pack_dir = Path(".").resolve()

    if not (pack_dir / "concepts").is_dir():
        print(f"[ERR] Invalid course pack directory (missing concepts/): {pack_dir}", file=sys.stderr)
        return 1

    authored_concepts, concepts_by_id = discover_authored_concepts(pack_dir)

    if args.concept:
        target_concepts: list[str] = []
        for cid in args.concept:
            if cid not in concepts_by_id:
                print(f'[ERR] Unknown concept ID "{cid}" (not found in {pack_dir / "concepts"})', file=sys.stderr)
                return 1
            status = concepts_by_id[cid].get("status")
            if status != "authored":
                print(
                    f'[ERR] Concept "{cid}" has status "{status}", expected "authored" for math verification.',
                    file=sys.stderr,
                )
                return 1
            if cid not in target_concepts:
                target_concepts.append(cid)
    else:
        target_concepts = authored_concepts
        if not target_concepts:
            print(f"[ERR] No concepts with status 'authored' found in {pack_dir / 'concepts'}", file=sys.stderr)
            return 1

    pack_checks_dir = pack_dir / "tools" / "checks"
    checks_dir = pack_checks_dir if pack_checks_dir.is_dir() else (Path(__file__).resolve().parent / "checks")

    executed_checks: list[str] = []
    missing_checks: list[str] = []
    total_exercises = 0

    for cid in target_concepts:
        lesson_path = pack_dir / "lessons" / f"{cid}.yaml"
        ex_path = pack_dir / "exercises" / f"{cid}.yaml"
        mod_path = checks_dir / f"{cid}.py"

        if mod_path.is_file():
            mod = load_check_module(mod_path)
            mod.verify(lesson_path, pack_dir)
            executed_checks.append(cid)
        else:
            missing_checks.append(cid)
            print(f"[INFO] [{cid}] No custom check module at {mod_path}; running universal exercise checks only.")

        total_exercises += verify_exercises(ex_path)

    print("\n=== Verification Summary ===")
    print(f"Checked authored concepts ({len(target_concepts)}): {', '.join(target_concepts)}")
    print(f"Check modules executed ({len(executed_checks)}): {', '.join(executed_checks) if executed_checks else 'none'}")
    print(
        f"Authored concepts without custom check module ({len(missing_checks)}): "
        f"{', '.join(missing_checks) if missing_checks else 'none'}"
    )
    print(f"Total exercises verified: {total_exercises}")

    if args.require_checks and missing_checks:
        print(
            f"[ERR] --require-checks failed; missing check module(s) for: {', '.join(missing_checks)}",
            file=sys.stderr,
        )
        return 1

    print("ALL TARGET MATHEMATICAL & TEMPLATE VERIFICATIONS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
