#!/usr/bin/env python3
"""Shared geometric helpers for programmatic per-lesson SVG generators."""

from __future__ import annotations

import math


def pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return round(cx + r * math.cos(rad), 2), round(cy - r * math.sin(rad), 2)


def arc_path(cx: float, cy: float, r: float, deg_start: float, deg_end: float, sweep_cw: bool) -> str:
    x1, y1 = pt(cx, cy, r, deg_start)
    x2, y2 = pt(cx, cy, r, deg_end)
    large_arc = 1 if abs(deg_end - deg_start) > 180 else 0
    sweep_flag = 1 if sweep_cw else 0
    return f"M{x1} {y1} A{r} {r} 0 {large_arc} {sweep_flag} {x2} {y2}"
