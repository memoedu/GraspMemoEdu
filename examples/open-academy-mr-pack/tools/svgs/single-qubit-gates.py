#!/usr/bin/env python3
"""Programmatic SVG diagrams for single-qubit-gates."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path, pt


FONT = "font-family=\"-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif\""


def build_svg_u2l1_equatorial_xy() -> str:
    """Equatorial x-y control plane for resonant single-qubit gates."""
    cx, cy, r = 152, 170, 82
    nx, ny = pt(cx, cy, r, 38)
    nlx, nly = pt(cx, cy, r + 14, 38)
    bx, by = pt(cx, cy, 44, 19)
    arc_beta = arc_path(cx, cy, 30, 0, 38, sweep_cw=False)

    xdot_x, xdot_y = pt(cx, cy, r, 0)
    ydot_x, ydot_y = pt(cx, cy, r, 90)

    return "\n".join(
        [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" '
                f'role="img" aria-label="共振赤道面控制几何：脉冲相位 beta 选择旋转轴 n_beta 与 X/Y 系列门矩阵">'
            ),
            "  <defs>",
            (
                '    <marker id="u2l1xy-axis" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            ),
            '      <path d="M 0 1 L 10 5 L 0 9 z" fill="#737373"/>',
            "    </marker>",
            (
                '    <marker id="u2l1xy-amber" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            ),
            '      <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b"/>',
            "    </marker>",
            "  </defs>",
            '  <rect x="0" y="0" width="640" height="300" fill="#ffffff"/>',
            f'  <text x="20" y="24" font-size="14" font-weight="700" fill="#171717" {FONT}>共振赤道面脉冲门 (δ = 0, θ = Ωt)</text>',
            f'  <text x="20" y="42" font-size="11.5" fill="#737373" {FONT}>驱动相位 β 决定赤道旋转轴 n_β = (cos β, sin β, 0)，脉宽决定转角 θ</text>',
            # Equatorial circle and axes
            f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.5" stroke-dasharray="4 3"/>',
            f'  <line x1="{cx - r - 18}" y1="{cy}" x2="{cx + r + 20}" y2="{cy}" stroke="#737373" stroke-width="1.6" marker-end="url(#u2l1xy-axis)"/>',
            f'  <line x1="{cx}" y1="{cy + r + 16}" x2="{cx}" y2="{cy - r - 20}" stroke="#737373" stroke-width="1.6" marker-end="url(#u2l1xy-axis)"/>',
            f'  <text x="{cx + r + 24}" y="{cy + 4}" font-size="11.5" font-weight="700" fill="#10b981" {FONT}>x (β=0)</text>',
            f'  <text x="{cx + 8}" y="{cy - r - 14}" font-size="11.5" font-weight="700" fill="#3b82f6" {FONT}>y (β=π/2)</text>',
            # Beta vector and arc
            f'  <path d="{arc_beta}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="1.8"/>',
            f'  <line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#f59e0b" stroke-width="2.8" marker-end="url(#u2l1xy-amber)"/>',
            f'  <text x="{bx}" y="{by}" font-size="12" font-weight="700" fill="#f59e0b" {FONT}>β</text>',
            f'  <text x="{nlx}" y="{nly}" font-size="12" font-weight="700" fill="#f59e0b" {FONT}>n_β</text>',
            # Axis markers
            f'  <circle cx="{xdot_x}" cy="{xdot_y}" r="4.5" fill="#10b981"/>',
            f'  <circle cx="{ydot_x}" cy="{ydot_y}" r="4.5" fill="#3b82f6"/>',
            f'  <circle cx="{cx}" cy="{cy}" r="3" fill="#171717"/>',
            f'  <text x="{xdot_x - 32}" y="{xdot_y + 18}" font-size="11" fill="#10b981" {FONT}>(π/2)_x, (π)_x</text>',
            f'  <text x="{ydot_x - 94}" y="{ydot_y + 6}" font-size="11" fill="#3b82f6" {FONT}>(π/2)_y, (π)_y</text>',
            f'  <text x="{cx}" y="286" text-anchor="middle" font-size="11" fill="#737373" {FONT}>(θ)_β = cos(θ/2)I − i sin(θ/2) n_β·σ</text>',
            # Right side: 3 signature gate cards
            # Card 1: (pi/2)_x
            '  <rect x="322" y="54" width="298" height="68" rx="8" fill="#ffffff" stroke="#10b981" stroke-width="1.6"/>',
            f'  <text x="334" y="73" font-size="12" font-weight="700" fill="#10b981" {FONT}>(π/2)_x   [β = 0, θ = π/2]</text>',
            f'  <text x="334" y="99" font-size="12" fill="#171717" {FONT}>1/√2</text>',
            '  <path d="M 374 80 L 368 80 L 368 112 L 374 112" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            '  <path d="M 434 80 L 440 80 L 440 112 L 434 112" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            f'  <text x="386" y="92" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>1</text>',
            f'  <text x="420" y="92" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>-i</text>',
            f'  <text x="386" y="108" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>-i</text>',
            f'  <text x="420" y="108" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>1</text>',
            f'  <text x="452" y="99" font-size="11" fill="#737373" {FONT}>→ 复相干等权叠加</text>',
            # Card 2: (pi/2)_y
            '  <rect x="322" y="132" width="298" height="68" rx="8" fill="#ffffff" stroke="#3b82f6" stroke-width="1.6"/>',
            f'  <text x="334" y="151" font-size="12" font-weight="700" fill="#3b82f6" {FONT}>(π/2)_y   [β = π/2, θ = π/2]</text>',
            f'  <text x="334" y="177" font-size="12" fill="#171717" {FONT}>1/√2</text>',
            '  <path d="M 374 158 L 368 158 L 368 190 L 374 190" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            '  <path d="M 434 158 L 440 158 L 440 190 L 434 190" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            f'  <text x="386" y="170" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>1</text>',
            f'  <text x="420" y="170" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>-1</text>',
            f'  <text x="386" y="186" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>1</text>',
            f'  <text x="420" y="186" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>1</text>',
            f'  <text x="452" y="177" font-size="11" fill="#737373" {FONT}>→ 实系数等权叠加</text>',
            # Card 3: (pi)_x
            '  <rect x="322" y="210" width="298" height="72" rx="8" fill="#ffffff" stroke="#ef4444" stroke-width="1.6"/>',
            f'  <text x="334" y="229" font-size="12" font-weight="700" fill="#ef4444" {FONT}>(π)_x = -i σ_x   [β = 0, θ = π]</text>',
            '  <path d="M 352 237 L 346 237 L 346 271 L 352 271" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            '  <path d="M 412 237 L 418 237 L 418 271 L 412 271" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.4"/>',
            f'  <text x="364" y="250" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>0</text>',
            f'  <text x="398" y="250" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>-i</text>',
            f'  <text x="364" y="266" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>-i</text>',
            f'  <text x="398" y="266" text-anchor="middle" font-size="11.5" fill="#171717" {FONT}>0</text>',
            f'  <text x="430" y="251" font-size="11" fill="#171717" {FONT}>比特翻转 (|0⟩ ↔ -i|1⟩)</text>',
            f'  <text x="430" y="268" font-size="10.5" fill="#ef4444" {FONT}>勘误: 讲义 p.7 误印为 (π)_π</text>',
            "</svg>",
        ]
    )


def build_svg_u2l1_control_plane() -> str:
    """(Omega, delta) parameter control plane showing resonant x/y, detuning z, and Hadamard rays."""
    ox, oy = 112, 244
    hx, hy = 216, 140
    h_arc = arc_path(ox, oy, 44, 45, 90, sweep_cw=False)
    alx, aly = pt(ox, oy, 64, 70)

    return "\n".join(
        [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" '
                f'role="img" aria-label="(Omega, delta) 参数控制平面：水平共振 X/Y 门射线、垂直失谐 T/S/Z 门射线与 45 度 Hadamard 门射线">'
            ),
            "  <defs>",
            (
                '    <marker id="u2l1hz-green" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            ),
            '      <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981"/>',
            "    </marker>",
            (
                '    <marker id="u2l1hz-blue" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            ),
            '      <path d="M 0 1 L 10 5 L 0 9 z" fill="#3b82f6"/>',
            "    </marker>",
            (
                '    <marker id="u2l1hz-amber" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            ),
            '      <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b"/>',
            "    </marker>",
            "  </defs>",
            '  <rect x="0" y="0" width="640" height="300" fill="#ffffff"/>',
            f'  <text x="20" y="24" font-size="14" font-weight="700" fill="#171717" {FONT}>(Ω, δ) 控制平面与三类脉冲门射线</text>',
            f'  <text x="20" y="42" font-size="11.5" fill="#737373" {FONT}>有效旋转角 θ = Ω_eff t，其中 Ω_eff = √(Ω² + δ²)，倾角满足 cos α = δ / Ω_eff</text>',
            # Right triangle projection for Hadamard point (Omega=delta -> (216, 140))
            f'  <line x1="{hx}" y1="{hy}" x2="{hx}" y2="{oy}" stroke="#d4d4d4" stroke-width="1.4" stroke-dasharray="4 3"/>',
            f'  <line x1="{ox}" y1="{hy}" x2="{hx}" y2="{hy}" stroke="#d4d4d4" stroke-width="1.4" stroke-dasharray="4 3"/>',
            # Three rays from origin (112, 244)
            f'  <line x1="{ox}" y1="{oy}" x2="348" y2="{oy}" stroke="#10b981" stroke-width="2.8" marker-end="url(#u2l1hz-green)"/>',
            f'  <line x1="{ox}" y1="{oy}" x2="{ox}" y2="66" stroke="#3b82f6" stroke-width="2.8" marker-end="url(#u2l1hz-blue)"/>',
            f'  <line x1="{ox}" y1="{oy}" x2="256" y2="100" stroke="#f59e0b" stroke-width="2.8" marker-end="url(#u2l1hz-amber)"/>',
            f'  <path d="{h_arc}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="1.6"/>',
            f'  <text x="{alx}" y="{aly}" text-anchor="middle" font-size="11" font-weight="700" fill="#f59e0b" {FONT}>α=45°</text>',
            # Axis labels and markers
            f'  <text x="274" y="264" font-size="12" font-weight="700" fill="#10b981" {FONT}>Ω (δ = 0)</text>',
            f'  <text x="150" y="264" font-size="11" fill="#10b981" {FONT}>共振 x/y 门</text>',
            f'  <circle cx="{hx}" cy="{oy}" r="3.8" fill="#10b981"/>',
            f'  <text x="{hx}" y="282" text-anchor="middle" font-size="10.5" fill="#737373" {FONT}>(π/2)_β, (π)_β</text>',
            # Vertical detuning ray labels placed cleanly to the left of blue axis
            f'  <text x="122" y="78" font-size="12" font-weight="700" fill="#3b82f6" {FONT}>δ (Ω = 0, 自由演化)</text>',
            f'  <circle cx="{ox}" cy="204" r="3.8" fill="#3b82f6"/>',
            f'  <circle cx="{ox}" cy="164" r="3.8" fill="#3b82f6"/>',
            f'  <circle cx="{ox}" cy="114" r="3.8" fill="#3b82f6"/>',
            f'  <text x="102" y="208" text-anchor="end" font-size="10.5" fill="#3b82f6" {FONT}>T (δt=π/4)</text>',
            f'  <text x="102" y="168" text-anchor="end" font-size="10.5" fill="#3b82f6" {FONT}>S (δt=π/2)</text>',
            f'  <text x="102" y="118" text-anchor="end" font-size="10.5" fill="#3b82f6" {FONT}>Z_MR (δt=π)</text>',
            # Hadamard point label
            f'  <circle cx="{hx}" cy="{hy}" r="4.2" fill="#f59e0b"/>',
            f'  <text x="220" y="92" font-size="12" font-weight="700" fill="#f59e0b" {FONT}>H_MR (Ω = δ, β = 0)</text>',
            f'  <text x="224" y="144" font-size="11" fill="#f59e0b" {FONT}>Ω_eff = √2 Ω, θ = π</text>',
            # Origin dot
            f'  <circle cx="{ox}" cy="{oy}" r="3.5" fill="#171717"/>',
            # Right summary card
            '  <rect x="370" y="64" width="252" height="214" rx="8" fill="#ffffff" stroke="#d4d4d4" stroke-width="1.5"/>',
            f'  <text x="384" y="87" font-size="12" font-weight="700" fill="#171717" {FONT}>控制射线与门对应关系</text>',
            '  <circle cx="390" cy="113" r="4.5" fill="#10b981"/>',
            f'  <text x="402" y="117" font-size="11.5" font-weight="700" fill="#171717" {FONT}>水平轴 δ = 0 (n 在赤道面)</text>',
            f'  <text x="402" y="134" font-size="11" fill="#737373" {FONT}>θ = Ωt → (π/2)_x,y, (π)_x,y</text>',
            '  <circle cx="390" cy="162" r="4.5" fill="#3b82f6"/>',
            f'  <text x="402" y="166" font-size="11.5" font-weight="700" fill="#171717" {FONT}>垂直轴 Ω = 0 (n = (0,0,1))</text>',
            f'  <text x="402" y="183" font-size="11" fill="#737373" {FONT}>θ = δt → T, S, Z_MR (对角相移)</text>',
            '  <circle cx="390" cy="211" r="4.5" fill="#f59e0b"/>',
            f'  <text x="402" y="215" font-size="11.5" font-weight="700" fill="#171717" {FONT}>45° 射线 Ω = δ, β = 0</text>',
            f'  <text x="402" y="232" font-size="10.8" fill="#737373" {FONT}>θ = √2 Ωt = π → H_MR = -i(σ_x+σ_z)/√2</text>',
            f'  <text x="384" y="263" font-size="11" fill="#171717" {FONT}>全部物理脉冲均满足 det(U) = +1 ∈ SU(2)</text>',
            "</svg>",
        ]
    )


KP_SVGS = {
    "gate-resonant-xy-pulses": build_svg_u2l1_equatorial_xy,
    "gate-z-and-hadamard-pulses": build_svg_u2l1_control_plane,
}

LEGACY_FILES: dict[str, str] = {}
