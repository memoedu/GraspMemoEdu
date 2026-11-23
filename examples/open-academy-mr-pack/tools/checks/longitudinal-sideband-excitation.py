"""Mathematical and worked-example verification for longitudinal-sideband-excitation (Unit 2 Concept 4)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import scipy.special as sc
import sympy as sp

from _common import assert_no_python_worked, load_lesson, mat_zero, numpy_spin_ops, sympy_spin_ops


def verify_symbolic_and_bessel() -> None:
    ops = sympy_spin_ops()
    sx, sy, sz = ops["Sx"], ops["Sy"], ops["Sz"]
    sp_op, sm_op = ops["Sp"], ops["Sm"]

    w0, w, wz, Om, Omz, chi, ph, phz, jn, dn, t = sp.symbols(
        "w0 w wz Om Omz chi ph phz jn dn t", real=True
    )

    # 1. Factor 1/2 ladder identity (fixing textbook Eqs. 1.26, 1.28, 1.30, 1.31)
    trans_trig = sp.cos(w * t + ph) * sx + sp.sin(w * t + ph) * sy
    trans_ladder = sp.Rational(1, 2) * (
        sp.exp(-sp.I * (w * t + ph)) * sp_op + sp.exp(sp.I * (w * t + ph)) * sm_op
    )
    assert mat_zero(trans_trig - trans_ladder), "Ladder conversion must keep factor 1/2"
    assert not mat_zero(trans_trig - 2 * trans_ladder), "Dropping 1/2 doubles transverse operator"

    # 2. Time-dependent interaction frame Ui(t) = exp(-i * [w0*t + (Omz/wz)*sin(wz*t + phz)] * Sz)
    theta_t = w0 * t + (Omz / wz) * sp.sin(wz * t + phz)
    ui = sp.Matrix([[sp.exp(-sp.I * theta_t / 2), 0], [0, sp.exp(sp.I * theta_t / 2)]])
    ui_dag = ui.H
    assert mat_zero(ui_dag * ui - sp.eye(2)), "Ui(t) must be unitary"
    assert mat_zero(ui * sz - sz * ui), "Ui(t) must commute with Sz"
    # Verify scalar-like derivative holds since [Theta(t)*Sz, dTheta/dt*Sz] == 0
    assert mat_zero(sp.diff(ui, t) + sp.I * sp.diff(theta_t, t) * sz * ui)

    h_total = (w0 + Omz * sp.cos(wz * t + phz)) * sz + Om * trans_trig
    h_i_deriv = ui_dag * h_total * ui - ui_dag * sp.I * sp.diff(ui, t)
    phase_mod = sp.exp(sp.I * (Omz / wz) * sp.sin(wz * t + phz))
    h_i_eq128 = sp.Rational(1, 2) * Om * (
        sp.exp(sp.I * ((w0 - w) * t - ph)) * phase_mod * sp_op
        + sp.exp(-sp.I * ((w0 - w) * t - ph)) * sp.conjugate(phase_mod) * sm_op
    )
    assert mat_zero(h_i_deriv - h_i_eq128), "Eq. (1.28) symbolic derivation mismatch"

    # Numerical derivative verification of U_i(t) at random t and parameters (< 1e-12)
    np_ops = numpy_spin_ops()
    np_sx, np_sy, np_sz = np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]
    np_sp, np_sm = np_ops["Sp"], np_ops["Sm"]
    rng = np.random.default_rng(2026)
    for _ in range(10):
        v_w0 = float(rng.uniform(5.0, 20.0))
        v_w = float(rng.uniform(4.0, 21.0))
        v_wz = float(rng.uniform(0.5, 4.0))
        v_omz = float(rng.uniform(0.1, 3.0))
        v_om = float(rng.uniform(0.1, 2.0))
        v_ph = float(rng.uniform(-np.pi, np.pi))
        v_phz = float(rng.uniform(-np.pi, np.pi))
        v_t = float(rng.uniform(0.0, 10.0))
        v_chi = v_omz / v_wz

        th = v_w0 * v_t + v_chi * math.sin(v_wz * v_t + v_phz)
        dth_dt = v_w0 + v_omz * math.cos(v_wz * v_t + v_phz)
        u_num = np.diag([np.exp(-0.5j * th), np.exp(0.5j * th)])
        du_dt = -1j * dth_dt * (np_sz @ u_num)
        h_num = dth_dt * np_sz + v_om * (math.cos(v_w * v_t + v_ph) * np_sx + math.sin(v_w * v_t + v_ph) * np_sy)
        h_i_num = u_num.conj().T @ h_num @ u_num - 1j * (u_num.conj().T @ du_dt)

        fac = 0.5 * v_om * np.exp(1j * ((v_w0 - v_w) * v_t - v_ph)) * np.exp(1j * v_chi * math.sin(v_wz * v_t + v_phz))
        h_i_ref = fac * np_sp + np.conj(fac) * np_sm
        assert np.max(np.abs(h_i_num - h_i_ref)) < 1e-12, "Numerical Ui(t) Eq. (1.28) check failed"

        # 3. Jacobi-Anger truncation check |n| <= 25 (< 1e-12)
        n_grid = np.arange(-25, 26)
        ja_sum = np.sum(sc.jv(n_grid, v_chi) * np.exp(1j * n_grid * (v_wz * v_t + v_phz)))
        exact_mod = np.exp(1j * v_chi * math.sin(v_wz * v_t + v_phz))
        assert abs(ja_sum - exact_mod) < 1e-12, f"Jacobi-Anger mismatch: {abs(ja_sum - exact_mod)}"

        # Check integral representation (1/pi) * int_0^pi cos(n*a - chi*sin(a)) da == J_n(chi)
        a_grid = np.linspace(0.0, np.pi, 4001)
        for n_test in (-2, -1, 0, 1, 2):
            integ = np.trapezoid(np.cos(n_test * a_grid - v_chi * np.sin(a_grid)), a_grid) / math.pi
            assert abs(integ - sc.jv(n_test, v_chi)) < 1e-10, f"Bessel integral mismatch for n={n_test}"
        # Check cos(a)*cos(chi*sin(a)) vanishes on [0, pi] by odd symmetry around pi/2
        cos_odd = np.trapezoid(np.cos(a_grid) * np.cos(v_chi * np.sin(a_grid)), a_grid)
        assert abs(cos_odd) < 1e-12, "Odd-symmetric cos(a)*cos(chi*sin(a)) integral must vanish"

    # Small-chi integral limit J_1(chi) ~ (1/pi)*int_0^pi chi*sin^2(a) da = chi/2
    a_small = np.linspace(0.0, np.pi, 4001)
    chi_small = 0.01
    j1_lin = np.trapezoid(chi_small * (np.sin(a_small) ** 2), a_small) / math.pi
    assert abs(j1_lin - 0.5 * chi_small) < 1e-12
    assert abs(sc.jv(1, chi_small) - j1_lin) < 1e-6 and abs(sc.jv(-1, chi_small) + j1_lin) < 1e-6

    # 4. Bessel parity and first carrier zero
    for chi_val in (0.2, 1.2, 2.4048):
        for n_test in range(1, 6):
            assert abs(sc.jv(-n_test, chi_val) - ((-1) ** n_test) * sc.jv(n_test, chi_val)) < 1e-14
    chi_zero = float(sc.jn_zeros(0, 1)[0])
    assert abs(chi_zero - 2.4048255576957724) < 1e-12
    assert abs(sc.jv(0, chi_zero)) < 1e-12

    # 5. Second frame U2 = exp(+i * dn * t * Sz) yielding exact Eq. (1.32) with Sx restored
    n_ord = sp.Symbol("n_ord", integer=True)
    h_i_single = sp.Rational(1, 2) * jn * Om * (
        sp.exp(sp.I * (n_ord * phz - ph)) * sp.exp(sp.I * dn * t) * sp_op
        + sp.exp(-sp.I * (n_ord * phz - ph)) * sp.exp(-sp.I * dn * t) * sm_op
    )
    u2 = sp.Matrix([[sp.exp(sp.I * dn * t / 2), 0], [0, sp.exp(-sp.I * dn * t / 2)]])
    u2_dag = u2.H
    h_i_eff = u2_dag * h_i_single * u2 - u2_dag * sp.I * sp.diff(u2, t)
    h_i_eff_expected = dn * sz + jn * Om * (
        sp.cos(ph - n_ord * phz) * sx + sp.sin(ph - n_ord * phz) * sy
    )
    assert mat_zero(h_i_eff - h_i_eff_expected), "Eq. (1.32) derivation mismatch"
    # Verify textbook erratum (dropping Sx) would fail tracelessness / equality
    h_i_erratum = dn * sz + jn * Om * (
        sp.cos(ph - n_ord * phz) * sp.eye(2) + sp.sin(ph - n_ord * phz) * sy
    )
    assert sp.simplify(sp.trace(h_i_eff_expected)) == 0
    assert sp.simplify(sp.trace(h_i_erratum)) != 0

    # 6. Subharmonic resonance w = w0 / (1 - n) and small-chi scaling
    delta_sub = w0 - w + n_ord * w
    sol_w = sp.solve(delta_sub, w)[0]
    assert sp.simplify(sol_w - w0 / (1 - n_ord)) == 0, "Subharmonic frequency formula mismatch"
    assert sol_w.subs(n_ord, 0) == w0
    assert sol_w.subs(n_ord, -1) == w0 / 2
    assert sol_w.subs(n_ord, -2) == w0 / 3

    print("[PASS] [longitudinal-sideband-excitation] Symbolic Eqs. (1.24)-(1.32), errata, & Jacobi-Anger checks passed.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    kps = assert_no_python_worked(lesson)

    # Worked 1: Om_z/2pi = 10 MHz, w_z/2pi = 50 MHz, Om/2pi = 10 MHz => chi = 0.2
    chi1 = 10.0 / 50.0
    assert math.isclose(chi1, 0.2, abs_tol=1e-12)
    om_mhz = 10.0
    j0_amp = abs(float(sc.jv(0, chi1))) * om_mhz
    j1_amp = abs(float(sc.jv(1, chi1))) * om_mhz
    jm1_amp = abs(float(sc.jv(-1, chi1))) * om_mhz
    j2_amp = abs(float(sc.jv(2, chi1))) * om_mhz
    assert math.isclose(j0_amp, 9.900, abs_tol=1e-3)
    assert math.isclose(j1_amp, 0.995, abs_tol=1e-3)
    assert math.isclose(jm1_amp, 0.995, abs_tol=1e-3)
    assert math.isclose(j2_amp, 0.0498, abs_tol=1e-4)
    w1 = kps["sideband-time-dependent-frame-and-jacobi-anger"]["worked"]
    assert "9.900" in w1 and "0.995" in w1 and "0.0498" in w1

    # Worked 2: w0=2000 MHz, w_z=50 MHz, w=2052 MHz (n=+1), phi=pi/3, phi_z=pi/6
    delta_p1 = 2000.0 - 2052.0 + 1 * 50.0
    assert math.isclose(delta_p1, -2.0, abs_tol=1e-12)
    eff_phase = math.pi / 3.0 - 1.0 * math.pi / 6.0
    assert math.isclose(eff_phase, math.pi / 6.0, abs_tol=1e-12)
    np_ops = numpy_spin_ops()
    sx, sy, sz = np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]
    j1_signed = float(sc.jv(1, 0.2)) * om_mhz
    h_eff_2 = delta_p1 * sz + j1_signed * (math.cos(eff_phase) * sx + math.sin(eff_phase) * sy)
    off_diag = 0.5 * j1_signed * np.exp(-1j * eff_phase)
    h_ref_2 = np.array([[-1.0, off_diag], [np.conj(off_diag), 1.0]], dtype=complex)
    assert np.max(np.abs(h_eff_2 - h_ref_2)) < 1e-12
    assert math.isclose(off_diag.real, 0.4309, abs_tol=5e-4)
    assert math.isclose(off_diag.imag, -0.2488, abs_tol=5e-4)
    w2 = kps["sideband-single-resonance-and-effective-hi"]["worked"]
    assert "-2" in w2 and "0.4309" in w2 and "0.2488" in w2

    # Worked 3: w0=10 GHz, w=5 GHz (n=-1), Om=Om_z=50 MHz vs 10 MHz
    chi3_strong = 50.0 / 5000.0
    assert math.isclose(chi3_strong, 0.01, abs_tol=1e-12)
    coup_strong_khz = abs(float(sc.jv(-1, chi3_strong))) * 50.0 * 1000.0
    assert math.isclose(coup_strong_khz, 250.0, abs_tol=0.01)

    chi3_weak = 10.0 / 5000.0
    assert math.isclose(chi3_weak, 0.002, abs_tol=1e-12)
    coup_weak_khz = abs(float(sc.jv(-1, chi3_weak))) * 10.0 * 1000.0
    assert math.isclose(coup_weak_khz, 10.0, abs_tol=0.01)
    assert math.isclose(coup_strong_khz / coup_weak_khz, 25.0, abs_tol=1e-2)
    w3 = kps["sideband-subharmonic-and-mas-transfer"]["worked"]
    assert "250" in w3 and "10" in w3

    print("[PASS] [longitudinal-sideband-excitation] Worked examples numerical verification passed.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic and worked-example checks for longitudinal-sideband-excitation."""
    _ = pack_dir
    verify_symbolic_and_bessel()
    verify_worked(lesson_path)
