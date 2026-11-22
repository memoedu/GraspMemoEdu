#!/usr/bin/env python3
"""Programmatically compute exact coordinates for SVGs in rotating-wave-and-frame."""

from __future__ import annotations

import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from academy_check import validate_svg_block


def pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return round(cx + r * math.cos(rad), 2), round(cy - r * math.sin(rad), 2)


def arc_path(cx: float, cy: float, r: float, deg_start: float, deg_end: float, sweep_cw: bool) -> str:
    x1, y1 = pt(cx, cy, r, deg_start)
    x2, y2 = pt(cx, cy, r, deg_end)
    large_arc = 1 if abs(deg_end - deg_start) > 180 else 0
    sweep_flag = 1 if sweep_cw else 0
    return f"M{x1} {y1} A{r} {r} 0 {large_arc} {sweep_flag} {x2} {y2}"


def build_svg_rwa_split() -> str:
    # Panel 1 (left): Two-level diagram (x=115..220)
    # Panel 2 (right): x-y plane decomposition at alpha = 38 deg
    cx, cy = 425.0, 165.0
    r = 82.0
    alpha = 38.0
    x_plus, y_plus = pt(cx, cy, r, alpha)
    x_minus, y_minus = pt(cx, cy, r, -alpha)
    x_sum = round(cx + 2 * r * math.cos(math.radians(alpha)), 2)

    # Curved rotation arrows
    ccw_arc = arc_path(cx, cy, r + 15, alpha - 10, alpha + 34, sweep_cw=False)
    cw_arc = arc_path(cx, cy, r + 15, -(alpha - 10), -(alpha + 34), sweep_cw=True)
    alpha_arc = arc_path(cx, cy, 28, 0, alpha, sweep_cw=False)
    ax_lbl, ay_lbl = pt(cx, cy, 42, alpha / 2)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="左图为自旋二分之一的两能级示意图，下能级 m_S 等于负二分之一与上能级 m_S 等于正二分之一之间的能级差为 omega_0，向上跃迁角动量变化为 +1；右图为 x-y 平面驱动场分解图，沿 x 轴的线偏振驱动场拆成幅度均为 Omega 的逆时针蓝色分量（角动量 +1，保留）与顺时针红色分量①（角动量 -1，被旋波近似舍去）。">
<defs>
<marker id="rwa1-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="rwa1-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
<marker id="rwa1-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
<marker id="rwa1-green" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#10b981"/></marker>
<marker id="rwa1-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<line x1="278" y1="22" x2="278" y2="278" stroke="#d4d4d4" stroke-width="1"/>
<text x="145" y="28" text-anchor="middle" font-size="14" font-weight="600">静态能级 (H₀ = ω₀ S_z)</text>
<line x1="115" y1="78" x2="225" y2="78" stroke="#171717" stroke-width="2.5"/>
<line x1="115" y1="222" x2="225" y2="222" stroke="#171717" stroke-width="2.5"/>
<text x="106" y="83" text-anchor="end">|m_S = +1/2⟩</text>
<text x="106" y="227" text-anchor="end">|m_S = -1/2⟩</text>
<line x1="168" y1="216" x2="168" y2="85" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#rwa1-amber)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="176" y="143" fill="#f59e0b">Δm_S = +1</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="176" y="162" fill="#f59e0b">能隙 ω₀</text>
<text x="455" y="28" text-anchor="middle" font-size="14" font-weight="600">x-y 平面圆偏振分解 (+z 朝外)</text>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.5" stroke-dasharray="4 4"/>
<line x1="{cx - r - 20}" y1="{cy}" x2="{x_sum + 38}" y2="{cy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#rwa1-dark)"/>
<line x1="{cx}" y1="{cy + r + 24}" x2="{cx}" y2="{cy - r - 28}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#rwa1-dark)"/>
<text x="{x_sum + 44}" y="{cy + 4}">x</text>
<text x="{cx + 7}" y="{cy - r - 24}">y</text>
<line x1="{x_plus}" y1="{y_plus}" x2="{x_plus}" y2="{y_minus}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{x_plus}" y1="{y_plus}" x2="{x_sum}" y2="{cy}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{x_minus}" y1="{y_minus}" x2="{x_sum}" y2="{cy}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{cx}" y1="{cy}" x2="{x_sum}" y2="{cy}" stroke="#10b981" stroke-width="2.5" marker-end="url(#rwa1-green)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_sum - 4}" y="{cy + 20}" text-anchor="middle" fill="#10b981">合矢量 2Ω cos(ωt+φ)</text>
<line x1="{cx}" y1="{cy}" x2="{x_plus}" y2="{y_plus}" stroke="#3b82f6" stroke-width="3" marker-end="url(#rwa1-blue)"/>
<line x1="{cx}" y1="{cy}" x2="{x_minus}" y2="{y_minus}" stroke="#ef4444" stroke-width="3" marker-end="url(#rwa1-red)"/>
<path d="{ccw_arc}" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="2" marker-end="url(#rwa1-blue)"/>
<path d="{cw_arc}" fill="#ffffff" fill-opacity="0" stroke="#ef4444" stroke-width="2" marker-end="url(#rwa1-red)"/>
<path d="{alpha_arc}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{ax_lbl + 12}" y="{ay_lbl + 4}" fill="#737373">ωt+φ</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_plus + 8}" y="{y_plus - 14}" fill="#3b82f6">逆时针 (+1 保留)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_plus + 8}" y="{y_plus + 2}" fill="#3b82f6">幅值 Ω</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_minus + 8}" y="{y_minus + 14}" fill="#ef4444">顺时针 (-1 忽略①)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_minus + 8}" y="{y_minus + 30}" fill="#ef4444">幅值 Ω</text>
</g>
</svg>'''
    return svg


def build_svg_rotating_frame() -> str:
    # Reconstruct lecture note p.3 vector rotation diagram cleanly
    cx, cy = 195.0, 240.0
    r = 165.0
    phi = 25.0
    wt = 42.0
    alpha = phi + wt

    xr, yr = pt(cx, cy, r, alpha)
    xrp, yrp = pt(cx, cy, r, phi)

    phi_arc = arc_path(cx, cy, 52, 0, phi, sweep_cw=False)
    wt_arc = arc_path(cx, cy, 112, alpha, phi, sweep_cw=True)
    phi_lbl_x, phi_lbl_y = pt(cx, cy, 68, phi / 2)
    wt_lbl_x, wt_lbl_y = pt(cx, cy, 128, phi + wt / 2)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="x-y 平面内三维旋转公式示意图：实验室坐标系中随时间转到角度 omega t 加 phi 的黑色矢量 r，沿橙色箭头绕 z 轴负方向（即顺时针）转动角度 omega t 后，回到固定角度 phi 的蓝色矢量 r'，坐标为 (cos phi, sin phi, 0)，从而消除时间变量 t。">
<defs>
<marker id="rwa2-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="rwa2-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="rwa2-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<path d="{arc_path(cx, cy, r, 0, 88, sweep_cw=False)}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.5" stroke-dasharray="4 4"/>
<line x1="{cx - 25}" y1="{cy}" x2="{cx + r + 48}" y2="{cy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#rwa2-dark)"/>
<line x1="{cx}" y1="{cy + 25}" x2="{cx}" y2="{cy - r - 28}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#rwa2-dark)"/>
<text x="{cx + r + 54}" y="{cy + 4}">x</text>
<text x="{cx + 8}" y="{cy - r - 24}">y</text>
<text x="{cx - 14}" y="{cy + 16}" fill="#737373">O</text>
<path d="{phi_arc}" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="2"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{phi_lbl_x}" y="{phi_lbl_y + 4}" fill="#10b981">φ</text>
<path d="{wt_arc}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#rwa2-amber)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{wt_lbl_x}" y="{wt_lbl_y + 4}" fill="#f59e0b">顺时针转 ωt</text>
<line x1="{cx}" y1="{cy}" x2="{xr}" y2="{yr}" stroke="#171717" stroke-width="3" marker-end="url(#rwa2-dark)"/>
<line x1="{cx}" y1="{cy}" x2="{xrp}" y2="{yrp}" stroke="#3b82f6" stroke-width="3" marker-end="url(#rwa2-blue)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{xr + 8}" y="{yr - 6}" font-weight="600">r⃗ = (cos(ωt+φ), sin(ωt+φ), 0)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{xrp + 10}" y="{yrp + 4}" fill="#3b82f6" font-weight="600">r⃗' = (cos φ, sin φ, 0)</text>
<rect x="405" y="205" width="222" height="74" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<text x="417" y="227" fill="#171717" font-weight="600">变换 U_i = exp(-i ω t S_z)</text>
<text x="417" y="248" fill="#737373">转轴 n⃗ = (0, 0, -1)，转角 θ = ωt</text>
<text x="417" y="268" fill="#3b82f6">转动后与时间 t 无关</text>
</g>
</svg>'''
    return svg


if __name__ == "__main__":
    for name, fn in [("svg1_split", build_svg_rwa_split), ("svg2_frame", build_svg_rotating_frame)]:
        s = fn()
        err = validate_svg_block(s)
        print(f"{name}: validate -> {'OK' if err is None else err}")
        if err:
            raise SystemExit(1)
    out_dir = Path(__file__).resolve().parent / "_generated_svgs"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "svg1.svg").write_text(build_svg_rwa_split(), encoding="utf-8")
    (out_dir / "svg2.svg").write_text(build_svg_rotating_frame(), encoding="utf-8")
    print("Saved preview SVGs to", out_dir)
