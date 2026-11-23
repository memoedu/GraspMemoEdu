"""Shared symbolic/numerical spin-1/2 primitives and lesson assertion helpers.

Computational spin-1/2 basis convention (matches notation.yaml & Unit 1 lessons):
  |0> = |m_S = +1/2> <-> |e> = [1, 0]^T  (S_z eigenvalue +1/2)
  |1> = |m_S = -1/2> <-> |g> = [0, 1]^T  (S_z eigenvalue -1/2)
Pauli correspondence:
  sigma_x,y,z = 2 * S_x,y,z
  sigma_p = |0><1| = S_+ = S_x + i*S_y,  sigma_m = |1><0| = S_- = S_x - i*S_y
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
import yaml


def mat_zero(m: sp.Matrix) -> bool:
    """Return True iff every entry of a SymPy Matrix simplifies to zero."""
    return m.applyfunc(lambda x: sp.simplify(x.rewrite(sp.exp))) == sp.zeros(m.rows, m.cols)


def sympy_spin_ops() -> dict[str, sp.Matrix]:
    """Return fresh SymPy spin-1/2, Pauli, ladder operators, and basis kets."""
    i2 = sp.eye(2)
    sigma_x = sp.Matrix([[0, 1], [1, 0]])
    sigma_y = sp.Matrix([[0, -sp.I], [sp.I, 0]])
    sigma_z = sp.Matrix([[1, 0], [0, -1]])
    sx = sp.Rational(1, 2) * sigma_x
    sy = sp.Rational(1, 2) * sigma_y
    sz = sp.Rational(1, 2) * sigma_z
    sp_op = sx + sp.I * sy
    sm_op = sx - sp.I * sy
    ket_0 = sp.Matrix([1, 0])
    ket_1 = sp.Matrix([0, 1])
    return {
        "I2": i2,
        "sigma_x": sigma_x,
        "sigma_y": sigma_y,
        "sigma_z": sigma_z,
        "sigma_p": ket_0 * ket_1.T,
        "sigma_m": ket_1 * ket_0.T,
        "Sx": sx,
        "Sy": sy,
        "Sz": sz,
        "Sp": sp_op,
        "Sm": sm_op,
        "ket_0": ket_0,
        "ket_1": ket_1,
    }


def numpy_spin_ops() -> dict[str, np.ndarray]:
    """Return fresh NumPy complex128 spin-1/2, Pauli, ladder operators, and basis kets."""
    i2 = np.eye(2, dtype=complex)
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sigma_y = np.array([[0.0, -1j], [1j, 0.0]], dtype=complex)
    sigma_z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    sx = 0.5 * sigma_x
    sy = 0.5 * sigma_y
    sz = 0.5 * sigma_z
    sp_op = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=complex)
    sm_op = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=complex)
    ket_0 = np.array([1.0, 0.0], dtype=complex)
    ket_1 = np.array([0.0, 1.0], dtype=complex)
    return {
        "I2": i2,
        "sigma_x": sigma_x,
        "sigma_y": sigma_y,
        "sigma_z": sigma_z,
        "sigma_p": sp_op,
        "sigma_m": sm_op,
        "Sx": sx,
        "Sy": sy,
        "Sz": sz,
        "Sp": sp_op.copy(),
        "Sm": sm_op.copy(),
        "ket_0": ket_0,
        "ket_1": ket_1,
    }


def load_lesson(lesson_path: Path) -> dict[str, Any]:
    """Load and validate a lesson YAML mapping."""
    data = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in lesson YAML: {lesson_path}")
    return data


def assert_no_python_worked(lesson: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Assert no KP worked example embeds executable Python blocks and return KP map."""
    kps: dict[str, dict[str, Any]] = {}
    for kp in lesson.get("knowledge_points") or []:
        kp_id = kp["id"]
        worked = kp.get("worked") or ""
        assert "```python" not in worked, f"Unexpected python block in {kp_id}.worked"
        kps[kp_id] = kp
    return kps
