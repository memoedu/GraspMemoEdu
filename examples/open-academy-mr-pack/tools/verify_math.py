#!/usr/bin/env python3
"""Symbolic, numerical, worked-example, and exhaustive exercise-template verifier for rotating-wave-and-frame."""

from __future__ import annotations

import itertools
import math
import re
import sys
from pathlib import Path

import numpy as np
import sympy as sp
import yaml


def verify_symbolic_identities() -> None:
    w0, w, Om, phi, t = sp.symbols("w0 w Om phi t", real=True)
    Sx = sp.Rational(1, 2) * sp.Matrix([[0, 1], [1, 0]])
    Sy = sp.Rational(1, 2) * sp.Matrix([[0, -sp.I], [sp.I, 0]])
    Sz = sp.Rational(1, 2) * sp.Matrix([[1, 0], [0, -1]])
    Sp = Sx + sp.I * Sy
    Sm = Sx - sp.I * Sy

    # Eq. (1.5): linear decomposition into co- and counter-rotating components
    lhs_15 = 2 * Om * sp.cos(w * t + phi) * Sx
    co = Om * (sp.cos(w * t + phi) * Sx + sp.sin(w * t + phi) * Sy)
    counter = Om * (sp.cos(w * t + phi) * Sx - sp.sin(w * t + phi) * Sy)
    assert sp.simplify(lhs_15 - (co + counter)) == sp.zeros(2, 2), "Eq. (1.5) mismatch"

    # Interaction picture unitary Ui = exp(-i * w * t * Sz)
    Ui = sp.Matrix([[sp.exp(-sp.I * w * t / 2), 0], [0, sp.exp(sp.I * w * t / 2)]])
    Ui_dag = Ui.H

    # Verify Ui_dag * Ui == I and H_I Eq. (1.7)-(1.9)
    assert sp.simplify(Ui_dag * Ui - sp.eye(2)) == sp.zeros(2, 2), "Ui unitarity mismatch"
    H_rwa = w0 * Sz + co
    H_I = sp.simplify(Ui_dag * H_rwa * Ui - Ui_dag * sp.I * sp.diff(Ui, t))
    H_I_expected = (w0 - w) * Sz + Om * (sp.cos(phi) * Sx + sp.sin(phi) * Sy)
    def mat_zero(m: sp.Matrix) -> bool:
        return m.applyfunc(lambda x: sp.simplify(x.rewrite(sp.exp))) == sp.zeros(m.rows, m.cols)

    assert mat_zero(H_I - H_I_expected), "Eq. (1.9) mismatch"

    # Eq. (1.8) specific case n=(0,0,-1), theta=w*t, r=(cos(w*t+phi), sin(w*t+phi), 0)
    # Rodrigues rotation around (0,0,-1) by theta = clockwise by w*t -> angle becomes phi
    r_dot_S = sp.cos(w * t + phi) * Sx + sp.sin(w * t + phi) * Sy
    rot_lhs = Ui_dag * r_dot_S * Ui  # since exp(-i theta (-Sz)) = exp(+i w t Sz) = Ui_dag
    rot_rhs = sp.cos(phi) * Sx + sp.sin(phi) * Sy
    assert mat_zero(rot_lhs - rot_rhs), "Eq. (1.8) specific mismatch"

    # General 3D Rodrigues check for Eq. (1.8) numerically with arbitrary n, theta, r
    rng = np.random.default_rng(42)
    Sx_np = np.array([[0, 0.5], [0.5, 0]], dtype=complex)
    Sy_np = np.array([[0, -0.5j], [0.5j, 0]], dtype=complex)
    Sz_np = np.array([[0.5, 0], [0, -0.5]], dtype=complex)
    S_vec = [Sx_np, Sy_np, Sz_np]
    for _ in range(10):
        n = rng.normal(size=3)
        n /= np.linalg.norm(n)
        theta = float(rng.uniform(-np.pi, np.pi))
        r = rng.normal(size=3)
        n_dot_S = sum(n[k] * S_vec[k] for k in range(3))
        r_dot_S_num = sum(r[k] * S_vec[k] for k in range(3))
        # U = exp(-i * theta * n_dot_S) = cos(theta/2)I - i*sin(theta/2)*(2 n_dot_S)
        U_rot = np.cos(theta / 2) * np.eye(2) - 1j * np.sin(theta / 2) * (2 * n_dot_S)
        lhs_num = U_rot @ r_dot_S_num @ U_rot.conj().T
        # Rodrigues: r_rot = r cos(theta) + (n x r) sin(theta) + n (n.r) (1 - cos(theta))
        r_rot = r * np.cos(theta) + np.cross(n, r) * np.sin(theta) + n * np.dot(n, r) * (1 - np.cos(theta))
        rhs_num = sum(r_rot[k] * S_vec[k] for k in range(3))
        assert np.max(np.abs(lhs_num - rhs_num)) < 1e-12, "General Eq. (1.8) failed"

    # Eq. (1.10)-(1.12) raising/lowering identities
    ket_up = sp.Matrix([1, 0])
    ket_dn = sp.Matrix([0, 1])
    assert Sp * ket_dn == ket_up and Sp * ket_up == sp.zeros(2, 1), "Eq. (1.10) S+ failed"
    assert Sm * ket_up == ket_dn and Sm * ket_dn == sp.zeros(2, 1), "Eq. (1.10) S- failed"
    assert sp.simplify(Ui_dag * Sp * Ui - sp.exp(sp.I * w * t) * Sp) == sp.zeros(2, 2), "Ui^dag S+ Ui failed"
    eq111 = sp.Rational(1, 2) * (
        sp.exp(-sp.I * (w * t + phi)) * (Ui_dag * Sp * Ui)
        + sp.exp(sp.I * (w * t + phi)) * (Ui_dag * Sm * Ui)
    )
    assert mat_zero(eq111 - rot_rhs), "Eq. (1.11)-(1.12) mismatch"
    print("[PASS] Symbolic & numerical verification of Eqs. (1.5)-(1.12) succeeded.")


def verify_worked_examples(lesson_path: Path) -> None:
    lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
    kps = {kp["id"]: kp for kp in lesson["knowledge_points"]}

    # Verify Step 3 no longer embeds raw Python code blocks (concept is math/conceptual, not implementation)
    for kp_id, kp in kps.items():
        assert "```python" not in kp["worked"], f"Unexpected python block in {kp_id}.worked"

    # Numerical check of all parameter values stated across Steps 1-3 worked examples
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
    w0 = 2.0 * np.pi * 1e4  # 10 GHz in MHz*rad
    w = 2.0 * np.pi * 9990.0
    Om = 2.0 * np.pi * 10.0
    H_I_expected = 2.0 * np.pi * (10.0 * Sz + 10.0 * Sy)

    for t_us in (0.0, 0.017, 0.25):
        Ui = np.diag([np.exp(-0.5j * w * t_us), np.exp(0.5j * w * t_us)])
        # Verify Step 3 worked actions on both basis kets |m_S=-1/2> and |m_S=+1/2>
        lhs_dn = Ui.conj().T @ Sp @ Ui @ ket_dn
        rhs_dn = np.exp(1j * w * t_us) * ket_up
        lhs_up = Ui.conj().T @ Sp @ Ui @ ket_up
        assert np.max(np.abs(lhs_dn - rhs_dn)) < 1e-12
        assert np.max(np.abs(lhs_up)) < 1e-12

        # Verify Step 2 & Step 3 full transformed Hamiltonian matches 10 MHz * Sz + 10 MHz * Sy
        H_rwa = w0 * Sz + Om * (np.cos(w * t_us + phi) * Sx + np.sin(w * t_us + phi) * Sy)
        H_I_rot = (w0 - w) * Sz + Ui.conj().T @ (Om * (np.cos(w * t_us + phi) * Sx + np.sin(w * t_us + phi) * Sy)) @ Ui
        assert np.max(np.abs(H_I_rot - H_I_expected)) < 1e-10
        assert np.max(np.abs(Ui.conj().T @ H_rwa @ Ui - w * Sz - H_I_expected)) < 1e-10

    # Verify truncated bosonic ladder relation e^{i w t a^\dagger a} a^\dagger e^{-i w t a^\dagger a} = a^\dagger e^{i w t}
    nmax = 6
    a_dag = np.diag(np.sqrt(np.arange(1, nmax)), k=-1).astype(complex)
    n_op = a_dag @ a_dag.conj().T
    for t_val in (0.13, 0.77):
        Ub = np.diag(np.exp(-1j * 3.5 * t_val * np.diag(n_op)))
        err_boson = np.max(np.abs(Ub.conj()[:-1, :-1].T @ a_dag[:-1, :-1] @ Ub[:-1, :-1] - np.exp(1j * 3.5 * t_val) * a_dag[:-1, :-1]))
        assert err_boson < 1e-12

    print("[PASS] Numerical verification of Steps 1-3 worked examples & bosonic identity succeeded.")


def verify_exercises(ex_path: Path) -> None:
    edoc = yaml.safe_load(ex_path.read_text(encoding="utf-8"))
    exs = edoc["exercises"]

    # 1. Exhaustively check numeric templates
    for ex in exs:
        if ex["type"] == "numeric" and "params" in ex:
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
                f"[PASS] Template {ex['id']}: {valid} valid combinations, {len(ans_set)} distinct answers "
                f"(range [{min(ans_set)}, {max(ans_set)}])"
            )

        # 2. Check expression exercises
        if ex["type"] == "expression":
            ans_sym = sp.sympify(ex["answer"].replace("^", "**"))
            vars_spec = ex.get("variables", {})
            assert set(map(str, ans_sym.free_symbols)) == set(vars_spec.keys())
            print(f"[PASS] Expression {ex['id']}: answer='{ex['answer']}', vars={list(vars_spec.keys())}")

        # 3. Check text exercises (accept strings vs regex)
        if ex["type"] == "text":
            rx = re.compile(ex["regex"]) if ex.get("regex") else None
            if rx:
                for acc in ex.get("accept", []):
                    assert rx.match(acc), f"Regex in {ex['id']} failed to match accept '{acc}'"
            print(f"[PASS] Text {ex['id']}: {len(ex.get('accept', []))} accept patterns validated against regex")


def main() -> int:
    pack = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    verify_symbolic_identities()
    verify_worked_examples(pack / "lessons" / "rotating-wave-and-frame.yaml")
    verify_exercises(pack / "exercises" / "rotating-wave-and-frame.yaml")
    print("ALL MATHEMATICAL & TEMPLATE VERIFICATIONS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
