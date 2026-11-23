#!/usr/bin/env python3
"""SVG generators for concept: longitudinal-sideband-excitation."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path


def _bessel_j(n: int, x: float, terms: int = 24) -> float:
    """Compute integer-order Bessel function J_n(x) via power series."""
    if n < 0:
        sign = -1.0 if ((-n) % 2 == 1) else 1.0
        return sign * _bessel_j(-n, x, terms=terms)
    half = 0.5 * x
    total = 0.0
    for k in range(terms):
        coeff = ((-1.0) ** k) / (math.factorial(k) * math.factorial(k + n))
        total += coeff * (half ** (2 * k + n))
    return total


def build_svg_l4_sideband_comb_and_bessel() -> str:
    # Left panel: Sideband resonance comb at chi = 1.2
    chi_demo = 1.2
    base_y = 232.0
    unit_h = 166.0  # 1.0 corresponds to y = 66
    cx = 168.0
    dx = 46.0

    comb_specs = [
        (-2, "#f59e0b", "0.16"),
        (-1, "#10b981", "0.50"),
        (0, "#3b82f6", "0.67"),
        (1, "#10b981", "0.50"),
        (2, "#f59e0b", "0.16"),
    ]
    comb_elems: list[str] = []
    for n_ord, color, lbl_val in comb_specs:
        px = round(cx + n_ord * dx, 2)
        amp = abs(_bessel_j(n_ord, chi_demo))
        y_top = round(base_y - amp * unit_h, 2)
        n_str = f"+{n_ord}" if n_ord > 0 else ("n=0" if n_ord == 0 else str(n_ord))
        comb_elems.append(f'<line x1="{px}" y1="{base_y}" x2="{px}" y2="{y_top}" stroke="{color}" stroke-width="4"/>')
        comb_elems.append(f'<circle cx="{px}" cy="{y_top}" r="3.5" fill="{color}"/>')
        comb_elems.append(
            f'<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" '
            f'x="{px}" y="{round(y_top - 8, 2)}" text-anchor="middle" font-size="11.5" fill="{color}" font-weight="600">{lbl_val}</text>'
        )
        comb_elems.append(f'<text x="{px}" y="249" text-anchor="middle" font-size="12" fill="{color}" font-weight="600">{n_str}</text>')

    # Right panel: |J_n(chi)| vs chi in [0, 3.5]
    px0, px1 = 358.0, 610.0  # width = 252 => 72 px per chi
    py0, py1 = 232.0, 62.0   # height = 170 => 170 px per unit

    def bessel_pts(n_ord: int) -> str:
        pts: list[str] = []
        steps = 140
        for i in range(steps + 1):
            chi = 3.5 * i / steps
            val = abs(_bessel_j(n_ord, chi))
            px = round(px0 + (chi / 3.5) * (px1 - px0), 2)
            py = round(py0 - val * (py0 - py1), 2)
            pts.append(f"{px},{py}")
        return " ".join(pts)

    pts_j0 = bessel_pts(0)
    pts_j1 = bessel_pts(1)
    pts_j2 = bessel_pts(2)

    chi_zero = 2.4048
    x_zero = round(px0 + (chi_zero / 3.5) * (px1 - px0), 2)
    y_half = round(py0 - 0.5 * (py0 - py1), 2)

    ticks_x = []
    for chi_t, lbl in [(0.0, "0"), (1.0, "1"), (2.0, "2"), (3.0, "3"), (3.5, "3.5")]:
        tx = round(px0 + (chi_t / 3.5) * (px1 - px0), 2)
        ticks_x.append(f'<line x1="{tx}" y1="{py0}" x2="{tx}" y2="{py0 + 4}" stroke="#171717" stroke-width="1.2"/>')
        ticks_x.append(f'<text x="{tx}" y="249" text-anchor="middle" font-size="11.5">{lbl}</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="双栏边带激发与贝塞尔包络图：左栏展示纵向调制下在频率 omega_0 两侧等间距 omega_z 分布的边带共振梳 omega_0 + n omega_z（以调制指数 chi 等于 1.2 为例标出 n 等于 0、正负 1、正负 2 阶相对强度）；右栏绘制零阶、一阶、二阶贝塞尔函数绝对值随调制指数 chi 在 0 到 3.5 的变化曲线，并用红点标出 chi 约等于 2.4048 处首次出现的载波抑制零点 J_0 等于 0。">
<defs>
<marker id="l4s1-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="12.5" fill="#171717">
<text x="156" y="24" text-anchor="middle" font-size="13.5" font-weight="600">边带共振梳 ω = ω₀ + nω_z (例: χ = 1.2)</text>
<line x1="44" y1="66" x2="282" y2="66" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<line x1="44" y1="149" x2="282" y2="149" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<text x="38" y="70" text-anchor="end" font-size="11" fill="#737373">1.0</text>
<text x="38" y="153" text-anchor="end" font-size="11" fill="#737373">0.5</text>
<line x1="38" y1="{base_y}" x2="290" y2="{base_y}" stroke="#171717" stroke-width="1.5" marker-end="url(#l4s1-dark)"/>
<line x1="44" y1="{base_y}" x2="44" y2="48" stroke="#171717" stroke-width="1.5" marker-end="url(#l4s1-dark)"/>
<text x="294" y="236" font-size="12">ω</text>
<text x="48" y="47" font-size="11.5" font-weight="600">|J_n(χ)|</text>
{"".join(comb_elems)}
<text x="168" y="266" text-anchor="middle" font-size="12" fill="#3b82f6" font-weight="600">ω₀</text>
<line x1="168" y1="92" x2="214" y2="92" stroke="#737373" stroke-width="1.4"/>
<line x1="168" y1="87" x2="168" y2="97" stroke="#737373" stroke-width="1.4"/>
<line x1="214" y1="87" x2="214" y2="97" stroke="#737373" stroke-width="1.4"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="191" y="83" text-anchor="middle" font-size="11.5" fill="#737373">间距 ω_z</text>
<text x="162" y="286" text-anchor="middle" font-size="12" fill="#737373">各阶有效耦合幅度 |J_n(χ)|Ω</text>
<line x1="308" y1="18" x2="308" y2="284" stroke="#d4d4d4" stroke-width="1"/>
<text x="476" y="24" text-anchor="middle" font-size="13.5" font-weight="600">贝塞尔包络 |J_n(χ)| 随 χ 变化</text>
<line x1="{px0}" y1="{y_half}" x2="{px1}" y2="{y_half}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#d4d4d4" stroke-width="1" stroke-dasharray="4 4"/>
<text x="{px0 - 6}" y="{py1 + 4}" text-anchor="end" font-size="11" fill="#737373">1.0</text>
<text x="{px0 - 6}" y="{y_half + 4}" text-anchor="end" font-size="11" fill="#737373">0.5</text>
<text x="{px0 - 6}" y="{py0 + 4}" text-anchor="end" font-size="11" fill="#737373">0</text>
<line x1="{x_zero}" y1="{py0}" x2="{x_zero}" y2="128" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4 3"/>
<line x1="{px0}" y1="{py0}" x2="{px1 + 14}" y2="{py0}" stroke="#171717" stroke-width="1.5" marker-end="url(#l4s1-dark)"/>
<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1 - 14}" stroke="#171717" stroke-width="1.5" marker-end="url(#l4s1-dark)"/>
<text x="{px0 + 6}" y="47" font-size="11.5" font-weight="600">|J_n|</text>
{"".join(ticks_x)}
<text x="484" y="286" text-anchor="middle" font-size="12" fill="#737373">无量纲调制指数 χ = Ω_z / ω_z</text>
<polyline points="{pts_j2}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2.2" stroke-dasharray="6 3"/>
<polyline points="{pts_j1}" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="2.4"/>
<polyline points="{pts_j0}" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="2.6"/>
<circle cx="{x_zero}" cy="{py0}" r="4.5" fill="#ef4444"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_zero}" y="122" text-anchor="middle" font-size="11.5" fill="#ef4444" font-weight="600">χ ≈ 2.4048 (J₀=0)</text>
<text x="{x_zero}" y="266" text-anchor="middle" font-size="11" fill="#ef4444" font-weight="600">载波零点</text>
<rect x="476" y="40" width="144" height="62" rx="6" fill="#ffffff" fill-opacity="0.95" stroke="#d4d4d4" stroke-width="1.2"/>
<line x1="485" y1="54" x2="508" y2="54" stroke="#3b82f6" stroke-width="2.6"/>
<text x="514" y="58" font-size="11.5">|J₀(χ)| 载波 (n=0)</text>
<line x1="485" y1="72" x2="508" y2="72" stroke="#10b981" stroke-width="2.4"/>
<text x="514" y="76" font-size="11.5">|J₁(χ)| 一阶边带</text>
<line x1="485" y1="90" x2="508" y2="90" stroke="#f59e0b" stroke-width="2.2" stroke-dasharray="6 3"/>
<text x="514" y="94" font-size="11.5">|J₂(χ)| 二阶边带</text>
</g>
</svg>'''


def build_svg_l4_tilted_coil_and_subharmonic() -> str:
    # Left panel: tilted coil geometry
    ox, oy = 84.0, 206.0
    length = 136.0
    theta_deg = 48.0  # angle from +z axis
    dx = round(length * math.sin(math.radians(theta_deg)), 2)
    dy = round(length * math.cos(math.radians(theta_deg)), 2)
    tip_x = round(ox + dx, 2)
    tip_y = round(oy - dy, 2)
    theta_arc = arc_path(ox, oy, 52.0, 90.0 - theta_deg, 90.0, sweep_cw=False)
    x_mid_hz = round(0.5 * (ox + tip_x), 2)

    # Right panel: harmonic ladder & passband
    y_top, y_bot = 74.0, 202.0
    y_mid_2 = round(0.5 * (y_top + y_bot), 2)
    y_3_1 = round(y_bot - (y_bot - y_top) / 3.0, 2)
    y_3_2 = round(y_bot - 2.0 * (y_bot - y_top) / 3.0, 2)

    # Bandwidth bar: 0 to 11 GHz mapped to x = 308..605 (27 px / GHz)
    bx0 = 308.0
    px_per_ghz = 27.0
    x_333 = round(bx0 + (10.0 / 3.0) * px_per_ghz, 2)
    x_5 = round(bx0 + 5.0 * px_per_ghz, 2)
    x_6 = round(bx0 + 6.0 * px_per_ghz, 2)
    x_10 = round(bx0 + 10.0 * px_per_ghz, 2)
    x_11 = round(bx0 + 11.0 * px_per_ghz, 2)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="倾斜线圈几何与同源倍频激发阶梯图：左图展示单根倾斜驱动线圈的磁场 B_ac 与静磁场 z 轴成非 90 度夹角 theta_B，同时投影出沿 x 轴的横向驱动 Omega 与沿 z 轴的同频纵向调制 Omega_z（满足 omega_z 等于 omega）；右图对比基频 n 等于 0（10 GHz，超出 6 GHz 功放带宽）、二倍频 n 等于负 1（5 GHz）与三倍频 n 等于负 2（约 3.33 GHz）如何跨越 10 GHz 自旋能隙。">
<defs>
<marker id="l4s2-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="l4s2-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="l4s2-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
<marker id="l4s2-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
<marker id="l4s2-green" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#10b981"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="12.5" fill="#171717">
<text x="140" y="24" text-anchor="middle" font-size="13.5" font-weight="600">倾斜单线圈同时产生 Ω 与 Ω_z</text>
<line x1="{ox}" y1="{oy + 16}" x2="{ox}" y2="48" stroke="#171717" stroke-width="1.8" marker-end="url(#l4s2-dark)"/>
<line x1="{ox - 20}" y1="{oy}" x2="250" y2="{oy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#l4s2-dark)"/>
<text x="{ox + 7}" y="55" font-weight="600">z (B₀)</text>
<text x="255" y="{oy + 4}">x</text>
<line x1="{tip_x}" y1="{tip_y}" x2="{tip_x}" y2="{oy}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{tip_x}" y1="{tip_y}" x2="{ox}" y2="{tip_y}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{tip_x}" y2="{oy}" stroke="#3b82f6" stroke-width="3" marker-end="url(#l4s2-blue)"/>
<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{tip_y}" stroke="#ef4444" stroke-width="3" marker-end="url(#l4s2-red)"/>
<line x1="{ox}" y1="{oy}" x2="{tip_x}" y2="{tip_y}" stroke="#f59e0b" stroke-width="3" marker-end="url(#l4s2-amber)"/>
<path d="{theta_arc}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{ox + 5}" y="138" font-size="11.5" fill="#737373">θ_B ≠ 90°</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{tip_x + 4}" y="{tip_y - 8}" font-size="12" fill="#f59e0b" font-weight="600">B_ac(ω)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_mid_hz}" y="{oy + 18}" text-anchor="middle" font-size="12" fill="#3b82f6" font-weight="600">横向 Ω (ω)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{ox - 8}" y="152" text-anchor="end" font-size="12" fill="#ef4444" font-weight="600">纵向 Ω_z</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{ox - 8}" y="168" text-anchor="end" font-size="11.5" fill="#ef4444">(ω_z = ω)</text>
<rect x="16" y="242" width="246" height="44" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<text x="139" y="260" text-anchor="middle" font-size="11.5" fill="#171717">单源倾斜: ω_z = ω，调制指数 χ = Ω_z / ω</text>
<text x="139" y="278" text-anchor="middle" font-size="11.5" fill="#737373">共振条件 ω = ω₀ / (1 - n) (n = 0, -1, -2...)</text>
<line x1="278" y1="18" x2="278" y2="286" stroke="#d4d4d4" stroke-width="1"/>
<text x="458" y="24" text-anchor="middle" font-size="13.5" font-weight="600">倍频激发阶梯：5 GHz 驱动 10 GHz 跃迁</text>
<line x1="298" y1="{y_top}" x2="554" y2="{y_top}" stroke="#171717" stroke-width="2.2"/>
<line x1="298" y1="{y_bot}" x2="554" y2="{y_bot}" stroke="#171717" stroke-width="2.2"/>
<text x="560" y="{y_top + 4}" font-size="12" font-weight="600">|+1/2⟩</text>
<text x="560" y="{y_bot + 4}" font-size="12" font-weight="600">|-1/2⟩</text>
<line x1="604" y1="{y_bot}" x2="604" y2="{y_top}" stroke="#737373" stroke-width="1.2" marker-end="url(#l4s2-dark)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="604" y="142" text-anchor="middle" font-size="11.5" fill="#737373">10 GHz</text>
<line x1="340" y1="{y_bot - 3}" x2="340" y2="{y_top + 5}" stroke="#ef4444" stroke-width="2.2" stroke-dasharray="5 3" marker-end="url(#l4s2-red)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="340" y="55" text-anchor="middle" font-size="11.5" fill="#ef4444" font-weight="600">n=0: ω₀</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="340" y="140" text-anchor="middle" font-size="11" fill="#ef4444">10 GHz 超带宽</text>
<line x1="408" y1="{y_mid_2}" x2="452" y2="{y_mid_2}" stroke="#d4d4d4" stroke-width="1.4" stroke-dasharray="3 3"/>
<line x1="430" y1="{y_bot - 3}" x2="430" y2="{y_mid_2 + 4}" stroke="#3b82f6" stroke-width="2.5" marker-end="url(#l4s2-blue)"/>
<line x1="430" y1="{y_mid_2 - 3}" x2="430" y2="{y_top + 5}" stroke="#3b82f6" stroke-width="2.5" marker-end="url(#l4s2-blue)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="430" y="55" text-anchor="middle" font-size="11.5" fill="#3b82f6" font-weight="600">n=-1: ω₀/2</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="456" y="110" font-size="11" fill="#3b82f6">5 GHz</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="456" y="175" font-size="11" fill="#3b82f6">5 GHz</text>
<line x1="504" y1="{y_3_1}" x2="544" y2="{y_3_1}" stroke="#d4d4d4" stroke-width="1.4" stroke-dasharray="3 3"/>
<line x1="504" y1="{y_3_2}" x2="544" y2="{y_3_2}" stroke="#d4d4d4" stroke-width="1.4" stroke-dasharray="3 3"/>
<line x1="524" y1="{y_bot - 3}" x2="524" y2="{y_3_1 + 4}" stroke="#10b981" stroke-width="2.2" marker-end="url(#l4s2-green)"/>
<line x1="524" y1="{y_3_1 - 3}" x2="524" y2="{y_3_2 + 4}" stroke="#10b981" stroke-width="2.2" marker-end="url(#l4s2-green)"/>
<line x1="524" y1="{y_3_2 - 3}" x2="524" y2="{y_top + 5}" stroke="#10b981" stroke-width="2.2" marker-end="url(#l4s2-green)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="524" y="55" text-anchor="middle" font-size="11.5" fill="#10b981" font-weight="600">n=-2: ω₀/3</text>
<rect x="{bx0}" y="236" width="{round(x_6 - bx0, 2)}" height="24" rx="4" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="1.5"/>
<text x="{round(0.5 * (bx0 + x_6), 2)}" y="252" text-anchor="middle" font-size="11.5" fill="#10b981" font-weight="600">功放可用带宽 (0–6 GHz)</text>
<line x1="{bx0}" y1="264" x2="{x_11}" y2="264" stroke="#171717" stroke-width="1.4" marker-end="url(#l4s2-dark)"/>
<circle cx="{x_333}" cy="264" r="4" fill="#10b981"/>
<circle cx="{x_5}" cy="264" r="4.5" fill="#3b82f6"/>
<line x1="{x_6}" y1="258" x2="{x_6}" y2="270" stroke="#737373" stroke-width="1.4" stroke-dasharray="2 2"/>
<circle cx="{x_10}" cy="264" r="4" fill="#ef4444"/>
<text x="{x_333}" y="282" text-anchor="middle" font-size="11" fill="#10b981" font-weight="600">3.33</text>
<text x="{x_5}" y="282" text-anchor="middle" font-size="11" fill="#3b82f6" font-weight="600">5 GHz</text>
<text x="{x_6}" y="282" text-anchor="middle" font-size="10.5" fill="#737373">6</text>
<text x="{x_10}" y="282" text-anchor="middle" font-size="11" fill="#ef4444" font-weight="600">10 GHz (超限)</text>
</g>
</svg>'''


KP_SVGS = {
    "sideband-time-dependent-frame-and-jacobi-anger": build_svg_l4_sideband_comb_and_bessel,
    "sideband-subharmonic-and-mas-transfer": build_svg_l4_tilted_coil_and_subharmonic,
}

LEGACY_FILES: dict[str, str] = {}
