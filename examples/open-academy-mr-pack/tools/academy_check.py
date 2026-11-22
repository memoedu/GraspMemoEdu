#!/usr/bin/env python3
"""Open Academy Content Validator & Prereqs CLI (with CJK equivalent word counting)."""

from __future__ import annotations

import argparse
import itertools
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sympy as sp
import yaml


SVG_FENCE_RE = re.compile(r"```svg([^\r\n]*)\r?\n([\s\S]*?)```", re.IGNORECASE)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
MATH_SPAN_RE = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$")
CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
HEX_COLOR_RE = re.compile(r"^#(?:[\da-f]{3}|[\da-f]{4}|[\da-f]{6}|[\da-f]{8})$", re.IGNORECASE)
ALLOWED_SVG_HEX = {
    "#171717",
    "#737373",
    "#d4d4d4",
    "#10b981",
    "#f59e0b",
    "#3b82f6",
    "#ef4444",
    "#ffffff",
}
SVG_COLOR_PROPS = {
    "color",
    "fill",
    "stroke",
    "stop-color",
    "flood-color",
    "lighting-color",
    "solid-color",
    "background-color",
}
PLAIN_TEXT_MATH_RE = re.compile(r"[A-Za-z]_[A-Za-z0-9({]|[A-Za-z][\u2080-\u2089]|[∇θ‖]")
LESSON_CONTEXT_PROMPT_RE = re.compile(
    r"worked example|\bthe worked\b|\bin steps? \d|\bsteps? \d\b|\bthis step\b|"
    r"\bin the picture\b|\bin the table\b|\bthe lesson'?s?\b|\bin the lesson\b|"
    r"taught in the lesson|例题中|本节|这一步|本步|上图中|下图中|本课",
    re.IGNORECASE,
)
MATH_PROSE_KEYS = {"criterion", "exemplar", "text", "feedback", "prompt", "hints", "solution"}
STRING_METADATA_KEYS = {"id", "type", "role", "dimension", "category", "knowledge_point"}
AVOIDED_EXCLUDE_KEYS = {
    "accept",
    "answer",
    "answer_expr",
    "answers",
    "code",
    "concept",
    "constraints",
    "exercise",
    "fast_path",
    "final",
    "params",
    "prereqs",
    "problems",
    "projects",
    "regex",
    "reflection",
    "related",
    "source",
    "sources",
    "starter",
    "tests",
    "variables",
}
REVIEWABLE_ROLES = {"review", "recall", "core", "practice", "transfer", "basics"}


@dataclass
class Issue:
    file: str
    item_id: str
    message: str


def count_kp_words_cjk(text: str) -> tuple[int, int, int, int]:
    """Return (eq_words, cjk_chars, latin_tokens, math_spans)."""
    stripped = CODE_FENCE_RE.sub(" ", text or "")
    math_spans = len(MATH_SPAN_RE.findall(stripped))
    no_math = MATH_SPAN_RE.sub(" ", stripped)
    cjk_chars = len(CJK_CHAR_RE.findall(no_math))
    no_cjk = CJK_CHAR_RE.sub(" ", no_math)
    latin_tokens = len(LATIN_TOKEN_RE.findall(no_cjk))
    eq_words = round(cjk_chars * 0.6 + latin_tokens + math_spans)
    return eq_words, cjk_chars, latin_tokens, math_spans


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_pack(pack_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = {
        "curriculum": None,
        "sources": None,
        "notation": None,
        "courses": [],
        "concepts": [],
        "lessons": [],
        "exercises": [],
    }
    if (pack_dir / "curriculum.yaml").exists():
        data["curriculum"] = ("curriculum.yaml", load_yaml(pack_dir / "curriculum.yaml"))
    if (pack_dir / "sources" / "index.yaml").exists():
        data["sources"] = ("sources/index.yaml", load_yaml(pack_dir / "sources" / "index.yaml"))
    if (pack_dir / "notation.yaml").exists():
        data["notation"] = ("notation.yaml", load_yaml(pack_dir / "notation.yaml"))

    for folder, key in [
        ("courses", "courses"),
        ("concepts", "concepts"),
        ("lessons", "lessons"),
        ("exercises", "exercises"),
    ]:
        sub = pack_dir / folder
        if sub.exists():
            for p in sorted(sub.glob("*.yaml")):
                data[key].append((f"{folder}/{p.name}", load_yaml(p)))
    return data


def string_values(obj: Any, exclude_keys: set[str] | None = None) -> list[str]:
    excl = exclude_keys or set()
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, list):
        out: list[str] = []
        for item in obj:
            out.extend(string_values(item, excl))
        return out
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            if k in STRING_METADATA_KEYS or k in excl:
                continue
            out.extend(string_values(v, excl))
        return out
    return []


def check_plain_text_math(obj: Any, key: str | None = None) -> list[str]:
    hits: list[str] = []
    if isinstance(obj, str):
        if key in MATH_PROSE_KEYS:
            prose = re.sub(r"\$\$[\s\S]*?\$\$", "", obj)
            prose = re.sub(r"\$[^$\n]*\$", "", prose)
            prose = re.sub(r"(`+)[\s\S]*?\1", "", prose)
            m = PLAIN_TEXT_MATH_RE.search(prose)
            if m:
                hits.append(m.group(0))
        return hits
    if isinstance(obj, list):
        for item in obj:
            hits.extend(check_plain_text_math(item, key))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(check_plain_text_math(v, k))
    return hits


def validate_svg_block(svg_src: str) -> str | None:
    if re.search(r"<\s*(script|foreignObject)\b", svg_src, re.IGNORECASE):
        return "forbidden <script> or <foreignObject> element"
    if re.search(r"\bon[a-z0-9_-]*\s*=", svg_src, re.IGNORECASE):
        return "event attributes are forbidden"
    if re.search(r"\b(?:xlink:)?href\s*=\s*(['\"])(?!#)[\s\S]*?\1", svg_src, re.IGNORECASE):
        return "external href references are forbidden"
    if re.search(r"\bvar\s*\(|--[a-z0-9_-]+\s*:", svg_src, re.IGNORECASE):
        return "CSS variables are forbidden"

    try:
        root = ET.fromstring(svg_src.strip())
    except ET.ParseError as exc:
        return f"malformed XML: {exc}"

    local_root = root.tag.split("}")[-1]
    if local_root != "svg":
        return f"root element must be svg, got {local_root}"

    viewbox = (root.attrib.get("viewBox") or "").strip()
    if not viewbox:
        return "root SVG needs a non-empty viewBox"
    parts = re.split(r"[\s,]+", viewbox)
    if len(parts) != 4:
        return f"invalid viewBox '{viewbox}'"
    try:
        vb_w = float(parts[2])
        vb_h = float(parts[3])
        if vb_w > 640 or vb_w <= 0 or vb_h <= 0:
            return f"viewBox width must be in (0, 640], got {vb_w}"
    except ValueError:
        return f"non-numeric viewBox '{viewbox}'"

    if not (root.attrib.get("aria-label") or "").strip():
        return "root SVG needs a non-empty aria-label"

    for elem in root.iter():
        tag_name = elem.tag.split("}")[-1].lower()
        if tag_name in {"script", "foreignobject"}:
            return f"forbidden element <{tag_name}>"
        for k, v in elem.attrib.items():
            attr = k.split("}")[-1].lower()
            if attr.startswith("on"):
                return f"forbidden event attribute {attr}"
            if attr == "href" and v and not v.startswith("#"):
                return f"forbidden external href '{v}'"
            if attr in SVG_COLOR_PROPS:
                val = v.strip().lower()
                if not HEX_COLOR_RE.match(val):
                    return f'color property {attr}="{v}" must be a literal hex value (e.g. #ffffff with fill-opacity="0")'
                if val not in ALLOWED_SVG_HEX:
                    return f'color property {attr}="{v}" is outside the 7-color palette (+ #ffffff)'
            if attr == "style":
                for decl in v.split(";"):
                    if ":" not in decl:
                        continue
                    prop, col = [x.strip().lower() for x in decl.split(":", 1)]
                    if prop in SVG_COLOR_PROPS and col:
                        if not HEX_COLOR_RE.match(col) or col not in ALLOWED_SVG_HEX:
                            return f'style color {prop}:{col} invalid or outside palette'
    return None


def is_template(ex: dict[str, Any]) -> bool:
    return ex.get("type") == "numeric" and ("params" in ex or "answer_expr" in ex)


def eval_math_expr(expr: str, env: dict[str, float]) -> float:
    safe_expr = expr.replace("^", "**")
    local_syms = {k: sp.Float(v) for k, v in env.items()}
    val = sp.sympify(safe_expr, locals=local_syms)
    return float(sp.N(val))


def format_template_number(val: float) -> str:
    if abs(val - round(val)) < 1e-9:
        return str(int(round(val)))
    return f"{val:.6g}"


def render_template_text(text: str, env: dict[str, float]) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        val = eval_math_expr(inner, env)
        return format_template_number(val)

    return re.sub(r"\{\{=\s*([^}]+?)\s*\}\}", repl, text)


def validate_template_exercise(ex: dict[str, Any], file: str, issues: list[Issue]) -> None:
    if "answer" in ex and "answer_expr" in ex:
        issues.append(Issue(file, ex["id"], "numeric exercise cannot have both answer and answer_expr"))
        return
    if "answer_expr" not in ex or "params" not in ex:
        issues.append(Issue(file, ex["id"], "template exercise requires both params and answer_expr"))
        return
    if ex.get("role") != "practice":
        issues.append(Issue(file, ex["id"], "templates must have practice role"))

    param_names = list(ex["params"].keys())
    param_grids: list[list[float]] = []
    for name in param_names:
        spec = ex["params"][name]
        p_min = float(spec["min"])
        p_max = float(spec["max"])
        step = float(spec.get("step", 1))
        vals: list[float] = []
        cur = p_min
        while cur <= p_max + 1e-9:
            vals.append(round(cur, 9))
            cur += step
        param_grids.append(vals)

    answers: set[float] = set()
    valid_combos = 0
    for combo in itertools.product(*param_grids):
        env = dict(zip(param_names, combo))
        # Check constraints
        ok = True
        for cond in ex.get("constraints", []):
            cond_py = cond.replace("&&", " and ").replace("||", " or ")
            try:
                if not eval(cond_py, {"__builtins__": {}}, env):
                    ok = False
                    break
            except Exception as exc:
                issues.append(Issue(file, ex["id"], f"constraint '{cond}' eval error: {exc}"))
                return
        if not ok:
            continue
        valid_combos += 1
        try:
            ans = eval_math_expr(ex["answer_expr"], env)
        except Exception as exc:
            issues.append(Issue(file, ex["id"], f"answer_expr error for {env}: {exc}"))
            return
        if not math.isfinite(ans):
            issues.append(Issue(file, ex["id"], f"answer is not finite for {env}"))
            return
        answers.add(round(ans, 9))

        for txt in string_values(ex):
            rendered = render_template_text(txt, env)
            if "{{" in rendered:
                issues.append(Issue(file, ex["id"], f"unresolved {{{{ placeholder in rendered text: {rendered}"))
                return
            for m in re.finditer(r"[+-]\s*-\d", rendered):
                idx = m.start()
                if idx == 0 or rendered[idx - 1] != "(":
                    issues.append(Issue(file, ex["id"], f'adjacent signs near "{m.group(0)}" in {env}'))
                    return

        tol = ex.get("tolerance") or {"abs": 1e-6}
        tol_abs = float(tol.get("abs", 1e-6))
        tol_rel = float(tol.get("rel", 0))
        for wrong in ex.get("common_wrong", []):
            if "answer_expr" in wrong:
                w_val = eval_math_expr(wrong["answer_expr"], env)
            elif "answer" in wrong:
                w_val = float(wrong["answer"])
            else:
                continue
            w_tol = wrong.get("tolerance") or tol
            w_abs = float(w_tol.get("abs", tol_abs))
            w_rel = float(w_tol.get("rel", tol_rel))
            thresh = max(w_abs, w_rel * max(abs(w_val), abs(ans)))
            if abs(w_val - ans) <= thresh:
                issues.append(
                    Issue(file, ex["id"], f"common_wrong {w_val} collides with answer {ans} for {env}")
                )
                return

    if valid_combos == 0:
        issues.append(Issue(file, ex["id"], "template constraints leave 0 valid combinations"))
    elif len(answers) < 3:
        issues.append(Issue(file, ex["id"], f"template produces only {len(answers)} distinct answers; need >= 3"))


def hard_ancestors(concept_id: str, concepts_by_id: dict[str, dict[str, Any]]) -> set[str]:
    anc: set[str] = set()
    def visit(cid: str) -> None:
        c = concepts_by_id.get(cid)
        if not c:
            return
        for pr in c.get("prereqs", []):
            pid = pr["id"]
            strength = pr.get("strength", "hard")
            if strength != "hard" or pid in anc:
                continue
            anc.add(pid)
            visit(pid)
    visit(concept_id)
    return anc


def soft_only_ancestors(concept_id: str, concepts_by_id: dict[str, dict[str, Any]], hard_anc: set[str]) -> set[str]:
    soft: set[str] = set()
    for cid in [concept_id, *hard_anc]:
        c = concepts_by_id.get(cid)
        if not c:
            continue
        for pr in c.get("prereqs", []):
            if pr.get("strength", "hard") == "soft" and pr["id"] not in hard_anc:
                soft.add(pr["id"])
    return soft


def check_pack(pack_dir: Path, verbose: bool = False) -> tuple[list[Issue], list[Issue]]:
    data = load_pack(pack_dir)
    issues: list[Issue] = []
    warnings: list[Issue] = []

    if not data["curriculum"]:
        issues.append(Issue("curriculum.yaml", "<file>", "missing curriculum.yaml"))
        return issues, warnings

    cur_file, curriculum = data["curriculum"]
    domains = {d["id"] for d in curriculum.get("domains", [])}
    grounded = bool(curriculum.get("grounded", False))

    source_ids: set[str] = set()
    if data["sources"]:
        _, src_idx = data["sources"]
        source_ids = {s["id"] for s in src_idx.get("sources", [])}
    elif grounded:
        issues.append(Issue("sources/index.yaml", "<file>", "grounded: true requires sources/index.yaml"))

    concepts_by_id: dict[str, dict[str, Any]] = {}
    concept_file: dict[str, str] = {}
    for cfile, cdoc in data["concepts"]:
        dom = cdoc.get("domain")
        if dom not in domains:
            issues.append(Issue(cfile, str(dom), f'unknown domain "{dom}"'))
        for c in cdoc.get("concepts", []):
            cid = c["id"]
            if cid in concepts_by_id:
                issues.append(Issue(cfile, cid, "duplicate concept id"))
            concepts_by_id[cid] = c
            concept_file[cid] = cfile

    # Prereq & confused_with checks + cycle detection
    for cid, c in concepts_by_id.items():
        cfile = concept_file[cid]
        for pr in c.get("prereqs", []):
            pid = pr["id"]
            if pid == cid:
                issues.append(Issue(cfile, cid, "concept cannot require itself"))
            elif pid not in concepts_by_id:
                issues.append(Issue(cfile, cid, f'unknown prerequisite "{pid}"'))
        for conf in c.get("confused_with", []):
            if conf == cid:
                issues.append(Issue(cfile, cid, "confused_with cannot reference self"))
            elif conf not in concepts_by_id:
                issues.append(Issue(cfile, cid, f'unknown confused_with "{conf}"'))
            else:
                other_conf = concepts_by_id[conf].get("confused_with", [])
                if cid in other_conf:
                    issues.append(Issue(cfile, cid, f'confused_with pair ({cid}, {conf}) listed on both sides'))

    # Cycles
    state: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=done
    def dfs(cid: str, stack: list[str]) -> None:
        state[cid] = 1
        stack.append(cid)
        for pr in concepts_by_id[cid].get("prereqs", []):
            pid = pr["id"]
            if pid not in concepts_by_id:
                continue
            if state.get(pid, 0) == 1:
                idx = stack.index(pid)
                issues.append(Issue(concept_file[cid], cid, f"prerequisite cycle: {' -> '.join(stack[idx:] + [pid])}"))
            elif state.get(pid, 0) == 0:
                dfs(pid, stack)
        stack.pop()
        state[cid] = 2

    for cid in concepts_by_id:
        if state.get(cid, 0) == 0:
            dfs(cid, [])

    # Courses & structural warnings
    courses_by_id: dict[str, dict[str, Any]] = {}
    course_file: dict[str, str] = {}
    for kfile, kdoc in data["courses"]:
        kid = kdoc["id"]
        if kid in courses_by_id:
            issues.append(Issue(kfile, kid, "duplicate course id"))
        courses_by_id[kid] = kdoc
        course_file[kid] = kfile

    for cid_course in curriculum.get("courses", []):
        if cid_course not in courses_by_id:
            issues.append(Issue(cur_file, cid_course, f'curriculum references unknown course "{cid_course}"'))

    unit_opening_topics: set[str] = set()
    for kid, kdoc in courses_by_id.items():
        for u in kdoc.get("units", []):
            if u.get("concepts"):
                unit_opening_topics.add(u["concepts"][0])

    for kid, kdoc in courses_by_id.items():
        kfile = course_file[kid]
        flat_topics: list[tuple[str, int]] = []
        for u_idx, u in enumerate(kdoc.get("units", []), start=1):
            for cid in u.get("concepts", []):
                if cid not in concepts_by_id:
                    issues.append(Issue(kfile, kid, f'unit {u_idx} references unknown concept "{cid}"'))
                else:
                    flat_topics.append((cid, u_idx))
        # Warnings: prerequisite-free deep topic & sequential bottleneck
        for pos, (cid, u_num) in enumerate(flat_topics):
            c = concepts_by_id.get(cid, {})
            if not c.get("prereqs") and cid not in unit_opening_topics and not (u_num == 1 and pos < 3):
                warnings.append(Issue(concept_file[cid], cid, f"has no prerequisites in unit {u_num} of {kdoc['title']}"))

        topic_id_set = {cid for cid, _ in flat_topics}
        if len(flat_topics) >= 6:
            done: set[str] = set()
            max_open = 0
            for cid, _ in flat_topics:
                open_cnt = 0
                for cand, _ in flat_topics:
                    if cand in done:
                        continue
                    c = concepts_by_id.get(cand, {})
                    hard_reqs = [p["id"] for p in c.get("prereqs", []) if p.get("strength", "hard") == "hard"]
                    if all((req not in topic_id_set) or (req in done) for req in hard_reqs):
                        open_cnt += 1
                max_open = max(max_open, open_cnt)
                done.add(cid)
            if max_open <= 1:
                warnings.append(
                    Issue(kfile, kid, "every topic waits on the one before it (maximumOpen <= 1); check hard prerequisites")
                )

    # Exercises
    exercises_by_id: dict[str, tuple[str, str, dict[str, Any]]] = {}
    exercises_by_concept: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for efile, edoc in data["exercises"]:
        econ = edoc["concept"]
        if econ not in concepts_by_id:
            issues.append(Issue(efile, econ, f'exercises file references unknown concept "{econ}"'))
        for ex in edoc.get("exercises", []):
            eid = ex["id"]
            if eid in exercises_by_id:
                issues.append(Issue(efile, eid, "duplicate exercise id"))
            exercises_by_id[eid] = (econ, efile, ex)
            exercises_by_concept.setdefault(econ, []).append((efile, ex))

            if ex.get("type") == "explain":
                rubric = ex.get("rubric", [])
                req_cnt = sum(1 for r in rubric if r.get("required"))
                if req_cnt > 4 or len(rubric) > 6:
                    issues.append(Issue(efile, eid, f"explain rubric has {req_cnt} required and {len(rubric)} total (max 4/6)"))

            if ex.get("type") == "mc":
                opts = ex.get("options", [])
                if not any(o.get("correct") for o in opts):
                    issues.append(Issue(efile, eid, "MC exercise must have >= 1 correct option"))
                texts = [o["text"].strip().lower() for o in opts]
                if len(set(texts)) != len(texts):
                    issues.append(Issue(efile, eid, "MC option texts must be unique"))
                if ex.get("role") not in {"diagnostic", "basics"}:
                    for o in opts:
                        if not o.get("correct") and not (o.get("feedback") or "").strip():
                            issues.append(Issue(efile, eid, f'incorrect option "{o["id"]}" missing feedback'))
                if ex.get("role") == "basics":
                    for o in opts:
                        if not (o.get("feedback") or "").strip():
                            issues.append(Issue(efile, eid, f'basics option "{o["id"]}" missing feedback'))

            if ex.get("role") != "diagnostic" and not ex.get("lesson_only"):
                if LESSON_CONTEXT_PROMPT_RE.search(ex.get("prompt", "")):
                    issues.append(Issue(efile, eid, "standalone exercise prompt must not refer to lesson/worked example/picture"))

            plain_hits = check_plain_text_math(ex)
            if plain_hits:
                issues.append(Issue(efile, eid, f"plain-text maths outside $...$: {plain_hits}"))

            if is_template(ex):
                validate_template_exercise(ex, efile, issues)

    # Lessons
    lessons_by_concept: dict[str, tuple[str, dict[str, Any]]] = {}
    for lfile, ldoc in data["lessons"]:
        lcon = ldoc["concept"]
        if lcon not in concepts_by_id:
            issues.append(Issue(lfile, lcon, f'lesson references unknown concept "{lcon}"'))
        if lcon in lessons_by_concept:
            issues.append(Issue(lfile, lcon, "duplicate lesson for concept"))
        lessons_by_concept[lcon] = (lfile, ldoc)

    authored_lessons = set(lessons_by_concept.keys())
    problem_refs: dict[str, int] = {}

    for lcon, (lfile, ldoc) in lessons_by_concept.items():
        if grounded:
            srcs = ldoc.get("sources") or []
            if not srcs:
                issues.append(Issue(lfile, lcon, "grounded: true requires at least one source citation"))
            for s in srcs:
                if s.get("source") not in source_ids:
                    issues.append(Issue(lfile, lcon, f'unknown source id "{s.get("source")}"'))

        prereq_ids = {p["id"] for p in concepts_by_id.get(lcon, {}).get("prereqs", [])}
        if "recap" in ldoc and ldoc["recap"] is not None:
            seen_recap: set[str] = set()
            for r in ldoc["recap"]:
                rc = r["concept"]
                if rc not in prereq_ids:
                    issues.append(Issue(lfile, lcon, f'recap concept "{rc}" is not a prerequisite'))
                if rc not in authored_lessons:
                    issues.append(Issue(lfile, lcon, f'recap concept "{rc}" has no authored lesson'))
                if rc in seen_recap:
                    issues.append(Issue(lfile, lcon, f'recap concept "{rc}" listed twice'))
                seen_recap.add(rc)
                rw, _, _, _ = count_kp_words_cjk(r["text"])
                if rw > 40:
                    issues.append(Issue(lfile, lcon, f'recap for "{rc}" has {rw} eq-words; max 40'))
            for pid in prereq_ids:
                if pid in authored_lessons and pid not in seen_recap:
                    issues.append(Issue(lfile, lcon, f'recap for authored prerequisite "{pid}" is missing'))

        wtf = ldoc.get("where_this_fits") or ""
        wtf_eq, wtf_cjk, wtf_lat, wtf_math = count_kp_words_cjk(wtf)
        if verbose:
            print(f"[words] {lcon}.where_this_fits: eq={wtf_eq} (cjk={wtf_cjk}, latin={wtf_lat}, math={wtf_math})")
        if wtf_eq < 30 or wtf_eq > 130:
            issues.append(Issue(lfile, lcon, f"where_this_fits has {wtf_eq} eq-words; expected 30-130"))

        summary = ldoc.get("summary") or ""
        if not any(line.lstrip().startswith("**Next:**") for line in summary.splitlines()):
            issues.append(Issue(lfile, lcon, 'summary must contain a line starting with "**Next:**"'))

        kps = ldoc.get("knowledge_points") or []
        if not (1 <= len(kps) <= 4):
            issues.append(Issue(lfile, lcon, f"lesson has {len(kps)} knowledge_points; expected 1-4"))

        kp_ids: set[str] = set()
        for kp in kps:
            kpid = kp["id"]
            kp_ids.add(kpid)
            tldr = kp.get("tldr")
            if not tldr:
                warnings.append(Issue(lfile, kpid, "step has no tldr"))
            else:
                tldr_body = re.sub(r"^\s*[-*]\s+", "", tldr, flags=re.MULTILINE)
                tldr_eq, tldr_cjk, _, _ = count_kp_words_cjk(tldr_body)
                if verbose:
                    print(f"[words] {kpid}.tldr: eq={tldr_eq} (cjk={tldr_cjk})")
                if tldr_eq > 60:
                    warnings.append(Issue(lfile, kpid, f"tldr has {tldr_eq} eq-words; max 60"))

            explain = kp.get("explain") or ""
            if not explain.strip():
                issues.append(Issue(lfile, kpid, "knowledge-point explain must not be empty"))
            exp_eq, exp_cjk, exp_lat, exp_math = count_kp_words_cjk(explain)
            if verbose:
                print(f"[words] {kpid}.explain: eq={exp_eq} (cjk={exp_cjk}, latin={exp_lat}, math={exp_math})")
            if exp_eq > 380:
                issues.append(Issue(lfile, kpid, f"explain has {exp_eq} eq-words; max 380"))
            elif exp_eq < 150:
                warnings.append(Issue(lfile, kpid, f"explain has {exp_eq} eq-words; skill target is 150-380"))

            if not (kp.get("worked") or "").strip():
                issues.append(Issue(lfile, kpid, "knowledge-point worked must not be empty"))

            probs = kp.get("problems") or []
            if len(probs) < 3:
                issues.append(Issue(lfile, kpid, f"knowledge point has {len(probs)} problems; min 3"))
            elif len(probs) < 5:
                warnings.append(Issue(lfile, kpid, f"knowledge point has {len(probs)} problems; skill recommends >= 5"))

            first_ex = exercises_by_id.get(probs[0]) if probs else None
            if not first_ex or first_ex[2].get("role") != "basics":
                issues.append(Issue(lfile, kpid, "first problem must have role: basics"))
            elif first_ex[2].get("type") != "mc" or first_ex[2].get("dimension") != "conceptual":
                issues.append(Issue(lfile, kpid, "first problem must be conceptual MC basics"))

            has_lesson_only = any(
                exercises_by_id.get(pid) and exercises_by_id[pid][2].get("lesson_only") is True
                for pid in probs
            )
            if not has_lesson_only:
                issues.append(Issue(lfile, kpid, "missing lesson_only self-explanation problem"))

            fixed_cnt = 0
            template_cnt = 0
            seen_in_kp: set[str] = set()
            for pid in probs:
                if pid in seen_in_kp:
                    issues.append(Issue(lfile, kpid, f'duplicate problem "{pid}" in KP'))
                seen_in_kp.add(pid)
                problem_refs[pid] = problem_refs.get(pid, 0) + 1
                if pid not in exercises_by_id:
                    issues.append(Issue(lfile, kpid, f'references missing problem "{pid}"'))
                    continue
                econ, _, ex_obj = exercises_by_id[pid]
                if econ != lcon:
                    issues.append(Issue(lfile, kpid, f'problem "{pid}" belongs to "{econ}", not "{lcon}"'))
                if ex_obj.get("type") == "explain":
                    issues.append(Issue(lfile, kpid, f'KP problem "{pid}" cannot be type explain'))
                if ex_obj.get("role") not in {"practice", "check"} and not (pid == probs[0] and ex_obj.get("role") == "basics"):
                    issues.append(Issue(lfile, kpid, f'problem "{pid}" must have practice/check (or first basics) role'))
                if is_template(ex_obj):
                    template_cnt += 1
                else:
                    fixed_cnt += 1

            if fixed_cnt < 1:
                issues.append(Issue(lfile, kpid, "must include at least 1 fixed problem"))
            if fixed_cnt < 3 and template_cnt == 0:
                issues.append(Issue(lfile, kpid, "needs 3 fixed problems or >= 1 template"))

        final_id = ldoc.get("final")
        if not final_id or final_id not in exercises_by_id:
            issues.append(Issue(lfile, lcon, f'final exercise "{final_id}" does not exist'))
        else:
            fcon, _, fex = exercises_by_id[final_id]
            if fcon != lcon:
                issues.append(Issue(lfile, lcon, "final exercise must belong to lesson concept"))
            if fex.get("type") != "explain":
                issues.append(Issue(lfile, lcon, "final exercise must be type explain"))
            if fex.get("role") == "basics":
                issues.append(Issue(lfile, lcon, "basics exercise cannot be final"))
            if any(final_id in (kp.get("problems") or []) for kp in kps):
                issues.append(Issue(lfile, lcon, "final exercise cannot appear in KP problems"))

        # Check SVG blocks inside lesson
        for txt in string_values(ldoc):
            for match in SVG_FENCE_RE.finditer(txt):
                meta = match.group(1).strip()
                if meta and meta != "academy-visual=eigen-directions":
                    issues.append(Issue(lfile, lcon, f"unsupported SVG metadata: {meta}"))
                err = validate_svg_block(match.group(2))
                if err:
                    issues.append(Issue(lfile, lcon, f"invalid SVG: {err}"))

    # Exercise reference checks & recall checks
    for eid, (econ, efile, ex) in exercises_by_id.items():
        role = ex.get("role")
        if role == "practice":
            if problem_refs.get(eid, 0) != 1:
                issues.append(Issue(efile, eid, "practice exercise must be referenced by exactly one KP"))
        elif role == "basics":
            if problem_refs.get(eid, 0) != 1:
                issues.append(Issue(efile, eid, "basics exercise must be referenced by exactly one KP"))
        elif role == "recall":
            kpid = ex.get("knowledge_point")
            lesson_entry = lessons_by_concept.get(econ)
            valid_kp_ids = {kp["id"] for kp in (lesson_entry[1].get("knowledge_points") or [])} if lesson_entry else set()
            if not kpid or kpid not in valid_kp_ids:
                issues.append(Issue(efile, eid, f'recall knowledge_point "{kpid}" missing in lesson'))
            if ex.get("lesson_only"):
                issues.append(Issue(efile, eid, "recall exercise must not be lesson_only"))
            if is_template(ex):
                issues.append(Issue(efile, eid, "recall exercise must not be a template"))
            if problem_refs.get(eid, 0) > 0:
                issues.append(Issue(efile, eid, "recall exercise must not be in KP problems"))

    # Recall count per KP + authored vs stub concept checks
    for cid, c in concepts_by_id.items():
        cfile = concept_file[cid]
        cex_list = exercises_by_concept.get(cid, [])
        if c.get("status") == "authored":
            if cid not in lessons_by_concept:
                issues.append(Issue(cfile, cid, "authored concept is missing its lesson"))
            if len(cex_list) < 3:
                issues.append(Issue(cfile, cid, f"authored concept has {len(cex_list)} exercises; min 3"))
            if not any(ex.get("role") in {"core", "review"} for _, ex in cex_list):
                issues.append(Issue(cfile, cid, "authored concept has no core/review-eligible exercise"))
            dims = {ex.get("dimension") for _, ex in cex_list}
            for dim in dims:
                if not any(
                    ex.get("dimension") == dim
                    and ex.get("role") in REVIEWABLE_ROLES
                    and not ex.get("lesson_only")
                    and not is_template(ex)
                    for _, ex in cex_list
                ):
                    issues.append(Issue(cfile, cid, f'dimension "{dim}" lacks non-template reviewable exercise'))
            if cid in lessons_by_concept:
                lfile, ldoc = lessons_by_concept[cid]
                for kp in ldoc.get("knowledge_points") or []:
                    recalls = [ex for _, ex in cex_list if ex.get("role") == "recall" and ex.get("knowledge_point") == kp["id"]]
                    if len(recalls) < 3:
                        warnings.append(Issue(lfile, kp["id"], f"has {len(recalls)} recall exercises; skill expects 3 (explain, mc, expression/text)"))
        else:
            if cid in lessons_by_concept:
                issues.append(Issue(lessons_by_concept[cid][0], cid, "stub concept must not have a lesson"))
            for efile, ex in cex_list:
                if ex.get("role") != "diagnostic":
                    issues.append(Issue(efile, ex["id"], "stub concept may only have diagnostic exercises"))

    # Notation usage validation
    if data["notation"]:
        nfile, ndoc = data["notation"]
        terms = ndoc.get("terms") or []
        seen_term_ids: set[str] = set()
        for t in terms:
            tid = t["id"]
            if tid in seen_term_ids:
                issues.append(Issue(nfile, tid, "duplicate notation term id"))
            seen_term_ids.add(tid)

        for cid in concepts_by_id:
            if cid not in lessons_by_concept and cid not in exercises_by_concept:
                continue
            hard_anc = hard_ancestors(cid, concepts_by_id)
            soft_anc = soft_only_ancestors(cid, concepts_by_id, hard_anc)
            allowed_introducers = {cid} | hard_anc

            entries: list[tuple[str, str, str]] = []
            if cid in lessons_by_concept:
                lfile, ldoc = lessons_by_concept[cid]
                for r in ldoc.get("recap") or []:
                    entries.append((lfile, cid, r.get("text", "")))
                entries.append((lfile, cid, ldoc.get("where_this_fits", "")))
                entries.append((lfile, cid, ldoc.get("summary", "")))
                for kp in ldoc.get("knowledge_points") or []:
                    for txt in [kp.get("title", ""), kp.get("tldr", ""), kp.get("explain", ""), kp.get("worked", "")]:
                        entries.append((lfile, kp["id"], txt))
            for efile, ex in exercises_by_concept.get(cid, []):
                for txt in string_values(ex):
                    entries.append((efile, ex["id"], txt))

            for t in terms:
                introducers = set(t.get("introduced_by") or [])
                if introducers & allowed_introducers:
                    continue
                for pat in t.get("match") or []:
                    rx = re.compile(pat)
                    matched = None
                    for ef, eid, txt in entries:
                        m = rx.search(txt)
                        if m:
                            matched = (ef, eid, m.group(0))
                            break
                    if matched:
                        ef, eid, frag = matched
                        soft_hit = sorted(introducers & soft_anc)
                        if not introducers:
                            msg = f'uses {t["label"]} ("{frag}"), but no topic teaches it yet'
                        elif soft_hit:
                            msg = f'uses {t["label"]} ("{frag}"), taught by soft prereq {", ".join(soft_hit)}; make it hard'
                        else:
                            msg = f'uses {t["label"]} ("{frag}"), introduced by {", ".join(sorted(introducers))}, not in hard prereqs'
                        issues.append(Issue(ef, eid, msg))
                        break

        # avoid prose rules
        for rule in ndoc.get("avoid") or []:
            rx = re.compile(rule["pattern"])
            for lfile, ldoc in data["lessons"]:
                for txt in string_values(ldoc, AVOIDED_EXCLUDE_KEYS):
                    cleaned = CODE_FENCE_RE.sub(" ", txt)
                    for m in rx.finditer(cleaned):
                        issues.append(Issue(lfile, ldoc["concept"], f'"{m.group(0)}": {rule["use"]}'))

    return issues, warnings


def print_prereqs(pack_dir: Path, topic_id: str) -> int:
    data = load_pack(pack_dir)
    concepts_by_id = {
        c["id"]: c for _, cdoc in data["concepts"] for c in cdoc.get("concepts", [])
    }
    if topic_id not in concepts_by_id:
        print(f'Unknown topic "{topic_id}".', file=sys.stderr)
        return 1
    topic = concepts_by_id[topic_id]
    lessons_by_concept = {ldoc["concept"]: ldoc for _, ldoc in data["lessons"]}

    # Curriculum order
    order: dict[str, int] = {}
    idx = 0
    for _, kdoc in data["courses"]:
        for u in kdoc.get("units", []):
            for cid in u.get("concepts", []):
                if cid not in order:
                    order[cid] = idx
                    idx += 1

    hard_req = hard_ancestors(topic_id, concepts_by_id)
    ordered_hard: list[str] = []
    visited_topo: set[str] = set()

    def _topo_visit(cid: str) -> None:
        if cid in visited_topo or cid not in hard_req:
            return
        visited_topo.add(cid)
        c = concepts_by_id.get(cid, {})
        deps = [
            p["id"]
            for p in c.get("prereqs", [])
            if p.get("strength", "hard") == "hard" and p["id"] in hard_req
        ]
        for dep in sorted(deps, key=lambda d: (order.get(d, -1), d)):
            _topo_visit(dep)
        ordered_hard.append(cid)

    for cid in sorted(hard_req, key=lambda c: (order.get(c, -1), c)):
        _topo_visit(cid)
    soft_req = sorted(soft_only_ancestors(topic_id, concepts_by_id, hard_req), key=lambda cid: (order.get(cid, 10**9), cid))

    terms = (data["notation"][1].get("terms") or []) if data["notation"] else []
    taught_terms = []
    not_yet_taught = []
    for t in terms:
        intros = t.get("introduced_by") or []
        req_intros = [i for i in intros if i in hard_req]
        if req_intros:
            taught_terms.append(f'- {t["label"]} (introduced by {", ".join(req_intros)})')
        elif topic_id not in intros:
            other = [i for i in intros if i != topic_id]
            not_yet_taught.append(f'- {t["label"]} (introduced by {", ".join(other) if other else "no topic yet"})')

    req_blocks = []
    for cid in ordered_hard:
        c = concepts_by_id[cid]
        lines = [f'### {c["title"]} ({cid})', c.get("description", "")]
        if cid not in lessons_by_concept:
            lines.append("(no lesson yet; prereq contract from concept definition & objectives)")
            for obj in c.get("objectives", []):
                lines.append(f'- [{obj.get("dimension", "conceptual")}] {obj["text"]}')
        else:
            ldoc = lessons_by_concept[cid]
            for kp in ldoc.get("knowledge_points") or []:
                lines.append(f'- Step: {kp["title"]}')
                if kp.get("tldr"):
                    lines.append(kp["tldr"].strip())
            if ldoc.get("summary"):
                lines.append(ldoc["summary"].strip())
        req_blocks.append("\n".join(lines))

    soft_lines = [f'- {concepts_by_id[cid]["title"]} ({cid})' for cid in soft_req if cid in concepts_by_id]

    parts = [
        f'# What a learner starting {topic["title"]} ({topic_id}) has been taught',
        "\n\n".join(["## Required topics (hard prerequisites, direct or through a chain), prerequisites first", *req_blocks]),
        "\n".join(["## Notation and ideas already taught", *taught_terms]),
        "\n".join(["## Soft links (helpful background, NOT guaranteed; anything only taught here counts as untaught)", *soft_lines]),
        "\n".join(["## Not yet taught at this point", *not_yet_taught]),
    ]
    print("\n\n".join(parts))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Open Academy Python check & prereqs CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Validate an Open Academy course pack")
    p_check.add_argument("dir", nargs="?", default=".", help="Pack root directory")
    p_check.add_argument("-v", "--verbose", action="store_true")

    p_pre = sub.add_parser("prereqs", help="Print what a learner starting <topic-id> has been taught")
    p_pre.add_argument("topic_id")
    p_pre.add_argument("--pack", default=".", help="Pack root directory")

    args = parser.parse_args()
    if args.cmd == "prereqs":
        return print_prereqs(Path(args.pack), args.topic_id)

    pack_dir = Path(args.dir)
    issues, warnings = check_pack(pack_dir, verbose=args.verbose)
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARN] {w.file} ({w.item_id}): {w.message}")
    if issues:
        print(f"Errors ({len(issues)}):")
        for err in issues:
            print(f"  [ERR]  {err.file} ({err.item_id}): {err.message}")
        return 1
    print(f"OK: {pack_dir} passed academy_check with 0 errors and {len(warnings)} warnings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
