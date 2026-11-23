#!/usr/bin/env python3
"""SymPy and NumPy verification for Unit 2 Lesson 1: single-qubit-gates."""

from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import sympy as sp

from _common import (
    assert_no_python_worked,
    load_lesson,
    mat_zero,
    numpy_spin_ops,
    sympy_spin_ops,
)


def _su2_gate(
    theta: sp.Expr | float | int,
    alpha: sp.Expr | float | int,
    beta: sp.Expr | float | int,
    ops: dict[str, sp.Matrix],
) -> sp.Matrix:
    nx = sp.sin(alpha) * sp.cos(beta)
    ny = sp.sin(alpha) * sp.sin(beta)
    nz = sp.cos(alpha)
    n_dot_sigma = nx * ops["sigma_x"] + ny * ops["sigma_y"] + nz * ops["sigma_z"]
    return sp.cos(theta / 2) * ops["I2"] - sp.I * sp.sin(theta / 2) * n_dot_sigma


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Verify symbolic single-qubit gate matrices, SU(2) properties, G&K circuit, and worked examples."""
    del pack_dir  # unused here
    lesson = load_lesson(lesson_path)
    kps = assert_no_python_worked(lesson)

    ops = sympy_spin_ops()
    I2 = ops["I2"]
    sx, sy, sz = ops["sigma_x"], ops["sigma_y"], ops["sigma_z"]
    Sx, Sy, Sz = ops["Sx"], ops["Sy"], ops["Sz"]
    ket0, ket1 = ops["ket_0"], ops["ket_1"]

    theta, alpha, beta, phi = sp.symbols("theta alpha beta phi", real=True)

    # 1. General SU(2) exponential exp(-i * theta * n.S) == cos(theta/2)I - i sin(theta/2)(n.sigma)
    nx = sp.sin(alpha) * sp.cos(beta)
    ny = sp.sin(alpha) * sp.sin(beta)
    nz = sp.cos(alpha)
    n_dot_sigma = nx * sx + ny * sy + nz * sz
    assert mat_zero(n_dot_sigma * n_dot_sigma - I2), "(n.sigma)^2 must equal I2"
    n_dot_S = nx * Sx + ny * Sy + nz * Sz
    assert mat_zero(2 * n_dot_S - n_dot_sigma), "n.S != (n.sigma)/2"
    U_gen = _su2_gate(theta, alpha, beta, ops)
    # Direct matrix exponential checks: exact symbolic for X/Y/Z axes + high-precision arbitrary axis
    assert mat_zero((-sp.I * theta * Sx).exp() - U_gen.subs({alpha: sp.pi / 2, beta: 0}))
    assert mat_zero((-sp.I * theta * Sy).exp() - U_gen.subs({alpha: sp.pi / 2, beta: sp.pi / 2}))
    assert mat_zero((-sp.I * theta * Sz).exp() - U_gen.subs({alpha: 0, beta: 0}))
    U_exp_num = (-sp.I * (sp.pi / 3) * n_dot_S.subs({alpha: sp.pi / 4, beta: sp.pi / 6})).exp()
    U_rot_num = U_gen.subs({theta: sp.pi / 3, alpha: sp.pi / 4, beta: sp.pi / 6})
    max_exp_err = max(abs(complex(entry.evalf(50))) for entry in (U_exp_num - U_rot_num))
    assert max_exp_err < 1e-40, f"General SU(2) expansion mismatch with exp(-i theta n.S): err={max_exp_err}"

    # 2. KP 1: Resonant equatorial pulses (delta = 0 => alpha = pi/2)
    pi2_beta_expected = sp.Matrix(
        [[1, -sp.I * sp.exp(-sp.I * beta)], [-sp.I * sp.exp(sp.I * beta), 1]]
    ) / sp.sqrt(2)
    pi_beta_expected = sp.Matrix(
        [[0, -sp.I * sp.exp(-sp.I * beta)], [-sp.I * sp.exp(sp.I * beta), 0]]
    )
    pi2_beta = _su2_gate(sp.pi / 2, sp.pi / 2, beta, ops)
    pi_beta = _su2_gate(sp.pi, sp.pi / 2, beta, ops)
    assert mat_zero(pi2_beta - pi2_beta_expected), "(pi/2)_beta matrix mismatch"
    assert mat_zero(pi_beta - pi_beta_expected), "(pi)_beta matrix mismatch"

    pi2_x = pi2_beta.subs(beta, 0)
    pi2_y = pi2_beta.subs(beta, sp.pi / 2)
    X_mr = pi_beta.subs(beta, 0)
    Y_mr = pi_beta.subs(beta, sp.pi / 2)

    assert mat_zero(pi2_x - sp.Matrix([[1, -sp.I], [-sp.I, 1]]) / sp.sqrt(2))
    assert mat_zero(pi2_y - sp.Matrix([[1, -1], [1, 1]]) / sp.sqrt(2))
    assert mat_zero(X_mr - (-sp.I * sx)), "(pi)_x != -i sigma_x"
    assert mat_zero(Y_mr - (-sp.I * sy)), "(pi)_y != -i sigma_y"
    # Verify textbook p.7 typo note: beta=pi gives +i*sigma_x != (pi)_x
    pi_beta_pi = pi_beta.subs(beta, sp.pi)
    assert mat_zero(pi_beta_pi - (sp.I * sx))
    assert not mat_zero(pi_beta_pi - X_mr), "Erratum check: beta=pi should not equal (pi)_x"

    # Transfer exercise check: (pi/2)_{-pi/2} == (pi/2)_y^\dagger
    pi2_minus_y = pi2_beta.subs(beta, -sp.pi / 2)
    assert mat_zero(pi2_minus_y * pi2_y - I2), "(pi/2)_{-pi/2} must invert (pi/2)_y"

    # 3. KP 2: Free evolution z-gates (Omega = 0 => alpha = 0) and tilted Hadamard (Omega = delta, beta = 0)
    U_z_theta = _su2_gate(theta, 0, 0, ops)
    U_z_diag = sp.diag(sp.exp(-sp.I * theta / 2), sp.exp(sp.I * theta / 2))
    assert mat_zero(U_z_theta - U_z_diag), "U|_{Omega=0} != diag(e^{-i theta/2}, e^{i theta/2})"

    T_mr = sp.diag(sp.exp(-sp.I * sp.pi / 8), sp.exp(sp.I * sp.pi / 8))
    S_mr = sp.diag(sp.exp(-sp.I * sp.pi / 4), sp.exp(sp.I * sp.pi / 4))
    Z_mr = U_z_theta.subs(theta, sp.pi)
    assert max(abs(complex(x.evalf(50))) for x in (U_z_theta.subs(theta, sp.pi / 4) - T_mr)) < 1e-40
    assert mat_zero(U_z_theta.subs(theta, sp.pi / 2) - sp.expand_complex(S_mr))
    assert mat_zero(Z_mr - sp.diag(-sp.I, sp.I))
    assert mat_zero(Z_mr - (-sp.I * sz)), "Z_MR != -i sigma_z"

    H_mr = _su2_gate(sp.pi, sp.pi / 4, 0, ops)
    H_mr_expected = -sp.I * (sx + sz) / sp.sqrt(2)
    assert mat_zero(H_mr - H_mr_expected), "H_MR != -i (sigma_x + sigma_z)/sqrt(2)"
    assert mat_zero(H_mr - (-sp.I / sp.sqrt(2)) * sp.Matrix([[1, 1], [1, -1]]))
    # Explicit basis-action comparison with (pi/2)_y
    assert mat_zero(H_mr * ket0 - (-sp.I * pi2_y * ket0))
    assert mat_zero(H_mr * ket1 - (sp.I * pi2_y * ket1))
    assert mat_zero(pi2_y * pi2_y - Y_mr)

    # Transfer variant with beta=pi, alpha=pi/4, theta=pi
    H_beta_pi = _su2_gate(sp.pi, sp.pi / 4, sp.pi, ops)
    assert mat_zero(H_beta_pi - (-sp.I / sp.sqrt(2)) * sp.Matrix([[1, -1], [-1, -1]]))

    # 4. SU(2) unitarity (U^\dagger U == I) and det(U) == 1 across all physical pulse gates
    for name, gate in [
        ("U_gen", U_gen),
        ("pi2_beta", pi2_beta),
        ("pi_beta", pi_beta),
        ("pi2_x", pi2_x),
        ("pi2_y", pi2_y),
        ("X_mr", X_mr),
        ("Y_mr", Y_mr),
        ("T_mr", T_mr),
        ("S_mr", S_mr),
        ("Z_mr", Z_mr),
        ("H_mr", H_mr),
    ]:
        assert mat_zero(gate.H * gate - I2), f"{name} failed unitarity U^H U = I"
        det_diff = sp.simplify((sp.det(gate) - 1).rewrite(sp.exp))
        assert det_diff == 0, f"{name} determinant is {sp.det(gate)}, expected 1"

    # 5. KP 3: G&K computational U(2) gates, global phase, and Eq. (11.29) synthesis circuit
    U_H = sp.Matrix([[1, 1], [1, -1]]) / sp.sqrt(2)
    assert sp.simplify(sp.det(U_H) + 1) == 0, "det(U_H) must be -1"
    assert mat_zero(U_H * U_H - I2), "U_H^2 must be +I"
    assert mat_zero(H_mr - (-sp.I * U_H)), "H_MR must equal -i * U_H"
    assert mat_zero(H_mr * H_mr + I2), "H_MR^2 must be -I"

    def U_PG(p: sp.Expr) -> sp.Matrix:
        return sp.diag(1, sp.exp(sp.I * p))

    assert mat_zero(U_PG(phi) - sp.exp(sp.I * phi / 2) * U_z_theta.subs(theta, phi))
    assert mat_zero(U_PG(sp.pi / 4) - sp.exp(sp.I * sp.pi / 8) * T_mr)
    assert mat_zero(U_PG(sp.pi / 2) - sp.exp(sp.I * sp.pi / 4) * S_mr)
    assert mat_zero(U_PG(sp.pi) - sp.I * Z_mr)

    # Exact G&K Eq. (11.29) step-by-step derivation with explicit global phase e^{i*theta}
    g1 = U_H * ket0
    assert mat_zero(g1 - (ket0 + ket1) / sp.sqrt(2))
    g2 = U_PG(2 * theta) * g1
    assert mat_zero(
        g2 - sp.exp(sp.I * theta) * (sp.exp(-sp.I * theta) * ket0 + sp.exp(sp.I * theta) * ket1) / sp.sqrt(2)
    )
    g3 = U_H * g2
    assert mat_zero(g3 - sp.exp(sp.I * theta) * (sp.cos(theta) * ket0 - sp.I * sp.sin(theta) * ket1))
    psi_gk = U_PG(phi + sp.pi / 2) * g3
    psi_target = sp.exp(sp.I * theta) * (
        sp.cos(theta) * ket0 + sp.exp(sp.I * phi) * sp.sin(theta) * ket1
    )
    assert mat_zero(psi_gk - psi_target), "G&K Eq. (11.29) circuit identity failed"

    # SU(2) physical hardware replacement check (u2-l1-su2-phase-transfer)
    psi_mr = (
        U_z_theta.subs(theta, phi + sp.pi / 2)
        * H_mr
        * U_z_theta.subs(theta, 2 * theta)
        * H_mr
        * ket0
    )
    expected_rel_phase = sp.exp(-sp.I * (theta + phi / 2 + sp.Rational(5, 4) * sp.pi))
    assert mat_zero(psi_mr - expected_rel_phase * psi_gk), "Physical SU(2) circuit global-phase relation failed"

    # 6. Numerical worked-example checks (NumPy)
    np_ops = numpy_spin_ops()
    np_ket0 = np_ops["ket_0"]
    np_ket1 = np_ops["ket_1"]

    # Worked 1: Omega / 2pi = 10 MHz
    nu_om_1 = 10e6  # Hz
    t_pi2 = (math.pi / 2) / (2 * math.pi * nu_om_1) * 1e9  # ns
    t_pi = math.pi / (2 * math.pi * nu_om_1) * 1e9  # ns
    assert abs(t_pi2 - 25.0) < 1e-9
    assert abs(t_pi - 50.0) < 1e-9

    np_pi2_y = np.array([[1.0, -1.0], [1.0, 1.0]], dtype=np.complex128) / math.sqrt(2)
    out_pi2_y = np_pi2_y @ np_ket1
    assert np.allclose(out_pi2_y, (-np_ket0 + np_ket1) / math.sqrt(2), atol=1e-12)
    assert np.allclose(np.abs(out_pi2_y.ravel()) ** 2, [0.5, 0.5], atol=1e-12)

    np_X_mr = -1j * np_ops["sigma_x"]
    out_X_mr = np_X_mr @ np_ket1
    assert np.allclose(out_X_mr, -1j * np_ket0, atol=1e-12)

    # Worked 2: Omega/2pi = delta/2pi = 5 MHz
    nu_om_2 = 5e6
    nu_eff_2 = math.sqrt(2) * nu_om_2
    t_H_ns = math.pi / (2 * math.pi * nu_eff_2) * 1e9
    t_S_ns = (math.pi / 2) / (2 * math.pi * nu_om_2) * 1e9
    t_T_ns = (math.pi / 4) / (2 * math.pi * nu_om_2) * 1e9
    t_Z_ns = math.pi / (2 * math.pi * nu_om_2) * 1e9
    assert abs(t_H_ns - 100.0 / math.sqrt(2)) < 1e-9
    assert abs(t_H_ns - 70.71067811865474) < 1e-9
    assert abs(t_S_ns - 50.0) < 1e-9
    assert abs(t_T_ns - 25.0) < 1e-9
    assert abs(t_Z_ns - 100.0) < 1e-9

    # Worked 3: Step-by-step G&K circuit at theta = pi/6, phi = pi/2
    th_num, ph_num = math.pi / 6, math.pi / 2
    np_UH = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / math.sqrt(2)

    def np_UPG(ang: float) -> np.ndarray:
        return np.diag([1.0, np.exp(1j * ang)]).astype(np.complex128)

    s1 = np_UH @ np_ket0
    s2 = np_UPG(2 * th_num) @ s1
    s3 = np_UH @ s2
    s4 = np_UPG(ph_num + math.pi / 2) @ s3
    exp_s3 = np.exp(1j * th_num) * (math.sqrt(3) / 2 * np_ket0 - 0.5j * np_ket1)
    exp_s4 = np.exp(1j * th_num) * (math.sqrt(3) / 2 * np_ket0 + 0.5j * np_ket1)
    assert np.allclose(s3, exp_s3, atol=1e-12)
    assert np.allclose(s4, exp_s4, atol=1e-12)
    probs = np.abs(s4.ravel()) ** 2
    assert np.allclose(probs, [0.75, 0.25], atol=1e-12)

    # Cross-check worked prose numbers in YAML
    w1 = kps["gate-resonant-xy-pulses"]["worked"]
    assert "25" in w1 and "50" in w1
    w2 = kps["gate-z-and-hadamard-pulses"]["worked"]
    assert "70.71" in w2 and "50" in w2 and "25" in w2
    w3 = kps["gate-su2-global-phase-and-circuits"]["worked"]
    assert "3/4" in w3 and "1/4" in w3
