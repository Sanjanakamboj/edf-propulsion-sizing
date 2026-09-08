"""Independent verification of Milestone 3 motor electrical-power and
shaft-torque relations."""

from __future__ import annotations

import math

import pytest

from edf_sizing import rotational as rot
from edf_sizing.motor import MotorAssumptions, motor_electrical_power, shaft_torque


def test_motor_electrical_power_hand_case():
    p_shaft, eta = 3000.0, 0.90
    expected = 3000.0 / 0.90  # computed independently
    assumption = MotorAssumptions(eta_motor=eta)
    result = float(motor_electrical_power(p_shaft, assumption))
    assert result == pytest.approx(expected, rel=1e-12)
    assert result == pytest.approx(3333.333333, rel=1e-6)


def test_motor_electrical_power_always_at_least_shaft_power():
    for eta in (0.99, 0.9, 0.7, 0.1):
        assumption = MotorAssumptions(eta_motor=eta)
        result = float(motor_electrical_power(500.0, assumption))
        assert result >= 500.0


def test_lower_motor_efficiency_increases_electrical_power():
    p_hi = float(motor_electrical_power(1000.0, MotorAssumptions(eta_motor=0.95)))
    p_lo = float(motor_electrical_power(1000.0, MotorAssumptions(eta_motor=0.80)))
    assert p_lo > p_hi


@pytest.mark.parametrize("bad_eta", [0.0, -0.1, 1.1, 2.0])
def test_motor_assumptions_rejects_invalid_efficiency(bad_eta):
    with pytest.raises(ValueError):
        MotorAssumptions(eta_motor=bad_eta)


def test_motor_assumptions_rejects_invalid_rated_power():
    with pytest.raises(ValueError):
        MotorAssumptions(eta_motor=0.9, rated_electrical_power_W=0.0)
    with pytest.raises(ValueError):
        MotorAssumptions(eta_motor=0.9, rated_electrical_power_W=-100.0)


def test_motor_electrical_power_rejects_negative_shaft_power():
    with pytest.raises(ValueError):
        motor_electrical_power(-1.0, MotorAssumptions(eta_motor=0.9))


# ---------------------------------------------------------------------------
# Shaft torque
# ---------------------------------------------------------------------------


def test_shaft_torque_hand_case():
    # P = 3429.7 W, RPM = 9298.313211084502 (M2 reference static case)
    p_shaft, rpm = 3429.719884475293, 9298.313211084502
    omega_hand = 2.0 * math.pi * (rpm / 60.0)
    q_hand = p_shaft / omega_hand
    q = float(shaft_torque(p_shaft, rpm))
    assert q == pytest.approx(q_hand, rel=1e-12)
    assert q == pytest.approx(3.5223, abs=1e-3)


def test_shaft_torque_matches_independent_omega_from_rotational_module():
    p_shaft, rpm = 633.8900315344832, 3001.0176845292235
    omega_independent = float(rot.angular_speed(rpm))
    q_hand = p_shaft / omega_independent
    q = float(shaft_torque(p_shaft, rpm))
    assert q == pytest.approx(q_hand, rel=1e-12)


def test_shaft_torque_is_positive_for_positive_power_and_rpm():
    q = float(shaft_torque(1000.0, 5000.0))
    assert q > 0.0


def test_shaft_torque_reconstructs_power_independently():
    """P_mech = Q * omega -- independent reconstruction using the
    rotational module's omega, never the production shaft_torque formula."""
    p_shaft, rpm = 2000.0, 8000.0
    q = float(shaft_torque(p_shaft, rpm))
    omega = float(rot.angular_speed(rpm))
    p_reconstructed = q * omega
    assert p_reconstructed == pytest.approx(p_shaft, rel=1e-9)


def test_shaft_torque_rejects_zero_or_negative_rpm():
    with pytest.raises(ValueError):
        shaft_torque(1000.0, 0.0)
    with pytest.raises(ValueError):
        shaft_torque(1000.0, -100.0)


def test_shaft_torque_rejects_negative_power():
    with pytest.raises(ValueError):
        shaft_torque(-1.0, 5000.0)
