"""Independent verification of Milestone 2 speed-of-sound / tip-Mach / RPM
ceiling relations."""

from __future__ import annotations

import math

import pytest

from edf_sizing import compressibility as comp
from edf_sizing import rotational as rot


@pytest.fixture
def ambient() -> comp.AmbientCondition:
    return comp.AmbientCondition()  # ISA sea level default, 288.15 K


def test_speed_of_sound_hand_case(ambient):
    a_hand = math.sqrt(ambient.gamma * ambient.r_specific_J_per_kgK * ambient.temperature_K)
    assert a_hand == pytest.approx(340.29, abs=0.01)
    assert comp.speed_of_sound(ambient) == pytest.approx(a_hand, rel=1e-12)


def test_speed_of_sound_matches_isa_sea_level_reference(ambient):
    # Standard ISA sea-level speed of sound is ~340.3 m/s.
    assert comp.speed_of_sound(ambient) == pytest.approx(340.3, abs=0.1)


def test_static_tip_mach_hand_case(ambient):
    a = comp.speed_of_sound(ambient)
    u_tip = 170.0
    mach_hand = u_tip / a
    assert float(comp.static_tip_mach(u_tip, a)) == pytest.approx(mach_hand, rel=1e-12)


def test_relative_tip_mach_hand_case(ambient):
    a = comp.speed_of_sound(ambient)
    u_tip, v_inf = 200.0, 30.0
    mach_hand = math.sqrt(u_tip**2 + v_inf**2) / a
    assert float(comp.relative_tip_mach(u_tip, v_inf, a)) == pytest.approx(mach_hand, rel=1e-12)


def test_relative_tip_mach_reduces_to_static_at_zero_v_inf(ambient):
    a = comp.speed_of_sound(ambient)
    u_tip = 150.0
    static_val = float(comp.static_tip_mach(u_tip, a))
    relative_val = float(comp.relative_tip_mach(u_tip, 0.0, a))
    assert relative_val == pytest.approx(static_val, rel=1e-12)


def test_relative_tip_mach_always_geq_static_tip_mach(ambient):
    a = comp.speed_of_sound(ambient)
    for u_tip in (50.0, 150.0, 300.0):
        for v_inf in (0.0, 10.0, 40.0):
            static_val = float(comp.static_tip_mach(u_tip, a))
            relative_val = float(comp.relative_tip_mach(u_tip, v_inf, a))
            assert relative_val >= static_val - 1e-12


def test_tip_mach_increases_monotonically_with_rpm(ambient):
    a = comp.speed_of_sound(ambient)
    d = 0.5
    rpms = [1000.0, 3000.0, 6000.0, 9000.0, 12000.0]
    machs = [
        float(comp.static_tip_mach(float(rot.tip_speed(d, r)), a)) for r in rpms
    ]
    assert all(x < y for x, y in zip(machs, machs[1:], strict=False))


# ---------------------------------------------------------------------------
# RPM ceiling: analytic exact-boundary tests
# ---------------------------------------------------------------------------


def test_max_rpm_static_hand_case(ambient):
    d, m_max = 0.5, 0.85
    a = comp.speed_of_sound(ambient)
    rpm_max_hand = 60.0 * m_max * a / (math.pi * d)
    rpm_max = comp.max_rpm_static(d, m_max, ambient)
    assert rpm_max == pytest.approx(rpm_max_hand, rel=1e-9)


def test_max_rpm_static_matches_general_forward_flight_at_zero_v_inf(ambient):
    d, m_max = 0.4, 0.8
    rpm_static = comp.max_rpm_static(d, m_max, ambient)
    result = comp.max_rpm_for_tip_mach(d, 0.0, m_max, ambient)
    assert result.feasible
    assert result.rpm_max == pytest.approx(rpm_static, rel=1e-9)


def test_rpm_ceiling_exact_boundary_passes_and_just_above_fails(ambient):
    d, m_max = 0.5, 0.85
    rpm_max = comp.max_rpm_static(d, m_max, ambient)
    a = comp.speed_of_sound(ambient)

    # Exactly at the ceiling: tip Mach must equal m_max (to numerical precision).
    u_tip_at_ceiling = float(rot.tip_speed(d, rpm_max))
    mach_at_ceiling = float(comp.static_tip_mach(u_tip_at_ceiling, a))
    assert mach_at_ceiling == pytest.approx(m_max, rel=1e-9)

    # Just below the ceiling -> passes.
    rpm_below = rpm_max * (1.0 - 1e-6)
    mach_below = float(comp.static_tip_mach(float(rot.tip_speed(d, rpm_below)), a))
    assert mach_below < m_max

    # Just above the ceiling -> fails.
    rpm_above = rpm_max * (1.0 + 1e-4)
    mach_above = float(comp.static_tip_mach(float(rot.tip_speed(d, rpm_above)), a))
    assert mach_above > m_max


def test_forward_flight_rpm_ceiling_hand_case(ambient):
    d, v_inf, m_max = 0.5, 25.0, 0.85
    a = comp.speed_of_sound(ambient)
    limit_speed = m_max * a
    u_tip_max_hand = math.sqrt(limit_speed**2 - v_inf**2)
    rpm_max_hand = 60.0 * u_tip_max_hand / (math.pi * d)

    result = comp.max_rpm_for_tip_mach(d, v_inf, m_max, ambient)
    assert result.feasible
    assert result.u_tip_max_m_s == pytest.approx(u_tip_max_hand, rel=1e-9)
    assert result.rpm_max == pytest.approx(rpm_max_hand, rel=1e-9)

    # Verify by reconstruction: relative tip Mach at rpm_max_hand equals m_max.
    u_tip_check = float(rot.tip_speed(d, result.rpm_max))
    mach_check = float(comp.relative_tip_mach(u_tip_check, v_inf, a))
    assert mach_check == pytest.approx(m_max, rel=1e-6)


def test_forward_flight_rpm_ceiling_exact_boundary_infeasible_case(ambient):
    d, m_max = 0.5, 0.85
    a = comp.speed_of_sound(ambient)
    limit_speed = m_max * a

    # Per the spec, impossible cases are exactly "m_tip_max*a <= V_inf" --
    # so the boundary V_inf == m_max*a itself is rejected as infeasible
    # (no RPM, not even 0, gives a relative tip Mach strictly at/under the
    # ceiling once V_inf alone already equals it in this formulation).
    result_boundary = comp.max_rpm_for_tip_mach(d, limit_speed, m_max, ambient)
    assert not result_boundary.feasible
    assert result_boundary.rpm_max is None
    assert result_boundary.reason is not None

    # Just below the boundary -> feasible, with a small positive RPM ceiling.
    result_just_below = comp.max_rpm_for_tip_mach(d, limit_speed * 0.999, m_max, ambient)
    assert result_just_below.feasible
    assert result_just_below.rpm_max > 0.0

    # Further above the boundary -> infeasible.
    result_infeasible = comp.max_rpm_for_tip_mach(d, limit_speed * 1.001, m_max, ambient)
    assert not result_infeasible.feasible
    assert result_infeasible.rpm_max is None
    assert result_infeasible.reason is not None


def test_rpm_ceiling_scales_inversely_with_diameter(ambient):
    m_max = 0.85
    d1, d2 = 0.3, 0.6
    rpm1 = comp.max_rpm_static(d1, m_max, ambient)
    rpm2 = comp.max_rpm_static(d2, m_max, ambient)
    # RPM_max ~ 1/D -> rpm1/rpm2 should equal d2/d1
    assert rpm1 / rpm2 == pytest.approx(d2 / d1, rel=1e-9)


def test_stricter_tip_mach_limit_gives_lower_allowable_rpm(ambient):
    d = 0.5
    rpm_loose = comp.max_rpm_static(d, 0.95, ambient)
    rpm_strict = comp.max_rpm_static(d, 0.75, ambient)
    assert rpm_strict < rpm_loose


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_ambient_condition_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        comp.AmbientCondition(temperature_K=0.0)
    with pytest.raises(ValueError):
        comp.AmbientCondition(temperature_K=-10.0)
    with pytest.raises(ValueError):
        comp.AmbientCondition(gamma=1.0)
    with pytest.raises(ValueError):
        comp.AmbientCondition(r_specific_J_per_kgK=0.0)


def test_max_rpm_for_tip_mach_rejects_invalid_inputs(ambient):
    with pytest.raises(ValueError):
        comp.max_rpm_for_tip_mach(0.0, 10.0, 0.85, ambient)
    with pytest.raises(ValueError):
        comp.max_rpm_for_tip_mach(0.5, -1.0, 0.85, ambient)
    with pytest.raises(ValueError):
        comp.max_rpm_for_tip_mach(0.5, 10.0, 0.0, ambient)


def test_static_tip_mach_rejects_nonpositive_speed_of_sound():
    with pytest.raises(ValueError):
        comp.static_tip_mach(100.0, 0.0)
    with pytest.raises(ValueError):
        comp.static_tip_mach(100.0, -340.0)
