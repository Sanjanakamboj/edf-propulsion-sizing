"""Independent verification of Milestone 2 pressure-jump and nondimensional
fan/propeller coefficient relations."""

from __future__ import annotations

import math

import pytest

from edf_sizing import actuator_disk as ad
from edf_sizing import fan_loading as fl

# ---------------------------------------------------------------------------
# Pressure jump
# ---------------------------------------------------------------------------


def test_pressure_jump_disk_hand_case():
    T, A = 147.10, 0.19634954084936207
    dp_hand = T / A
    assert dp_hand == pytest.approx(749.14, abs=0.05)
    assert float(fl.pressure_jump_disk(T, A)) == pytest.approx(dp_hand, rel=1e-12)


def test_pressure_jump_disk_identity_with_m1_disk_loading():
    """The M2 pressure-jump estimate must numerically equal the M1 disk
    loading for the same (T, A) -- same actuator-disk quantity, computed
    via the independent M1 module."""
    T, D = 147.0997500000000015, 0.5  # M1 selected-fan static thrust/diameter
    area = float(ad.disk_area(D))
    dl_m1 = float(ad.disk_loading(T, area))
    dp_m2 = float(fl.pressure_jump_disk(T, area))
    assert dp_m2 == pytest.approx(dl_m1, rel=1e-12)


def test_pressure_jump_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        fl.pressure_jump_disk(-1.0, 0.1)
    with pytest.raises(ValueError):
        fl.pressure_jump_disk(10.0, 0.0)


# ---------------------------------------------------------------------------
# C_T, C_P, J -- hand-derived
# ---------------------------------------------------------------------------


def test_thrust_coefficient_hand_case():
    T, rho, n, D = 150.0, 1.225, 150.0, 0.5
    ct_hand = T / (rho * n**2 * D**4)
    assert float(fl.thrust_coefficient(T, rho, n, D)) == pytest.approx(ct_hand, rel=1e-12)


def test_power_coefficient_hand_case():
    P, rho, n, D = 3000.0, 1.225, 150.0, 0.5
    cp_hand = P / (rho * n**3 * D**5)
    assert float(fl.power_coefficient(P, rho, n, D)) == pytest.approx(cp_hand, rel=1e-12)


def test_advance_ratio_hand_case():
    V, n, D = 30.0, 150.0, 0.5
    j_hand = V / (n * D)
    assert float(fl.advance_ratio(V, n, D)) == pytest.approx(j_hand, rel=1e-12)


def test_advance_ratio_zero_at_static_condition():
    n, D = 150.0, 0.5
    assert float(fl.advance_ratio(0.0, n, D)) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Scaling behavior
# ---------------------------------------------------------------------------


def test_thrust_coefficient_scales_as_n_inverse_square():
    T, rho, D = 150.0, 1.225, 0.5
    n1, n2 = 100.0, 200.0
    ct1 = float(fl.thrust_coefficient(T, rho, n1, D))
    ct2 = float(fl.thrust_coefficient(T, rho, n2, D))
    assert ct1 / ct2 == pytest.approx((n2 / n1) ** 2, rel=1e-9)


def test_power_coefficient_scales_as_n_inverse_cube():
    P, rho, D = 3000.0, 1.225, 0.5
    n1, n2 = 100.0, 250.0
    cp1 = float(fl.power_coefficient(P, rho, n1, D))
    cp2 = float(fl.power_coefficient(P, rho, n2, D))
    assert cp1 / cp2 == pytest.approx((n2 / n1) ** 3, rel=1e-9)


def test_thrust_coefficient_rejects_zero_or_negative_n():
    with pytest.raises(ValueError):
        fl.thrust_coefficient(100.0, 1.225, 0.0, 0.5)
    with pytest.raises(ValueError):
        fl.thrust_coefficient(100.0, 1.225, -10.0, 0.5)


def test_power_coefficient_rejects_zero_n():
    with pytest.raises(ValueError):
        fl.power_coefficient(1000.0, 1.225, 0.0, 0.5)


def test_advance_ratio_rejects_zero_n():
    with pytest.raises(ValueError):
        fl.advance_ratio(20.0, 0.0, 0.5)


# ---------------------------------------------------------------------------
# RPM (n) inversion from C_T
# ---------------------------------------------------------------------------


def test_rev_per_second_from_thrust_coefficient_hand_case():
    T, rho, D, ct = 147.0997500000000015, 1.225, 0.5, 0.08
    n_hand = math.sqrt(T / (rho * ct * D**4))
    n = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, ct))
    assert n == pytest.approx(n_hand, rel=1e-12)


def test_rev_per_second_from_thrust_coefficient_round_trip():
    """Recompute C_T from the inferred n and confirm it recovers the
    original assumed C_T (round-trip identity)."""
    T, rho, D, ct_assumed = 200.0, 1.225, 0.4, 0.10
    n = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, ct_assumed))
    ct_recovered = float(fl.thrust_coefficient(T, rho, n, D))
    assert ct_recovered == pytest.approx(ct_assumed, rel=1e-9)


def test_required_rpm_decreases_with_larger_c_t_at_fixed_thrust_and_diameter():
    T, rho, D = 150.0, 1.225, 0.5
    n_low_ct = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, 0.05))
    n_high_ct = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, 0.15))
    assert n_high_ct < n_low_ct


def test_required_rpm_scales_as_c_t_inverse_sqrt():
    T, rho, D = 150.0, 1.225, 0.5
    ct1, ct2 = 0.05, 0.20
    n1 = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, ct1))
    n2 = float(fl.rev_per_second_from_thrust_coefficient(T, rho, D, ct2))
    assert n1 / n2 == pytest.approx(math.sqrt(ct2 / ct1), rel=1e-9)


def test_required_rpm_decreases_with_larger_diameter_at_fixed_thrust_and_c_t():
    T, rho, ct = 150.0, 1.225, 0.08
    n_small_d = float(fl.rev_per_second_from_thrust_coefficient(T, rho, 0.3, ct))
    n_large_d = float(fl.rev_per_second_from_thrust_coefficient(T, rho, 0.6, ct))
    assert n_large_d < n_small_d


def test_required_rpm_scales_as_diameter_inverse_square():
    T, rho, ct = 150.0, 1.225, 0.08
    d1, d2 = 0.3, 0.6
    n1 = float(fl.rev_per_second_from_thrust_coefficient(T, rho, d1, ct))
    n2 = float(fl.rev_per_second_from_thrust_coefficient(T, rho, d2, ct))
    assert n1 / n2 == pytest.approx((d2 / d1) ** 2, rel=1e-9)


def test_rev_per_second_from_thrust_coefficient_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        fl.rev_per_second_from_thrust_coefficient(-1.0, 1.225, 0.5, 0.08)
    with pytest.raises(ValueError):
        fl.rev_per_second_from_thrust_coefficient(150.0, 0.0, 0.5, 0.08)
    with pytest.raises(ValueError):
        fl.rev_per_second_from_thrust_coefficient(150.0, 1.225, 0.0, 0.08)
    with pytest.raises(ValueError):
        fl.rev_per_second_from_thrust_coefficient(150.0, 1.225, 0.5, 0.0)
    with pytest.raises(ValueError):
        fl.rev_per_second_from_thrust_coefficient(150.0, 1.225, 0.5, -0.05)
