"""Mathematical and worked-example verification for spin-zeeman-and-drive (Lesson 1)."""

from __future__ import annotations

import math
from pathlib import Path

import sympy as sp

from _common import assert_no_python_worked, load_lesson, sympy_spin_ops


def verify_symbolic() -> None:
    ops = sympy_spin_ops()
    sx, sz = ops["Sx"], ops["Sz"]
    ket_0, ket_1 = ops["ket_0"], ops["ket_1"]

    w0, w, t, V, hbar = sp.symbols("w0 w t V hbar", real=True, positive=True)

    # Eqs. (1.1)-(1.4) & Quantum Optics Ch. 4 isomorphism:
    # 2*Sz == sigma_3, 2*Sx == sigma_+ + sigma_-, Omega == V / hbar
    sigma_3 = ket_0 * ket_0.T - ket_1 * ket_1.T
    sigma_p = ket_0 * ket_1.T
    sigma_m = ket_1 * ket_0.T
    assert sp.simplify(2 * sz - sigma_3) == sp.zeros(2, 2), "2*Sz != sigma_3"
    assert sp.simplify(2 * sx - (sigma_p + sigma_m)) == sp.zeros(2, 2), "2*Sx != sigma_+ + sigma_-"

    h_mr = w0 * sz + 2 * (V / hbar) * sp.cos(w * t) * sx
    h_qo = sp.Rational(1, 2) * w0 * sigma_3 + (V / hbar) * sp.cos(w * t) * (sigma_p + sigma_m)
    assert sp.simplify(h_mr - h_qo) == sp.zeros(2, 2), "Spin-dipole Hamiltonian isomorphism mismatch"
    print("[PASS] [spin-zeeman-and-drive] Symbolic Eqs. (1.1)-(1.4) & spin-dipole isomorphism succeeded.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    assert_no_python_worked(lesson)

    # Step 1: NV electron vs proton in B0 = 500 G
    b0_s1 = 500.0
    ge_nv = -2.8033  # MHz/G
    gn_p_khz = 4.2577  # kHz/G (= 4.2577e-3 MHz/G)
    w0_e_mhz = -ge_nv * b0_s1
    w0_p_khz = gn_p_khz * b0_s1
    assert math.isclose(w0_e_mhz, 1401.65, abs_tol=1e-6)
    assert math.isclose(w0_p_khz, 2128.85, abs_tol=1e-6)
    assert math.isclose(w0_e_mhz / (w0_p_khz / 1e3), 658.407, abs_tol=0.5)

    # Step 2: B0 = 200 G, Bx = 10 G, gamma_e/(2pi) = -2.8 MHz/G
    w0_s2 = 2.8 * 200.0
    two_om_s2 = 2.8 * 10.0
    om_s2 = two_om_s2 / 2.0
    assert math.isclose(w0_s2, 560.0, abs_tol=1e-9)
    assert math.isclose(two_om_s2, 28.0, abs_tol=1e-9)
    assert math.isclose(om_s2, 14.0, abs_tol=1e-9)

    # Step 3: V/h = 12 MHz -> Omega/(2pi) = 12 MHz, Bx = 24 / 2.8 = 8.5714 G
    v_mhz = 12.0
    bx_equiv = (2.0 * v_mhz) / 2.8
    assert math.isclose(bx_equiv, 8.57142857, abs_tol=1e-3)
    print("[PASS] [spin-zeeman-and-drive] Worked examples numerical verification succeeded.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic and worked-example checks for spin-zeeman-and-drive."""
    _ = pack_dir
    verify_symbolic()
    verify_worked(lesson_path)
