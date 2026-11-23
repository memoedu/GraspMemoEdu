#!/usr/bin/env python3
"""SVG generators for concept: bloch-sphere-representation."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _geom import arc_path, pt  # noqa: F401


def _proj(
    cx: float,
    cy: float,
    r: float,
    x: float,
    y: float,
    z: float,
    az_deg: float = 34.0,
    el_deg: float = 18.0,
) -> tuple[float, float, float]:
    """Orthographic 3D-to-2D projection returning (screen_x, screen_y, depth)."""
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    sx = -x * math.sin(az) + y * math.cos(az)
    sy = -x * math.sin(el) * math.cos(az) - y * math.sin(el) * math.sin(az) + z * math.cos(el)
    depth = x * math.cos(el) * math.cos(az) + y * math.cos(el) * math.sin(az) + z * math.sin(el)
    return round(cx + r * sx, 2), round(cy - r * sy, 2), depth


def _split_3d_curve(
    pts_3d: list[tuple[float, float, float]],
    cx: float,
    cy: float,
    r: float,
    az_deg: float = 34.0,
    el_deg: float = 18.0,
) -> tuple[list[str], list[str]]:
    """Project 3D curve points into front (depth >= 0) and back (depth < 0) polyline strings."""
    front_segs: list[list[str]] = []
    back_segs: list[list[str]] = []
    cur_seg: list[str] = []
    cur_front: bool | None = None

    for x, y, z in pts_3d:
        px, py, d = _proj(cx, cy, r, x, y, z, az_deg, el_deg)
        is_front = d >= -0.02
        coord = f"{px},{py}"
        if cur_front is None:
            cur_front = is_front
            cur_seg = [coord]
        elif is_front == cur_front:
            cur_seg.append(coord)
        else:
            cur_seg.append(coord)
            if cur_front:
                front_segs.append(cur_seg)
            else:
                back_segs.append(cur_seg)
            cur_front = is_front
            cur_seg = [coord]

    if cur_seg:
        if cur_front:
            front_segs.append(cur_seg)
        else:
            back_segs.append(cur_seg)

    return [" ".join(s) for s in front_segs if len(s) >= 2], [" ".join(s) for s in back_segs if len(s) >= 2]


def build_svg_bloch_pure_mixed() -> str:
    """SVG 1: Bloch sphere mapping pure states (surface) and mixed states (interior)."""
    cx, cy, r = 172.0, 152.0, 88.0

    # Equator circle in 3D (z = 0)
    eq_pts = [
        (math.cos(2 * math.pi * i / 120), math.sin(2 * math.pi * i / 120), 0.0)
        for i in range(121)
    ]
    eq_front, eq_back = _split_3d_curve(eq_pts, cx, cy, r)

    # Coordinate axes endpoints
    ox, oy, _ = _proj(cx, cy, r, 0, 0, 0)
    x_pos = _proj(cx, cy, r, 1.24, 0, 0)[:2]
    x_surf = _proj(cx, cy, r, 1.0, 0, 0)[:2]
    y_pos = _proj(cx, cy, r, 0, 1.22, 0)[:2]
    y_surf = _proj(cx, cy, r, 0, 1.0, 0)[:2]
    z_pos = _proj(cx, cy, r, 0, 0, 1.24)[:2]
    z_surf = _proj(cx, cy, r, 0, 0, 1.0)[:2]
    z_neg = _proj(cx, cy, r, 0, 0, -1.16)[:2]
    z_nsurf = _proj(cx, cy, r, 0, 0, -1.0)[:2]

    # Pure state vector (theta = 46 deg, phi = 58 deg) on unit surface
    th_p, ph_p = math.radians(46.0), math.radians(58.0)
    px3 = math.sin(th_p) * math.cos(ph_p)
    py3 = math.sin(th_p) * math.sin(ph_p)
    pz3 = math.cos(th_p)
    p_tip = _proj(cx, cy, r, px3, py3, pz3)[:2]
    p_eq = _proj(cx, cy, r, px3, py3, 0.0)[:2]
    p_eq_edge = _proj(cx, cy, r, math.cos(ph_p), math.sin(ph_p), 0.0)[:2]

    # Meridian arc from north pole (+z) through pure state to equator
    merid_pts = [
        (
            math.sin(0.5 * math.pi * i / 40) * math.cos(ph_p),
            math.sin(0.5 * math.pi * i / 40) * math.sin(ph_p),
            math.cos(0.5 * math.pi * i / 40),
        )
        for i in range(41)
    ]
    merid_str = " ".join(f"{_proj(cx, cy, r, *pt3)[0]},{_proj(cx, cy, r, *pt3)[1]}" for pt3 in merid_pts)

    # Arcs for theta (from +z to pure vector) and phi (in x-y plane from +x to p_eq)
    th_arc_pts = [
        (
            0.34 * math.sin(th_p * i / 20) * math.cos(ph_p),
            0.34 * math.sin(th_p * i / 20) * math.sin(ph_p),
            0.34 * math.cos(th_p * i / 20),
        )
        for i in range(21)
    ]
    th_arc_str = " ".join(f"{_proj(cx, cy, r, *pt3)[0]},{_proj(cx, cy, r, *pt3)[1]}" for pt3 in th_arc_pts)
    th_lbl = _proj(
        cx,
        cy,
        r,
        0.52 * math.sin(th_p * 0.5) * math.cos(ph_p),
        0.52 * math.sin(th_p * 0.5) * math.sin(ph_p),
        0.52 * math.cos(th_p * 0.5),
    )[:2]

    ph_arc_pts = [
        (0.27 * math.cos(ph_p * i / 20), 0.27 * math.sin(ph_p * i / 20), 0.0)
        for i in range(21)
    ]
    ph_arc_str = " ".join(f"{_proj(cx, cy, r, *pt3)[0]},{_proj(cx, cy, r, *pt3)[1]}" for pt3 in ph_arc_pts)
    ph_lbl = _proj(cx, cy, r, 0.44 * math.cos(ph_p * 0.52), 0.44 * math.sin(ph_p * 0.52), 0.0)[:2]

    # Mixed state interior vector (|n| = 0.58 < 1, theta = 62 deg, phi = -42 deg)
    th_m, ph_m, rad_m = math.radians(62.0), math.radians(-42.0), 0.58
    mx3 = rad_m * math.sin(th_m) * math.cos(ph_m)
    my3 = rad_m * math.sin(th_m) * math.sin(ph_m)
    mz3 = rad_m * math.cos(th_m)
    m_tip = _proj(cx, cy, r, mx3, my3, mz3)[:2]

    eq_back_elems = "\n".join(
        f'<polyline points="{pts}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="4 4"/>'
        for pts in eq_back
    )
    eq_front_elems = "\n".join(
        f'<polyline points="{pts}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.4"/>'
        for pts in eq_front
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="Bloch 球面与单比特态几何映射图：单位球北极 +z 为 |0⟩、南极 -z 为 |1⟩，赤道 +x 为 (|0⟩+|1⟩)/√2、+y 为 (|0⟩+i|1⟩)/√2；蓝色纯态矢量 n⃗（模长等于 1）端点落在单位球面上，由极角 θ 与方位角 φ 唯一确定；橙色混态矢量（模长小于 1）端点位于单位球内部，右侧面板列出密度矩阵表达式及纯态与混态判据。">
<defs>
<marker id="bloch1-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="bloch1-gray" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#737373"/></marker>
<marker id="bloch1-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="bloch1-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#171717">
<text x="172" y="22" text-anchor="middle" font-size="14" font-weight="600">Bloch 球面纯态与球内混态</text>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" fill-opacity="0" stroke="#737373" stroke-width="1.5"/>
{eq_back_elems}
<polyline points="{merid_str}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{z_neg[0]}" y2="{z_neg[1]}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{z_pos[0]}" y2="{z_pos[1]}" stroke="#737373" stroke-width="1.5" marker-end="url(#bloch1-gray)"/>
<line x1="{ox}" y1="{oy}" x2="{x_pos[0]}" y2="{x_pos[1]}" stroke="#737373" stroke-width="1.5" marker-end="url(#bloch1-gray)"/>
<line x1="{ox}" y1="{oy}" x2="{y_pos[0]}" y2="{y_pos[1]}" stroke="#737373" stroke-width="1.5" marker-end="url(#bloch1-gray)"/>
{eq_front_elems}
<line x1="{ox}" y1="{oy}" x2="{p_eq_edge[0]}" y2="{p_eq_edge[1]}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<line x1="{p_eq[0]}" y1="{p_eq[1]}" x2="{p_tip[0]}" y2="{p_tip[1]}" stroke="#d4d4d4" stroke-width="1.2" stroke-dasharray="3 3"/>
<polyline points="{th_arc_str}" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="1.8"/>
<polyline points="{ph_arc_str}" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="1.8"/>
<line x1="{ox}" y1="{oy}" x2="{p_tip[0]}" y2="{p_tip[1]}" stroke="#3b82f6" stroke-width="2.8" marker-end="url(#bloch1-blue)"/>
<line x1="{ox}" y1="{oy}" x2="{m_tip[0]}" y2="{m_tip[1]}" stroke="#f59e0b" stroke-width="2.8" marker-end="url(#bloch1-amber)"/>
<circle cx="{ox}" cy="{oy}" r="3" fill="#171717"/>
<circle cx="{z_surf[0]}" cy="{z_surf[1]}" r="4" fill="#171717"/>
<circle cx="{z_nsurf[0]}" cy="{z_nsurf[1]}" r="4" fill="#171717"/>
<circle cx="{x_surf[0]}" cy="{x_surf[1]}" r="4" fill="#171717"/>
<circle cx="{y_surf[0]}" cy="{y_surf[1]}" r="4" fill="#171717"/>
<circle cx="{p_tip[0]}" cy="{p_tip[1]}" r="4.5" fill="#3b82f6"/>
<circle cx="{m_tip[0]}" cy="{m_tip[1]}" r="4.5" fill="#f59e0b"/>
<text x="{z_pos[0] + 10}" y="{z_pos[1] + 5}" font-weight="600">+z: |0⟩ = |+1/2⟩</text>
<text x="{z_neg[0] + 10}" y="{z_neg[1] + 10}" font-weight="600">-z: |1⟩ = |-1/2⟩</text>
<text x="86" y="198" text-anchor="end">+x: |+x⟩</text>
<text x="86" y="213" text-anchor="end" fill="#737373">(|0⟩+|1⟩)/√2</text>
<text x="266" y="192" text-anchor="start">+y: |+y⟩</text>
<text x="266" y="207" text-anchor="start" fill="#737373">(|0⟩+i|1⟩)/√2</text>
<text x="{th_lbl[0] + 3}" y="{th_lbl[1] - 3}" fill="#10b981" font-weight="600">θ</text>
<text x="{ph_lbl[0] - 2}" y="{ph_lbl[1] + 4}" fill="#10b981" font-weight="600">φ</text>
<text x="260" y="92" fill="#3b82f6" font-weight="600">纯态 |n⃗|=1</text>
<text x="260" y="108" fill="#3b82f6">(θ, φ)</text>
<text x="78" y="122" text-anchor="end" fill="#f59e0b" font-weight="600">混态 |n⃗|&lt;1</text>
<rect x="364" y="28" width="264" height="252" rx="8" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.4"/>
<text x="378" y="54" font-size="13.5" font-weight="600">Bloch 球坐标与密度矩阵</text>
<text x="378" y="80" fill="#737373">|ψ⟩ = cos(θ/2)|0⟩ + sin(θ/2)e^(iφ)|1⟩</text>
<text x="378" y="104" fill="#737373">n⃗ = (sinθ cosφ, sinθ sinφ, cosθ)</text>
<text x="378" y="128" fill="#171717" font-weight="600">ρ = (𝟙 + n⃗·σ⃗)/2</text>
<text x="378" y="148" fill="#171717" font-size="11.5">= ½ [1+n_z, n_x−in_y ; n_x+in_y, 1−n_z]</text>
<line x1="378" y1="164" x2="614" y2="164" stroke="#d4d4d4" stroke-width="1"/>
<circle cx="386" cy="186" r="4" fill="#3b82f6"/>
<text x="398" y="190" fill="#3b82f6" font-weight="600">球面 |n⃗| = 1：纯态 (Tr ρ² = 1)</text>
<circle cx="386" cy="212" r="4" fill="#f59e0b"/>
<text x="398" y="216" fill="#f59e0b" font-weight="600">球内 |n⃗| &lt; 1：混态 (Tr ρ² &lt; 1)</text>
<text x="378" y="242" fill="#737373">球心 n⃗ = 0 ⇒ ρ = 𝟙/2 (最大混态)</text>
<text x="378" y="264" fill="#10b981">对跖点 ±n⃗ 对应相互正交的纯态</text>
</g>
</svg>'''


def build_svg_bloch_gate_rotation() -> str:
    """SVG 2: Commutative isomorphism ρ_0 <-> n_0 -> n_f <-> ρ_f and U_x(pi/2)|1> 3D trajectory."""
    cx, cy, r = 446.0, 156.0, 86.0

    # Equator circle in 3D
    eq_pts = [
        (math.cos(2 * math.pi * i / 120), math.sin(2 * math.pi * i / 120), 0.0)
        for i in range(121)
    ]
    eq_front, eq_back = _split_3d_curve(eq_pts, cx, cy, r)

    # Axes
    ox, oy, _ = _proj(cx, cy, r, 0, 0, 0)
    x_pos = _proj(cx, cy, r, 1.24, 0, 0)[:2]
    y_pos = _proj(cx, cy, r, 0, 1.18, 0)[:2]
    y_surf = _proj(cx, cy, r, 0, 1.0, 0)[:2]
    z_pos = _proj(cx, cy, r, 0, 0, 1.24)[:2]
    z_surf = _proj(cx, cy, r, 0, 0, 1.0)[:2]
    z_neg = _proj(cx, cy, r, 0, 0, -1.16)[:2]
    z_nsurf = _proj(cx, cy, r, 0, 0, -1.0)[:2]

    # Trajectory from (0, 0, -1) rotated +90 deg around +x to (0, +1, 0):
    # n(t) = (0, sin(t), -cos(t)) for t in [0, pi/2]
    traj_pts = [
        (0.0, math.sin(0.5 * math.pi * i / 36), -math.cos(0.5 * math.pi * i / 36))
        for i in range(37)
    ]
    traj_str = " ".join(f"{_proj(cx, cy, r, *pt3)[0]},{_proj(cx, cy, r, *pt3)[1]}" for pt3 in traj_pts)

    # Right-hand-rule curl arrow around +x axis at x = 0.62
    curl_pts = [
        (0.62, 0.22 * math.cos(t), 0.22 * math.sin(t))
        for t in [math.radians(-65 + i * 10) for i in range(25)]
    ]
    curl_str = " ".join(f"{_proj(cx, cy, r, *pt3)[0]},{_proj(cx, cy, r, *pt3)[1]}" for pt3 in curl_pts)

    eq_back_elems = "\n".join(
        f'<polyline points="{pts}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="4 4"/>'
        for pts in eq_back
    )
    eq_front_elems = "\n".join(
        f'<polyline points="{pts}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.3"/>'
        for pts in eq_front
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" aria-label="单比特幺正门与 Bloch 矢量三维旋转同构图：左侧为交换同构图，密度矩阵经幺正演化 rho_f 等于 U rho_0 U dagger 等价于先映射为 Bloch 矢量 n_0，再绕单位轴 n 旋转角度 theta 得到 n_f，最后映射回 rho_f；右侧展示 U_x(pi/2) 作用在南极 |1⟩（n_0=(0,0,-1)）时，按右手定则绕 +x 轴转过 +90° 到达赤道 +y（n_f=(0,+1,0)），几何上与态矢 (|1⟩-i|0⟩)/√2 完全一致。">
<defs>
<marker id="bloch2-dark" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#171717"/></marker>
<marker id="bloch2-gray" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#737373"/></marker>
<marker id="bloch2-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#3b82f6"/></marker>
<marker id="bloch2-green" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#10b981"/></marker>
<marker id="bloch2-amber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f59e0b"/></marker>
<marker id="bloch2-red" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#ef4444"/></marker>
</defs>
<g font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#171717">
<line x1="336" y1="18" x2="336" y2="282" stroke="#d4d4d4" stroke-width="1"/>
<text x="168" y="23" text-anchor="middle" font-size="14" font-weight="600">幺正门与三维旋转同构框图</text>
<rect x="18" y="48" width="56" height="36" rx="6" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.5"/>
<text x="46" y="71" text-anchor="middle" font-size="14" font-weight="600">ρ₀</text>
<rect x="200" y="48" width="56" height="36" rx="6" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="1.5"/>
<text x="228" y="71" text-anchor="middle" font-size="14" font-weight="600" fill="#3b82f6">ρ_f</text>
<line x1="76" y1="66" x2="196" y2="66" stroke="#ef4444" stroke-width="2.2" marker-end="url(#bloch2-red)"/>
<text x="136" y="57" text-anchor="middle" fill="#ef4444" font-weight="600">U = exp(-i θ n⃗·S⃗)</text>
<text x="136" y="83" text-anchor="middle" fill="#737373" font-size="11.5">ρ_f = U ρ₀ U†</text>
<rect x="18" y="150" width="56" height="36" rx="6" fill="#ffffff" fill-opacity="0" stroke="#171717" stroke-width="1.5"/>
<text x="46" y="173" text-anchor="middle" font-size="14" font-weight="600">n⃗₀</text>
<rect x="200" y="150" width="56" height="36" rx="6" fill="#ffffff" fill-opacity="0" stroke="#3b82f6" stroke-width="1.5"/>
<text x="228" y="173" text-anchor="middle" font-size="14" font-weight="600" fill="#3b82f6">n⃗_f</text>
<line x1="76" y1="168" x2="196" y2="168" stroke="#3b82f6" stroke-width="2.4" marker-end="url(#bloch2-blue)"/>
<text x="136" y="158" text-anchor="middle" fill="#3b82f6" font-weight="600">三维旋转 R_(n⃗·θ)</text>
<text x="136" y="185" text-anchor="middle" fill="#737373" font-size="11.5">n⃗_f = R_(n⃗·θ)(n⃗₀)</text>
<line x1="46" y1="87" x2="46" y2="146" stroke="#737373" stroke-width="1.8" marker-end="url(#bloch2-gray)"/>
<line x1="228" y1="147" x2="228" y2="88" stroke="#737373" stroke-width="1.8" marker-end="url(#bloch2-gray)"/>
<text x="52" y="121" fill="#737373" font-size="11">Tr(ρ₀σ⃗)</text>
<text x="235" y="121" fill="#737373" font-size="11">(𝟙+n⃗_f·σ⃗)/2</text>
<rect x="16" y="206" width="298" height="74" rx="6" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.3"/>
<text x="28" y="227" font-weight="600">实例验证：U_x(π/2) 作用在初态 |1⟩</text>
<text x="28" y="248" fill="#737373">代数演化：(|1⟩ - i|0⟩)/√2 = -i|+y⟩</text>
<text x="28" y="269" fill="#3b82f6" font-weight="600">几何旋转：R_(x·π/2)(0,0,-1) = (0,+1,0)</text>
<text x="480" y="23" text-anchor="middle" font-size="14" font-weight="600">右手定则轨迹：绕 +x 转 +90°</text>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" fill-opacity="0" stroke="#d4d4d4" stroke-width="1.4"/>
{eq_back_elems}
<line x1="{ox}" y1="{oy}" x2="{z_neg[0]}" y2="{z_neg[1]}" stroke="#d4d4d4" stroke-width="1.3" stroke-dasharray="3 3"/>
<line x1="{ox}" y1="{oy}" x2="{z_pos[0]}" y2="{z_pos[1]}" stroke="#737373" stroke-width="1.4" marker-end="url(#bloch2-gray)"/>
<line x1="{ox}" y1="{oy}" x2="{y_pos[0]}" y2="{y_pos[1]}" stroke="#737373" stroke-width="1.4" marker-end="url(#bloch2-gray)"/>
{eq_front_elems}
<line x1="{ox}" y1="{oy}" x2="{x_pos[0]}" y2="{x_pos[1]}" stroke="#10b981" stroke-width="2.4" marker-end="url(#bloch2-green)"/>
<polyline points="{curl_str}" fill="#ffffff" fill-opacity="0" stroke="#10b981" stroke-width="2" marker-end="url(#bloch2-green)"/>
<polyline points="{traj_str}" fill="#ffffff" fill-opacity="0" stroke="#f59e0b" stroke-width="2.8" marker-end="url(#bloch2-amber)"/>
<line x1="{ox}" y1="{oy}" x2="{z_nsurf[0]}" y2="{z_nsurf[1]}" stroke="#171717" stroke-width="2.8" marker-end="url(#bloch2-dark)"/>
<line x1="{ox}" y1="{oy}" x2="{y_surf[0]}" y2="{y_surf[1]}" stroke="#3b82f6" stroke-width="2.8" marker-end="url(#bloch2-blue)"/>
<circle cx="{ox}" cy="{oy}" r="3" fill="#171717"/>
<circle cx="{z_surf[0]}" cy="{z_surf[1]}" r="3.8" fill="#737373"/>
<circle cx="{z_nsurf[0]}" cy="{z_nsurf[1]}" r="4.5" fill="#171717"/>
<circle cx="{y_surf[0]}" cy="{y_surf[1]}" r="4.5" fill="#3b82f6"/>
<text x="{z_pos[0] + 10}" y="{z_pos[1] + 4}" fill="#737373">+z (|0⟩)</text>
<text x="{x_pos[0] - 6}" y="{x_pos[1] + 16}" text-anchor="middle" fill="#10b981" font-weight="600">转轴 +x</text>
<text x="{z_nsurf[0] + 8}" y="{z_nsurf[1] + 18}" font-weight="600">n⃗₀ = (0,0,-1) |1⟩</text>
<text x="{y_surf[0] + 18}" y="{y_surf[1] - 28}" fill="#3b82f6" font-weight="600">n⃗_f = (0,+1,0)</text>
<text x="{y_surf[0] + 18}" y="{y_surf[1] - 12}" fill="#3b82f6" font-size="11.5">(|1⟩-i|0⟩)/√2</text>
<text x="520" y="214" fill="#f59e0b" font-weight="600">+90°</text>
</g>
</svg>'''


KP_SVGS = {
    "bloch-pure-state-mapping": build_svg_bloch_pure_mixed,
    "bloch-gate-as-3d-rotation": build_svg_bloch_gate_rotation,
}

LEGACY_FILES: dict[str, str] = {}
