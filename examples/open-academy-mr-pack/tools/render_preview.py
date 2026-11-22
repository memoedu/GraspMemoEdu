#!/usr/bin/env python3
"""Render Unit 1 of open-academy-mr-pack into a multi-lesson interactive web app
with localStorage persistence and a 12-card FSRS-5 review-time prediction dashboard."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import yaml


UNIT1_DEFAULT_CONCEPTS = [
    "spin-zeeman-and-drive",
    "rotating-wave-and-frame",
    "su2-evolution-and-rabi-prob",
]


def md_block_to_html(text: str) -> str:
    """Convert lesson/exercise markdown with fenced svg/python and $$ math to clean HTML."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    fence_re = re.compile(r"```(svg|python)([^\r\n]*)\r?\n([\s\S]*?)```", re.IGNORECASE)
    for m in fence_re.finditer(text):
        if m.start() > pos:
            tokens.append(("md", text[pos : m.start()]))
        tokens.append((m.group(1).lower(), m.group(3)))
        pos = m.end()
    if pos < len(text):
        tokens.append(("md", text[pos:]))

    out: list[str] = []
    for kind, body in tokens:
        if kind == "svg":
            out.append(f'<div class="svg-wrap">{body}</div>')
        elif kind == "python":
            out.append(f'<pre class="code-block"><code>{html.escape(body.rstrip())}</code></pre>')
        else:
            math_store: list[str] = []

            def keep_display(m: re.Match[str]) -> str:
                math_store.append(m.group(0))
                return f"@@MATH{len(math_store)-1}@@"

            protected = re.sub(r"\$\$[\s\S]*?\$\$", keep_display, body)
            protected = re.sub(r"\$[^$\n]+\$", keep_display, protected)
            lines = protected.splitlines()
            html_lines: list[str] = []
            in_ul = False
            in_ol = False

            def close_lists() -> None:
                nonlocal in_ul, in_ol
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False

            def fmt_inline(s: str) -> str:
                s = html.escape(s)
                s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
                s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
                for idx, math_txt in enumerate(math_store):
                    s = s.replace(f"@@MATH{idx}@@", html.escape(math_txt))
                return s

            for line in lines:
                s = line.strip()
                if not s:
                    close_lists()
                    continue
                if s.startswith("### "):
                    close_lists()
                    html_lines.append(f"<h4>{fmt_inline(s[4:])}</h4>")
                elif s.startswith("- "):
                    if in_ol:
                        html_lines.append("</ol>")
                        in_ol = False
                    if not in_ul:
                        html_lines.append("<ul>")
                        in_ul = True
                    html_lines.append(f"<li>{fmt_inline(s[2:])}</li>")
                elif re.match(r"^\d+\.\s+", s):
                    if in_ul:
                        html_lines.append("</ul>")
                        in_ul = False
                    if not in_ol:
                        html_lines.append("<ol>")
                        in_ol = True
                    item = re.sub(r"^\d+\.\s+", "", s)
                    html_lines.append(f"<li>{fmt_inline(item)}</li>")
                else:
                    if in_ol and s.startswith("@@MATH"):
                        html_lines.append(f'<div class="step-math">{fmt_inline(s)}</div>')
                    else:
                        close_lists()
                        html_lines.append(f"<p>{fmt_inline(s)}</p>")
            close_lists()
            out.append("\n".join(html_lines))
    return "\n".join(out)


def render_exercise_slot(ex: dict) -> str:
    badge = (
        "FSRS Recall"
        if ex.get("role") == "recall"
        else ("概念基础" if ex.get("role") == "basics" else ("例题自解释" if ex.get("lesson_only") else f"难度 {ex['difficulty']}"))
    )
    dim_tag = ex.get("dimension", "conceptual")
    cls = "prob recall" if ex.get("role") == "recall" else "prob"
    target_sec = max(15, round(float(ex.get("est_minutes", 1)) * 60))
    return (
        f'<div class="{cls}" data-ex-id="{html.escape(ex["id"])}">'
        f'<div class="prob-head">'
        f'<span>{html.escape(ex["id"])} · {html.escape(ex["type"])}</span>'
        f'<span class="prob-meta-right">'
        f'<span class="timer-pill" data-timer>计时 0s / 目标 {target_sec}s</span> '
        f'<span class="rating-pill" data-rating>未作答</span> '
        f'<span class="tag">{html.escape(dim_tag)}</span> '
        f'<span class="tag">{html.escape(badge)}</span>'
        f'</span></div>'
        f'<div class="prob-body"></div>'
        f"</div>"
    )


def build_html(pack_dir: Path, default_concept: str = "spin-zeeman-and-drive") -> str:
    course = yaml.safe_load((pack_dir / "courses" / "mr-fundamentals.yaml").read_text(encoding="utf-8"))
    concepts_doc = yaml.safe_load((pack_dir / "concepts" / "magnetic-resonance.yaml").read_text(encoding="utf-8"))
    concepts_by_id = {c["id"]: c for c in concepts_doc["concepts"]}

    unit1 = course["units"][0]
    concept_ids = list(unit1.get("concepts") or UNIT1_DEFAULT_CONCEPTS)

    ex_map: dict[str, dict] = {}
    kp_meta: list[dict] = []
    lessons_meta: list[dict] = []
    tabs_html: list[str] = []
    lessons_sections_html: list[str] = []

    for l_idx, cid in enumerate(concept_ids, start=1):
        lesson = yaml.safe_load((pack_dir / "lessons" / f"{cid}.yaml").read_text(encoding="utf-8"))
        ex_doc = yaml.safe_load((pack_dir / "exercises" / f"{cid}.yaml").read_text(encoding="utf-8"))
        cmeta = concepts_by_id[cid]
        local_ex_map = {e["id"]: e for e in ex_doc["exercises"]}
        for ex_id, ex_obj in local_ex_map.items():
            enriched = dict(ex_obj)
            enriched["lessonId"] = cid
            ex_map[ex_id] = enriched

        lessons_meta.append(
            {
                "id": cid,
                "index": l_idx,
                "title": cmeta["title"],
                "version": lesson.get("version", 1),
                "estMinutes": cmeta.get("est_minutes", 30),
                "exerciseIds": [e["id"] for e in ex_doc["exercises"]],
            }
        )

        is_default = cid == default_concept
        active_cls = " active" if is_default else ""
        tabs_html.append(
            f'<button type="button" class="lesson-tab{active_cls}" data-lesson-tab="{html.escape(cid)}">'
            f'<span class="tab-kicker">第 {l_idx} 课 · v{lesson.get("version", 1)}</span>'
            f'<span class="tab-title">{html.escape(cmeta["title"])}</span>'
            f'<span class="tab-prog" data-lesson-prog="{html.escape(cid)}">0 / {len(ex_doc["exercises"])}</span>'
            f'</button>'
        )

        prereq_titles = [
            f"{concepts_by_id[pid]['title']}（{pid}）" if pid in concepts_by_id else pid
            for pid in cmeta.get("prereq_ids", [])
        ]
        prereq_chain = " 、 ".join(prereq_titles) if prereq_titles else "无"
        sources_str = " · ".join(f"{s['source']}（{s.get('section', '')}）" for s in lesson.get("sources", []))

        recap_blocks: list[str] = []
        for rec in lesson.get("recap", []):
            rcid = rec["concept"]
            rtitle = concepts_by_id.get(rcid, {}).get("title", rcid)
            jump_btn = (
                f' <button type="button" class="btn btn-jump-lesson" data-jump-lesson="{html.escape(rcid)}">跳转复习本节 →</button>'
                if rcid in concept_ids
                else ""
            )
            recap_blocks.append(
                f'<div class="recap-item">'
                f'<div class="recap-head"><strong>前置回顾 · {html.escape(rtitle)}（{html.escape(rcid)}）</strong>{jump_btn}</div>'
                f'<div>{md_block_to_html(rec.get("text", ""))}</div>'
                f'</div>'
            )
        recap_html = f'<section class="card recap-card"><h3>前置衔接（Recap）</h3>{"".join(recap_blocks)}</section>' if recap_blocks else ""

        steps_html: list[str] = []
        for s_idx, kp in enumerate(lesson["knowledge_points"], start=1):
            probs_html = [render_exercise_slot(local_ex_map[pid]) for pid in kp["problems"]]
            recalls = [e for e in ex_doc["exercises"] if e.get("role") == "recall" and e.get("knowledge_point") == kp["id"]]
            recalls_html = [render_exercise_slot(r) for r in recalls]
            kp_meta.append(
                {
                    "id": kp["id"],
                    "lessonId": cid,
                    "lessonIndex": l_idx,
                    "lessonTitle": cmeta["title"],
                    "step": s_idx,
                    "title": kp["title"],
                    "problemIds": list(kp["problems"]),
                    "recallIds": [r["id"] for r in recalls],
                }
            )
            steps_html.append(
                f"""
                <section class="card step" id="step-{html.escape(cid)}-{s_idx}">
                  <div class="step-num">第 {l_idx} 课 Step {s_idx} · {html.escape(kp['id'])}</div>
                  <h2>{html.escape(kp['title'])}</h2>
                  <div class="tldr"><strong>本步要点 (TL;DR)</strong>{md_block_to_html(kp.get('tldr', ''))}</div>
                  <div class="explain">{md_block_to_html(kp['explain'])}</div>
                  <div class="worked"><h3>Worked Example</h3>{md_block_to_html(kp['worked'])}</div>
                  <details class="problems-box" open id="problems-{html.escape(kp['id'])}">
                    <summary>随堂与测验题库（{len(kp['problems'])} 题 · 自动计时与存档）</summary>
                    {''.join(probs_html)}
                  </details>
                  <details class="problems-box" id="recalls-{html.escape(kp['id'])}">
                    <summary>FSRS 间隔复习 Recall 题（{len(recalls)} 题 · 完成后可更新复习时间）</summary>
                    {''.join(recalls_html)}
                    <div class="recall-batch-bar">
                      <button type="button" class="btn btn-primary btn-commit-recall" data-kp="{html.escape(kp['id'])}">提交本步 3 题 Recall 复习并更新下次复习时间</button>
                      <span class="recall-batch-status" data-kp-recall-status="{html.escape(kp['id'])}"></span>
                    </div>
                  </details>
                </section>
                """
            )

        final_ex = local_ex_map[lesson["final"]]
        nav_btns: list[str] = []
        if l_idx > 1:
            prev_cid = concept_ids[l_idx - 2]
            prev_title = concepts_by_id[prev_cid]["title"]
            nav_btns.append(f'<button type="button" class="btn btn-jump-lesson" data-jump-lesson="{html.escape(prev_cid)}">← 上一课：{html.escape(prev_title)}</button>')
        if l_idx < len(concept_ids):
            next_cid = concept_ids[l_idx]
            next_title = concepts_by_id[next_cid]["title"]
            nav_btns.append(f'<button type="button" class="btn btn-primary btn-jump-lesson" data-jump-lesson="{html.escape(next_cid)}">下一课：{html.escape(next_title)} →</button>')

        lessons_sections_html.append(
            f"""
            <div class="lesson-pane{active_cls}" data-lesson-pane="{html.escape(cid)}">
              <div class="meta">课程：{html.escape(course['title'])}（{html.escape(unit1['title'])} · 第 {l_idx}/3 课） · 双源依据：{html.escape(sources_str)} · 预计 {cmeta.get('est_minutes', 30)} 分钟</div>
              <h1>{html.escape(cmeta['title'])}</h1>
              <section class="card">
                <div class="meta">直接前置依赖：{html.escape(prereq_chain)}</div>
                {md_block_to_html(lesson['where_this_fits'])}
              </section>
              {recap_html}
              {''.join(steps_html)}
              <section class="card">
                <h3>Explain it（课末自评总结题）</h3>
                {render_exercise_slot(final_ex)}
              </section>
              <section class="card">
                <h3>本节总结</h3>
                {md_block_to_html(lesson['summary'])}
              </section>
              <div class="lesson-footer-nav">{''.join(nav_btns)}</div>
            </div>
            """
        )

    ex_json = json.dumps(ex_map, ensure_ascii=False).replace("</", "<\\/")
    kp_json = json.dumps(kp_meta, ensure_ascii=False).replace("</", "<\\/")
    lessons_json = json.dumps(lessons_meta, ensure_ascii=False).replace("</", "<\\/")
    default_json = json.dumps(default_concept, ensure_ascii=False)

    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(course['title'])} · Unit 1 全三课互动学习与 FSRS 预测预览</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" />
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    onload="window.__renderAllMath && window.__renderAllMath();"></script>
  <style>
    :root {{ --bg:#f8fafc; --card:#ffffff; --text:#0f172a; --muted:#64748b; --border:#e2e8f0; --accent:#2563eb; --ok:#16a34a; --warn:#d97706; --bad:#dc2626; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:ui-sans-serif,system-ui,-apple-system,sans-serif; line-height:1.75; }}
    main {{ max-width:940px; margin:20px auto; padding:0 18px 90px; }}
    .meta {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
    h1 {{ font-size:28px; margin:4px 0 12px; }}
    .unit-switcher {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:10px; margin:0 0 14px; }}
    .lesson-tab {{ display:flex; flex-direction:column; align-items:flex-start; gap:3px; padding:10px 12px; border:1px solid var(--border); border-radius:10px; background:#fff; cursor:pointer; text-align:left; transition:border-color .15s,background .15s,box-shadow .15s; }}
    .lesson-tab:hover {{ border-color:var(--accent); background:#f8fbff; }}
    .lesson-tab.active {{ border-color:var(--accent); background:#eff6ff; box-shadow:0 2px 10px rgba(37,99,235,.12); }}
    .tab-kicker {{ font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase; }}
    .tab-title {{ font-size:14px; font-weight:700; color:var(--text); line-height:1.35; }}
    .tab-prog {{ font-size:11px; color:var(--muted); }}
    .lesson-pane {{ display:none; }}
    .lesson-pane.active {{ display:block; }}
    .scorebar {{ position:sticky; top:0; z-index:30; background:rgba(255,255,255,.96); backdrop-filter:blur(8px); border:1px solid var(--border); border-radius:10px; padding:10px 14px; margin-bottom:14px; display:flex; flex-wrap:wrap; gap:10px; justify-content:space-between; align-items:center; font-size:13px; box-shadow:0 2px 8px rgba(15,23,42,.05); }}
    .score-stats {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:22px 24px; margin:18px 0; }}
    .recap-card {{ border-color:#dbeafe; background:#f8fbff; }}
    .recap-item {{ border-top:1px dashed #cbd5e1; padding-top:10px; margin-top:10px; }}
    .recap-item:first-of-type {{ border-top:none; padding-top:0; margin-top:0; }}
    .recap-head {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px; margin-bottom:4px; }}
    .dash-panel {{ border:1px solid #bfdbfe; background:#f8fbff; border-radius:12px; padding:16px 18px; margin:12px 0 20px; }}
    .dash-panel summary {{ cursor:pointer; font-weight:700; font-size:15px; color:#1e3a8a; }}
    .dash-controls {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:12px 0; }}
    .clock-pill {{ background:#e0e7ff; color:#1e3a8a; padding:4px 10px; border-radius:99px; font-size:12px; font-weight:600; }}
    .forecast-strip {{ display:grid; grid-template-columns:repeat(8, minmax(0, 1fr)); gap:6px; margin:10px 0 14px; }}
    .fc-cell {{ background:#fff; border:1px solid var(--border); border-radius:8px; padding:6px 4px; text-align:center; font-size:12px; }}
    .fc-cell.due {{ border-color:#f59e0b; background:#fffbeb; }}
    .fc-cell .fc-cnt {{ font-size:16px; font-weight:700; color:var(--accent); }}
    .fsrs-table {{ width:100%; border-collapse:collapse; font-size:12px; background:#fff; border-radius:8px; overflow:hidden; margin-top:8px; }}
    .fsrs-table th, .fsrs-table td {{ border:1px solid var(--border); padding:7px 8px; text-align:left; vertical-align:middle; }}
    .fsrs-table th {{ background:#f1f5f9; color:#334155; font-weight:600; }}
    .pill {{ display:inline-block; padding:1px 7px; border-radius:99px; font-size:11px; font-weight:600; }}
    .pill-new {{ background:#f1f5f9; color:#475569; }}
    .pill-ok {{ background:#dcfce7; color:#166534; }}
    .pill-hard {{ background:#fef3c7; color:#92400e; }}
    .pill-due {{ background:#fee2e2; color:#991b1b; }}
    .step-num {{ font-size:12px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--accent); }}
    .tldr {{ background:#eff6ff; border-left:3px solid var(--accent); padding:10px 14px; border-radius:6px; margin:12px 0 18px; font-size:14px; }}
    .worked {{ background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:14px 18px; margin-top:16px; }}
    .svg-wrap {{ margin:16px 0; text-align:center; overflow-x:auto; }}
    .svg-wrap svg {{ max-width:100%; height:auto; border:1px solid #f0f0f0; border-radius:8px; background:#fff; }}
    .problems-box {{ margin-top:14px; border:1px solid var(--border); border-radius:8px; padding:10px 14px; background:#fcfcfd; }}
    .problems-box summary {{ cursor:pointer; font-weight:600; font-size:14px; padding:2px 0; }}
    .prob {{ border-top:1px solid var(--border); padding:14px 0; font-size:14px; }}
    .prob-head {{ display:flex; flex-wrap:wrap; gap:6px; justify-content:space-between; align-items:center; color:var(--muted); font-size:12px; font-family:ui-monospace,monospace; margin-bottom:6px; }}
    .prob-meta-right {{ display:flex; flex-wrap:wrap; gap:5px; align-items:center; }}
    .timer-pill {{ background:#f1f5f9; color:#334155; padding:1px 7px; border-radius:99px; font-family:sans-serif; font-size:11px; }}
    .rating-pill {{ background:#f1f5f9; color:#475569; padding:1px 7px; border-radius:99px; font-family:sans-serif; font-size:11px; font-weight:600; }}
    .rating-pill.good {{ background:#dcfce7; color:#166534; }}
    .rating-pill.hard {{ background:#fef3c7; color:#92400e; }}
    .rating-pill.again {{ background:#fee2e2; color:#991b1b; }}
    .tag {{ background:#eef2ff; padding:2px 8px; border-radius:99px; color:#3730a3; font-family:sans-serif; font-size:11px; }}
    .opts-grid {{ display:flex; flex-direction:column; gap:8px; margin-top:8px; }}
    .opt-btn {{ text-align:left; background:#fff; border:1px solid var(--border); border-radius:8px; padding:9px 12px; cursor:pointer; font-size:14px; line-height:1.5; transition:border-color .15s,background .15s; }}
    .opt-btn:hover {{ border-color:var(--accent); background:#f8fafc; }}
    .opt-btn.picked-ok {{ border-color:var(--ok); background:#f0fdf4; }}
    .opt-btn.picked-bad {{ border-color:var(--bad); background:#fef2f2; }}
    .input-row {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:8px; }}
    .txt-in {{ padding:7px 10px; border:1px solid #cbd5e1; border-radius:7px; font-size:14px; min-width:220px; }}
    .btn {{ padding:6px 11px; border:1px solid var(--border); border-radius:7px; background:#fff; cursor:pointer; font-size:12px; }}
    .btn-primary {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
    .btn-danger {{ border-color:#fecaca; color:#b91c1c; background:#fff; }}
    .btn:hover {{ opacity:.9; }}
    .fb {{ margin-top:10px; padding:9px 12px; border-radius:7px; font-size:13px; display:none; }}
    .fb.ok {{ display:block; background:#f0fdf4; border:1px solid #bbf7d0; color:#14532d; }}
    .fb.bad {{ display:block; background:#fef2f2; border:1px solid #fecaca; color:#7f1d1d; }}
    .fb.info {{ display:block; background:#f1f5f9; border:1px solid #cbd5e1; color:#1e293b; }}
    .hint-box {{ margin-top:8px; font-size:13px; color:#475569; background:#f8fafc; border-left:3px solid #94a3b8; padding:6px 10px; display:none; }}
    textarea.explain-in {{ width:100%; box-sizing:border-box; min-height:64px; padding:8px 10px; border:1px solid #cbd5e1; border-radius:7px; font-size:13px; font-family:inherit; margin-top:6px; }}
    .rubric-list {{ list-style:none; padding-left:4px; margin:8px 0; }}
    .rubric-list li {{ margin:4px 0; }}
    .recall-batch-bar {{ margin-top:12px; padding-top:10px; border-top:1px dashed var(--border); display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
    .recall-batch-status {{ font-size:12px; color:#334155; }}
    .lesson-footer-nav {{ display:flex; justify-content:space-between; gap:10px; margin-top:20px; flex-wrap:wrap; }}
    .step-math {{ margin:6px 0 10px 16px; }}
    .katex-display {{ overflow-x:auto; overflow-y:hidden; padding:4px 0; }}
    @media (max-width: 720px) {{ .unit-switcher {{ grid-template-columns:1fr; }} .forecast-strip {{ grid-template-columns:repeat(4, minmax(0, 1fr)); }} .fsrs-table {{ display:block; overflow-x:auto; }} }}
  </style>
</head>
<body>
<main>
  <div class="scorebar">
    <div><strong>Open Academy · Unit 1 全三课互动学习</strong> · 双教材集成 · <code>localStorage</code> 自动存档</div>
    <div class="score-stats">
      <span id="score-readout">Unit 1：自动判题 0 / 63 · 自评 0 / 12</span>
      <span id="lesson-readout">当前课：0 / 25</span>
      <span id="time-readout">累计作答 0s</span>
      <span id="due-readout">今日到期卡片：0 / 12</span>
    </div>
  </div>

  <nav class="unit-switcher" aria-label="Unit 1 课程切换">
    {''.join(tabs_html)}
  </nav>

  <details class="dash-panel" open>
    <summary>Unit 1 全局学习进度与 12 卡 FSRS-5 复习时间预测面板（目标保持率 90% · 最长间隔 60 天）</summary>
    <div class="dash-controls">
      <span class="clock-pill" id="sim-clock-readout">当前参考时间：真实时间</span>
      <button type="button" class="btn" data-shift-days="1">时间快进 +1 天</button>
      <button type="button" class="btn" data-shift-days="3">+3 天</button>
      <button type="button" class="btn" data-shift-days="7">+7 天</button>
      <button type="button" class="btn" data-shift-days="14">+14 天</button>
      <button type="button" class="btn btn-primary" id="btn-fast-forward-due">快进到最早到期卡</button>
      <button type="button" class="btn" id="btn-clock-reset">回到真实时间</button>
      <button type="button" class="btn" id="btn-export-json">导出进度 JSON</button>
      <button type="button" class="btn" id="btn-import-json">导入进度 JSON</button>
      <input type="file" id="import-file-input" accept="application/json" style="display:none" />
      <button type="button" class="btn btn-danger" id="btn-reset-all">重置全部进度</button>
    </div>
    <div class="meta">说明：Unit 1 共 3 课、9 个知识点（9 张 KP 卡 + 3 张维度卡 = 12 张 FSRS 卡）。做完某步全部 5 题自动为该知识点建卡；后续可通过该步的 3 题 Recall 批量提交推进 FSRS 排程（使用提示、重试或超时 <code>durationMs &gt; targetSeconds</code> 会从 Good 降级为 Hard）。</div>
    <div class="forecast-strip" id="forecast-strip"></div>
    <table class="fsrs-table">
      <thead>
        <tr>
          <th>记忆卡片（9 知识点 / 3 维度）</th>
          <th>状态</th>
          <th>稳定度 S / 难度 D</th>
          <th>当前保持率 R(t)</th>
          <th>预测下次复习时间</th>
          <th>下一轮三档预测（Again / Hard / Good）</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody id="fsrs-tbody"></tbody>
    </table>
  </details>

  {''.join(lessons_sections_html)}
</main>
<script>
const EX_MAP = {ex_json};
const KP_META = {kp_json};
const LESSONS_META = {lessons_json};
const DEFAULT_LESSON_ID = {default_json};
const STORAGE_KEY = "open_academy_mr_progress_v1";

// ============================================================================
// FSRS-5 Core Engine matching apps/api/src/learning/fsrs.ts
// request_retention: 0.9, maximum_interval: 60, enable_short_term: false
// ============================================================================
const FSRS_W = [
  0.40255, 1.18385, 3.173, 15.69105, 7.1949,
  0.5345, 1.4604, 0.0046, 1.54575, 0.1192,
  1.01925, 1.9395, 0.11, 0.29605, 2.2698,
  0.2315, 2.9898, 0.51655, 0.6621
];
const REQUEST_RETENTION = 0.9;
const MAX_INTERVAL_DAYS = 60;
const FSRS_FACTOR = 19 / 81;
const FSRS_DECAY = -0.5;
const MS_PER_DAY = 86400000;

function clamp(v, lo, hi) {{
  return Math.min(hi, Math.max(lo, v));
}}

function startOfLocalCalendarDayMs(tsMs) {{
  const d = new Date(tsMs);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0).getTime();
}}

function startOfNextCalendarDayMs(tsMs) {{
  const d = new Date(tsMs);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1, 0, 0, 0, 0).getTime();
}}

function ratingToNum(rating) {{
  if (rating === "again" || rating === 1) return 1;
  if (rating === "hard" || rating === 2) return 2;
  if (rating === "good" || rating === 3) return 3;
  if (rating === "easy" || rating === 4) return 3;
  return 1;
}}

function createEmptyCard(nowMs) {{
  return {{
    state: "new",
    dueMs: nowMs,
    stability: 0,
    difficulty: 0,
    elapsedDays: 0,
    scheduledDays: 0,
    reps: 0,
    lapses: 0,
    lastReviewMs: null,
    lastRating: null
  }};
}}

function initDifficulty(g) {{
  return clamp(FSRS_W[4] - Math.exp(FSRS_W[5] * (g - 1)) + 1, 1, 10);
}}

function initStability(g) {{
  return Math.max(0.1, FSRS_W[g - 1]);
}}

function nextDifficulty(d, g) {{
  const delta = -FSRS_W[6] * (g - 3);
  const damped = delta * (10 - d) / 9;
  const meanTarget = initDifficulty(4);
  return clamp(FSRS_W[7] * meanTarget + (1 - FSRS_W[7]) * (d + damped), 1, 10);
}}

function forgettingCurve(elapsedDays, stability) {{
  if (!stability || stability <= 0) return 1;
  const t = Math.max(0, elapsedDays);
  return Math.pow(1 + FSRS_FACTOR * (t / stability), FSRS_DECAY);
}}

function nextIntervalDays(stability) {{
  const raw = (stability / FSRS_FACTOR) * (Math.pow(REQUEST_RETENTION, -2) - 1);
  return clamp(Math.round(raw), 1, MAX_INTERVAL_DAYS);
}}

function nextRecallStability(d, s, r, g) {{
  const hardPenalty = g === 2 ? FSRS_W[15] : 1;
  const factor = Math.exp(FSRS_W[8]) * (11 - d) * Math.pow(s, -FSRS_W[9]) * (Math.exp((1 - r) * FSRS_W[10]) - 1) * hardPenalty;
  return Math.max(0.1, s * (1 + factor));
}}

function nextForgetStability(d, s, r) {{
  const sMin = s / Math.exp(FSRS_W[17] * FSRS_W[18]);
  const sNew = FSRS_W[11] * Math.pow(d, -FSRS_W[12]) * (Math.pow(s + 1, FSRS_W[13]) - 1) * Math.exp((1 - r) * FSRS_W[14]);
  return clamp(Math.min(sNew, sMin), 0.1, MAX_INTERVAL_DAYS);
}}

function scheduleReview(card, nowMs, rating) {{
  const g = ratingToNum(rating);
  const prev = card || createEmptyCard(nowMs);
  let newS, newD;
  let lapses = prev.lapses || 0;
  let elapsedDays = 0;

  if (prev.state === "new" || !prev.lastReviewMs || prev.reps === 0) {{
    newD = initDifficulty(g);
    newS = initStability(g);
    if (g === 1) lapses += 1;
  }} else {{
    elapsedDays = Math.max(0, (nowMs - prev.lastReviewMs) / MS_PER_DAY);
    const r = forgettingCurve(elapsedDays, prev.stability);
    newD = nextDifficulty(prev.difficulty, g);
    if (g === 1) {{
      newS = nextForgetStability(newD, prev.stability, r);
      lapses += 1;
    }} else {{
      newS = nextRecallStability(newD, prev.stability, r, g);
    }}
  }}

  const intervalDays = g === 1 ? 1 : nextIntervalDays(newS);
  const rawDueMs = nowMs + intervalDays * MS_PER_DAY;
  const earliestDueMs = startOfNextCalendarDayMs(nowMs);
  const dueMs = Math.max(rawDueMs, earliestDueMs);

  return {{
    card: {{
      state: g === 1 ? "relearning" : "review",
      dueMs,
      stability: Number(newS.toFixed(4)),
      difficulty: Number(newD.toFixed(4)),
      elapsedDays: Number(elapsedDays.toFixed(3)),
      scheduledDays: intervalDays,
      reps: (prev.reps || 0) + 1,
      lapses,
      lastReviewMs: nowMs,
      lastRating: g === 1 ? "again" : (g === 2 ? "hard" : "good")
    }},
    intervalDays
  }};
}}

function cardRetrievability(card, nowMs) {{
  if (!card || card.state === "new" || !card.lastReviewMs || !card.stability) return 1;
  const elapsedDays = Math.max(0, (nowMs - card.lastReviewMs) / MS_PER_DAY);
  return forgettingCurve(elapsedDays, card.stability);
}}

function isDueToday(card, nowMs) {{
  if (!card || card.state === "new" || card.reps === 0) return false;
  return card.dueMs < startOfNextCalendarDayMs(nowMs);
}}

function getTargetSeconds(ex) {{
  return Math.max(15, Math.round((ex.est_minutes || 1) * 60));
}}

function mapReviewRating(input) {{
  if ((input.correct || 0) <= 0) return "again";
  const slow = input.durationMs !== null && input.durationMs !== undefined && input.durationMs > input.targetSeconds * 1000;
  if ((input.hintsUsed || 0) > 0 || (input.attemptNo || 1) > 1 || (input.correct || 0) < 1 || slow) {{
    return "hard";
  }}
  return "good";
}}

function reviewActivityRating(items) {{
  if (!items || items.length === 0) return "again";
  const correctCount = items.filter(it => (it.correct || 0) >= 1).length;
  const allClean = correctCount === items.length && items.every(it => (it.hintsUsed || 0) === 0 && (it.attemptNo || 1) <= 1 && !((it.durationMs || 0) > it.targetSeconds * 1000));
  if (allClean) return "good";
  return correctCount / items.length >= 2 / 3 ? "hard" : "again";
}}

// ============================================================================
// Persistent State Management (localStorage) & Lesson Switching
// ============================================================================
function makeDefaultState() {{
  return {{
    version: 2,
    activeLesson: DEFAULT_LESSON_ID,
    simOffsetMs: 0,
    exercises: {{}},
    cards: {{}}
  }};
}}

function loadState() {{
  try {{
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return makeDefaultState();
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return makeDefaultState();
    const st = Object.assign(makeDefaultState(), parsed);
    if (!LESSONS_META.some(l => l.id === st.activeLesson)) st.activeLesson = DEFAULT_LESSON_ID;
    return st;
  }} catch (e) {{
    return makeDefaultState();
  }}
}}

let STATE = loadState();
const ACTIVE_TIMERS = {{}};

function saveState() {{
  try {{
    localStorage.setItem(STORAGE_KEY, JSON.stringify(STATE));
  }} catch (e) {{}}
}}

function switchLesson(lessonId, scrollTop = false) {{
  if (!LESSONS_META.some(l => l.id === lessonId)) return;
  STATE.activeLesson = lessonId;
  saveState();
  document.querySelectorAll("[data-lesson-tab]").forEach(btn => {{
    btn.classList.toggle("active", btn.dataset.lessonTab === lessonId);
  }});
  document.querySelectorAll("[data-lesson-pane]").forEach(pane => {{
    pane.classList.toggle("active", pane.dataset.lessonPane === lessonId);
  }});
  renderDashboard();
  if (scrollTop && typeof window.scrollTo === "function") {{
    window.scrollTo({{ top: 0, behavior: "smooth" }});
  }}
}}

function virtualNowMs() {{
  return Date.now() + (STATE.simOffsetMs || 0);
}}

function getExState(id) {{
  if (!STATE.exercises[id]) {{
    STATE.exercises[id] = {{
      env: null,
      pickedOpt: null,
      textVal: "",
      explainVal: "",
      rubricChecked: [],
      correct: null,
      attemptNo: 0,
      hintsUsed: 0,
      durationMs: 0,
      rating: null,
      lastAnsweredAt: null
    }};
  }}
  return STATE.exercises[id];
}}

function cardSpecs() {{
  const specs = [];
  for (const kp of KP_META) {{
    const pDone = kp.problemIds.filter(pid => getExState(pid).correct !== null).length;
    const rDone = kp.recallIds.filter(rid => getExState(rid).correct !== null).length;
    specs.push({{
      key: `kp:${{kp.id}}`,
      label: `L${{kp.lessonIndex}} Step ${{kp.step}} · ${{kp.title}}`,
      progressTxt: `随堂 ${{pDone}}/${{kp.problemIds.length}} · Recall ${{rDone}}/${{kp.recallIds.length}}`,
      kind: "kp",
      kpId: kp.id,
      lessonId: kp.lessonId
    }});
  }}
  const dimNames = {{
    conceptual: "Unit 1 维度 · 概念理解 (conceptual)",
    math: "Unit 1 维度 · 数学推导 (math)",
    transfer: "Unit 1 维度 · 迁移应用 (transfer)"
  }};
  for (const dim of ["conceptual", "math", "transfer"]) {{
    const dimIds = Object.values(EX_MAP).filter(e => e.dimension === dim && e.role !== "recall").map(e => e.id);
    const doneCnt = dimIds.filter(id => getExState(id).correct !== null).length;
    specs.push({{
      key: `dim:${{dim}}`,
      label: dimNames[dim],
      progressTxt: `已完成 ${{doneCnt}}/${{dimIds.length}} 题`,
      kind: "dim",
      dim
    }});
  }}
  return specs;
}}

function getOrCreateCard(key, nowMs) {{
  if (!STATE.cards[key]) {{
    STATE.cards[key] = createEmptyCard(nowMs);
  }}
  return STATE.cards[key];
}}

function maybeAutoUpdateCards(exId) {{
  const nowMs = virtualNowMs();
  for (const kp of KP_META) {{
    if (kp.problemIds.includes(exId)) {{
      const states = kp.problemIds.map(pid => getExState(pid));
      if (states.every(st => st.correct !== null)) {{
        const key = `kp:${{kp.id}}`;
        const card = getOrCreateCard(key, nowMs);
        if (card.state === "new" || card.reps === 0) {{
          const items = kp.problemIds.map(pid => {{
            const s = getExState(pid);
            return {{
              correct: s.correct ? 1 : 0,
              hintsUsed: s.hintsUsed,
              attemptNo: s.attemptNo,
              durationMs: s.durationMs,
              targetSeconds: getTargetSeconds(EX_MAP[pid])
            }};
          }});
          const r = reviewActivityRating(items);
          STATE.cards[key] = scheduleReview(card, nowMs, r).card;
        }}
      }}
    }}
  }}
  const ex = EX_MAP[exId];
  if (ex && ex.role !== "recall") {{
    const dimIds = Object.values(EX_MAP).filter(e => e.dimension === ex.dimension && e.role !== "recall").map(e => e.id);
    if (dimIds.length && dimIds.every(id => getExState(id).correct !== null)) {{
      const key = `dim:${{ex.dimension}}`;
      const card = getOrCreateCard(key, nowMs);
      const items = dimIds.map(id => {{
        const s = getExState(id);
        return {{
          correct: s.correct ? 1 : 0,
          hintsUsed: s.hintsUsed,
          attemptNo: s.attemptNo,
          durationMs: s.durationMs,
          targetSeconds: getTargetSeconds(EX_MAP[id])
        }};
      }});
      const r = reviewActivityRating(items);
      if (card.state === "new" || card.reps === 0) {{
        STATE.cards[key] = scheduleReview(card, nowMs, r).card;
      }}
    }}
  }}
}}

// ============================================================================
// UI Formatting & Dashboard Rendering
// ============================================================================
function fmtDateTime(ms) {{
  const d = new Date(ms);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${{d.getFullYear()}}-${{mm}}-${{dd}} ${{hh}}:${{mi}}`;
}}

function fmtRelativeDue(dueMs, nowMs) {{
  const dayDiff = Math.round((startOfLocalCalendarDayMs(dueMs) - startOfLocalCalendarDayMs(nowMs)) / MS_PER_DAY);
  if (dayDiff < 0) return `已逾期 ${{-dayDiff}} 天`;
  if (dayDiff === 0) return "今天到期";
  return `${{dayDiff}} 天后`;
}}

function renderDashboard() {{
  const nowMs = virtualNowMs();
  const autoAll = Object.values(EX_MAP).filter(e => e.type !== "explain");
  const explainAll = Object.values(EX_MAP).filter(e => e.type === "explain");
  const autoOk = autoAll.filter(e => getExState(e.id).correct === true).length;
  const explainOk = explainAll.filter(e => getExState(e.id).correct !== null).length;
  const totalSec = Math.round(Object.values(STATE.exercises).reduce((acc, s) => acc + (s.durationMs || 0), 0) / 1000);

  document.getElementById("score-readout").textContent = `Unit 1：自动判题 ${{autoOk}} / ${{autoAll.length}} · 自评 ${{explainOk}} / ${{explainAll.length}}`;
  document.getElementById("time-readout").textContent = `累计作答 ${{totalSec}}s`;

  const curLesson = LESSONS_META.find(l => l.id === STATE.activeLesson) || LESSONS_META[0];
  const curDone = curLesson.exerciseIds.filter(id => getExState(id).correct !== null).length;
  document.getElementById("lesson-readout").textContent = `第 ${{curLesson.index}} 课：${{curDone}} / ${{curLesson.exerciseIds.length}}`;

  for (const lm of LESSONS_META) {{
    const el = document.querySelector(`[data-lesson-prog="${{lm.id}}"]`);
    if (el) {{
      const done = lm.exerciseIds.filter(id => getExState(id).correct !== null).length;
      el.textContent = `已做 ${{done}} / ${{lm.exerciseIds.length}}`;
    }}
  }}

  const offDays = Math.round((STATE.simOffsetMs || 0) / MS_PER_DAY);
  document.getElementById("sim-clock-readout").textContent =
    offDays === 0 ? `当前参考时间：真实时间（${{fmtDateTime(nowMs)}}）` : `虚拟快进 +${{offDays}} 天（${{fmtDateTime(nowMs)}}）`;

  const specs = cardSpecs();
  let dueTodayCount = 0;
  const forecastBuckets = [0, 0, 0, 0, 0, 0, 0, 0];
  const todayDayStart = startOfLocalCalendarDayMs(nowMs);

  const rowsHtml = specs.map(sp => {{
    const card = STATE.cards[sp.key] || createEmptyCard(nowMs);
    const isNew = card.state === "new" || card.reps === 0;
    const due = !isNew && isDueToday(card, nowMs);
    if (due) dueTodayCount += 1;

    if (!isNew) {{
      const bucket = Math.floor((startOfLocalCalendarDayMs(card.dueMs) - todayDayStart) / MS_PER_DAY);
      if (bucket <= 0) forecastBuckets[0] += 1;
      else if (bucket >= 1 && bucket <= 7) forecastBuckets[bucket] += 1;
    }}

    const statusBadge = isNew
      ? `<span class="pill pill-new">未建卡</span>`
      : (due ? `<span class="pill pill-due">到期待复习</span>` : (card.lastRating === "hard" ? `<span class="pill pill-hard">已排程 (Hard)</span>` : `<span class="pill pill-ok">已排程 (Good)</span>`));

    const retPct = isNew ? "—" : `${{(cardRetrievability(card, nowMs) * 100).toFixed(1)}}%`;
    const sdTxt = isNew ? "—" : `S=${{card.stability.toFixed(2)}}d · D=${{card.difficulty.toFixed(2)}}`;
    const dueTxt = isNew ? `完成对应练习后建卡<br/><span class="meta">${{sp.progressTxt}}</span>` : `${{fmtDateTime(card.dueMs)}}<br/><span class="meta">${{fmtRelativeDue(card.dueMs, nowMs)}} · 第 ${{card.reps}} 轮</span>`;

    const pAgain = scheduleReview(card, nowMs, "again");
    const pHard = scheduleReview(card, nowMs, "hard");
    const pGood = scheduleReview(card, nowMs, "good");
    const previewTxt = `Again ${{pAgain.intervalDays}}d / Hard ${{pHard.intervalDays}}d / Good ${{pGood.intervalDays}}d`;

    const actionBtn = sp.kind === "kp"
      ? `<button type="button" class="btn btn-open-recall" data-kp="${{sp.kpId}}" data-lesson="${{sp.lessonId}}">打开 Recall</button>`
      : `<span class="meta">${{sp.progressTxt}}</span>`;

    return `<tr><td><strong>${{sp.label}}</strong></td><td>${{statusBadge}}</td><td>${{sdTxt}}</td><td>${{retPct}}</td><td>${{dueTxt}}</td><td><code>${{previewTxt}}</code></td><td>${{actionBtn}}</td></tr>`;
  }}).join("");

  document.getElementById("fsrs-tbody").innerHTML = rowsHtml;
  document.getElementById("due-readout").textContent = `今日到期卡片：${{dueTodayCount}} / ${{specs.length}}`;

  document.getElementById("forecast-strip").innerHTML = forecastBuckets.map((cnt, dIdx) => {{
    const dayLabel = dIdx === 0 ? "今天(含逾期)" : `+${{dIdx}} 天`;
    const dateStr = fmtDateTime(nowMs + dIdx * MS_PER_DAY).slice(5, 10);
    return `<div class="fc-cell ${{cnt > 0 && dIdx === 0 ? "due" : ""}}"><div>${{dayLabel}} (${{dateStr}})</div><div class="fc-cnt">${{cnt}}</div></div>`;
  }}).join("");

  document.querySelectorAll(".btn-open-recall").forEach(btn => {{
    btn.addEventListener("click", () => {{
      if (btn.dataset.lesson) switchLesson(btn.dataset.lesson, false);
      const box = document.getElementById(`recalls-${{btn.dataset.kp}}`);
      if (box) {{
        box.open = true;
        box.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }});
  }});
}}

// ============================================================================
// Exercise Interaction, Math Expression Evaluator, Timing & Persistence
// ============================================================================
function normalizeMathExpr(expr) {{
  return String(expr)
    .replace(/[−–]/g, "-")
    .replace(/\\^/g, "**")
    .replace(/\\band\\b/g, "&&")
    .replace(/\\bor\\b/g, "||")
    .replace(/\\bnot\\s+/g, "!");
}}

function evalExpr(expr, env) {{
  const mathBuiltins = {{
    sqrt: Math.sqrt,
    abs: Math.abs,
    sin: Math.sin,
    cos: Math.cos,
    tan: Math.tan,
    exp: Math.exp,
    log: Math.log,
    pow: Math.pow,
    min: Math.min,
    max: Math.max,
    pi: Math.PI,
    PI: Math.PI
  }};
  const scope = Object.assign({{}}, mathBuiltins, env || {{}});
  const names = Object.keys(scope);
  const vals = names.map(k => scope[k]);
  const jsExpr = normalizeMathExpr(expr);
  return Function(...names, "Math", `return (${{jsExpr}});`)(...vals, Math);
}}

function pickParams(ex) {{
  if (!ex.params) return {{}};
  const keys = Object.keys(ex.params);
  for (let tries = 0; tries < 120; tries++) {{
    const env = {{}};
    for (const k of keys) {{
      const s = ex.params[k];
      const step = s.step || 1;
      const count = Math.floor((s.max - s.min + 1e-9) / step) + 1;
      const idx = Math.floor(Math.random() * count);
      env[k] = Number((s.min + idx * step).toFixed(9));
    }}
    try {{
      const ok = (ex.constraints || []).every(c => Boolean(evalExpr(c, env)));
      if (ok) return env;
    }} catch (e) {{}}
  }}
  return Object.fromEntries(keys.map(k => [k, ex.params[k].min]));
}}

function getNumericAnswer(ex, env) {{
  if (ex.answer !== undefined && ex.answer !== null) return Number(ex.answer);
  return evalExpr(ex.answer_expr, env);
}}

function fillTemplate(str, env) {{
  if (!str) return "";
  return str.replace(/\\{{\\{{=([^}}]+)\\}}\\}}/g, (_, inner) => {{
    const v = evalExpr(inner.trim(), env);
    return Number.isInteger(v) ? String(v) : String(Number(v.toFixed(6)));
  }});
}}

function escHtml(s) {{
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}

window.__renderAllMath = function(root) {{
  if (typeof renderMathInElement === "function") {{
    renderMathInElement(root || document.body, {{
      delimiters: [{{left:"$$", right:"$$", display:true}}, {{left:"$", right:"$", display:false}}]
    }});
  }}
}};

function updateSlotHeader(slot, id) {{
  const ex = EX_MAP[id];
  const st = getExState(id);
  const targetSec = getTargetSeconds(ex);
  let liveMs = st.durationMs || 0;
  if (ACTIVE_TIMERS[id]) {{
    liveMs += (Date.now() - ACTIVE_TIMERS[id]);
  }}
  const sec = Math.round(liveMs / 1000);
  const tEl = slot.querySelector("[data-timer]");
  const rEl = slot.querySelector("[data-rating]");
  if (tEl) tEl.textContent = `计时 ${{sec}}s / 目标 ${{targetSec}}s`;
  if (rEl) {{
    rEl.className = "rating-pill";
    if (!st.rating) {{
      rEl.textContent = st.attemptNo > 0 ? `第 ${{st.attemptNo}} 次尝试` : "未作答";
    }} else if (st.rating === "good") {{
      rEl.classList.add("good");
      rEl.textContent = "评级: Good";
    }} else if (st.rating === "hard") {{
      rEl.classList.add("hard");
      rEl.textContent = "评级: Hard";
    }} else {{
      rEl.classList.add("again");
      rEl.textContent = "评级: Again";
    }}
  }}
}}

function startTimer(slot, id) {{
  const st = getExState(id);
  if (st.correct === true) return;
  if (!ACTIVE_TIMERS[id]) {{
    ACTIVE_TIMERS[id] = Date.now();
  }}
  updateSlotHeader(slot, id);
}}

function commitTimingAndGrade(slot, id, isCorrect) {{
  const ex = EX_MAP[id];
  const st = getExState(id);
  if (ACTIVE_TIMERS[id]) {{
    st.durationMs = (st.durationMs || 0) + Math.max(500, Date.now() - ACTIVE_TIMERS[id]);
    delete ACTIVE_TIMERS[id];
  }} else if ((st.durationMs || 0) === 0) {{
    st.durationMs = 1000;
  }}
  st.attemptNo = (st.attemptNo || 0) + 1;
  st.correct = isCorrect;
  st.lastAnsweredAt = virtualNowMs();
  const targetSeconds = getTargetSeconds(ex);
  st.rating = mapReviewRating({{
    correct: isCorrect ? 1 : 0,
    hintsUsed: st.hintsUsed || 0,
    attemptNo: st.attemptNo,
    durationMs: st.durationMs,
    targetSeconds
  }});
  maybeAutoUpdateCards(id);
  saveState();
  updateSlotHeader(slot, id);
  renderDashboard();
  return {{
    targetSeconds,
    slow: st.durationMs > targetSeconds * 1000,
    rating: st.rating
  }};
}}

function renderDowngradeNote(meta, st) {{
  if (!st.correct) return "";
  const reasons = [];
  if (st.hintsUsed > 0) reasons.push(`使用了提示 (${{st.hintsUsed}} 次)`);
  if (st.attemptNo > 1) reasons.push(`非首次作答 (第 ${{st.attemptNo}} 次)`);
  if (meta.slow) reasons.push(`作答超过目标耗时 (${{Math.round(st.durationMs/1000)}}s &gt; ${{meta.targetSeconds}}s)`);
  if (reasons.length === 0) return ` · <span style="color:#166534;">[首遍独立快速通过 → Good]</span>`;
  return ` · <span style="color:#92400e;">[因 ${{reasons.join("、")}} → 记为 Hard]</span>`;
}}

function renderSlot(slot) {{
  const id = slot.dataset.exId;
  const ex = EX_MAP[id];
  const st = getExState(id);
  const body = slot.querySelector(".prob-body");

  if (ex.params && !st.env) {{
    st.env = pickParams(ex);
    saveState();
  }}

  slot.addEventListener("pointerenter", () => startTimer(slot, id));
  slot.addEventListener("focusin", () => startTimer(slot, id));

  function redraw() {{
    const env = st.env || {{}};
    const promptTxt = fillTemplate(ex.prompt, env);
    const solTxt = fillTemplate(ex.solution || "", env);
    let html = `<p>${{escHtml(promptTxt)}}</p>`;

    if (ex.type === "mc") {{
      html += `<div class="opts-grid">` + ex.options.map(o => {{
        let cls = "opt-btn";
        if (st.pickedOpt === o.id) cls += o.correct ? " picked-ok" : " picked-bad";
        return `<button type="button" class="${{cls}}" data-opt="${{o.id}}"><strong>${{o.id.toUpperCase()}}.</strong> ${{escHtml(o.text)}}</button>`;
      }}).join("") + `</div>`;
      html += `<div class="input-row"><button type="button" class="btn btn-sol">查看解析</button></div>`;
      html += `<div class="fb"></div>`;
    }} else if (ex.type === "numeric") {{
      html += `<div class="input-row">`;
      html += `<input type="number" step="any" class="txt-in" value="${{escHtml(st.textVal || "")}}" placeholder="输入数值结果..." />`;
      html += `<button type="button" class="btn btn-primary btn-check">提交检查</button>`;
      if (ex.params) html += `<button type="button" class="btn btn-reroll">换一组参数</button>`;
      if (ex.hints && ex.hints.length) html += `<button type="button" class="btn btn-hint">提示 (${{st.hintsUsed}}/${{ex.hints.length}})</button>`;
      html += `<button type="button" class="btn btn-sol">查看解答</button>`;
      html += `</div><div class="hint-box"></div><div class="fb"></div>`;
    }} else if (ex.type === "text" || ex.type === "expression") {{
      const vnames = Object.keys(ex.variables || {{}});
      const ph = ex.type === "expression" ? `输入表达式（可用变量: ${{vnames.join(", ")}}）` : "键入表达式或公式...";
      html += `<div class="input-row">`;
      html += `<input type="text" class="txt-in" value="${{escHtml(st.textVal || "")}}" placeholder="${{escHtml(ph)}}" />`;
      html += `<button type="button" class="btn btn-primary btn-check">提交检查</button>`;
      html += `<button type="button" class="btn btn-sol">查看解答</button>`;
      html += `</div><div class="fb"></div>`;
    }} else if (ex.type === "explain") {{
      html += `<textarea class="explain-in" placeholder="先试着用自己的话作答（会自动保存到 localStorage），再展开评分标准核对...">${{escHtml(st.explainVal || "")}}</textarea>`;
      html += `<div class="input-row"><button type="button" class="btn btn-primary btn-sol">展开评分标准与参考范例</button></div>`;
      html += `<div class="fb"></div>`;
    }}

    body.innerHTML = html;
    const fb = body.querySelector(".fb");

    function showExplainRubric(autoNote) {{
      const rub = (ex.rubric || []).map((r, rIdx) => {{
        const checked = (st.rubricChecked || []).includes(rIdx) ? "checked" : "";
        return `<li><label><input type="checkbox" class="rubric-chk" data-ridx="${{rIdx}}" ${{checked}} /> <strong>${{r.required ? "[必答]" : "[加分]"}}</strong> ${{escHtml(r.criterion)}}</label></li>`;
      }}).join("");
      fb.className = "fb info";
      fb.innerHTML = `<strong>自评要点清单：</strong><ul class="rubric-list">${{rub}}</ul>`
        + `<div class="input-row" style="margin:6px 0 8px;">`
        + `<button type="button" class="btn btn-primary btn-self-eval">按当前勾选提交自评</button>`
        + `<span>${{autoNote || ""}}</span></div>`
        + `<strong>参考范例：</strong>${{escHtml(ex.exemplar || "")}}`;
      fb.querySelectorAll(".rubric-chk").forEach(chk => {{
        chk.addEventListener("change", () => {{
          const rIdx = Number(chk.dataset.ridx);
          const set = new Set(st.rubricChecked || []);
          if (chk.checked) set.add(rIdx); else set.delete(rIdx);
          st.rubricChecked = Array.from(set);
          saveState();
        }});
      }});
      fb.querySelector(".btn-self-eval").addEventListener("click", () => {{
        startTimer(slot, id);
        const reqIdxs = (ex.rubric || []).map((r, i) => (r.required ? i : -1)).filter(i => i >= 0);
        const set = new Set(st.rubricChecked || []);
        const passed = reqIdxs.every(i => set.has(i));
        const meta = commitTimingAndGrade(slot, id, passed);
        showExplainRubric(passed ? `已记为通过 (${{meta.rating}})` : `必答要点尚缺，已记为 Again 需再复习`);
      }});
      window.__renderAllMath(fb);
    }}

    if (ex.type === "mc") {{
      if (st.pickedOpt) {{
        const opt = ex.options.find(o => o.id === st.pickedOpt);
        if (opt) {{
          fb.className = "fb " + (opt.correct ? "ok" : "bad");
          fb.innerHTML = `<strong>${{opt.correct ? "正确：" : "再想想："}}</strong>${{escHtml(opt.feedback || "")}}`;
        }}
      }}
      body.querySelectorAll(".opt-btn").forEach(btn => {{
        btn.addEventListener("click", () => {{
          startTimer(slot, id);
          const opt = ex.options.find(o => o.id === btn.dataset.opt);
          st.pickedOpt = opt.id;
          const meta = commitTimingAndGrade(slot, id, Boolean(opt.correct));
          body.querySelectorAll(".opt-btn").forEach(b => b.classList.remove("picked-ok", "picked-bad"));
          btn.classList.add(opt.correct ? "picked-ok" : "picked-bad");
          fb.className = "fb " + (opt.correct ? "ok" : "bad");
          fb.innerHTML = `<strong>${{opt.correct ? "正确：" : "再想想："}}</strong>${{escHtml(opt.feedback || "")}}${{renderDowngradeNote(meta, st)}}`;
          window.__renderAllMath(fb);
        }});
      }});
      body.querySelector(".btn-sol").addEventListener("click", () => {{
        fb.className = "fb info";
        fb.innerHTML = `<strong>完整解答：</strong>${{escHtml(solTxt)}}`;
        window.__renderAllMath(fb);
      }});
    }} else if (ex.type === "numeric") {{
      const txtIn = body.querySelector(".txt-in");
      txtIn.addEventListener("input", () => {{ st.textVal = txtIn.value; saveState(); }});
      const hintBox = body.querySelector(".hint-box");
      const btnHint = body.querySelector(".btn-hint");
      if (st.hintsUsed > 0 && hintBox) {{
        hintBox.style.display = "block";
        hintBox.innerHTML = ex.hints.slice(0, st.hintsUsed).map((h, i) => `提示 ${{i+1}}：${{escHtml(fillTemplate(h, env))}}`).join("<br/>");
        window.__renderAllMath(hintBox);
      }}
      if (st.correct !== null) {{
        const ans = getNumericAnswer(ex, env);
        fb.className = "fb " + (st.correct ? "ok" : "bad");
        fb.innerHTML = st.correct ? `<strong>上次已答对：</strong>${{escHtml(solTxt)}}` : `<strong>上次答错：</strong>可修改后重提交或查看提示（参考值约 ${{Number(ans.toFixed(4))}}）。`;
      }}
      if (btnHint) {{
        btnHint.addEventListener("click", () => {{
          startTimer(slot, id);
          st.hintsUsed = Math.min(ex.hints.length, (st.hintsUsed || 0) + 1);
          saveState();
          btnHint.textContent = `提示 (${{st.hintsUsed}}/${{ex.hints.length}})`;
          hintBox.style.display = "block";
          hintBox.innerHTML = ex.hints.slice(0, st.hintsUsed).map((h, i) => `提示 ${{i+1}}：${{escHtml(fillTemplate(h, env))}}`).join("<br/>");
          window.__renderAllMath(hintBox);
        }});
      }}
      if (ex.params) {{
        body.querySelector(".btn-reroll").addEventListener("click", () => {{
          st.env = pickParams(ex);
          st.textVal = "";
          st.correct = null;
          st.attemptNo = 0;
          st.hintsUsed = 0;
          st.durationMs = 0;
          st.rating = null;
          delete ACTIVE_TIMERS[id];
          saveState();
          redraw();
          updateSlotHeader(slot, id);
          renderDashboard();
        }});
      }}
      body.querySelector(".btn-check").addEventListener("click", () => {{
        startTimer(slot, id);
        st.textVal = txtIn.value;
        const val = parseFloat(txtIn.value);
        if (Number.isNaN(val)) {{
          fb.className = "fb bad";
          fb.textContent = "请先输入一个有效数字。";
          return;
        }}
        const ans = getNumericAnswer(ex, env);
        const absTol = (ex.tolerance && ex.tolerance.abs) || 1e-6;
        const ok = Math.abs(val - ans) <= absTol;
        const meta = commitTimingAndGrade(slot, id, ok);
        if (ok) {{
          fb.className = "fb ok";
          fb.innerHTML = `<strong>正确！</strong> ${{escHtml(solTxt)}}${{renderDowngradeNote(meta, st)}}`;
        }} else {{
          const hitWrong = (ex.common_wrong || []).find(w => {{
            const wAns = w.answer !== undefined && w.answer !== null ? Number(w.answer) : evalExpr(w.answer_expr, env);
            return Math.abs(val - wAns) <= ((w.tolerance && w.tolerance.abs) || absTol);
          }});
          fb.className = "fb bad";
          fb.innerHTML = hitWrong ? `<strong>常见误区：</strong>${{escHtml(fillTemplate(hitWrong.feedback, env))}}` : `<strong>结果不匹配：</strong>建议点「提示」再试一次（答案约 ${{Number(ans.toFixed(4))}}）。`;
        }}
        window.__renderAllMath(fb);
      }});
      body.querySelector(".btn-sol").addEventListener("click", () => {{
        fb.className = "fb info";
        fb.innerHTML = `<strong>解析：</strong>${{escHtml(solTxt)}}`;
        window.__renderAllMath(fb);
      }});
    }} else if (ex.type === "expression" || ex.type === "text") {{
      const txtIn = body.querySelector(".txt-in");
      txtIn.addEventListener("input", () => {{ st.textVal = txtIn.value; saveState(); }});
      if (st.correct !== null) {{
        fb.className = "fb " + (st.correct ? "ok" : "bad");
        fb.innerHTML = st.correct ? `<strong>上次已答对：</strong>${{escHtml(solTxt)}}` : `<strong>上次未匹配：</strong>请调整后重新提交。`;
      }}
      body.querySelector(".btn-check").addEventListener("click", () => {{
        startTimer(slot, id);
        const raw = txtIn.value.trim();
        st.textVal = raw;
        if (!raw) return;
        let ok = false;
        if (ex.type === "expression") {{
          ok = true;
          const vnames = Object.keys(ex.variables || {{}});
          for (let i = 0; i < 5; i++) {{
            const testEnv = {{}};
            for (const vn of vnames) {{
              const [lo, hi] = ex.variables[vn];
              testEnv[vn] = lo + Math.random() * (hi - lo);
            }}
            try {{
              const uv = evalExpr(raw, testEnv);
              const av = evalExpr(ex.answer, testEnv);
              if (!Number.isFinite(uv) || Math.abs(uv - av) > 1e-6) {{ ok = false; break; }}
            }} catch (e) {{ ok = false; break; }}
          }}
        }} else {{
          const rx = ex.regex ? new RegExp(ex.regex) : null;
          ok = (ex.accept || []).includes(raw) || (rx ? rx.test(raw) : false);
        }}
        const meta = commitTimingAndGrade(slot, id, ok);
        fb.className = "fb " + (ok ? "ok" : "bad");
        fb.innerHTML = ok
          ? `<strong>正确！</strong> ${{escHtml(solTxt)}}${{renderDowngradeNote(meta, st)}}`
          : (ex.type === "expression" ? `<strong>未通过数值比对：</strong>请检查表达式变量（可用: ${{Object.keys(ex.variables || {{}}).join(", ")}}）与运算符。` : `<strong>暂未匹配：</strong>可参考格式 <code>${{escHtml((ex.accept || [""])[0])}}</code>。`);
        window.__renderAllMath(fb);
      }});
      body.querySelector(".btn-sol").addEventListener("click", () => {{
        fb.className = "fb info";
        const ansShow = ex.type === "expression" ? ex.answer : ((ex.accept || [""])[0]);
        fb.innerHTML = `<strong>标准参考：</strong><code>${{escHtml(ansShow)}}</code> · ${{escHtml(solTxt)}}`;
        window.__renderAllMath(fb);
      }});
    }} else if (ex.type === "explain") {{
      const ta = body.querySelector(".explain-in");
      ta.addEventListener("input", () => {{ st.explainVal = ta.value; saveState(); }});
      if (st.correct !== null || (st.rubricChecked && st.rubricChecked.length)) {{
        showExplainRubric(st.correct === true ? "已记录自评通过" : (st.correct === false ? "已记录需再巩固" : ""));
      }}
      body.querySelector(".btn-sol").addEventListener("click", () => showExplainRubric(""));
    }}

    updateSlotHeader(slot, id);
    window.__renderAllMath(body);
  }}

  redraw();
}}

// Lesson navigation bindings
document.querySelectorAll("[data-lesson-tab]").forEach(btn => {{
  btn.addEventListener("click", () => switchLesson(btn.dataset.lessonTab, true));
}});
document.querySelectorAll("[data-jump-lesson]").forEach(btn => {{
  btn.addEventListener("click", () => switchLesson(btn.dataset.jumpLesson, true));
}});

// Live 1s timer tick for currently active exercises
setInterval(() => {{
  for (const id of Object.keys(ACTIVE_TIMERS)) {{
    const slot = document.querySelector(`.prob[data-ex-id="${{id}}"]`);
    if (slot) updateSlotHeader(slot, id);
  }}
}}, 1000);

// Recall batch commit buttons
document.querySelectorAll(".btn-commit-recall").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const kpId = btn.dataset.kp;
    const kp = KP_META.find(k => k.id === kpId);
    if (!kp) return;
    const statusEl = document.querySelector(`[data-kp-recall-status="${{kpId}}"]`);
    const missing = kp.recallIds.filter(rid => getExState(rid).correct === null);
    if (missing.length > 0) {{
      statusEl.textContent = `请先完成本步全部 3 道 Recall 题（还差 ${{missing.join("、")}}，第 1 题请展开评分清单并点「按当前勾选提交自评」）。`;
      return;
    }}
    const nowMs = virtualNowMs();
    const items = kp.recallIds.map(rid => {{
      const s = getExState(rid);
      return {{
        correct: s.correct ? 1 : 0,
        hintsUsed: s.hintsUsed,
        attemptNo: s.attemptNo,
        durationMs: s.durationMs,
        targetSeconds: getTargetSeconds(EX_MAP[rid])
      }};
    }});
    const batchRating = reviewActivityRating(items);
    const key = `kp:${{kpId}}`;
    const res = scheduleReview(getOrCreateCard(key, nowMs), nowMs, batchRating);
    STATE.cards[key] = res.card;
    saveState();
    renderDashboard();
    statusEl.textContent = `已完成第 ${{res.card.reps}} 轮 Recall（评级 ${{batchRating.toUpperCase()}}）→ 下次复习间隔 ${{res.intervalDays}} 天（${{fmtDateTime(res.card.dueMs)}}）。`;
  }});
}});

// Time-travel & persistence controls
document.querySelectorAll("[data-shift-days]").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const days = Number(btn.dataset.shiftDays);
    STATE.simOffsetMs = (STATE.simOffsetMs || 0) + days * MS_PER_DAY;
    saveState();
    renderDashboard();
  }});
}});

document.getElementById("btn-fast-forward-due").addEventListener("click", () => {{
  const nowMs = virtualNowMs();
  const nextCutoff = startOfNextCalendarDayMs(nowMs);
  const futureCards = Object.values(STATE.cards || {{}}).filter(c => c && c.state !== "new" && c.reps > 0 && c.dueMs >= nextCutoff);
  if (!futureCards.length) {{
    alert("当前尚无未到期的已排程卡片；请先完成某一课步并生成复习卡，或直接点击时间快进。");
    return;
  }}
  const earliestDue = Math.min(...futureCards.map(c => c.dueMs));
  const deltaDays = Math.max(1, Math.ceil((earliestDue - nextCutoff + 1) / MS_PER_DAY));
  STATE.simOffsetMs = (STATE.simOffsetMs || 0) + deltaDays * MS_PER_DAY;
  saveState();
  renderDashboard();
}});

document.getElementById("btn-clock-reset").addEventListener("click", () => {{
  STATE.simOffsetMs = 0;
  saveState();
  renderDashboard();
}});

document.getElementById("btn-export-json").addEventListener("click", () => {{
  const blob = new Blob([JSON.stringify(STATE, null, 2)], {{ type: "application/json" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `open-academy-mr-progress-${{new Date().toISOString().slice(0,10)}}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}});

document.getElementById("btn-import-json").addEventListener("click", () => {{
  document.getElementById("import-file-input").click();
}});

document.getElementById("import-file-input").addEventListener("change", ev => {{
  const f = ev.target.files && ev.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {{
    try {{
      const parsed = JSON.parse(String(reader.result));
      STATE = Object.assign(makeDefaultState(), parsed);
      saveState();
      location.reload();
    }} catch (err) {{
      alert("JSON 格式无效：" + err.message);
    }}
  }};
  reader.readAsText(f, "utf-8");
}});

document.getElementById("btn-reset-all").addEventListener("click", () => {{
  if (!confirm("确定要清空当前浏览器里的全部做题进度、计时记录与 FSRS 复习排程吗？")) return;
  localStorage.removeItem(STORAGE_KEY);
  STATE = makeDefaultState();
  location.reload();
}});

document.querySelectorAll(".prob").forEach(renderSlot);
switchLesson(STATE.activeLesson || DEFAULT_LESSON_ID, false);
</script>
</body>
</html>"""
    return "\n".join(line.rstrip() for line in page.splitlines()) + "\n"


def render(pack_dir: Path) -> list[Path]:
    out_dir = pack_dir / "preview"
    out_dir.mkdir(exist_ok=True)
    targets = [
        (out_dir / "index.html", "spin-zeeman-and-drive"),
        (out_dir / "rotating-wave-and-frame.html", "rotating-wave-and-frame"),
    ]
    written: list[Path] = []
    for path, default_cid in targets:
        clean_page = build_html(pack_dir, default_concept=default_cid)
        path.write_text(clean_page, encoding="utf-8", newline="\n")
        written.append(path)
        print("Generated interactive HTML preview:", path)
    return written


if __name__ == "__main__":
    pack = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    render(pack)
