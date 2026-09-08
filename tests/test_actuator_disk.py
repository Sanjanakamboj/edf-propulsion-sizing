"""Independent verification of the ideal actuator-disk relations.

These tests deliberately avoid calling the production formula on both sides
of a comparison. Expected values are computed either by hand (literal
numbers) or via an independently coded formula (e.g. via mass-flow /
far-wake reasoning rather than the T^(3/2)/sqrt(2*rho*A) shortcut).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from edf_sizing import actuator_disk as ad

# ---------------------------------------------------------------------------
# Hand-derived static checks
# ---------------------------------------------------------------------------


def test_static_induced_velocity_hand_derived():
    # T = 100 N, rho = 1.225 kg/m^3, D = 0.4 m -> A = pi*0.16/4 = 0.12566 m^2
    # vi = sqrt(100 / (2*1.225*0.12566)) = sqrt(100/0.307869) = sqrt(324.82...)
    T, rho, D = 100.0, 1.225, 0.4
    A_hand = math.pi * D**2 / 4.0
    vi_hand = math.sqrt(T / (2.0 * rho * A_hand))
    assert vi_hand == pytest.approx(18.02238, abs=1e-3)

    A = ad.disk_area(D)
    vi = ad.static_induced_velocity(T, rho, A)
    assert float(vi) == pytest.approx(vi_hand, rel=1e-10)


def test_static_ideal_power_hand_derived():
    # Same case as above; Pi = T * vi (hand value) and independently
    # Pi = T^1.5 / sqrt(2*rho*A).
    T, rho, D = 100.0, 1.225, 0.4
    A_hand = math.pi * D**2 / 4.0
    vi_hand = math.sqrt(T / (2.0 * rho * A_hand))
    Pi_hand_via_T_vi = T * vi_hand
    Pi_hand_via_closed_form = T**1.5 / math.sqrt(2.0 * rho * A_hand)
    assert Pi_hand_via_T_vi == pytest.approx(Pi_hand_via_closed_form, rel=1e-12)
    assert Pi_hand_via_T_vi == pytest.approx(1802.24, abs=0.5)

    A = ad.disk_area(D)
    Pi = ad.static_ideal_power(T, rho, A)
    assert float(Pi) == pytest.approx(Pi_hand_via_T_vi, rel=1e-10)


def test_disk_loading_hand_derived():
    T, D = 150.0, 0.5
    A_hand = math.pi * 0.25 / 4.0  # 0.19635
    dl_hand = T / A_hand
    assert dl_hand == pytest.approx(763.94, abs=0.1)
    dl = ad.disk_loading(T, ad.disk_area(D))
    assert float(dl) == pytest.approx(dl_hand, rel=1e-10)


# ---------------------------------------------------------------------------
# Analytic verification of the forward-flight quadratic root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "T,rho,D,V",
    [
        (50.0, 1.225, 0.3, 10.0),
        (150.0, 1.225, 0.5, 25.0),
        (20.0, 1.05, 0.25, 40.0),
        (300.0, 1.225, 0.6, 0.5),
    ],
)
def test_forward_induced_velocity_satisfies_thrust_equation(T, rho, D, V):
    """Plug the computed root back into T = 2*rho*A*vi*(V+vi) independently."""
    A = float(ad.disk_area(D))
    vi = float(ad.forward_induced_velocity(T, rho, A, V))
    T_reconstructed = 2.0 * rho * A * vi * (V + vi)
    assert T_reconstructed == pytest.approx(T, rel=1e-9)
    assert vi > 0.0  # physically valid root


def test_forward_induced_velocity_matches_quadratic_formula_by_hand():
    # T=150, rho=1.225, D=0.5 -> A=0.19635, V=25
    T, rho, D, V = 150.0, 1.225, 0.5, 25.0
    A = math.pi * D**2 / 4.0
    a_coef = 2.0 * rho * A
    b_coef = 2.0 * rho * A * V
    c_coef = -T
    vi_hand = (-b_coef + math.sqrt(b_coef**2 - 4 * a_coef * c_coef)) / (2 * a_coef)
    vi = float(ad.forward_induced_velocity(T, rho, A, V))
    assert vi == pytest.approx(vi_hand, rel=1e-9)


# ---------------------------------------------------------------------------
# Limiting behavior as V_inf -> 0
# ---------------------------------------------------------------------------


def test_forward_flight_reduces_to_static_as_v_inf_vanishes():
    T, rho, D = 120.0, 1.225, 0.4
    A = float(ad.disk_area(D))
    vi_static = float(ad.static_induced_velocity(T, rho, A))
    vi_forward_zero = float(ad.forward_induced_velocity(T, rho, A, 0.0))
    assert vi_forward_zero == pytest.approx(vi_static, rel=1e-12)

    vi_forward_tiny = float(ad.forward_induced_velocity(T, rho, A, 1e-6))
    assert vi_forward_tiny == pytest.approx(vi_static, rel=1e-4)


def test_forward_ideal_power_reduces_to_static_as_v_inf_vanishes():
    T, rho, D = 120.0, 1.225, 0.4
    A = float(ad.disk_area(D))
    vi_static = float(ad.static_induced_velocity(T, rho, A))
    Pi_static = float(ad.static_ideal_power(T, rho, A))
    Pi_forward_zero = float(ad.forward_ideal_power(T, 0.0, vi_static))
    assert Pi_forward_zero == pytest.approx(Pi_static, rel=1e-12)


# ---------------------------------------------------------------------------
# Dimensional / monotonic sanity checks
# ---------------------------------------------------------------------------


def test_disk_loading_and_power_decrease_with_diameter_at_fixed_thrust():
    T, rho = 150.0, 1.225
    diameters = [0.2, 0.3, 0.4, 0.5, 0.6]
    areas = [float(ad.disk_area(d)) for d in diameters]
    disk_loadings = [float(ad.disk_loading(T, a)) for a in areas]
    powers = [float(ad.static_ideal_power(T, rho, a)) for a in areas]
    induced_vels = [float(ad.static_induced_velocity(T, rho, a)) for a in areas]

    assert all(x > y for x, y in zip(disk_loadings, disk_loadings[1:], strict=False))
    assert all(x > y for x, y in zip(powers, powers[1:], strict=False))
    assert all(x > y for x, y in zip(induced_vels, induced_vels[1:], strict=False))


def test_power_increases_with_thrust_at_fixed_diameter():
    rho, D = 1.225, 0.4
    A = float(ad.disk_area(D))
    thrusts = [10.0, 50.0, 100.0, 200.0, 400.0]
    powers = [float(ad.static_ideal_power(t, rho, A)) for t in thrusts]
    assert all(x < y for x, y in zip(powers, powers[1:], strict=False))


def test_forward_power_increases_with_thrust_at_fixed_diameter_and_speed():
    rho, D, V = 1.225, 0.4, 20.0
    A = float(ad.disk_area(D))
    thrusts = [10.0, 50.0, 100.0, 200.0]
    powers = []
    for t in thrusts:
        vi = float(ad.forward_induced_velocity(t, rho, A, V))
        powers.append(float(ad.forward_ideal_power(t, V, vi)))
    assert all(x < y for x, y in zip(powers, powers[1:], strict=False))


def test_units_are_dimensionally_sane_orders_of_magnitude():
    # A 0.3 m EDF at ~100 N static thrust should have induced velocity of
    # tens of m/s and power of a few kW -- not micro/mega magnitudes.
    T, rho, D = 100.0, 1.225, 0.3
    A = float(ad.disk_area(D))
    vi = float(ad.static_induced_velocity(T, rho, A))
    Pi = float(ad.static_ideal_power(T, rho, A))
    assert 5.0 < vi < 100.0
    assert 100.0 < Pi < 20000.0


# ---------------------------------------------------------------------------
# Scalar / vector consistency
# ---------------------------------------------------------------------------


def test_vectorized_matches_scalar_loop_static():
    rho = 1.225
    diameters = np.array([0.2, 0.3, 0.4, 0.5])
    T = 80.0
    areas_vec = ad.disk_area(diameters)
    vi_vec = ad.static_induced_velocity(T, rho, areas_vec)
    pi_vec = ad.static_ideal_power(T, rho, areas_vec)

    for i, d in enumerate(diameters):
        area_scalar = float(ad.disk_area(float(d)))
        vi_scalar = float(ad.static_induced_velocity(T, rho, area_scalar))
        pi_scalar = float(ad.static_ideal_power(T, rho, area_scalar))
        assert float(areas_vec[i]) == pytest.approx(area_scalar, rel=1e-12)
        assert float(vi_vec[i]) == pytest.approx(vi_scalar, rel=1e-12)
        assert float(pi_vec[i]) == pytest.approx(pi_scalar, rel=1e-12)


def test_vectorized_matches_scalar_loop_forward_flight():
    rho, D = 1.225, 0.35
    A = float(ad.disk_area(D))
    thrusts = np.array([20.0, 50.0, 100.0])
    v_inf = np.array([5.0, 15.0, 30.0])
    vi_vec = ad.forward_induced_velocity(thrusts, rho, A, v_inf)
    pi_vec = ad.forward_ideal_power(thrusts, v_inf, vi_vec)

    for i in range(len(thrusts)):
        vi_scalar = float(
            ad.forward_induced_velocity(float(thrusts[i]), rho, A, float(v_inf[i]))
        )
        pi_scalar = float(ad.forward_ideal_power(float(thrusts[i]), float(v_inf[i]), vi_scalar))
        assert float(vi_vec[i]) == pytest.approx(vi_scalar, rel=1e-12)
        assert float(pi_vec[i]) == pytest.approx(pi_scalar, rel=1e-12)


# ---------------------------------------------------------------------------
# Invalid-input rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_diameter", [0.0, -0.1, -5.0])
def test_disk_area_rejects_nonpositive_diameter(bad_diameter):
    with pytest.raises(ValueError):
        ad.disk_area(bad_diameter)


@pytest.mark.parametrize("bad_area", [0.0, -1.0])
def test_disk_loading_rejects_nonpositive_area(bad_area):
    with pytest.raises(ValueError):
        ad.disk_loading(100.0, bad_area)


def test_disk_loading_rejects_negative_thrust():
    with pytest.raises(ValueError):
        ad.disk_loading(-10.0, 0.1)


@pytest.mark.parametrize("bad_rho", [0.0, -1.225])
def test_static_induced_velocity_rejects_nonpositive_rho(bad_rho):
    with pytest.raises(ValueError):
        ad.static_induced_velocity(100.0, bad_rho, 0.1)


def test_static_induced_velocity_rejects_negative_thrust():
    with pytest.raises(ValueError):
        ad.static_induced_velocity(-10.0, 1.225, 0.1)


def test_forward_induced_velocity_rejects_negative_v_inf():
    with pytest.raises(ValueError):
        ad.forward_induced_velocity(100.0, 1.225, 0.1, -5.0)


def test_forward_induced_velocity_rejects_nonpositive_area():
    with pytest.raises(ValueError):
        ad.forward_induced_velocity(100.0, 1.225, 0.0, 10.0)


def test_forward_ideal_power_rejects_negative_inputs():
    with pytest.raises(ValueError):
        ad.forward_ideal_power(-1.0, 10.0, 5.0)
    with pytest.raises(ValueError):
        ad.forward_ideal_power(10.0, -1.0, 5.0)
    with pytest.raises(ValueError):
        ad.forward_ideal_power(10.0, 10.0, -1.0)


# ---------------------------------------------------------------------------
# Independent energy/power reconstruction (mass-flow / far-wake argument)
# ---------------------------------------------------------------------------


def test_independent_energy_reconstruction_static():
    """Reconstruct static ideal power from a fully independent chain:

    mdot = rho * A * vi
    Ve   = 2 * vi           (far-wake velocity is twice the induced velocity)
    Pi   = 1/2 * mdot * Ve^2

    This must match T*vi even though it never uses the T^(3/2)/sqrt(2 rho A)
    closed form or the momentum thrust equation directly.
    """
    T, rho, D = 175.0, 1.225, 0.45
    A = float(ad.disk_area(D))
    vi = float(ad.static_induced_velocity(T, rho, A))

    mdot = rho * A * vi
    Ve = 2.0 * vi
    Pi_energy = 0.5 * mdot * Ve**2

    Pi_production = float(ad.static_ideal_power(T, rho, A))
    assert Pi_energy == pytest.approx(Pi_production, rel=1e-9)

    # Also cross-check thrust from momentum: T = mdot * Ve
    T_momentum = mdot * Ve
    assert T_momentum == pytest.approx(T, rel=1e-9)


def test_independent_energy_reconstruction_forward_flight():
    """Same independent mass-flow / far-wake reconstruction, forward flight.

    At the disk, flow velocity is V_inf + vi; far downstream it is
    V_inf + 2*vi. Flow power delivered to the stream is the kinetic-energy
    flux difference between far wake and freestream, per unit time, which
    for actuator-disk theory equals T*(V_inf + vi).
    """
    T, rho, D, V = 90.0, 1.225, 0.35, 22.0
    A = float(ad.disk_area(D))
    vi = float(ad.forward_induced_velocity(T, rho, A, V))

    mdot = rho * A * (V + vi)
    Ve = V + 2.0 * vi
    T_momentum = mdot * (Ve - V)
    assert T_momentum == pytest.approx(T, rel=1e-9)

    # Kinetic energy flux gained by the stream per unit time:
    KE_rate = 0.5 * mdot * (Ve**2 - V**2)
    Pi_production = float(ad.forward_ideal_power(T, V, vi))
    assert KE_rate == pytest.approx(Pi_production, rel=1e-9)
