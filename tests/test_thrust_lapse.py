"""Independent verification of the Milestone 5 forward-flight thrust-lapse
model."""

from __future__ import annotations

import pytest

from edf_sizing.thrust_lapse import ThrustLapseModel, available_thrust_N, lapse_factor


def test_linear_lapse_gives_exactly_one_at_zero_speed():
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    assert float(lapse_factor(0.0, model)) == pytest.approx(1.0, abs=1e-12)


def test_quadratic_lapse_gives_exactly_one_at_zero_speed():
    model = ThrustLapseModel(kind="quadratic", k=0.30, v_ref_m_s=60.0)
    assert float(lapse_factor(0.0, model)) == pytest.approx(1.0, abs=1e-12)


def test_linear_lapse_hand_case():
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    v = 30.0
    expected = 1.0 - 0.30 * (30.0 / 60.0)
    assert float(lapse_factor(v, model)) == pytest.approx(expected, rel=1e-12)
    assert float(lapse_factor(v, model)) == pytest.approx(0.85, abs=1e-9)


def test_quadratic_lapse_hand_case():
    model = ThrustLapseModel(kind="quadratic", k=0.30, v_ref_m_s=60.0)
    v = 30.0
    expected = 1.0 - 0.30 * (30.0 / 60.0) ** 2
    assert float(lapse_factor(v, model)) == pytest.approx(expected, rel=1e-12)
    assert float(lapse_factor(v, model)) == pytest.approx(0.925, abs=1e-9)


def test_lapse_factor_bounded_in_zero_one_over_wide_range():
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    for v in (0.0, 10.0, 60.0, 200.0, 1000.0):
        f = float(lapse_factor(v, model))
        assert 0.0 <= f <= 1.0


def test_quadratic_lapse_factor_bounded_in_zero_one_over_wide_range():
    model = ThrustLapseModel(kind="quadratic", k=0.30, v_ref_m_s=60.0)
    for v in (0.0, 10.0, 60.0, 200.0, 1000.0):
        f = float(lapse_factor(v, model))
        assert 0.0 <= f <= 1.0


def test_increasing_speed_lowers_available_thrust_for_baseline_lapse():
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    t_static = 132.39
    values = [float(available_thrust_N(t_static, v, model)) for v in (0.0, 10.0, 20.0, 30.0, 40.0)]
    assert all(a > b for a, b in zip(values, values[1:], strict=False))


def test_available_thrust_hand_case():
    t_static, v = 132.39, 30.0
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    expected = 132.39 * (1.0 - 0.30 * (30.0 / 60.0))
    assert float(available_thrust_N(t_static, v, model)) == pytest.approx(expected, rel=1e-9)


def test_available_thrust_at_zero_speed_equals_static_available():
    t_static = 132.39
    model = ThrustLapseModel(kind="linear", k=0.30, v_ref_m_s=60.0)
    assert float(available_thrust_N(t_static, 0.0, model)) == pytest.approx(t_static, rel=1e-12)


@pytest.mark.parametrize("bad_kind", ["bogus", "", "LINEAR"])
def test_rejects_invalid_kind(bad_kind):
    with pytest.raises(ValueError):
        ThrustLapseModel(kind=bad_kind, k=0.3, v_ref_m_s=60.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_k", [-0.1, -5.0])
def test_rejects_negative_k(bad_k):
    with pytest.raises(ValueError):
        ThrustLapseModel(kind="linear", k=bad_k, v_ref_m_s=60.0)


@pytest.mark.parametrize("bad_vref", [0.0, -10.0])
def test_rejects_invalid_v_ref(bad_vref):
    with pytest.raises(ValueError):
        ThrustLapseModel(kind="linear", k=0.3, v_ref_m_s=bad_vref)


def test_rejects_negative_airspeed():
    model = ThrustLapseModel(kind="linear", k=0.3, v_ref_m_s=60.0)
    with pytest.raises(ValueError):
        lapse_factor(-1.0, model)
    with pytest.raises(ValueError):
        available_thrust_N(100.0, -1.0, model)


def test_available_thrust_rejects_negative_static_thrust():
    model = ThrustLapseModel(kind="linear", k=0.3, v_ref_m_s=60.0)
    with pytest.raises(ValueError):
        available_thrust_N(-1.0, 10.0, model)
