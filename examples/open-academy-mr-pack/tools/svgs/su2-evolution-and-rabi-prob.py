#!/usr/bin/env python3
"""SVG generators for concept: su2-evolution-and-rabi-prob."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path, pt  # noqa: F401


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


KP_SVGS = {
    "su2-effective-field-and-unitary": build_svg_l3_effective_field,
    "rabi-probability-and-ode-duality": build_svg_l3_rabi_curves,
}

LEGACY_FILES = {
    "su2-effective-field-and-unitary": "svg_l3_1.svg",
    "rabi-probability-and-ode-duality": "svg_l3_2.svg",
}
