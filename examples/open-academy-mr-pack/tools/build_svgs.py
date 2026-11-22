#!/usr/bin/env python3
"""Programmatically compute exact coordinates for all 6 SVGs across Unit 1 lessons."""

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


def build_svg_l1_zeeman() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="双体系能级对照图：左栏展示电子自旋在静磁场中的塞曼能级，因旋磁比小于零，下能级为 m_S 等于负二分之一、上能级为 m_S 等于正二分之一，能隙为 omega_0 等于负 gamma_e B_0（对质子约 658 倍，量级相差约 10 的 3 次方倍）；右栏展示质子核自旋能级，因旋磁比大于零而上下能级顺序反转。">
<defs>
<marker id="l1z-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
<marker id="l1z-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<line x1="320" y1="20" x2="320" y2="236" stroke="#d4d4d4" stroke-width="1"/>
<text x="160" y="28" text-anchor="middle" font-size="14" font-weight="600" fill="#3b82f6">电子自旋 (γ_e &lt; 0, MHz/G 量级)</text>
<line x1="40" y1="140" x2="290" y2="140" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<text x="42" y="134" font-size="11" fill="#737373">E = 0</text>
<line x1="95" y1="74" x2="225" y2="74" stroke="#3b82f6" stroke-width="3"/>
<line x1="95" y1="206" x2="225" y2="206" stroke="#3b82f6" stroke-width="3"/>
<text x="90" y="79" text-anchor="end">|m_S = +1/2⟩</text>
<text x="232" y="79" fill="#3b82f6">上态 (+ω₀/2)</text>
<text x="90" y="211" text-anchor="end">|m_S = -1/2⟩</text>
<text x="232" y="211" fill="#3b82f6">下态 (-ω₀/2)</text>
<line x1="160" y1="200" x2="160" y2="81" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#l1z-amber)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="168" y="128" fill="#f59e0b" font-weight="600">ω₀ = -γ_e B₀</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="168" y="156" fill="#737373" font-size="12">~ 2.8 MHz/G</text>
<text x="480" y="28" text-anchor="middle" font-size="14" font-weight="600" fill="#ef4444">质子核自旋 (γ_n &gt; 0, kHz/G 量级)</text>
<line x1="350" y1="140" x2="600" y2="140" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<text x="352" y="134" font-size="11" fill="#737373">E = 0</text>
<line x1="415" y1="108" x2="535" y2="108" stroke="#ef4444" stroke-width="2.5"/>
<line x1="415" y1="172" x2="535" y2="172" stroke="#ef4444" stroke-width="2.5"/>
<text x="408" y="113" text-anchor="end">|m_S = -1/2⟩</text>
<text x="542" y="113" fill="#ef4444">上态 (+γ_n B₀/2)</text>
<text x="408" y="177" text-anchor="end">|m_S = +1/2⟩</text>
<text x="542" y="177" fill="#ef4444">下态 (-γ_n B₀/2)</text>
<line x1="475" y1="166" x2="475" y2="115" stroke="#ef4444" stroke-width="2" marker-end="url(#l1z-red)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="483" y="153" fill="#737373" font-size="12">~ 4.26 kHz/G</text>
<rect x="34" y="246" width="572" height="40" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<text x="320" y="270" text-anchor="middle" font-size="12.5" fill="#171717">能级顺序判据：H₀ = -γ B₀ S_z（γ_e &lt; 0 时 |-1/2⟩ 在下；γ_n &gt; 0 时 |+1/2⟩ 在下，分裂差约 10³ 倍）</text>
</g>
</svg>'''


def build_svg_l1_drive_geom() -> str:
    ox, oy = 165.0, 200.0
    r_tilted = 140.0
    theta_b = 58.0
    tx, ty = pt(ox, oy, r_tilted, 90.0 - theta_b)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="实验室外磁场几何分解图：z 轴方向施加静磁场 B_0，倾斜角为 theta_B 的交变线圈驱动场 B_dri(t) 可分解为沿 x 轴的横向驱动分量 B_x（正比于 sin theta_B，产生横向耦合 S_x）与沿 z 轴的纵向分量 B_z（仅当 theta_B 等于 90 度时为零）；右侧展示由 -mu 点乘 B 除以 hbar 化为无量纲自旋算符哈密顿量的对应步骤。">
<defs>
<marker id="l1d-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="l1d-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="l1d-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
<marker id="l1d-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<text x="165" y="28" text-anchor="middle" font-size="14" font-weight="600">实验室静磁场与交变驱动场分解</text>
<line x1="{ox - 45}" y1="{oy}" x2="{ox + 150}" y2="{oy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#l1d-dark)"/>
<line x1="{ox}" y1="{oy + 35}" x2="{ox}" y2="{oy - 150}" stroke="#171717" stroke-width="2.5" marker-end="url(#l1d-dark)"/>
<text x="{ox + 156}" y="{oy + 4}">x</text>
<text x="{ox - 12}" y="{oy - 144}" font-weight="600">z (B₀ 方向)</text>
<line x1="{tx}" y1="{ty}" x2="{tx}" y2="{oy}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{tx}" y1="{ty}" x2="{ox}" y2="{ty}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{tx}" y2="{oy}" stroke="#3b82f6" stroke-width="3" marker-end="url(#l1d-blue)"/>
<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{ty}" stroke="#ef4444" stroke-width="2.5" marker-end="url(#l1d-red)"/>
<line x1="{ox}" y1="{oy}" x2="{tx}" y2="{ty}" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#l1d-amber)"/>
<path d="{arc_path(ox, oy, 36, 90.0 - theta_b, 90.0, sweep_cw=False)}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="180" y="156" fill="#737373">θ_B</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{tx + 8}" y="{ty - 6}" fill="#f59e0b" font-weight="600">B_dri(t) cos(ωt+φ)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="195" y="220" fill="#3b82f6" font-weight="600">横向 B_x cos(ωt+φ)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="42" y="{ty + 4}" fill="#ef4444">纵向 B_z</text>
<text x="165" y="260" text-anchor="middle" font-size="12" fill="#737373">垂直布置 θ_B = 90° 时 B_z = 0（θ_B ≠ 90° 时另作边带处理）</text>
<rect x="355" y="48" width="265" height="218" rx="8" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.4"/>
<text x="372" y="76" font-weight="600" fill="#171717">除以 ℏ 后的标准驱动形式</text>
<text x="372" y="102" fill="#737373">1. 磁共振：H = -γ B₀ S_z - γ B_x S_x cos(ωt+φ)</text>
<text x="372" y="128" fill="#3b82f6" font-weight="600">2. 令 ω₀ = -γ_e B₀，2Ω = -γ_e B_x</text>
<text x="372" y="152" fill="#171717">   得 H = ω₀ S_z + 2Ω cos(ωt+φ) S_x</text>
<line x1="372" y1="168" x2="602" y2="168" stroke="#d4d4d4" stroke-width="1"/>
<text x="372" y="194" font-weight="600" fill="#171717">3. 量子光学电偶极同构 (§4.4–§4.5)</text>
<text x="372" y="218" fill="#737373">   H/ℏ = ½ω₀ σ_3 + (V/ℏ) cos(ωt) (σ_+ + σ_-)</text>
<text x="372" y="242" fill="#3b82f6" font-weight="600">   对应：2S_z ↔ σ_3，2S_x ↔ σ_+ + σ_-，Ω ↔ V/ℏ</text>
</g>
</svg>'''


def build_svg_rwa_split() -> str:
    cx, cy = 425.0, 165.0
    r = 82.0
    alpha = 38.0
    x_plus, y_plus = pt(cx, cy, r, alpha)
    x_minus, y_minus = pt(cx, cy, r, -alpha)
    x_sum = round(cx + 2 * r * math.cos(math.radians(alpha)), 2)

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


def build_svg_l3_effective_field() -> str:
    ox, oy = 165.0, 210.0
    xy_x, xy_y = 262.0, 232.0
    z_x, z_y = 165.0, 108.0
    eff_x, eff_y = 262.0, 130.0
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="旋转坐标系有效场示意图：有效磁场矢量 Omega_eff n⃗ 由横向驱动分量 Omega（蓝色，沿方位角 phi 指向 x-y 平面内）与纵向失谐分量 delta（绿色，沿 z 轴）合成，与 z 轴夹角为 theta'（满足 cos theta' 等于 delta 除以 Omega_eff，sin theta' 等于 Omega 除以 Omega_eff），演化算符 U_I 让量子态绕 n⃗ 旋转角度 theta 等于 Omega_eff t；当共振 delta 等于零时，有效转轴倒向赤道 x-y 平面。">
<defs>
<marker id="l3f-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="l3f-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="l3f-green" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#10b981"/></marker>
<marker id="l3f-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
<marker id="l3f-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<text x="175" y="28" text-anchor="middle" font-size="14" font-weight="600">有效拉比场矢量与旋转轴 n⃗</text>
<line x1="{ox}" y1="{oy + 25}" x2="{ox}" y2="48" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#l3f-dark)"/>
<line x1="{ox - 20}" y1="{oy}" x2="320" y2="{oy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#l3f-dark)"/>
<line x1="{ox + 15}" y1="{oy - 12}" x2="88" y2="270" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#l3f-dark)"/>
<text x="{ox - 12}" y="52">z</text>
<text x="325" y="{oy + 4}">y</text>
<text x="74" y="276">x</text>
<line x1="{z_x}" y1="{z_y}" x2="{eff_x}" y2="{eff_y}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{xy_x}" y1="{xy_y}" x2="{eff_x}" y2="{eff_y}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{z_x}" y2="{z_y}" stroke="#10b981" stroke-width="2.5" marker-end="url(#l3f-green)"/>
<line x1="{ox}" y1="{oy}" x2="{xy_x}" y2="{xy_y}" stroke="#3b82f6" stroke-width="2.5" marker-end="url(#l3f-blue)"/>
<line x1="{ox}" y1="{oy}" x2="{eff_x}" y2="{eff_y}" stroke="#ef4444" stroke-width="3" marker-end="url(#l3f-red)"/>
<path d="M165 158 A52 52 0 0 1 206 177" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="184" y="152" fill="#737373">θ'</text>
<path d="M198 210 A33 33 0 0 1 196 218" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="1.5"/>
<path d="M236 122 A24 14 -25 0 1 268 158" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2" marker-end="url(#l3f-amber)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="122" y="152" fill="#10b981" font-weight="600">δ = ω₀ - ω</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="220" y="254" fill="#3b82f6" font-weight="600">Ω (方位角 φ)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="268" y="122" fill="#ef4444" font-weight="600">Ω_eff n⃗</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="262" y="176" fill="#f59e0b" font-size="12">转角 θ = Ω_eff t</text>
<rect x="358" y="48" width="262" height="218" rx="8" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.4"/>
<text x="374" y="76" font-weight="600" fill="#171717">SU(2) 演化算符与关键参数</text>
<text x="374" y="106" fill="#737373">H_I = Ω_eff n⃗·S⃗，Ω_eff = √(Ω² + δ²)</text>
<text x="374" y="134" fill="#737373">n⃗ = (sinθ' cosφ, sinθ' sinφ, cosθ')</text>
<text x="374" y="162" fill="#737373">cosθ' = δ / Ω_eff，sinθ' = Ω / Ω_eff</text>
<line x1="374" y1="180" x2="604" y2="180" stroke="#d4d4d4" stroke-width="1"/>
<text x="374" y="206" fill="#ef4444" font-weight="600">U_I = cos(θ/2)𝟙 - i sin(θ/2) n⃗·σ⃗</text>
<text x="374" y="232" fill="#737373">其中 θ = Ω_eff t，泡利矢量 σ⃗ = 2 S⃗</text>
<text x="374" y="254" fill="#3b82f6">共振 δ = 0 时 θ' = 90°，n⃗ 落在赤道面</text>
</g>
</svg>'''


def build_svg_l3_rabi_curves() -> str:
    x0, x1 = 68.0, 560.0
    y0, y1 = 236.0, 48.0

    def to_xy(u: float, p: float) -> str:
        px = round(x0 + (u / 3.0) * (x1 - x0), 2)
        py = round(y0 - p * (y0 - y1), 2)
        return f"{px},{py}"

    def curve_pts(delta_ratio: float) -> str:
        eff = math.sqrt(1.0 + delta_ratio * delta_ratio)
        amp = 1.0 / (1.0 + delta_ratio * delta_ratio)
        pts = []
        steps = 120
        for i in range(steps + 1):
            u = 3.0 * i / steps
            prob = amp * (math.sin(0.5 * eff * math.pi * u) ** 2)
            pts.append(to_xy(u, prob))
        return " ".join(pts)

    c0 = curve_pts(0.0)
    c1 = curve_pts(1.0)
    c2 = curve_pts(2.0)
    x_half = round(x0 + (0.5 / 3.0) * (x1 - x0), 2)
    y_half = round(y0 - 0.5 * (y0 - y1), 2)
    x_pi = round(x0 + (1.0 / 3.0) * (x1 - x0), 2)
    x_2pi = round(x0 + (2.0 / 3.0) * (x1 - x0), 2)
    x_3pi = x1

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="拉比跃迁概率随无量纲时间 Omega t 除以 pi 变化的曲线图（对照 Gerry &amp; Knight 图 4.4）：蓝色实线为完全共振 delta 等于零，在 Omega t 等于 pi/2 时达到 P 等于 0.50，在 Omega t 等于 pi 时达到峰值 P 等于 1.00；橙色虚线 delta 等于 Omega 最大概率降至 0.50 且振荡周期缩短；红色点线 delta 等于 2 Omega 最大概率进一步压低至 0.20。">
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="12.5" fill="#171717">
<text x="315" y="26" text-anchor="middle" font-size="14" font-weight="600">拉比跃迁概率 P(t) 与失谐对峰值及振荡频率的双重影响</text>
<line x1="{x0}" y1="{y_half}" x2="{x1}" y2="{y_half}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<line x1="{x_half}" y1="{y1}" x2="{x_half}" y2="{y0}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="3 3"/>
<line x1="{x_pi}" y1="{y1}" x2="{x_pi}" y2="{y0}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="3 3"/>
<line x1="{x0}" y1="{y0}" x2="{x1 + 18}" y2="{y0}" stroke="#171717" stroke-width="1.5"/>
<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1 - 12}" stroke="#171717" stroke-width="1.5"/>
<text x="20" y="{y1 + 6}">1.0</text>
<text x="20" y="{y_half + 4}">0.5</text>
<text x="20" y="{y0 + 4}">0.0</text>
<text x="16" y="138" font-weight="600">P(t)</text>
<text x="{x0}" y="256" text-anchor="middle">0</text>
<text x="{x_half}" y="256" text-anchor="middle">0.5 (π/2)</text>
<text x="{x_pi}" y="256" text-anchor="middle">1.0 (π)</text>
<text x="{x_2pi}" y="256" text-anchor="middle">2.0</text>
<text x="{x_3pi}" y="256" text-anchor="middle">3.0</text>
<text x="315" y="278" text-anchor="middle" fill="#737373">无量纲时间 Ω t / π</text>
<polyline points="{c2}" fill="#ffffff" fill-opacity="0" stroke="#ef4444" stroke-width="2" stroke-dasharray="2 4"/>
<polyline points="{c1}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2.2" stroke-dasharray="6 4"/>
<polyline points="{c0}" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="2.8"/>
<circle cx="{x_half}" cy="{y_half}" r="4.5" fill="#10b981"/>
<circle cx="{x_pi}" cy="{y1}" r="4.5" fill="#3b82f6"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_half + 8}" y="{y_half + 14}" fill="#10b981" font-weight="600">Ωt = π/2 (P=0.50)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_pi + 8}" y="{y1 + 14}" fill="#3b82f6" font-weight="600">Ωt = π (P=1.00)</text>
<rect x="404" y="54" width="218" height="68" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<line x1="414" y1="70" x2="438" y2="70" stroke="#3b82f6" stroke-width="2.8"/>
<text x="444" y="74" font-size="12">δ = 0（共振，峰值 1.00）</text>
<line x1="414" y1="90" x2="438" y2="90" stroke="#f59e0b" stroke-width="2.2" stroke-dasharray="6 4"/>
<text x="444" y="94" font-size="12">δ = Ω（失谐，峰值 0.50）</text>
<line x1="414" y1="110" x2="438" y2="110" stroke="#ef4444" stroke-width="2" stroke-dasharray="2 4"/>
<text x="444" y="114" font-size="12">δ = 2Ω（大失谐，峰值 0.20）</text>
</g>
</svg>'''


SVGS = [
    ("svg_l1_1.svg", build_svg_l1_zeeman),
    ("svg_l1_2.svg", build_svg_l1_drive_geom),
    ("svg1.svg", build_svg_rwa_split),
    ("svg2.svg", build_svg_rotating_frame),
    ("svg_l3_1.svg", build_svg_l3_effective_field),
    ("svg_l3_2.svg", build_svg_l3_rabi_curves),
]


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "_generated_svgs"
    out_dir.mkdir(exist_ok=True)
    for fname, fn in SVGS:
        s = "\n".join(line.rstrip() for line in fn().splitlines())
        err = validate_svg_block(s)
        print(f"{fname}: validate -> {'OK' if err is None else err}")
        if err:
            raise SystemExit(1)
        (out_dir / fname).write_text(s + "\n", encoding="utf-8", newline="\n")
    print(f"Saved {len(SVGS)} preview SVGs to {out_dir}")
