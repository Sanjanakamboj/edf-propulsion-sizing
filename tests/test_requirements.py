"""Tests for the generic representative UAV requirement."""

from __future__ import annotations

import pytest

from edf_sizing.requirements import G_STANDARD, UAVRequirement, default_requirement


def test_weight_and_thrust_hand_derived():
    req = UAVRequirement(
        mass_kg=25.0,
        n_fans=2,
        rho_kg_m3=1.225,
        v_cruise_m_s=30.0,
        static_thrust_to_weight=1.2,
        cruise_lift_to_drag=8.0,
    )
    expected_weight = 25.0 * G_STANDARD
    assert req.weight_N == pytest.approx(expected_weight, rel=1e-12)

    expected_static_total = 1.2 * expected_weight
    assert req.static_thrust_total_N == pytest.approx(expected_static_total, rel=1e-12)
    assert req.static_thrust_per_fan_N == pytest.approx(expected_static_total / 2.0, rel=1e-12)

    expected_cruise_total = expected_weight / 8.0
    assert req.cruise_thrust_total_N == pytest.approx(expected_cruise_total, rel=1e-12)
    assert req.cruise_thrust_per_fan_N == pytest.approx(expected_cruise_total / 2.0, rel=1e-12)


def test_default_requirement_is_generic_and_reasonable():
    req = default_requirement()
    assert 1.0 < req.mass_kg < 500.0  # generic small/medium UAV, not a real aircraft
    assert req.n_fans >= 1
    assert 0.9 < req.rho_kg_m3 < 1.3  # plausible atmospheric density
    assert 0.0 <= req.v_cruise_m_s < 150.0
    assert req.static_thrust_per_fan_N > 0.0
    assert req.cruise_thrust_per_fan_N > 0.0
    # Static thrust requirement should exceed cruise thrust requirement for
    # a sensible margin-based hover/vertical case vs. cruise drag case.
    assert req.static_thrust_per_fan_N > req.cruise_thrust_per_fan_N


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("mass_kg", 0.0),
        ("mass_kg", -1.0),
        ("n_fans", 0),
        ("rho_kg_m3", 0.0),
        ("rho_kg_m3", -1.0),
        ("v_cruise_m_s", -1.0),
        ("static_thrust_to_weight", 0.0),
        ("cruise_lift_to_drag", 0.0),
    ],
)
def test_requirement_rejects_invalid_inputs(field_name, bad_value):
    kwargs = {field_name: bad_value}
    with pytest.raises(ValueError):
        UAVRequirement(**kwargs)
