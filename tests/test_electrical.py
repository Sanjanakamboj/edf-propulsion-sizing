"""Independent verification of Milestone 3 generic electrical primitives
and the ESC model."""

from __future__ import annotations

import pytest

from edf_sizing.electrical import (
    ESCModel,
    battery_input_power,
    current_from_power,
    electrical_power,
    rating_margin,
)


def test_electrical_power_hand_case():
    v, i = 44.4, 88.5
    expected = 44.4 * 88.5
    assert float(electrical_power(v, i)) == pytest.approx(expected, rel=1e-12)


def test_current_from_power_hand_case():
    p, v = 3928.6, 44.4
    expected = 3928.6 / 44.4
    assert float(current_from_power(p, v)) == pytest.approx(expected, rel=1e-12)


def test_current_from_power_and_electrical_power_are_inverse():
    v, i = 51.8, 75.84
    p = float(electrical_power(v, i))
    i_recovered = float(current_from_power(p, v))
    assert i_recovered == pytest.approx(i, rel=1e-9)


def test_higher_voltage_gives_lower_current_at_fixed_power():
    p = 4000.0
    i_low_v = float(current_from_power(p, 44.4))
    i_high_v = float(current_from_power(p, 59.2))
    assert i_high_v < i_low_v


@pytest.mark.parametrize("bad_v", [0.0, -1.0])
def test_electrical_power_rejects_nonpositive_voltage(bad_v):
    with pytest.raises(ValueError):
        electrical_power(bad_v, 10.0)


def test_electrical_power_rejects_negative_current():
    with pytest.raises(ValueError):
        electrical_power(12.0, -5.0)


def test_current_from_power_rejects_negative_power():
    with pytest.raises(ValueError):
        current_from_power(-10.0, 12.0)


# ---------------------------------------------------------------------------
# ESC model
# ---------------------------------------------------------------------------


def test_battery_input_power_hand_case():
    p_motor, eta_esc = 3810.8, 0.97
    expected = 3810.8 / 0.97
    esc = ESCModel(eta_esc=eta_esc, i_esc_max_A=100.0)
    result = float(battery_input_power(p_motor, esc))
    assert result == pytest.approx(expected, rel=1e-12)


def test_lower_esc_efficiency_increases_battery_power():
    esc_hi = ESCModel(eta_esc=0.99, i_esc_max_A=100.0)
    esc_lo = ESCModel(eta_esc=0.90, i_esc_max_A=100.0)
    p_hi = float(battery_input_power(1000.0, esc_hi))
    p_lo = float(battery_input_power(1000.0, esc_lo))
    assert p_lo > p_hi


@pytest.mark.parametrize("bad_eta", [0.0, -0.1, 1.1])
def test_esc_model_rejects_invalid_efficiency(bad_eta):
    with pytest.raises(ValueError):
        ESCModel(eta_esc=bad_eta, i_esc_max_A=100.0)


@pytest.mark.parametrize("bad_i", [0.0, -10.0])
def test_esc_model_rejects_invalid_current_rating(bad_i):
    with pytest.raises(ValueError):
        ESCModel(eta_esc=0.97, i_esc_max_A=bad_i)


def test_esc_model_rejects_invalid_power_rating():
    with pytest.raises(ValueError):
        ESCModel(eta_esc=0.97, i_esc_max_A=100.0, p_esc_max_W=0.0)


def test_battery_input_power_rejects_negative_power():
    esc = ESCModel(eta_esc=0.97, i_esc_max_A=100.0)
    with pytest.raises(ValueError):
        battery_input_power(-1.0, esc)


# ---------------------------------------------------------------------------
# Rating margin
# ---------------------------------------------------------------------------


def test_rating_margin_hand_case():
    rated, required = 100.0, 80.0
    expected = 100.0 / 80.0 - 1.0  # = 0.25
    assert float(rating_margin(rated, required)) == pytest.approx(expected, rel=1e-12)
    assert float(rating_margin(rated, required)) == pytest.approx(0.25, rel=1e-12)


def test_rating_margin_exact_boundary_is_zero():
    assert float(rating_margin(100.0, 100.0)) == pytest.approx(0.0, abs=1e-12)


def test_rating_margin_just_below_rating_is_positive():
    margin = float(rating_margin(100.0, 99.999))
    assert margin > 0.0


def test_rating_margin_just_above_rating_is_negative():
    margin = float(rating_margin(100.0, 100.001))
    assert margin < 0.0


def test_rating_margin_is_negative_when_required_exceeds_rated():
    margin = float(rating_margin(80.0, 100.0))
    assert margin == pytest.approx(80.0 / 100.0 - 1.0, rel=1e-12)
    assert margin < 0.0


def test_rating_margin_not_clipped_at_zero():
    # A large deficit must produce a large negative margin, not 0.
    margin = float(rating_margin(10.0, 100.0))
    assert margin == pytest.approx(-0.9, rel=1e-9)


def test_rating_margin_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        rating_margin(0.0, 10.0)
    with pytest.raises(ValueError):
        rating_margin(-5.0, 10.0)
    with pytest.raises(ValueError):
        rating_margin(10.0, 0.0)
    with pytest.raises(ValueError):
        rating_margin(10.0, -5.0)
