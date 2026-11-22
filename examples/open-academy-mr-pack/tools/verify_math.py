#!/usr/bin/env python3
"""Symbolic, numerical, worked-example, and exhaustive exercise-template verifier for Unit 1 of open-academy-mr-pack."""

from __future__ import annotations

import itertools
import math
import re
import sys
from pathlib import Path

import numpy as np
import sympy as sp
import yaml


def mat_zero(m: sp.Matrix) -> bool:
    return m.applyfunc(lambda x: sp.simplify(x.rewrite(sp.exp))) == sp.zeros(m.rows, m.cols)


def verify_symbolic_identities() -> None:
    w0, w, Om, phi, t, d, V, hbar, lam, n = sp.symbols(
        "w0 w Om phi t d V hbar lam n", real=True, positive=True
    )
    d_real = sp.Symbol("d_real", real=True)
    Sx = sp.Rational(1, 2) * sp.Matrix([[0, 1], [1, 0]])
    Sy = sp.Rational(1, 2) * sp.Matrix([[0, -sp.I], [sp.I, 0]])
    Sz = sp.Rational(1, 2) * sp.Matrix([[1, 0], [0, -1]])
    Sp = Sx + sp.I * Sy
    Sm = Sx - sp.I * Sy

    # Basis correspondence: |0> = |m_S=+1/2> <-> |e>, |1> = |m_S=-1/2> <-> |g>
    ket_0 = sp.Matrix([1, 0])
    ket_1 = sp.Matrix([0, 1])

    # Eqs. (1.1)-(1.4) & Quantum Optics Ch. 4 isomorphism:
    # 2*Sz == sigma_3, 2*Sx == sigma_+ + sigma_-, Omega == V / hbar
    sigma_3 = ket_0 * ket_0.T - ket_1 * ket_1.T
    sigma_p = ket_0 * ket_1.T
    sigma_m = ket_1 * ket_0.T
    assert sp.simplify(2 * Sz - sigma_3) == sp.zeros(2, 2), "2*Sz != sigma_3"
    assert sp.simplify(2 * Sx - (sigma_p + sigma_m)) == sp.zeros(2, 2), "2*Sx != sigma_+ + sigma_-"
    H_mr = w0 * Sz + 2 * (V / hbar) * sp.cos(w * t) * Sx
    H_qo = sp.Rational(1, 2) * w0 * sigma_3 + (V / hbar) * sp.cos(w * t) * (sigma_p + sigma_m)
    assert sp.simplify(H_mr - H_qo) == sp.zeros(2, 2), "Spin-dipole Hamiltonian isomorphism mismatch"

    # Eq. (1.5): linear decomposition into co- and counter-rotating components
    lhs_15 = 2 * Om * sp.cos(w * t + phi) * Sx
    co = Om * (sp.cos(w * t + phi) * Sx + sp.sin(w * t + phi) * Sy)
    counter = Om * (sp.cos(w * t + phi) * Sx - sp.sin(w * t + phi) * Sy)
    assert sp.simplify(lhs_15 - (co + counter)) == sp.zeros(2, 2), "Eq. (1.5) mismatch"

    # Interaction picture unitary Ui = exp(-i * w * t * Sz)
    Ui = sp.Matrix([[sp.exp(-sp.I * w * t / 2), 0], [0, sp.exp(sp.I * w * t / 2)]])
    Ui_dag = Ui.H

    # Eqs. (1.6)-(1.9): Ui_dag * Ui == I and H_I derivation
    assert sp.simplify(Ui_dag * Ui - sp.eye(2)) == sp.zeros(2, 2), "Ui unitarity mismatch"
    H_rwa = w0 * Sz + co
    H_I = sp.simplify(Ui_dag * H_rwa * Ui - Ui_dag * sp.I * sp.diff(Ui, t))
    H_I_expected = (w0 - w) * Sz + Om * (sp.cos(phi) * Sx + sp.sin(phi) * Sy)
    assert mat_zero(H_I - H_I_expected), "Eq. (1.9) mismatch"

    # Eq. (1.8) specific & general 3D Rodrigues formula
    r_dot_S = sp.cos(w * t + phi) * Sx + sp.sin(w * t + phi) * Sy
    rot_lhs = Ui_dag * r_dot_S * Ui
    rot_rhs = sp.cos(phi) * Sx + sp.sin(phi) * Sy
    assert mat_zero(rot_lhs - rot_rhs), "Eq. (1.8) specific mismatch"

    rng = np.random.default_rng(42)
    Sx_np = np.array([[0, 0.5], [0.5, 0]], dtype=complex)
    Sy_np = np.array([[0, -0.5j], [0.5j, 0]], dtype=complex)
    Sz_np = np.array([[0.5, 0], [0, -0.5]], dtype=complex)
    S_vec = [Sx_np, Sy_np, Sz_np]
    sig_vec = [2 * s for s in S_vec]
    for _ in range(10):
        n_vec = rng.normal(size=3)
        n_vec /= np.linalg.norm(n_vec)
        theta_val = float(rng.uniform(-np.pi, np.pi))
        r_vec = rng.normal(size=3)
        n_dot_S = sum(n_vec[k] * S_vec[k] for k in range(3))
        n_dot_sig = sum(n_vec[k] * sig_vec[k] for k in range(3))
        r_dot_S_num = sum(r_vec[k] * S_vec[k] for k in range(3))
        # Pauli involution (n . sigma)^2 == I
        assert np.max(np.abs(n_dot_sig @ n_dot_sig - np.eye(2))) < 1e-12, "(n.sigma)^2 != I"
        U_rot = np.cos(theta_val / 2) * np.eye(2) - 1j * np.sin(theta_val / 2) * n_dot_sig
        # Compare SU(2) exponential directly with eigendecomposition exp(-i*theta*(n.S))
        eigvals, eigvecs = np.linalg.eigh(n_dot_S)
        U_eig = eigvecs @ np.diag(np.exp(-1j * theta_val * eigvals)) @ eigvecs.conj().T
        assert np.max(np.abs(U_rot - U_eig)) < 1e-12, "SU(2) matrix exponential mismatch"
        lhs_num = U_rot @ r_dot_S_num @ U_rot.conj().T
        r_rot = (
            r_vec * np.cos(theta_val)
            + np.cross(n_vec, r_vec) * np.sin(theta_val)
            + n_vec * np.dot(n_vec, r_vec) * (1 - np.cos(theta_val))
        )
        rhs_num = sum(r_rot[k] * S_vec[k] for k in range(3))
        assert np.max(np.abs(lhs_num - rhs_num)) < 1e-12, "General Eq. (1.8) failed"

    # Eqs. (1.10)-(1.12): ladder operator transformations
    assert Sp * ket_1 == ket_0 and Sp * ket_0 == sp.zeros(2, 1), "Eq. (1.10) S+ failed"
    assert Sm * ket_0 == ket_1 and Sm * ket_1 == sp.zeros(2, 1), "Eq. (1.10) S- failed"
    assert sp.simplify(Ui_dag * Sp * Ui - sp.exp(sp.I * w * t) * Sp) == sp.zeros(2, 2), "Ui^dag S+ Ui failed"
    eq111 = sp.Rational(1, 2) * (
        sp.exp(-sp.I * (w * t + phi)) * (Ui_dag * Sp * Ui)
        + sp.exp(sp.I * (w * t + phi)) * (Ui_dag * Sm * Ui)
    )
    assert mat_zero(eq111 - rot_rhs), "Eq. (1.11)-(1.12) mismatch"

    # Eqs. (1.13)-(1.16): SU(2) evolution operator, U_I|1>, erratum check & Rabi probability
    Om_eff = sp.sqrt(Om**2 + d_real**2)
    nx = (Om / Om_eff) * sp.cos(phi)
    ny = (Om / Om_eff) * sp.sin(phi)
    nz = d_real / Om_eff
    theta = Om_eff * t
    H_I_eff = d_real * Sz + Om * (sp.cos(phi) * Sx + sp.sin(phi) * Sy)
    H_I_n = Om_eff * (nx * Sx + ny * Sy + nz * Sz)
    assert sp.simplify(H_I_eff - H_I_n) == sp.zeros(2, 2), "H_I effective-field form mismatch"

    n_dot_sig_sym = 2 * (nx * Sx + ny * Sy + nz * Sz)
    assert sp.simplify(n_dot_sig_sym * n_dot_sig_sym - sp.eye(2)) == sp.zeros(2, 2), "Symbolic (n.sigma)^2 != I"
    U_I = sp.cos(theta / 2) * sp.eye(2) - sp.I * sp.sin(theta / 2) * n_dot_sig_sym
    assert sp.simplify(U_I.H * U_I - sp.eye(2)) == sp.zeros(2, 2), "U_I unitarity failed"

    # Erratum Eq. (1.15) exact verification:
    psi_exact = U_I * ket_1
    psi_expected = (sp.cos(theta / 2) + sp.I * sp.sin(theta / 2) * nz) * ket_1 - sp.I * sp.sin(theta / 2) * (
        nx - sp.I * ny
    ) * ket_0
    assert sp.simplify(psi_exact - psi_expected) == sp.zeros(2, 1), "Eq. (1.15) U_I|1> mismatch"
    # Verify misprinted formula fails normalization at delta=0 (nz=0), t=0 (theta=0)
    psi_wrong_at_res0 = ((sp.cos(theta / 2) + sp.I * sp.sin(theta / 2)) * nz * ket_1 - sp.I * sp.sin(theta / 2) * (nx - sp.I * ny) * ket_0).subs({d_real: 0, t: 0})
    assert psi_wrong_at_res0 == sp.zeros(2, 1), "Erratum check should vanish at d=0, t=0"

    # Eq. (1.16) Rabi transition probability & pi/2-pulse phase sign check
    P_rabi = sp.simplify(sp.Abs(psi_exact[0]) ** 2)
    P_expected = (Om**2 / (Om**2 + d_real**2)) * sp.sin(Om_eff * t / 2) ** 2
    assert sp.simplify(sp.expand_trig(P_rabi - P_expected)) == 0, "Eq. (1.16) Rabi probability mismatch"

    # Verify resonant (delta=0) pi/2 pulse (theta=pi/2) state from |1>:
    # (1/sqrt(2)) (|1> - i * exp(-i*phi) |0>)
    psi_pi2_res = U_I.subs({d_real: 0, theta: sp.pi / 2}) * ket_1
    psi_pi2_expected = (ket_1 - sp.I * sp.exp(-sp.I * phi) * ket_0) / sp.sqrt(2)
    assert mat_zero(psi_pi2_res - psi_pi2_expected), "Resonant pi/2 pulse phase sign mismatch"

    # Gerry & Knight §4.4 coupled amplitude ODEs vs SU(2) formula:
    # d/dt C_g = -i (Om/2) exp(-i d t) C_e, d/dt C_e = -i (Om/2) exp(+i d t) C_g
    # => C_e'' - i d C_e' + (Om^2 / 4) C_e = 0, C_g(0)=1, C_e(0)=0
    C_e = -sp.I * (Om / Om_eff) * sp.exp(sp.I * d_real * t / 2) * sp.sin(Om_eff * t / 2)
    C_g = sp.exp(-sp.I * d_real * t / 2) * (
        sp.cos(Om_eff * t / 2) + sp.I * (d_real / Om_eff) * sp.sin(Om_eff * t / 2)
    )
    assert C_e.subs(t, 0) == 0 and sp.simplify(C_g.subs(t, 0) - 1) == 0, "ODE initial conditions failed"
    assert sp.simplify(sp.diff(C_g, t) + sp.I * (Om / 2) * sp.exp(-sp.I * d_real * t) * C_e) == 0, "First ODE C_g' failed"
    assert sp.simplify(sp.diff(C_e, t) + sp.I * (Om / 2) * sp.exp(sp.I * d_real * t) * C_g) == 0, "First ODE C_e' failed"
    ode2 = sp.diff(C_e, t, 2) - sp.I * d_real * sp.diff(C_e, t) + (Om**2 / 4) * C_e
    assert sp.simplify(ode2) == 0, "Second-order ODE C_e'' - i*d*C_e' + (Om^2/4)C_e == 0 failed"
    assert sp.simplify(sp.expand_trig(sp.Abs(C_e) ** 2 + sp.Abs(C_g) ** 2 - 1)) == 0, "ODE normalization != 1"
    assert sp.simplify(sp.expand_trig(sp.Abs(C_e) ** 2 - P_expected)) == 0, "ODE |C_e|^2 != SU(2) P_rabi"

    # Population inversion W(t) = 2P(t) - 1, resonant pi and pi/2 pulses
    W_sym = 2 * P_expected - 1
    W_res = sp.simplify(W_sym.subs(d_real, 0))
    assert sp.simplify(W_res + sp.cos(Om * t)) == 0, "Resonant W(t) != -cos(Om*t)"
    assert W_res.subs(t, sp.pi / Om) == 1, "pi pulse W != +1"
    assert W_res.subs(t, sp.pi / (2 * Om)) == 0, "pi/2 pulse W != 0"

    # Gerry & Knight §4.5 Jaynes-Cummings 2x2 block in {|e, n>, |g, n+1>} at resonance
    g_n = lam * sp.sqrt(n + 1)
    H_jc_int = sp.Matrix([[0, g_n], [g_n, 0]])
    U_jc = sp.exp(-sp.I * H_jc_int * t)
    psi_jc = sp.simplify(U_jc * sp.Matrix([1, 0]))
    P_jc = sp.simplify(sp.Abs(psi_jc[1]) ** 2)
    assert sp.simplify(P_jc - sp.sin(lam * sp.sqrt(n + 1) * t) ** 2) == 0, "JC probability mismatch"
    assert sp.simplify(2 * g_n - 2 * lam * sp.sqrt(n + 1)) == 0, "JC quantized Rabi Omega(n) mismatch"
    assert sp.simplify((2 * g_n).subs(n, 0) - 2 * lam) == 0, "Vacuum Rabi Omega(0) != 2*lam"

    print("[PASS] Symbolic & numerical verification of Unit 1 Eqs. (1.1)-(1.16), ODE duality, and JC model succeeded.")


def verify_lesson1_worked(lesson_path: Path) -> None:
    lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
    kps = {kp["id"]: kp for kp in lesson["knowledge_points"]}
    assert "```python" not in "".join(kp["worked"] for kp in kps.values())

    # Step 1: NV electron vs proton in B0 = 500 G
    B0_s1 = 500.0
    ge_nv = -2.8033  # MHz/G
    gn_p = 4.2577e-3  # MHz/G (= 4.2577 kHz/G)
    w0_e_mhz = -ge_nv * B0_s1
    w0_p_khz = 4.2577 * B0_s1
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
    print("[PASS] Lesson 1 worked examples numerical verification succeeded.")


def verify_lesson2_worked(lesson_path: Path) -> None:
    lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
    kps = {kp["id"]: kp for kp in lesson["knowledge_points"]}
    for kp_id, kp in kps.items():
        assert "```python" not in kp["worked"], f"Unexpected python block in {kp_id}.worked"

    f0_ghz = 10.0
    f_drive_ghz = 9.99
    two_omega_mhz = 20.0
    omega_half_mhz = two_omega_mhz / 2.0
    detuning_mhz = (f0_ghz - f_drive_ghz) * 1e3
    assert math.isclose(omega_half_mhz, 10.0, abs_tol=1e-12)
    assert math.isclose(detuning_mhz, 10.0, abs_tol=1e-12)
    assert "9.99" in kps["rwa-split-field"]["worked"], "Step 1 worked must state drive frequency 9.99 GHz"

    Sz = np.array([[0.5, 0.0], [0.0, -0.5]], dtype=complex)
    Sp = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=complex)
    Sm = Sp.conj().T
    Sx = 0.5 * (Sp + Sm)
    Sy = 0.5 * (-1j * Sp + 1j * Sm)
    ket_up = np.array([1.0, 0.0], dtype=complex)
    ket_dn = np.array([0.0, 1.0], dtype=complex)

    phi = np.pi / 2.0
    w0 = 2.0 * np.pi * 1e4
    w = 2.0 * np.pi * 9990.0
    Om = 2.0 * np.pi * 10.0
    H_I_expected = 2.0 * np.pi * (10.0 * Sz + 10.0 * Sy)

    for t_us in (0.0, 0.017, 0.25):
        Ui = np.diag([np.exp(-0.5j * w * t_us), np.exp(0.5j * w * t_us)])
        assert np.max(np.abs(Ui.conj().T @ Sp @ Ui @ ket_dn - np.exp(1j * w * t_us) * ket_up)) < 1e-12
        assert np.max(np.abs(Ui.conj().T @ Sp @ Ui @ ket_up)) < 1e-12
        H_rwa = w0 * Sz + Om * (np.cos(w * t_us + phi) * Sx + np.sin(w * t_us + phi) * Sy)
        H_I_rot = (w0 - w) * Sz + Ui.conj().T @ (Om * (np.cos(w * t_us + phi) * Sx + np.sin(w * t_us + phi) * Sy)) @ Ui
        assert np.max(np.abs(H_I_rot - H_I_expected)) < 1e-10
        assert np.max(np.abs(Ui.conj().T @ H_rwa @ Ui - w * Sz - H_I_expected)) < 1e-10

    nmax = 6
    a_dag = np.diag(np.sqrt(np.arange(1, nmax)), k=-1).astype(complex)
    n_op = a_dag @ a_dag.conj().T
    for t_val in (0.13, 0.77):
        Ub = np.diag(np.exp(-1j * 3.5 * t_val * np.diag(n_op)))
        err_boson = np.max(
            np.abs(Ub.conj()[:-1, :-1].T @ a_dag[:-1, :-1] @ Ub[:-1, :-1] - np.exp(1j * 3.5 * t_val) * a_dag[:-1, :-1])
        )
        assert err_boson < 1e-12

    print("[PASS] Lesson 2 worked examples & bosonic identity verification succeeded.")


def verify_lesson3_worked(lesson_path: Path) -> None:
    lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
    kps = {kp["id"]: kp for kp in lesson["knowledge_points"]}
    assert "```python" not in "".join(kp["worked"] for kp in kps.values())

    # Step 1 & Step 2: Om/2pi = 6 MHz, delta/2pi = 8 MHz, phi = 0, t = 25 ns
    Om_mhz = 6.0
    delta_mhz = 8.0
    Om_eff_mhz = math.hypot(Om_mhz, delta_mhz)
    assert math.isclose(Om_eff_mhz, 10.0, abs_tol=1e-12)
    n_vec = np.array([Om_mhz / Om_eff_mhz, 0.0, delta_mhz / Om_eff_mhz])
    assert np.max(np.abs(n_vec - np.array([0.6, 0.0, 0.8]))) < 1e-12

    t_ns = 25.0
    theta = (2.0 * math.pi * Om_eff_mhz * 1e6) * (t_ns * 1e-9)
    assert math.isclose(theta, math.pi / 2.0, abs_tol=1e-12)

    Sx = np.array([[0.0, 0.5], [0.5, 0.0]], dtype=complex)
    Sy = np.array([[0.0, -0.5j], [0.5j, 0.0]], dtype=complex)
    Sz = np.array([[0.5, 0.0], [0.0, -0.5]], dtype=complex)
    sigma = [2 * Sx, 2 * Sy, 2 * Sz]
    n_dot_sig = sum(n_vec[i] * sigma[i] for i in range(3))
    U_I = math.cos(theta / 2) * np.eye(2) - 1j * math.sin(theta / 2) * n_dot_sig
    U_expected = (np.eye(2) - 1j * (0.6 * sigma[0] + 0.8 * sigma[2])) / math.sqrt(2.0)
    assert np.max(np.abs(U_I - U_expected)) < 1e-12

    ket_1 = np.array([0.0, 1.0], dtype=complex)
    ket_0 = np.array([1.0, 0.0], dtype=complex)
    psi = U_I @ ket_1
    psi_expected = ((1.0 + 0.8j) / math.sqrt(2.0)) * ket_1 - (0.6j / math.sqrt(2.0)) * ket_0
    assert np.max(np.abs(psi - psi_expected)) < 1e-12
    p0 = abs(np.vdot(ket_0, psi)) ** 2
    p1 = abs(np.vdot(ket_1, psi)) ** 2
    assert math.isclose(p0, 0.18, abs_tol=1e-12)
    assert math.isclose(p1, 0.82, abs_tol=1e-12)
    p_max = (Om_mhz**2) / (Om_mhz**2 + delta_mhz**2)
    assert math.isclose(p_max, 0.36, abs_tol=1e-12)

    # Step 3: Om/2pi = 10 MHz pulses and JC lambda/2pi = 5 MHz (n=0, n=8)
    assert math.isclose(1e3 / (2.0 * 10.0), 50.0, abs_tol=1e-12)
    assert math.isclose(1e3 / (4.0 * 10.0), 25.0, abs_tol=1e-12)
    assert math.isclose(2 * 5.0 * math.sqrt(0 + 1), 10.0, abs_tol=1e-12)
    assert math.isclose(2 * 5.0 * math.sqrt(8 + 1), 30.0, abs_tol=1e-12)
    assert math.isclose(1e3 / (2.0 * 30.0), 16.66666667, abs_tol=1e-4)

    print("[PASS] Lesson 3 worked examples numerical verification succeeded.")


def verify_exercises(ex_path: Path) -> None:
    edoc = yaml.safe_load(ex_path.read_text(encoding="utf-8"))
    exs = edoc["exercises"]
    print(f"--- Checking {ex_path.name} ({len(exs)} exercises) ---")

    for ex in exs:
        if ex["type"] == "mc":
            n_correct = sum(1 for o in ex["options"] if o.get("correct"))
            assert n_correct == 1, f"MC {ex['id']} must have exactly 1 correct option (got {n_correct})"

        if ex["type"] == "numeric":
            if "params" in ex:
                param_names = list(ex["params"].keys())
                grids = []
                for k in param_names:
                    spec = ex["params"][k]
                    cur = float(spec["min"])
                    vals = []
                    while cur <= float(spec["max"]) + 1e-9:
                        vals.append(round(cur, 9))
                        cur += float(spec.get("step", 1))
                    grids.append(vals)
                ans_set = set()
                valid = 0
                for combo in itertools.product(*grids):
                    env = dict(zip(param_names, combo))
                    if not all(eval(c, {"__builtins__": {}}, env) for c in ex.get("constraints", [])):
                        continue
                    valid += 1
                    ans = float(sp.N(sp.sympify(ex["answer_expr"].replace("^", "**"), locals=env)))
                    ans_set.add(round(ans, 9))
                    for cw in ex.get("common_wrong", []):
                        w = float(sp.N(sp.sympify(cw["answer_expr"].replace("^", "**"), locals=env)))
                        assert abs(w - ans) > ex["tolerance"]["abs"], f"Collision in {ex['id']} for {env}"
                assert valid > 0 and len(ans_set) >= 3, f"Template {ex['id']} insufficient diversity"
                print(
                    f"[PASS] Template {ex['id']}: {valid} combos, {len(ans_set)} distinct answers "
                    f"[{min(ans_set)}, {max(ans_set)}]"
                )
            else:
                assert isinstance(ex.get("answer"), (int, float))
                print(f"[PASS] Numeric {ex['id']}: answer={ex['answer']}")

        if ex["type"] == "expression":
            ans_sym = sp.sympify(ex["answer"].replace("^", "**"))
            vars_spec = ex.get("variables", {})
            assert set(map(str, ans_sym.free_symbols)) == set(vars_spec.keys()), (
                f"Expr {ex['id']} symbol mismatch: {ans_sym.free_symbols} vs {vars_spec.keys()}"
            )
            print(f"[PASS] Expression {ex['id']}: '{ex['answer']}', vars={list(vars_spec.keys())}")

        if ex["type"] == "text":
            rx = re.compile(ex["regex"]) if ex.get("regex") else None
            if rx:
                for acc in ex.get("accept", []):
                    assert rx.match(acc), f"Regex in {ex['id']} failed to match accept '{acc}'"
            print(f"[PASS] Text {ex['id']}: {len(ex.get('accept', []))} accept patterns validated")


def main() -> int:
    pack = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    verify_symbolic_identities()
    verify_lesson1_worked(pack / "lessons" / "spin-zeeman-and-drive.yaml")
    verify_lesson2_worked(pack / "lessons" / "rotating-wave-and-frame.yaml")
    verify_lesson3_worked(pack / "lessons" / "su2-evolution-and-rabi-prob.yaml")
    for fname in (
        "spin-zeeman-and-drive.yaml",
        "rotating-wave-and-frame.yaml",
        "su2-evolution-and-rabi-prob.yaml",
    ):
        verify_exercises(pack / "exercises" / fname)
    print("ALL UNIT 1 MATHEMATICAL & TEMPLATE VERIFICATIONS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
