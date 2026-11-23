"""Mathematical, dynamical, and worked-example verification for bloch-siegert-shift (Lesson 3)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import sympy as sp

from _common import assert_no_python_worked, load_lesson, mat_zero, numpy_spin_ops, sympy_spin_ops


def _evolve_tdse(
    h_func,
    psi0: np.ndarray,
    t_final: float,
    n_steps: int,
) -> np.ndarray:
    """Propagate 2x2 traceless-Hermitian TDSE using 2nd-order midpoint exact SU(2) exponential."""
    dt = t_final / n_steps
    psi = psi0.astype(complex).copy()
    for step in range(n_steps):
        t_mid = (step + 0.5) * dt
        h_mid = h_func(t_mid)
        # H = hx*Sx + hy*Sy + hz*Sz has eigenvalues +/- r/2 where r = sqrt(2*Tr(H^2))
        r = math.sqrt(max(0.0, 2.0 * float(np.real(np.sum(h_mid * h_mid.T)))))
        if r == 0.0:
            continue
        ang = 0.5 * r * dt
        u = math.cos(ang) * np.eye(2, dtype=complex) - 1j * (2.0 * math.sin(ang) / r) * h_mid
        psi = u @ psi
    return psi


def verify_symbolic_double_frame_and_errata() -> None:
    ops = sympy_spin_ops()
    sx, sy, sz = ops["Sx"], ops["Sy"], ops["Sz"]

    w0, w, wp, Om, Omp, phi, phip, t, theta, alpha = sp.symbols(
        "w0 w wp Om Omp phi phip t theta alpha", real=True
    )

    # 1. Specialization of general off-resonant drive (Eq. 1.17) to RWA counter-rotating term
    h_off = Omp * (sp.cos(wp * t + phip) * sx + sp.sin(wp * t + phip) * sy)
    h_counter_expected = Om * (sp.cos(w * t + phi) * sx - sp.sin(w * t + phi) * sy)
    assert mat_zero(h_off.subs({Omp: Om, wp: -w, phip: -phi}) - h_counter_expected), (
        "Counter-rotating specialization mismatch"
    )

    # 2. First rotating frame Ui' = exp(-i*(w'*t + phi')*Sz) -> Eq. (1.18)
    ui_p = sp.Matrix([[sp.exp(-sp.I * (wp * t + phip) / 2), 0], [0, sp.exp(sp.I * (wp * t + phip) / 2)]])
    assert mat_zero(ui_p.H * ui_p - sp.eye(2)), "Ui' unitarity failed"

    h_tot = w0 * sz + Om * (sp.cos(w * t + phi) * sx + sp.sin(w * t + phi) * sy) + h_off
    h_ip = sp.simplify(ui_p.H * h_tot * ui_p - ui_p.H * sp.I * sp.diff(ui_p, t))
    h_ip_expected = (
        (w0 - wp) * sz
        + Omp * sx
        + Om * (sp.cos((w - wp) * t + (phi - phip)) * sx + sp.sin((w - wp) * t + (phi - phip)) * sy)
    )
    assert mat_zero(h_ip - h_ip_expected), "Eq. (1.18) first rotating frame mismatch"

    # 3. Quantization-axis rotation around y by angle theta -> Eq. (1.19)
    sz_p = sp.cos(theta) * sz + sp.sin(theta) * sx
    sx_p = sp.cos(theta) * sx - sp.sin(theta) * sz
    sy_p = sy

    # Verify SU(2) spin commutation relations in primed axes
    assert mat_zero(sx_p * sy_p - sy_p * sx_p - sp.I * sz_p), "[Sx', Sy'] != i Sz'"
    assert mat_zero(sy_p * sz_p - sz_p * sy_p - sp.I * sx_p), "[Sy', Sz'] != i Sx'"
    assert mat_zero(sz_p * sx_p - sx_p * sz_p - sp.I * sy_p), "[Sz', Sx'] != i Sy'"

    # Verify inverse relations Sx = cos(theta)*Sx' + sin(theta)*Sz'
    assert mat_zero(sx - (sp.cos(theta) * sx_p + sp.sin(theta) * sz_p)), "Inverse Sx mismatch"
    assert mat_zero(sz - (sp.cos(theta) * sz_p - sp.sin(theta) * sx_p)), "Inverse Sz mismatch"

    # Diagonalization of static block (3) for both signs of (w0 - w')
    dz = sp.symbols("dz", real=True, positive=True)
    amp = sp.sqrt(dz**2 + Omp**2)
    # Case (a): w0 - w' = +dz > 0
    block_pos = dz * sz + Omp * sx
    diag_pos = amp * sz_p.subs({sp.cos(theta): dz / amp, sp.sin(theta): Omp / amp})
    assert mat_zero(block_pos - diag_pos), "Diagonalization failed for w0 > w'"
    # Case (b): w0 - w' = -dz < 0 (cos(theta) = |dz|/amp > 0, sin(theta) = -Omp/amp)
    block_neg = -dz * sz + Omp * sx
    diag_neg = -amp * sz_p.subs({sp.cos(theta): dz / amp, sp.sin(theta): -Omp / amp})
    assert mat_zero(block_neg - diag_neg), "Diagonalization failed for w0 < w'"

    # Erratum 1 check: missing square inside sqrt breaks unit norm cos^2 + sin^2 == 1
    assert sp.simplify((dz / sp.sqrt(dz + Omp**2)) ** 2 + (Omp / sp.sqrt(dz + Omp**2)) ** 2 - 1) != 0
    assert sp.simplify((dz / amp) ** 2 + (Omp / amp) ** 2 - 1) == 0, "Erratum 1 identity failed"

    # 4. Exact Eq. (1.20) cos^2(theta/2) / sin^2(theta/2) decomposition
    drive_proj = sp.cos(alpha) * (sp.cos(theta) * sx_p + sp.sin(theta) * sz_p) + sp.sin(alpha) * sy_p
    drive_decomposed = (
        sp.sin(theta) * sp.cos(alpha) * sz_p
        + sp.cos(theta / 2) ** 2 * (sp.cos(alpha) * sx_p + sp.sin(alpha) * sy_p)
        - sp.sin(theta / 2) ** 2 * (sp.cos(alpha) * sx_p - sp.sin(alpha) * sy_p)
    )
    assert mat_zero(drive_proj - drive_decomposed), "Eq. (1.20) exact decomposition mismatch"

    # Erratum 2 check: Taylor expansion of cos(theta) = 1/sqrt(1 + (Omp/dz)^2)
    eps = sp.symbols("eps", real=True)
    cos_series = sp.series(1 / sp.sqrt(1 + eps**2), eps, 0, 4).removeO()
    assert sp.simplify(cos_series - (1 - eps**2 / 2)) == 0, "Erratum 2 cos(theta) expansion mismatch"

    # 5. Second rotating frame Ui'' = exp(-i*((w - w')*t - phi')*Sz) -> Eq. (1.22)
    phase_2 = (w - wp) * t - phip
    ui_pp = sp.Matrix([[sp.exp(-sp.I * phase_2 / 2), 0], [0, sp.exp(sp.I * phase_2 / 2)]])
    assert mat_zero(ui_pp.H * ui_pp - sp.eye(2)), "Ui'' unitarity failed"

    e_tilde = sp.symbols("e_tilde", real=True)
    h_ip_approx = e_tilde * sz + Om * (
        sp.cos((w - wp) * t + (phi - phip)) * sx + sp.sin((w - wp) * t + (phi - phip)) * sy
    )
    h_i_final = sp.simplify(ui_pp.H * h_ip_approx * ui_pp - ui_pp.H * sp.I * sp.diff(ui_pp, t))
    h_i_expected = (e_tilde - (w - wp)) * sz + Om * (sp.cos(phi) * sx + sp.sin(phi) * sy)
    assert mat_zero(h_i_final - h_i_expected), "Eq. (1.22) second rotating frame / phase cancellation failed"

    # 6. Eq. (1.23) Delta_BS series for both w0 > w' (+dz) and w0 < w' (-dz)
    bs_pos = sp.series(sp.sqrt(dz**2 + Omp**2), Omp, 0, 4).removeO() - dz
    bs_neg = sp.series(-sp.sqrt(dz**2 + Omp**2), Omp, 0, 4).removeO() - (-dz)
    assert sp.simplify(bs_pos - Omp**2 / (2 * dz)) == 0, "Delta_BS positive detuning mismatch"
    assert sp.simplify(bs_neg - Omp**2 / (2 * (-dz))) == 0, "Delta_BS negative detuning mismatch"

    # Counter-rotating RWA limit: Delta_BS = Om^2 / (2*(w0 + w)) -> Om^2 / (4*w0)
    delta_bs_gen = Omp**2 / (2 * (w0 - wp))
    assert sp.simplify(delta_bs_gen.subs({Omp: Om, wp: -w}) - Om**2 / (2 * (w0 + w))) == 0
    assert sp.simplify(delta_bs_gen.subs({Omp: Om, wp: -w0}) - Om**2 / (4 * w0)) == 0

    print("[PASS] [bloch-siegert-shift] Symbolic double-frame Eqs. (1.17)-(1.23) & 3 errata succeeded.")


def verify_dispersive_jc_and_numeric_dynamics() -> None:
    np_ops = numpy_spin_ops()
    sx, sy, sz = np_ops["Sx"], np_ops["Sy"], np_ops["Sz"]
    sp_op, sm_op = np_ops["Sp"], np_ops["Sm"]
    ket_0, ket_1 = np_ops["ket_0"].reshape(2, 1), np_ops["ket_1"].reshape(2, 1)

    # 1. Jaynes-Cummings commutator identity and dispersive AC Stark correspondence
    nmax = 8
    a_op = np.diag(np.sqrt(np.arange(1, nmax)), k=1).astype(complex)
    a_dag = a_op.conj().T
    n_ph = a_dag @ a_op
    proj_e = np.diag([1.0, 0.0]).astype(complex)  # |e><e| in {|e>, |g>} basis

    jc_plus_a = np.kron(sp_op, a_op)
    jc_minus_adag = np.kron(sm_op, a_dag)
    comm = jc_plus_a @ jc_minus_adag - jc_minus_adag @ jc_plus_a
    expected_op = np.kron(proj_e, np.eye(nmax)) + 2.0 * np.kron(sz, n_ph)
    # Keep interior Fock indices n = 0..nmax-2 in both |e,n> and |g,n> blocks (excluding top Fock edge nmax-1)
    interior = list(range(nmax - 1)) + [nmax + k for k in range(nmax - 1)]
    assert np.max(np.abs(comm[np.ix_(interior, interior)] - expected_op[np.ix_(interior, interior)])) < 1e-12, (
        "JC dispersive commutator [S+ a, S- a^dag] mismatch"
    )

    lam = 2.0 * np.pi * 15.0
    for wc_diff in (2.0 * np.pi * 300.0, -2.0 * np.pi * 300.0):  # w0 - wc
        delta_disp = lam**2 / wc_diff
        h_eff = delta_disp * expected_op
        for n in range(1, nmax - 1):
            ket_en = np.kron(ket_0, np.eye(nmax)[:, [n]])
            ket_gn = np.kron(ket_1, np.eye(nmax)[:, [n]])
            shift_e = float(np.real((ket_en.conj().T @ h_eff @ ket_en)[0, 0]))
            shift_g = float(np.real((ket_gn.conj().T @ h_eff @ ket_gn)[0, 0]))
            stim_shift = (shift_e - shift_g) - delta_disp  # remove vacuum shift (n=0)
            om_p_equiv = 2.0 * lam * math.sqrt(n)
            bs_equiv = om_p_equiv**2 / (2.0 * wc_diff)
            assert math.isclose(stim_shift, bs_equiv, rel_tol=1e-12, abs_tol=1e-12), (
                f"JC stimulated AC Stark ({stim_shift}) != BS shift ({bs_equiv}) at n={n}"
            )

    # 2. Exact non-perturbative Floquet (Shirley 1965) simulation of linear-drive H(t) = w0*Sz + 2*Om*cos(w*t)*Sx
    w0 = 1.0
    m_max = 6
    dim_f = 2 * (2 * m_max + 1)
    m0_offset = 2 * m_max

    def floquet_avg_prob(w_val: float, om_val: float) -> float:
        h_f = np.zeros((dim_f, dim_f), dtype=complex)
        for idx_m, m in enumerate(range(-m_max, m_max + 1)):
            blk = slice(2 * idx_m, 2 * idx_m + 2)
            h_f[blk, blk] = w0 * sz + m * w_val * np.eye(2)
            if idx_m + 1 < 2 * m_max + 1:
                blk_p = slice(2 * (idx_m + 1), 2 * (idx_m + 1) + 2)
                h_f[blk, blk_p] = om_val * sx
                h_f[blk_p, blk] = om_val * sx
        _, vecs = np.linalg.eigh(h_f)
        p_avg = 0.0
        for col in range(dim_f):
            v = vecs[:, col]
            w_g0 = float(abs(v[m0_offset + 1]) ** 2)
            w_e = float(sum(abs(v[2 * k]) ** 2 for k in range(2 * m_max + 1)))
            p_avg += w_g0 * w_e
        return p_avg

    for om in (0.10, 0.20):
        pred_approx = om**2 / (4.0 * w0)
        freqs = np.linspace(w0 - 0.4 * pred_approx, w0 + 1.8 * pred_approx, 55)
        probs = [floquet_avg_prob(float(wf), om) for wf in freqs]
        idx = int(np.argmax(probs))
        assert 0 < idx < len(freqs) - 1, f"Resonance peak hit grid boundary for om={om}"
        x1, x2, x3 = freqs[idx - 1], freqs[idx], freqs[idx + 1]
        y1, y2, y3 = probs[idx - 1], probs[idx], probs[idx + 1]
        denom = (x1 - x2) * (x1 - x3) * (x2 - x3)
        a_quad = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom
        b_quad = (x3**2 * (y1 - y2) + x2**2 * (y3 - y1) + x1**2 * (y2 - y3)) / denom
        w_peak_refined = -b_quad / (2.0 * a_quad)
        measured_shift = w_peak_refined - w0
        delta_bs_pred = om**2 / (2.0 * (w0 + w_peak_refined))
        assert abs(measured_shift - delta_bs_pred) / delta_bs_pred < 0.02, (
            f"Floquet Bloch-Siegert shift mismatch at om={om}: measured={measured_shift:.6f}, pred={delta_bs_pred:.6f}"
        )

    # 3. Direct TDSE test of sign reversal for red (w' < w0) vs blue (w' > w0) spectator tone
    om_probe = 0.01
    om_spec = 0.06
    t_probe = math.pi / om_probe
    for wp_spec, expected_sign in ((0.70, +1.0), (1.30, -1.0)):
        # Predicted Delta_BS = 0.06^2 / (2*(1.0 - wp_spec)) = +/- 0.0060
        pred_shift = om_spec**2 / (2.0 * (w0 - wp_spec))
        assert math.copysign(1.0, pred_shift) == expected_sign
        scan_w = np.linspace(w0 + pred_shift - 0.006, w0 + pred_shift + 0.006, 17)
        p_scan = []
        for w_test in scan_w:
            psi_f = _evolve_tdse(
                lambda tt, wt=w_test, ws=wp_spec: (
                    w0 * sz
                    + om_probe * (math.cos(wt * tt) * sx + math.sin(wt * tt) * sy)
                    + om_spec * (math.cos(ws * tt) * sx + math.sin(ws * tt) * sy)
                ),
                ket_1,
                t_probe,
                n_steps=900,
            )
            p_scan.append(float(np.abs(psi_f[0, 0]) ** 2))
        w_spec_peak = float(scan_w[int(np.argmax(p_scan))])
        assert math.copysign(1.0, w_spec_peak - w0) == expected_sign, (
            f"Sign reversal TDSE check failed at w'={wp_spec}: peak={w_spec_peak}"
        )
        assert abs((w_spec_peak - w0) - pred_shift) < 0.001, (
            f"Spectator shift magnitude mismatch at w'={wp_spec}: got {w_spec_peak - w0}, pred {pred_shift}"
        )

    print("[PASS] [bloch-siegert-shift] Dispersive JC equivalence & full TDSE dynamical checks succeeded.")


def verify_worked(lesson_path: Path) -> None:
    lesson = load_lesson(lesson_path)
    kps = assert_no_python_worked(lesson)

    # KP 1 worked: w0 = 2.5 GHz, w' = -2.5 GHz, Om' = 10 MHz, probe Om = 10 MHz
    w0_1, wp_1, omp_1, om_1 = 2500.0, -2500.0, 10.0, 10.0
    dz_1 = w0_1 - wp_1
    assert math.isclose(dz_1, 5000.0, abs_tol=1e-12)
    tan_th = omp_1 / dz_1
    sin_th = omp_1 / math.sqrt(dz_1**2 + omp_1**2)
    assert math.isclose(tan_th, 2e-3, abs_tol=1e-12)
    long_osc_mhz = om_1 * sin_th
    phase_jitter_rad = long_osc_mhz / dz_1
    assert math.isclose(long_osc_mhz, 0.02, rel_tol=1e-4)  # 20 kHz
    assert math.isclose(phase_jitter_rad, 4e-6, rel_tol=1e-4)  # 4e-6 rad
    one_minus_cos = 1.0 - dz_1 / math.sqrt(dz_1**2 + omp_1**2)
    one_minus_cos_taylor = 0.5 * tan_th**2
    sin2_half = 0.5 * one_minus_cos
    assert math.isclose(one_minus_cos, 2e-6, rel_tol=1e-4)
    assert math.isclose(one_minus_cos_taylor, 2e-6, abs_tol=1e-12)
    assert math.isclose(sin2_half, 1e-6, rel_tol=1e-4)
    stretch_mhz = math.sqrt(dz_1**2 + omp_1**2) - dz_1
    assert math.isclose(stretch_mhz, 0.01, rel_tol=1e-4)  # 10 kHz
    assert "5000" in kps["bs-first-frame-and-axis-tilt"]["worked"]
    assert "20\\text{ kHz}" in kps["bs-first-frame-and-axis-tilt"]["worked"]
    assert "4\\times 10^{-6}" in kps["bs-first-frame-and-axis-tilt"]["worked"]

    # KP 2 worked: w0 = 5.0 GHz, weak Om = 10 MHz -> 5 kHz, ultrastrong Om = 1000 MHz -> 50 MHz
    w0_2 = 5000.0
    bs_weak_mhz = 10.0**2 / (4.0 * w0_2)
    bs_strong_mhz = 1000.0**2 / (4.0 * w0_2)
    assert math.isclose(bs_weak_mhz, 0.005, abs_tol=1e-12)  # 5 kHz
    assert math.isclose(bs_strong_mhz, 50.0, abs_tol=1e-12)  # 50 MHz
    assert math.isclose(bs_weak_mhz / 10.0, 5e-4, abs_tol=1e-12)
    assert math.isclose(bs_strong_mhz / 1000.0, 0.05, abs_tol=1e-12)
    assert "5\\text{ kHz}" in kps["bs-second-frame-and-shift-formula"]["worked"]
    assert "50\\text{ MHz}" in kps["bs-second-frame-and-shift-formula"]["worked"]

    # KP 3 worked: w0 = 3.0 GHz = 3000 MHz, Om' = 20 MHz, w' = 2.8 GHz / 3.2 GHz
    w0_3, omp_3 = 3000.0, 20.0
    bs_red = omp_3**2 / (2.0 * (w0_3 - 2800.0))
    bs_blue = omp_3**2 / (2.0 * (w0_3 - 3200.0))
    assert math.isclose(bs_red, 1.0, abs_tol=1e-12)
    assert math.isclose(bs_blue, -1.0, abs_tol=1e-12)
    exact_mag = math.sqrt(200.0**2 + 20.0**2) - 200.0
    rel_err = abs(1.0 - exact_mag) / exact_mag
    assert math.isclose(exact_mag, 0.9975124, abs_tol=1e-6)
    assert rel_err < 0.0025
    assert "3.001" in kps["bs-sign-level-repulsion-and-optical-stark"]["worked"]
    assert "2.999" in kps["bs-sign-level-repulsion-and-optical-stark"]["worked"]

    print("[PASS] [bloch-siegert-shift] All 3 worked-example verifications succeeded.")


def verify(lesson_path: Path, pack_dir: Path) -> None:
    """Run all symbolic, dynamical, and worked-example checks for bloch-siegert-shift."""
    _ = pack_dir
    verify_symbolic_double_frame_and_errata()
    verify_dispersive_jc_and_numeric_dynamics()
    verify_worked(lesson_path)
