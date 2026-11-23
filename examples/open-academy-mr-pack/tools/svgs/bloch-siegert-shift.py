#!/usr/bin/env python3
"""SVG generators for concept: bloch-siegert-shift."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path, pt


def build_svg_axis_tilt() -> str:
    cx, cy = 118.0, 238.0
    l_z = 162.0
    l_x = 78.0
    theta = math.degrees(math.atan2(l_x, l_z))

    x_tip, z_tip = round(cx + l_x, 2), round(cy - l_z, 2)
    x_circ, y_circ = pt(cx, cy, l_z, 90.0 - theta)
    xp_end_x, xp_end_y = pt(cx, cy, 108.0, -theta)

    ref_arc = arc_path(cx, cy, l_z, 90.0, 90.0 - theta - 5.0, sweep_cw=True)
    theta_arc = arc_path(cx, cy, 56.0, 90.0, 90.0 - theta, sweep_cw=True)
    th_lbl_x, th_lbl_y = pt(cx, cy, 70.0, 90.0 - theta / 2.0)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="左图为第一重旋转系下 x-z 平面自旋量化轴倾斜几何图：竖直分量 (omega_0 - omega') S_z 与水平微扰分量 Omega' S_x 合成为沿新量化轴 S'_z、倾角为 theta 的蓝色有效场③，其模长 sqrt((omega_0 - omega')^2 + Omega'^2) 超出原虚线圆弧，从而使有效能隙拉伸；右图总结轴旋转公式与教材式 (1.19)、(1.20) 的两处勘误修正。">
<defs>
<marker id="bs1-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="bs1-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="bs1-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<line x1="364" y1="20" x2="364" y2="282" stroke="#d4d4d4" stroke-width="1"/>
<text x="182" y="24" text-anchor="middle" font-size="14" font-weight="600">自旋轴倾斜与模长拉伸 (x-z 平面)</text>
<line x1="82" y1="{cy}" x2="306" y2="{cy}" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#bs1-dark)"/>
<line x1="{cx}" y1="264" x2="{cx}" y2="42" stroke="#d4d4d4" stroke-width="1.5" marker-end="url(#bs1-dark)"/>
<text x="312" y="{cy + 4}" fill="#737373">x (S_x)</text>
<text x="{cx + 8}" y="48" fill="#737373">z (S_z)</text>
<text x="{cx - 14}" y="{cy + 16}" fill="#737373">O</text>
<path d="{ref_arc}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5" stroke-dasharray="4 3"/>
<line x1="{cx}" y1="{z_tip}" x2="{x_tip}" y2="{z_tip}" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="4 3"/>
<line x1="{x_tip}" y1="{cy}" x2="{x_tip}" y2="{z_tip}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="4 3"/>
<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{z_tip + 3}" stroke="#171717" stroke-width="2.5" marker-end="url(#bs1-dark)"/>
<line x1="{cx}" y1="{cy}" x2="{x_tip - 3}" y2="{cy}" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#bs1-amber)"/>
<line x1="{cx}" y1="{cy}" x2="{xp_end_x}" y2="{xp_end_y}" stroke="#3b82f6" stroke-width="1.6" stroke-dasharray="4 3" marker-end="url(#bs1-blue)"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{xp_end_x + 6}" y="{xp_end_y + 4}" fill="#3b82f6">x' (S'_x)</text>
<line x1="{cx}" y1="{cy}" x2="{x_tip}" y2="{z_tip}" stroke="#3b82f6" stroke-width="3" marker-end="url(#bs1-blue)"/>
<circle cx="{x_circ}" cy="{y_circ}" r="4" fill="#10b981"/>
<path d="{theta_arc}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{th_lbl_x + 2}" y="{th_lbl_y - 2}" fill="#f59e0b" font-weight="600">θ</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{cx - 8}" y="156" text-anchor="end">(ω₀ - ω') S_z</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{round((cx + x_tip) / 2, 2)}" y="{cy - 10}" text-anchor="middle" fill="#f59e0b" font-weight="600">Ω' S_x</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_tip + 8}" y="{z_tip - 16}" fill="#3b82f6" font-weight="600">有效轴 ③: S'_z</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_tip + 8}" y="{z_tip + 2}" fill="#3b82f6">√((ω₀ - ω')² + Ω'²)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_tip + 16}" y="{z_tip + 42}" fill="#10b981" font-size="12">超出原半径 |ω₀ - ω'|</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_tip + 16}" y="{z_tip + 60}" fill="#10b981" font-size="12">伸长量 ≈ |Δ_BS|</text>
<text x="500" y="24" text-anchor="middle" font-size="14" font-weight="600">轴旋转变换与教材两处勘误</text>
<rect x="374" y="38" width="256" height="114" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<text x="384" y="59" font-weight="600">绕 y 轴旋转 θ 对角化 ③ (式 1.19)</text>
<text x="384" y="80" fill="#737373" font-size="12">S'_z = cosθ S_z + sinθ S_x,  S'_y = S_y</text>
<text x="384" y="100" fill="#737373" font-size="12">S_x = cosθ S'_x + sinθ S'_z</text>
<text x="384" y="121" fill="#3b82f6" font-size="12">cosθ = |ω₀ - ω'| / √((ω₀ - ω')² + Ω'²)</text>
<text x="384" y="141" fill="#ef4444" font-size="12">勘误1: 根号内须保留平方 (ω₀ - ω')²</text>
<rect x="374" y="164" width="256" height="118" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2"/>
<text x="384" y="185" font-weight="600">弱微扰展开 (|Ω'| ≪ |ω₀ - ω'|)</text>
<text x="384" y="206" fill="#737373" font-size="12">tanθ = Ω' / (ω₀ - ω')  (图中放大了 θ)</text>
<text x="384" y="226" fill="#10b981" font-size="12">cosθ ≈ 1 - ½[Ω'/(ω₀-ω')]²</text>
<text x="384" y="247" fill="#ef4444" font-size="12">勘误2: 分母是 ω₀ - ω' (非 ω - ω')</text>
<text x="384" y="268" fill="#10b981" font-size="12">cos²(θ/2) ≈ 1 - ¼[Ω'/(ω₀-ω')]² ≈ 1</text>
</g>
</svg>'''


def build_svg_shift_scaling() -> str:
    # Left panel: shifted Lorentzian resonance curve
    x_w0, x_res = 128.0, 198.0
    base_y, peak_h, gamma = 240.0, 144.0, 18.0

    rwa_pts: list[str] = []
    full_pts: list[str] = []
    for xi in range(62, 279, 3):
        y_rwa = base_y - peak_h * (gamma * gamma) / ((xi - x_w0) ** 2 + gamma * gamma)
        y_full = base_y - peak_h * (gamma * gamma) / ((xi - x_res) ** 2 + gamma * gamma)
        rwa_pts.append(f"{xi},{round(y_rwa, 2)}")
        full_pts.append(f"{xi},{round(y_full, 2)}")

    # Right panel: quadratic scaling curve Delta_BS / omega_0 = 0.25 * (Omega / omega_0)^2
    px0, px1 = 378.0, 608.0
    py0, py1 = 240.0, 60.0  # y range [0, 0.0625] -> [0%, 6.25%]
    u_max = 0.50
    y_max = 0.0625

    def px(u: float) -> float:
        return round(px0 + (u / u_max) * (px1 - px0), 2)

    def py(val: float) -> float:
        return round(py0 - (val / y_max) * (py0 - py1), 2)

    curve_pts: list[str] = []
    for k in range(51):
        u = 0.01 * k
        val = 0.25 * u * u
        curve_pts.append(f"{px(u)},{py(val)}")

    x_02, y_02 = px(0.2), py(0.25 * 0.04)
    x_04, y_04 = px(0.4), py(0.25 * 0.16)
    x_safe = px(0.05)

    x_ticks_svg = []
    for u_val in (0.1, 0.2, 0.3, 0.4, 0.5):
        xt = px(u_val)
        x_ticks_svg.append(
            f'<line x1="{xt}" y1="{py0}" x2="{xt}" y2="{py0 + 5}" stroke="#737373" stroke-width="1.2"/>'
            f'<text x="{xt}" y="{py0 + 18}" text-anchor="middle" font-size="11" fill="#737373">{u_val:.1f}</text>'
        )

    y_ticks_svg = []
    for pct in (0.02, 0.04, 0.06):
        yt = py(pct)
        y_ticks_svg.append(
            f'<line x1="{px0 - 5}" y1="{yt}" x2="{px0}" y2="{yt}" stroke="#737373" stroke-width="1.2"/>'
            f'<text x="{px0 - 8}" y="{yt + 4}" text-anchor="end" font-size="11" fill="#737373">{int(pct * 100)}%</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="左图为包含反向旋转项后自旋共振峰向高频蓝移的示意图，实际共振频率 omega_res = omega_0 + Delta_BS；右图为定量平方标度曲线 Delta_BS / omega_0 = 1/4 (Omega / omega_0)^2，标出弱驱动安全区 Omega / omega_0 小于等于 0.05（绿色）以及强驱动下平方增长的显著频移。">
<defs>
<marker id="bs2-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="bs2-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#171717">
<line x1="316" y1="20" x2="316" y2="282" stroke="#d4d4d4" stroke-width="1"/>
<text x="160" y="24" text-anchor="middle" font-size="14" font-weight="600">反向项引起的共振峰蓝移</text>
<line x1="42" y1="{base_y}" x2="294" y2="{base_y}" stroke="#171717" stroke-width="1.5" marker-end="url(#bs2-dark)"/>
<line x1="50" y1="{base_y + 10}" x2="50" y2="48" stroke="#171717" stroke-width="1.5" marker-end="url(#bs2-dark)"/>
<text x="298" y="{base_y + 4}">ω</text>
<text x="58" y="54" fill="#737373" font-size="12">跃迁响应</text>
<polyline points="{' '.join(rwa_pts)}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="2" stroke-dasharray="5 3"/>
<polyline points="{' '.join(full_pts)}" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="2.5"/>
<line x1="{x_w0}" y1="{base_y - peak_h}" x2="{x_w0}" y2="{base_y}" stroke="#737373" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{x_res}" y1="{base_y - peak_h}" x2="{x_res}" y2="{base_y}" stroke="#3b82f6" stroke-width="1.2" stroke-dasharray="3 3"/>
<text x="{x_w0}" y="{base_y + 18}" text-anchor="middle" fill="#737373">ω₀</text>
<text x="{x_res + 14}" y="{base_y + 18}" text-anchor="middle" fill="#3b82f6" font-weight="600">ω_res = ω₀ + Δ_BS</text>
<line x1="{x_w0 + 3}" y1="78" x2="{x_res - 3}" y2="78" stroke="#f59e0b" stroke-width="2.5" marker-end="url(#bs2-amber)"/>
<text x="{round((x_w0 + x_res) / 2, 2)}" y="68" text-anchor="middle" fill="#f59e0b" font-weight="600">+Δ_BS</text>
<text x="104" y="122" text-anchor="end" fill="#737373" font-size="12">RWA 预测</text>
<text x="224" y="122" fill="#3b82f6" font-size="12">含反向项</text>
<text x="168" y="280" text-anchor="middle" fill="#737373" font-size="12">反向项把真实共振峰推高 Ω² / [2(ω₀+ω)]</text>
<text x="482" y="24" text-anchor="middle" font-size="14" font-weight="600">二阶标度律 Δ_BS / ω₀ = ¼(Ω / ω₀)²</text>
<line x1="{px0}" y1="{py0}" x2="{px1 + 14}" y2="{py0}" stroke="#171717" stroke-width="1.5" marker-end="url(#bs2-dark)"/>
<line x1="{px0}" y1="{py0}" x2="{px0}" y2="48" stroke="#171717" stroke-width="1.5" marker-end="url(#bs2-dark)"/>
{''.join(x_ticks_svg)}
{''.join(y_ticks_svg)}
<text x="{px0 - 8}" y="{py0 + 18}" text-anchor="end" font-size="11" fill="#737373">0</text>
<text x="493" y="282" text-anchor="middle" font-size="12">Ω / ω₀</text>
<text x="{px0 + 8}" y="52" text-anchor="start" font-size="12" fill="#737373">Δ_BS / ω₀</text>
<line x1="{x_safe}" y1="{py0}" x2="{x_safe}" y2="96" stroke="#10b981" stroke-width="1.8" stroke-dasharray="4 3"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_safe + 6}" y="106" fill="#10b981" font-size="12">RWA 适用区 Ω/ω₀ ≤ 0.05</text>
<polyline points="{' '.join(curve_pts)}" fill="#ffffff" fill-opacity="0" stroke="#ef4444" stroke-width="2.5"/>
<circle cx="{x_02}" cy="{y_02}" r="4" fill="#ef4444"/>
<circle cx="{x_04}" cy="{y_04}" r="4" fill="#ef4444"/>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_02 + 8}" y="{y_02 + 16}" fill="#ef4444" font-size="12">(0.2, 1.0%)</text>
<text stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" x="{x_04 + 6}" y="{y_04 + 16}" text-anchor="start" fill="#ef4444" font-size="12">(0.4, 4.0%)</text>
</g>
</svg>'''


KP_SVGS = {
    "bs-first-frame-and-axis-tilt": build_svg_axis_tilt,
    "bs-second-frame-and-shift-formula": build_svg_shift_scaling,
}

LEGACY_FILES: dict[str, str] = {}
