"""Independent verification of the Milestone 5 thrust-effectiveness model."""

from __future__ import annotations

import pytest

from edf_sizing.duct_losses import ThrustEffectivenessModel, static_available_thrust_N


def test_thrust_effectiveness_hand_case():
    t_ideal, eta_T = 147.10, 0.90
    expected = 147.10 * 0.90
    model = ThrustEffectivenessModel(eta_T=eta_T)
    result = float(static_available_thrust_N(t_ideal, model))
    assert result == pytest.approx(expected, rel=1e-12)
    assert result == pytest.approx(132.39, abs=1e-2)


def test_eta_T_equal_one_reproduces_ideal_reference():
    t_ideal = 147.10
    model = ThrustEffectivenessModel(eta_T=1.0)
    result = float(static_available_thrust_N(t_ideal, model))
    assert result == pytest.approx(t_ideal, rel=1e-12)


def test_lower_eta_T_lowers_available_thrust_monotonically():
    t_ideal = 147.10
    values = [
        float(static_available_thrust_N(t_ideal, ThrustEffectivenessModel(eta_T=e)))
        for e in (1.00, 0.90, 0.80, 0.70)
    ]
    assert all(a > b for a, b in zip(values, values[1:], strict=False))


@pytest.mark.parametrize("bad_eta", [0.0, -0.1, 1.1, 2.0])
def test_rejects_invalid_eta_T(bad_eta):
    with pytest.raises(ValueError):
        ThrustEffectivenessModel(eta_T=bad_eta)


def test_rejects_negative_ideal_thrust():
    model = ThrustEffectivenessModel(eta_T=0.9)
    with pytest.raises(ValueError):
        static_available_thrust_N(-1.0, model)
