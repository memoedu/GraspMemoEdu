"""Mathematical, errata, and worked-example verification for bloch-sphere-representation (Unit 2, Lesson 2)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import sympy as sp

from _common import assert_no_python_worked, load_lesson, mat_zero, numpy_spin_ops, sympy_spin_ops


def _rodrigues_np(n_unit: np.ndarray, theta: float, r_vec: np.ndarray) -> np.ndarray:
    """Right-hand 3D Rodrigues rotation R_{n * theta}(r)."""
    return (
        r_vec * math.cos(theta)
        + np.cross(n_unit, r_vec) * math.sin(theta)
        + n_unit * float(np.dot(n_unit, r_vec)) * (1.0 - math.cos(theta))
    )


def verify_symbolic_and_errata() -> None:
    ops = sympy_spin_ops()
    i2 = ops["I2"]
    sx, sy, sz = ops["Sx"], ops["Sy"], ops["Sz"]
    sig = [ops["sigma_x"], ops["sigma_y"], ops["sigma_z"]]
    ket_0, ket_1 = ops["ket_0"], ops["ket_1"]

    th, ph = sp.symbols("th ph", real=True)
    nx_s, ny_s, nz_s = sp.symbols("nx_s ny_s nz_s", real=True)

    # 1. Eq. (1.34)-(1.35) pure-state density matrix equivalence & G&K Eq. (A26) global phase invariance
    psi_mr = sp.cos(th / 2) * ket_0 + sp.sin(th / 2) * sp.exp(sp.I * ph) * ket_1
    psi_gk = sp.cos(th / 2) * sp.exp(-sp.I * ph / 2) * ket_0 + sp.sin(th / 2) * sp.exp(sp.I * ph / 2) * ket_1
    rho_mr = psi_mr * psi_mr.H
    rho_gk = psi_gk * psi_gk.H
    assert mat_zero(rho_mr - rho_gk), "G&K Eq. (A26) and MR Eq. (1.34) density matrices must match"

    n_pure = [sp.sin(th) * sp.cos(ph), sp.sin(th) * sp.sin(ph), sp.cos(th)]
    assert sp.simplify(sum(c**2 for c in n_pure) - 1) == 0, "Pure Bloch vector norm != 1"
    rho_bloch_pure = (i2 + n_pure[0] * sig[0] + n_pure[1] * sig[1] + n_pure[2] * sig[2]) / 2
    assert mat_zero(rho_mr - rho_bloch_pure), "Eq. (1.35) pure-state density matrix mismatch"

    # Explicit matrix entry form matching sigma_y = [[0, -i], [i, 0]]
    rho_mat = sp.Matrix([[1 + nz_s, nx_s - sp.I * ny_s], [nx_s + sp.I * ny_s, 1 - nz_s]]) / 2
    rho_sig = (i2 + nx_s * sig[0] + ny_s * sig[1] + nz_s * sig[2]) / 2
    assert mat_zero(rho_mat - rho_sig), "Explicit matrix entries mismatch (I + n.sigma)/2"

    # Verify G&K Eq. (A25) flipped +/- i s2 sign fails for |+y> = (|0> + i|1>)/sqrt(2)
    ket_plus_y = (ket_0 + sp.I * ket_1) / sp.sqrt(2)
    rho_plus_y = ket_plus_y * ket_plus_y.H
    rho_gk_a25_typo = sp.Matrix([[1 + 0, 0 + sp.I * 1], [0 - sp.I * 1, 1 - 0]]) / 2
    assert not mat_zero(rho_plus_y - rho_gk_a25_typo), "G&K Eq. (A25) typo must contradict |+y>"
    assert mat_zero(rho_plus_y - rho_mat.subs({nx_s: 0, ny_s: 1, nz_s: 0})), "Corrected matrix must match |+y>"

    # Antipodal points +/- n correspond to orthogonal states: Tr(rho_+ * rho_-) == 0 for |n| == 1
    rho_anti_plus = rho_bloch_pure
    rho_anti_minus = (i2 - (n_pure[0] * sig[0] + n_pure[1] * sig[1] + n_pure[2] * sig[2])) / 2
    assert sp.simplify(sp.trace(rho_anti_plus * rho_anti_minus)) == 0, "Antipodal pure states not orthogonal"

    # Pure-state alignment formula |<psi_n|psi_m>|^2 == cos^2(alpha/2) == (1 + cos(alpha))/2
    alpha_s = sp.Symbol("alpha_s", real=True)
    psi_m_aligned = sp.cos(alpha_s / 2) * ket_0 + sp.sin(alpha_s / 2) * sp.exp(sp.I * ph) * ket_1
    overlap_sq = sp.simplify(sp.Abs((ket_0.H * psi_m_aligned)[0]) ** 2)
    assert sp.simplify(overlap_sq - (1 + sp.cos(alpha_s)) / 2) == 0, "Pure-state alignment formula mismatch"

    # 2. Pauli product algebra & textbook Eq. (1.38) /2 erratum check
    def levi_civita(i: int, j: int, k: int) -> int:
        return (i - j) * (j - k) * (k - i) // 2

    for i in range(3):
        for j in range(3):
            rhs = (1 if i == j else 0) * i2 + sp.I * sum(
                (levi_civita(i, j, k) * sig[k] for k in range(3)),
                sp.zeros(2, 2),
            )
            assert mat_zero(sig[i] * sig[j] - rhs), f"Pauli product identity failed for ({i},{j})"

    # Assert textbook's spurious /2 inside Pauli product fails for sigma_x * sigma_y
    wrong_pauli_xy = sp.I * sig[2] / 2
    assert not mat_zero(sig[0] * sig[1] - wrong_pauli_xy), "Spurious /2 erratum in sigma_x*sigma_y must fail"
    # Assert omitting outer 1/2 in Eq. (1.38) yields 2*n instead of n
    tr_no_half = [sp.simplify(sp.trace(2 * rho_sig * sig[j])) for j in range(3)]
    assert tr_no_half == [2 * nx_s, 2 * ny_s, 2 * nz_s], "Omitting outer 1/2 should double Bloch vector"

    # 3. Eq. (1.38) Trace inversion Tr(rho * sigma) == n
    tr_vec = [sp.simplify(sp.trace(rho_sig * sig[j])) for j in range(3)]
    assert tr_vec == [nx_s, ny_s, nz_s], "Eq. (1.38) Tr(rho * sigma) != n"

    # 4. Purity Tr(rho^2) == (1 + |n|^2)/2 & eigenvalues (1 +/- |n|)/2 (G&K Eqs. A15, A27)
    purity = sp.simplify(sp.trace(rho_sig * rho_sig))
    n2 = nx_s**2 + ny_s**2 + nz_s**2
    assert sp.simplify(purity - (1 + n2) / 2) == 0, "Purity formula Tr(rho^2) != (1+|n|^2)/2"
    eig_dict = rho_sig.eigenvals()
    n_norm = sp.sqrt(n2)
    expected_eigs = {(1 + n_norm) / 2, (1 - n_norm) / 2}
    assert {sp.simplify(ev) for ev in eig_dict.keys()} == {sp.simplify(ev) for ev in expected_eigs}, (
        "Eigenvalues (1 +/- |n|)/2 mismatch"
    )

    # 5. Eqs. (1.39)-(1.40) across 10 random unitaries & mixed Bloch vectors
    np_ops = numpy_spin_ops()
    np_i2 = np_ops["I2"]
    np_sig = [np_ops["sigma_x"], np_ops["sigma_y"], np_ops["sigma_z"]]
    np_s = [np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]]
    rng = np.random.default_rng(2026)

    for _ in range(10):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        angle = float(rng.uniform(-np.pi, np.pi))

        # Mixed Bloch vector inside unit ball
        n0 = rng.normal(size=3)
        n0 = n0 / np.linalg.norm(n0) * float(rng.uniform(0.05, 0.98))
        rho0 = 0.5 * (np_i2 + sum(n0[k] * np_sig[k] for k in range(3)))

        n_dot_s = sum(axis[k] * np_s[k] for k in range(3))
        eigvals, eigvecs = np.linalg.eigh(n_dot_s)
        u_gate = eigvecs @ np.diag(np.exp(-1j * angle * eigvals)) @ eigvecs.conj().T

        rho_f = u_gate @ rho0 @ u_gate.conj().T
        nf_from_tr = np.array([np.real(np.trace(rho_f @ np_sig[k])) for k in range(3)])
        nf_from_rot = _rodrigues_np(axis, angle, n0)
        assert np.max(np.abs(nf_from_tr - nf_from_rot)) < 1e-12, "Eqs. (1.39)-(1.40) rotation mismatch"

        rho_f_from_rot = 0.5 * (np_i2 + sum(nf_from_rot[k] * np_sig[k] for k in range(3)))
        assert np.max(np.abs(rho_f - rho_f_from_rot)) < 1e-12, "rho_f density matrix mismatch"

        # Purity preservation under unitary rotation
        pur0 = np.real(np.trace(rho0 @ rho0))
        purf = np.real(np.trace(rho_f @ rho_f))
        assert abs(pur0 - purf) < 1e-12, "Unitary gate altered purity"

    # Also verify specific symbolic rotation around +x on general state & pi reflection formula
    u_x = sp.cos(th / 2) * i2 - sp.I * sp.sin(th / 2) * sig[0]
    rho_1 = ket_1 * ket_1.H
    rho_1_rot = sp.simplify(u_x * rho_1 * u_x.H)
    nf_sym = [sp.simplify(sp.trace(rho_1_rot * sig[j])) for j in range(3)]
    assert [sp.simplify(nf_sym[0]), sp.simplify(nf_sym[1] - sp.sin(th)), sp.simplify(nf_sym[2] + sp.cos(th))] == [0, 0, 0]

    # Verify theta = pi reflection identity: R_{n*pi}(n0) = 2*(n.n0)*n - n0
    ax_pi = np.array([0.3, -0.4, math.sqrt(1.0 - 0.25)])
    r_pi_test = np.array([0.2, 0.7, -0.5])
    refl = 2.0 * float(np.dot(ax_pi, r_pi_test)) * ax_pi - r_pi_test
    assert np.max(np.abs(_rodrigues_np(ax_pi, math.pi, r_pi_test) - refl)) < 1e-12

    print("[PASS] [bloch-sphere-representation] Symbolic Eqs. (1.34)-(1.40), errata, purity & 10-trial SO(3) checks succeeded.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    kps = assert_no_python_worked(lesson)

    np_ops = numpy_spin_ops()
    np_i2 = np_ops["I2"]
    np_sig = [np_ops["sigma_x"], np_ops["sigma_y"], np_ops["sigma_z"]]
    ket_0 = np_ops["ket_0"]
    ket_1 = np_ops["ket_1"]

    # KP 1 worked: |psi> = (1/2)|0> + (sqrt(3)/2)i|1>
    psi1 = 0.5 * ket_0 + (math.sqrt(3) / 2.0) * 1j * ket_1
    rho1 = np.outer(psi1, psi1.conj())
    n1 = np.array([np.real(np.trace(rho1 @ np_sig[k])) for k in range(3)])
    n1_expected = np.array([0.0, math.sqrt(3) / 2.0, -0.5])
    assert np.max(np.abs(n1 - n1_expected)) < 1e-12
    assert math.isclose(np.linalg.norm(n1), 1.0, abs_tol=1e-12)
    rho1_expected = np.array([[0.25, -math.sqrt(3) * 1j / 4.0], [math.sqrt(3) * 1j / 4.0, 0.75]])
    assert np.max(np.abs(rho1 - rho1_expected)) < 1e-12
    assert "2\\pi/3" in kps["bloch-pure-state-mapping"]["worked"]

    # KP 2 worked: mixture p1 = 3/4 in |0>, p2 = 1/4 in |+>
    ket_plus = (ket_0 + ket_1) / math.sqrt(2.0)
    rho2 = 0.75 * np.outer(ket_0, ket_0.conj()) + 0.25 * np.outer(ket_plus, ket_plus.conj())
    rho2_expected = np.array([[7 / 8, 1 / 8], [1 / 8, 1 / 8]], dtype=complex)
    assert np.max(np.abs(rho2 - rho2_expected)) < 1e-12
    n2 = np.array([np.real(np.trace(rho2 @ np_sig[k])) for k in range(3)])
    assert np.max(np.abs(n2 - np.array([0.25, 0.0, 0.75]))) < 1e-12
    n2_norm = float(np.linalg.norm(n2))
    assert math.isclose(n2_norm, math.sqrt(10.0) / 4.0, abs_tol=1e-12)
    assert math.isclose(n2_norm, 0.790569415, abs_tol=1e-4)
    pur2 = float(np.real(np.trace(rho2 @ rho2)))
    assert math.isclose(pur2, 13.0 / 16.0, abs_tol=1e-12)
    assert math.isclose(pur2, 0.8125, abs_tol=1e-12)
    eigs2 = np.sort(np.linalg.eigvalsh(rho2))
    eigs2_expected = np.array([(4.0 - math.sqrt(10.0)) / 8.0, (4.0 + math.sqrt(10.0)) / 8.0])
    assert np.max(np.abs(eigs2 - eigs2_expected)) < 1e-12

    # KP 3 worked: initial |1> (n0 = (0,0,-1)) under (a) U_x(pi/2) and (b) pi-rot around (1,0,1)/sqrt(2)
    n0 = np.array([0.0, 0.0, -1.0])
    rho0 = np.outer(ket_1, ket_1.conj())

    # (a) U_x(pi/2)
    u_x_pi2 = (np_i2 - 1j * np_sig[0]) / math.sqrt(2.0)
    psi_a = u_x_pi2 @ ket_1
    psi_a_expected = (ket_1 - 1j * ket_0) / math.sqrt(2.0)
    assert np.max(np.abs(psi_a - psi_a_expected)) < 1e-12
    rho_a = u_x_pi2 @ rho0 @ u_x_pi2.conj().T
    nf_a = np.array([np.real(np.trace(rho_a @ np_sig[k])) for k in range(3)])
    assert np.max(np.abs(nf_a - np.array([0.0, 1.0, 0.0]))) < 1e-12
    assert np.max(np.abs(_rodrigues_np(np.array([1.0, 0.0, 0.0]), math.pi / 2.0, n0) - np.array([0.0, 1.0, 0.0]))) < 1e-12

    # (b) pi rotation about n = (1, 0, 1)/sqrt(2)
    axis_b = np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)
    u_b = -1j * (axis_b[0] * np_sig[0] + axis_b[2] * np_sig[2])
    hadamard = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=complex) / math.sqrt(2.0)
    assert np.max(np.abs(u_b - (-1j * hadamard))) < 1e-12
    psi_b = u_b @ ket_1
    assert np.max(np.abs(psi_b - (-1j * (ket_0 - ket_1) / math.sqrt(2.0)))) < 1e-12
    rho_b = u_b @ rho0 @ u_b.conj().T
    nf_b = np.array([np.real(np.trace(rho_b @ np_sig[k])) for k in range(3)])
    assert np.max(np.abs(nf_b - np.array([-1.0, 0.0, 0.0]))) < 1e-12
    assert np.max(np.abs(_rodrigues_np(axis_b, math.pi, n0) - np.array([-1.0, 0.0, 0.0]))) < 1e-12

    print("[PASS] [bloch-sphere-representation] Worked examples numerical verification succeeded.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic, errata, and worked-example checks for bloch-sphere-representation."""
    _ = pack_dir
    verify_symbolic_and_errata()
    verify_worked(lesson_path)
