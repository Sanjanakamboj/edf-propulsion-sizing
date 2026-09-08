"""Independent verification of Milestone 2 rotational kinematics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from edf_sizing import rotational as rot


def test_rpm_to_rev_per_second_hand_case():
    assert float(rot.rpm_to_rev_per_second(6000.0)) == pytest.approx(100.0, rel=1e-12)


def test_rev_per_second_to_rpm_hand_case():
    assert float(rot.rev_per_second_to_rpm(100.0)) == pytest.approx(6000.0, rel=1e-12)


def test_rpm_rev_per_second_round_trip():
    rpm = 8342.5
    n = rot.rpm_to_rev_per_second(rpm)
    rpm_back = rot.rev_per_second_to_rpm(n)
    assert float(rpm_back) == pytest.approx(rpm, rel=1e-12)


def test_angular_speed_hand_case():
    # RPM = 6000 -> n = 100 rev/s -> omega = 2*pi*100 = 628.318... rad/s
    omega_hand = 2.0 * math.pi * 100.0
    assert float(rot.angular_speed(6000.0)) == pytest.approx(omega_hand, rel=1e-12)


def test_tip_speed_hand_case():
    # D = 0.5 m, RPM = 6000 -> n = 100 rev/s -> U_tip = pi*0.5*100 = 157.0796...
    d, rpm = 0.5, 6000.0
    u_tip_hand = math.pi * d * 100.0
    assert float(rot.tip_speed(d, rpm)) == pytest.approx(u_tip_hand, rel=1e-12)
    assert float(rot.tip_speed(d, rpm)) == pytest.approx(157.07963, abs=1e-4)


def test_tip_speed_matches_omega_times_radius_independent_form():
    d, rpm = 0.37, 9500.0
    omega = float(rot.angular_speed(rpm))
    u_tip_via_omega_r = omega * (d / 2.0)
    u_tip = float(rot.tip_speed(d, rpm))
    assert u_tip == pytest.approx(u_tip_via_omega_r, rel=1e-12)


def test_tip_speed_increases_linearly_with_rpm():
    d = 0.4
    rpms = np.array([1000.0, 2000.0, 3000.0, 4000.0])
    tips = np.array([float(rot.tip_speed(d, r)) for r in rpms])
    ratios = tips[1:] / tips[:-1]
    rpm_ratios = rpms[1:] / rpms[:-1]
    assert ratios == pytest.approx(rpm_ratios, rel=1e-10)


def test_tip_speed_zero_rpm_gives_zero_tip_speed():
    assert float(rot.tip_speed(0.5, 0.0)) == pytest.approx(0.0, abs=1e-12)


def test_larger_diameter_at_fixed_rpm_gives_higher_tip_speed():
    rpm = 5000.0
    diameters = [0.2, 0.3, 0.4, 0.5, 0.6]
    tips = [float(rot.tip_speed(d, rpm)) for d in diameters]
    assert all(a < b for a, b in zip(tips, tips[1:], strict=False))


@pytest.mark.parametrize("bad_rpm", [-1.0, -100.0])
def test_rejects_negative_rpm(bad_rpm):
    with pytest.raises(ValueError):
        rot.rpm_to_rev_per_second(bad_rpm)
    with pytest.raises(ValueError):
        rot.angular_speed(bad_rpm)
    with pytest.raises(ValueError):
        rot.tip_speed(0.5, bad_rpm)


@pytest.mark.parametrize("bad_d", [0.0, -0.1, -5.0])
def test_rejects_nonpositive_diameter(bad_d):
    with pytest.raises(ValueError):
        rot.tip_speed(bad_d, 5000.0)


def test_rejects_negative_n():
    with pytest.raises(ValueError):
        rot.rev_per_second_to_rpm(-10.0)


def test_scalar_vector_consistency_tip_speed():
    d = 0.45
    rpms = np.array([1000.0, 3000.0, 7000.0])
    vec = rot.tip_speed(d, rpms)
    for i, r in enumerate(rpms):
        scalar = float(rot.tip_speed(d, float(r)))
        assert float(vec[i]) == pytest.approx(scalar, rel=1e-12)
