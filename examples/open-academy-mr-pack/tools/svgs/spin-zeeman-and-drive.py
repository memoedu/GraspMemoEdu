#!/usr/bin/env python3
"""SVG generators for concept: spin-zeeman-and-drive."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path, pt


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


KP_SVGS = {
    "zeeman-gyromagnetic-and-splitting": build_svg_l1_zeeman,
    "transverse-drive-hamiltonian": build_svg_l1_drive_geom,
}

LEGACY_FILES = {
    "zeeman-gyromagnetic-and-splitting": "svg_l1_1.svg",
    "transverse-drive-hamiltonian": "svg_l1_2.svg",
}
