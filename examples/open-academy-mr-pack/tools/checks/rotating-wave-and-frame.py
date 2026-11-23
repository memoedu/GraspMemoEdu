"""Mathematical and worked-example verification for rotating-wave-and-frame (Lesson 2)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import sympy as sp

from _common import assert_no_python_worked, load_lesson, mat_zero, numpy_spin_ops, sympy_spin_ops


def verify_symbolic_and_rodrigues() -> None:
    ops = sympy_spin_ops()
    sx, sy, sz = ops["Sx"], ops["Sy"], ops["Sz"]
    sp_op, sm_op = ops["Sp"], ops["Sm"]
    ket_0, ket_1 = ops["ket_0"], ops["ket_1"]

    w0, w, Om, phi, t = sp.symbols("w0 w Om phi t", real=True, positive=True)

    # Eq. (1.5): linear decomposition into co- and counter-rotating components
    lhs_15 = 2 * Om * sp.cos(w * t + phi) * sx
    co = Om * (sp.cos(w * t + phi) * sx + sp.sin(w * t + phi) * sy)
    counter = Om * (sp.cos(w * t + phi) * sx - sp.sin(w * t + phi) * sy)
    assert sp.simplify(lhs_15 - (co + counter)) == sp.zeros(2, 2), "Eq. (1.5) mismatch"

    # Interaction picture unitary Ui = exp(-i * w * t * Sz)
    ui = sp.Matrix([[sp.exp(-sp.I * w * t / 2), 0], [0, sp.exp(sp.I * w * t / 2)]])
    ui_dag = ui.H

    # Eqs. (1.6)-(1.9): Ui_dag * Ui == I and H_I derivation
    assert sp.simplify(ui_dag * ui - sp.eye(2)) == sp.zeros(2, 2), "Ui unitarity mismatch"
    h_rwa = w0 * sz + co
    h_i = sp.simplify(ui_dag * h_rwa * ui - ui_dag * sp.I * sp.diff(ui, t))
    h_i_expected = (w0 - w) * sz + Om * (sp.cos(phi) * sx + sp.sin(phi) * sy)
    assert mat_zero(h_i - h_i_expected), "Eq. (1.9) mismatch"

    # Eq. (1.8) specific & general 3D Rodrigues formula
    r_dot_s = sp.cos(w * t + phi) * sx + sp.sin(w * t + phi) * sy
    rot_lhs = ui_dag * r_dot_s * ui
    rot_rhs = sp.cos(phi) * sx + sp.sin(phi) * sy
    assert mat_zero(rot_lhs - rot_rhs), "Eq. (1.8) specific mismatch"

    np_ops = numpy_spin_ops()
    s_vec = [np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]]
    sig_vec = [np_ops["sigma_x"], np_ops["sigma_y"], np_ops["sigma_z"]]
    rng = np.random.default_rng(42)
    for _ in range(10):
        n_vec = rng.normal(size=3)
        n_vec /= np.linalg.norm(n_vec)
        theta_val = float(rng.uniform(-np.pi, np.pi))
        r_vec = rng.normal(size=3)
        n_dot_s = sum(n_vec[k] * s_vec[k] for k in range(3))
        n_dot_sig = sum(n_vec[k] * sig_vec[k] for k in range(3))
        r_dot_s_num = sum(r_vec[k] * s_vec[k] for k in range(3))
        # Pauli involution (n . sigma)^2 == I
        assert np.max(np.abs(n_dot_sig @ n_dot_sig - np.eye(2))) < 1e-12, "(n.sigma)^2 != I"
        u_rot = np.cos(theta_val / 2) * np.eye(2) - 1j * np.sin(theta_val / 2) * n_dot_sig
        # Compare SU(2) exponential directly with eigendecomposition exp(-i*theta*(n.S))
        eigvals, eigvecs = np.linalg.eigh(n_dot_s)
        u_eig = eigvecs @ np.diag(np.exp(-1j * theta_val * eigvals)) @ eigvecs.conj().T
        assert np.max(np.abs(u_rot - u_eig)) < 1e-12, "SU(2) matrix exponential mismatch"
        lhs_num = u_rot @ r_dot_s_num @ u_rot.conj().T
        r_rot = (
            r_vec * np.cos(theta_val)
            + np.cross(n_vec, r_vec) * np.sin(theta_val)
            + n_vec * np.dot(n_vec, r_vec) * (1 - np.cos(theta_val))
        )
        rhs_num = sum(r_rot[k] * s_vec[k] for k in range(3))
        assert np.max(np.abs(lhs_num - rhs_num)) < 1e-12, "General Eq. (1.8) failed"

    # Eqs. (1.10)-(1.12): ladder operator transformations
    assert sp_op * ket_1 == ket_0 and sp_op * ket_0 == sp.zeros(2, 1), "Eq. (1.10) S+ failed"
    assert sm_op * ket_0 == ket_1 and sm_op * ket_1 == sp.zeros(2, 1), "Eq. (1.10) S- failed"
    assert sp.simplify(ui_dag * sp_op * ui - sp.exp(sp.I * w * t) * sp_op) == sp.zeros(2, 2), "Ui^dag S+ Ui failed"
    eq111 = sp.Rational(1, 2) * (
        sp.exp(-sp.I * (w * t + phi)) * (ui_dag * sp_op * ui)
        + sp.exp(sp.I * (w * t + phi)) * (ui_dag * sm_op * ui)
    )
    assert mat_zero(eq111 - rot_rhs), "Eq. (1.11)-(1.12) mismatch"
    print("[PASS] [rotating-wave-and-frame] Symbolic Eqs. (1.5)-(1.12), Rodrigues & ladder identities succeeded.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    kps = assert_no_python_worked(lesson)

    f0_ghz = 10.0
    f_drive_ghz = 9.99
    two_omega_mhz = 20.0
    omega_half_mhz = two_omega_mhz / 2.0
    detuning_mhz = (f0_ghz - f_drive_ghz) * 1e3
    assert math.isclose(omega_half_mhz, 10.0, abs_tol=1e-12)
    assert math.isclose(detuning_mhz, 10.0, abs_tol=1e-12)
    assert "9.99" in kps["rwa-split-field"]["worked"], "Step 1 worked must state drive frequency 9.99 GHz"

    np_ops = numpy_spin_ops()
    sx, sy, sz = np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]
    sp_op = np_ops["Sp"]
    ket_up, ket_dn = np_ops["ket_0"], np_ops["ket_1"]

    phi = np.pi / 2.0
    w0 = 2.0 * np.pi * 1e4
    w = 2.0 * np.pi * 9990.0
    om = 2.0 * np.pi * 10.0
    h_i_expected = 2.0 * np.pi * (10.0 * sz + 10.0 * sy)

    for t_us in (0.0, 0.017, 0.25):
        ui = np.diag([np.exp(-0.5j * w * t_us), np.exp(0.5j * w * t_us)])
        assert np.max(np.abs(ui.conj().T @ sp_op @ ui @ ket_dn - np.exp(1j * w * t_us) * ket_up)) < 1e-12
        assert np.max(np.abs(ui.conj().T @ sp_op @ ui @ ket_up)) < 1e-12
        h_rwa = w0 * sz + om * (np.cos(w * t_us + phi) * sx + np.sin(w * t_us + phi) * sy)
        h_i_rot = (w0 - w) * sz + ui.conj().T @ (om * (np.cos(w * t_us + phi) * sx + np.sin(w * t_us + phi) * sy)) @ ui
        assert np.max(np.abs(h_i_rot - h_i_expected)) < 1e-10
        assert np.max(np.abs(ui.conj().T @ h_rwa @ ui - w * sz - h_i_expected)) < 1e-10

    nmax = 6
    a_dag = np.diag(np.sqrt(np.arange(1, nmax)), k=-1).astype(complex)
    n_op = a_dag @ a_dag.conj().T
    for t_val in (0.13, 0.77):
        ub = np.diag(np.exp(-1j * 3.5 * t_val * np.diag(n_op)))
        err_boson = np.max(
            np.abs(ub.conj()[:-1, :-1].T @ a_dag[:-1, :-1] @ ub[:-1, :-1] - np.exp(1j * 3.5 * t_val) * a_dag[:-1, :-1])
        )
        assert err_boson < 1e-12

    print("[PASS] [rotating-wave-and-frame] Worked examples & bosonic identity verification succeeded.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic and worked-example checks for rotating-wave-and-frame."""
    _ = pack_dir
    verify_symbolic_and_rodrigues()
    verify_worked(lesson_path)
