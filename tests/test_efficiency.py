"""Tests for the non-ideal efficiency bookkeeping layer.

Verifies the layer is a pure division bookkeeping step, independent of the
ideal actuator-disk physics, and rejects invalid inputs.
"""

from __future__ import annotations

import pytest

from edf_sizing.efficiency import NonIdealAssumption, estimated_shaft_power


def test_estimated_shaft_power_hand_derived():
    ideal_power = 1000.0
    eta = 0.8
    expected = 1000.0 / 0.8  # = 1250.0, computed by hand independently
    assumption = NonIdealAssumption(eta_overall=eta)
    result = float(estimated_shaft_power(ideal_power, assumption))
    assert result == pytest.approx(expected, rel=1e-12)
    assert result == pytest.approx(1250.0, rel=1e-12)


def test_estimated_shaft_power_always_at_least_ideal_power():
    for eta in (0.99, 0.8, 0.5, 0.1):
        assumption = NonIdealAssumption(eta_overall=eta)
        result = float(estimated_shaft_power(500.0, assumption))
        assert result >= 500.0


def test_estimated_shaft_power_monotonic_in_efficiency():
    # Lower efficiency -> higher estimated shaft power for the same Pi.
    p_hi_eta = float(estimated_shaft_power(500.0, NonIdealAssumption(eta_overall=0.9)))
    p_lo_eta = float(estimated_shaft_power(500.0, NonIdealAssumption(eta_overall=0.5)))
    assert p_lo_eta > p_hi_eta


@pytest.mark.parametrize("bad_eta", [0.0, -0.1, 1.1, 2.0])
def test_nonideal_assumption_rejects_invalid_efficiency(bad_eta):
    with pytest.raises(ValueError):
        NonIdealAssumption(eta_overall=bad_eta)


def test_estimated_shaft_power_rejects_negative_ideal_power():
    assumption = NonIdealAssumption(eta_overall=0.75)
    with pytest.raises(ValueError):
        estimated_shaft_power(-1.0, assumption)
