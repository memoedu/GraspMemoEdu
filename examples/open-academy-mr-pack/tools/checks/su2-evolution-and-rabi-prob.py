"""Mathematical and worked-example verification for su2-evolution-and-rabi-prob (Lesson 3)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import sympy as sp

from _common import assert_no_python_worked, load_lesson, mat_zero, numpy_spin_ops, sympy_spin_ops


def verify_symbolic_and_ode_and_jc() -> None:
    ops = sympy_spin_ops()
    sx, sy, sz = ops["Sx"], ops["Sy"], ops["Sz"]
    ket_0, ket_1 = ops["ket_0"], ops["ket_1"]

    Om, phi, t, lam, n = sp.symbols("Om phi t lam n", real=True, positive=True)
    d_real = sp.Symbol("d_real", real=True)

    # Eqs. (1.13)-(1.16): SU(2) evolution operator, U_I|1>, erratum check & Rabi probability
    om_eff = sp.sqrt(Om**2 + d_real**2)
    nx = (Om / om_eff) * sp.cos(phi)
    ny = (Om / om_eff) * sp.sin(phi)
    nz = d_real / om_eff
    theta = om_eff * t
    h_i_eff = d_real * sz + Om * (sp.cos(phi) * sx + sp.sin(phi) * sy)
    h_i_n = om_eff * (nx * sx + ny * sy + nz * sz)
    assert sp.simplify(h_i_eff - h_i_n) == sp.zeros(2, 2), "H_I effective-field form mismatch"

    n_dot_sig_sym = 2 * (nx * sx + ny * sy + nz * sz)
    assert sp.simplify(n_dot_sig_sym * n_dot_sig_sym - sp.eye(2)) == sp.zeros(2, 2), "Symbolic (n.sigma)^2 != I"
    u_i = sp.cos(theta / 2) * sp.eye(2) - sp.I * sp.sin(theta / 2) * n_dot_sig_sym
    assert sp.simplify(u_i.H * u_i - sp.eye(2)) == sp.zeros(2, 2), "U_I unitarity failed"

    # Erratum Eq. (1.15) exact verification:
    psi_exact = u_i * ket_1
    psi_expected = (sp.cos(theta / 2) + sp.I * sp.sin(theta / 2) * nz) * ket_1 - sp.I * sp.sin(theta / 2) * (
        nx - sp.I * ny
    ) * ket_0
    assert sp.simplify(psi_exact - psi_expected) == sp.zeros(2, 1), "Eq. (1.15) U_I|1> mismatch"
    # Verify misprinted formula fails normalization at delta=0 (nz=0), t=0 (theta=0)
    psi_wrong_at_res0 = (
        ((sp.cos(theta / 2) + sp.I * sp.sin(theta / 2)) * nz * ket_1 - sp.I * sp.sin(theta / 2) * (nx - sp.I * ny) * ket_0)
        .subs({d_real: 0, t: 0})
    )
    assert psi_wrong_at_res0 == sp.zeros(2, 1), "Erratum check should vanish at d=0, t=0"

    # Eq. (1.16) Rabi transition probability & pi/2-pulse phase sign check
    p_rabi = sp.simplify(sp.Abs(psi_exact[0]) ** 2)
    p_expected = (Om**2 / (Om**2 + d_real**2)) * sp.sin(om_eff * t / 2) ** 2
    assert sp.simplify(sp.expand_trig(p_rabi - p_expected)) == 0, "Eq. (1.16) Rabi probability mismatch"

    # Verify resonant (delta=0) pi/2 pulse (theta=pi/2) state from |1>:
    # (1/sqrt(2)) (|1> - i * exp(-i*phi) |0>)
    psi_pi2_res = u_i.subs({d_real: 0, theta: sp.pi / 2}) * ket_1
    psi_pi2_expected = (ket_1 - sp.I * sp.exp(-sp.I * phi) * ket_0) / sp.sqrt(2)
    assert mat_zero(psi_pi2_res - psi_pi2_expected), "Resonant pi/2 pulse phase sign mismatch"

    # Gerry & Knight §4.4 coupled amplitude ODEs vs SU(2) formula:
    # d/dt C_g = -i (Om/2) exp(-i d t) C_e, d/dt C_e = -i (Om/2) exp(+i d t) C_g
    # => C_e'' - i d C_e' + (Om^2 / 4) C_e = 0, C_g(0)=1, C_e(0)=0
    c_e = -sp.I * (Om / om_eff) * sp.exp(sp.I * d_real * t / 2) * sp.sin(om_eff * t / 2)
    c_g = sp.exp(-sp.I * d_real * t / 2) * (
        sp.cos(om_eff * t / 2) + sp.I * (d_real / om_eff) * sp.sin(om_eff * t / 2)
    )
    assert c_e.subs(t, 0) == 0 and sp.simplify(c_g.subs(t, 0) - 1) == 0, "ODE initial conditions failed"
    assert sp.simplify(sp.diff(c_g, t) + sp.I * (Om / 2) * sp.exp(-sp.I * d_real * t) * c_e) == 0, "First ODE C_g' failed"
    assert sp.simplify(sp.diff(c_e, t) + sp.I * (Om / 2) * sp.exp(sp.I * d_real * t) * c_g) == 0, "First ODE C_e' failed"
    ode2 = sp.diff(c_e, t, 2) - sp.I * d_real * sp.diff(c_e, t) + (Om**2 / 4) * c_e
    assert sp.simplify(ode2) == 0, "Second-order ODE C_e'' - i*d*C_e' + (Om^2/4)C_e == 0 failed"
    assert sp.simplify(sp.expand_trig(sp.Abs(c_e) ** 2 + sp.Abs(c_g) ** 2 - 1)) == 0, "ODE normalization != 1"
    assert sp.simplify(sp.expand_trig(sp.Abs(c_e) ** 2 - p_expected)) == 0, "ODE |C_e|^2 != SU(2) P_rabi"

    # Population inversion W(t) = 2P(t) - 1, resonant pi and pi/2 pulses
    w_sym = 2 * p_expected - 1
    w_res = sp.simplify(w_sym.subs(d_real, 0))
    assert sp.simplify(w_res + sp.cos(Om * t)) == 0, "Resonant W(t) != -cos(Om*t)"
    assert w_res.subs(t, sp.pi / Om) == 1, "pi pulse W != +1"
    assert w_res.subs(t, sp.pi / (2 * Om)) == 0, "pi/2 pulse W != 0"

    # Gerry & Knight §4.5 Jaynes-Cummings 2x2 block in {|e, n>, |g, n+1>} at resonance
    g_n = lam * sp.sqrt(n + 1)
    h_jc_int = sp.Matrix([[0, g_n], [g_n, 0]])
    u_jc = sp.exp(-sp.I * h_jc_int * t)
    psi_jc = sp.simplify(u_jc * sp.Matrix([1, 0]))
    p_jc = sp.simplify(sp.Abs(psi_jc[1]) ** 2)
    assert sp.simplify(p_jc - sp.sin(lam * sp.sqrt(n + 1) * t) ** 2) == 0, "JC probability mismatch"
    assert sp.simplify(2 * g_n - 2 * lam * sp.sqrt(n + 1)) == 0, "JC quantized Rabi Omega(n) mismatch"
    assert sp.simplify((2 * g_n).subs(n, 0) - 2 * lam) == 0, "Vacuum Rabi Omega(0) != 2*lam"
    print("[PASS] [su2-evolution-and-rabi-prob] Symbolic Eqs. (1.13)-(1.16), ODE duality, and JC model succeeded.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    assert_no_python_worked(lesson)

    # Step 1 & Step 2: Om/2pi = 6 MHz, delta/2pi = 8 MHz, phi = 0, t = 25 ns
    om_mhz = 6.0
    delta_mhz = 8.0
    om_eff_mhz = math.hypot(om_mhz, delta_mhz)
    assert math.isclose(om_eff_mhz, 10.0, abs_tol=1e-12)
    n_vec = np.array([om_mhz / om_eff_mhz, 0.0, delta_mhz / om_eff_mhz])
    assert np.max(np.abs(n_vec - np.array([0.6, 0.0, 0.8]))) < 1e-12

    t_ns = 25.0
    theta = (2.0 * math.pi * om_eff_mhz * 1e6) * (t_ns * 1e-9)
    assert math.isclose(theta, math.pi / 2.0, abs_tol=1e-12)

    np_ops = numpy_spin_ops()
    sigma = [np_ops["sigma_x"], np_ops["sigma_y"], np_ops["sigma_z"]]
    n_dot_sig = sum(n_vec[i] * sigma[i] for i in range(3))
    u_i = math.cos(theta / 2) * np.eye(2) - 1j * math.sin(theta / 2) * n_dot_sig
    u_expected = (np.eye(2) - 1j * (0.6 * sigma[0] + 0.8 * sigma[2])) / math.sqrt(2.0)
    assert np.max(np.abs(u_i - u_expected)) < 1e-12

    ket_1, ket_0 = np_ops["ket_1"], np_ops["ket_0"]
    psi = u_i @ ket_1
    psi_expected = ((1.0 + 0.8j) / math.sqrt(2.0)) * ket_1 - (0.6j / math.sqrt(2.0)) * ket_0
    assert np.max(np.abs(psi - psi_expected)) < 1e-12
    p0 = abs(np.vdot(ket_0, psi)) ** 2
    p1 = abs(np.vdot(ket_1, psi)) ** 2
    assert math.isclose(p0, 0.18, abs_tol=1e-12)
    assert math.isclose(p1, 0.82, abs_tol=1e-12)
    p_max = (om_mhz**2) / (om_mhz**2 + delta_mhz**2)
    assert math.isclose(p_max, 0.36, abs_tol=1e-12)

    # Step 3: Om/2pi = 10 MHz pulses and JC lambda/2pi = 5 MHz (n=0, n=8)
    assert math.isclose(1e3 / (2.0 * 10.0), 50.0, abs_tol=1e-12)
    assert math.isclose(1e3 / (4.0 * 10.0), 25.0, abs_tol=1e-12)
    assert math.isclose(2 * 5.0 * math.sqrt(0 + 1), 10.0, abs_tol=1e-12)
    assert math.isclose(2 * 5.0 * math.sqrt(8 + 1), 30.0, abs_tol=1e-12)
    assert math.isclose(1e3 / (2.0 * 30.0), 16.66666667, abs_tol=1e-4)

    print("[PASS] [su2-evolution-and-rabi-prob] Worked examples numerical verification succeeded.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic and worked-example checks for su2-evolution-and-rabi-prob."""
    _ = pack_dir
    verify_symbolic_and_ode_and_jc()
    verify_worked(lesson_path)
