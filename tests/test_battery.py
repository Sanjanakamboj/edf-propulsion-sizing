"""Independent verification of the Milestone 3 battery pack model."""

from __future__ import annotations

import pytest

from edf_sizing.battery import BatteryPack


def test_pack_nominal_voltage_hand_case():
    # 14S at 3.7 V/cell nominal -> 51.8 V (matches 2S=7.4V, 3S=11.1V convention)
    pack = BatteryPack(n_series=14, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    assert pack.v_pack_nom_V == pytest.approx(14 * 3.7, rel=1e-12)
    assert pack.v_pack_nom_V == pytest.approx(51.8, abs=1e-9)


def test_pack_full_charge_voltage_hand_case():
    pack = BatteryPack(n_series=12, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    assert pack.v_pack_full_V == pytest.approx(12 * 4.2, rel=1e-12)
    assert pack.v_pack_full_V == pytest.approx(50.4, abs=1e-9)


def test_2s_and_3s_reference_voltages():
    # Cross-check against the commonly cited 2S=7.4V, 3S=11.1V convention.
    pack_2s = BatteryPack(n_series=2, capacity_Ah=1.0, continuous_c_rate_limit=10.0)
    pack_3s = BatteryPack(n_series=3, capacity_Ah=1.0, continuous_c_rate_limit=10.0)
    assert pack_2s.v_pack_nom_V == pytest.approx(7.4, abs=1e-9)
    assert pack_3s.v_pack_nom_V == pytest.approx(11.1, abs=1e-9)


def test_pack_energy_wh_hand_case():
    pack = BatteryPack(n_series=14, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    expected = 51.8 * 4.0  # V_pack_nom * Capacity_Ah
    assert pack.energy_Wh_nom == pytest.approx(expected, rel=1e-9)


def test_c_rate_required_hand_case():
    pack = BatteryPack(n_series=14, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    current_A = 75.84
    expected = 75.84 / 4.0
    assert float(pack.c_rate_required(current_A)) == pytest.approx(expected, rel=1e-9)


def test_higher_capacity_lowers_required_c_rate_at_fixed_current():
    current_A = 80.0
    c_low_cap = float(
        BatteryPack(n_series=14, capacity_Ah=4.0, continuous_c_rate_limit=20.0).c_rate_required(
            current_A
        )
    )
    c_high_cap = float(
        BatteryPack(n_series=14, capacity_Ah=8.0, continuous_c_rate_limit=20.0).c_rate_required(
            current_A
        )
    )
    assert c_high_cap < c_low_cap
    assert c_low_cap / c_high_cap == pytest.approx(2.0, rel=1e-9)


def test_derived_continuous_current_limit_hand_case():
    pack = BatteryPack(n_series=14, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    expected = 4.0 * 20.0
    assert pack.i_continuous_max_A == pytest.approx(expected, rel=1e-12)


def test_default_cell_voltage_convention():
    pack = BatteryPack(n_series=1, capacity_Ah=1.0, continuous_c_rate_limit=10.0)
    assert pack.v_cell_nom_V == pytest.approx(3.7, abs=1e-9)
    assert pack.v_cell_full_V == pytest.approx(4.2, abs=1e-9)
    assert pack.v_cell_min_V == pytest.approx(3.0, abs=1e-9)


def test_cell_voltages_distinct_and_ordered():
    pack = BatteryPack(n_series=1, capacity_Ah=1.0, continuous_c_rate_limit=10.0)
    assert pack.v_cell_min_V < pack.v_cell_nom_V < pack.v_cell_full_V


# ---------------------------------------------------------------------------
# Invalid-input rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_n_series", [0, -1])
def test_rejects_invalid_series_count(bad_n_series):
    with pytest.raises(ValueError):
        BatteryPack(n_series=bad_n_series, capacity_Ah=4.0, continuous_c_rate_limit=20.0)


@pytest.mark.parametrize("bad_n_parallel", [0, -1])
def test_rejects_invalid_parallel_count(bad_n_parallel):
    with pytest.raises(ValueError):
        BatteryPack(
            n_series=12, capacity_Ah=4.0, continuous_c_rate_limit=20.0, n_parallel=bad_n_parallel
        )


@pytest.mark.parametrize("bad_capacity", [0.0, -1.0])
def test_rejects_invalid_capacity(bad_capacity):
    with pytest.raises(ValueError):
        BatteryPack(n_series=12, capacity_Ah=bad_capacity, continuous_c_rate_limit=20.0)


@pytest.mark.parametrize("bad_c_rate", [0.0, -5.0])
def test_rejects_invalid_c_rate_limit(bad_c_rate):
    with pytest.raises(ValueError):
        BatteryPack(n_series=12, capacity_Ah=4.0, continuous_c_rate_limit=bad_c_rate)


def test_rejects_disordered_cell_voltages():
    with pytest.raises(ValueError):
        BatteryPack(
            n_series=12,
            capacity_Ah=4.0,
            continuous_c_rate_limit=20.0,
            v_cell_min_V=4.0,
            v_cell_nom_V=3.7,
            v_cell_full_V=4.2,
        )
    with pytest.raises(ValueError):
        BatteryPack(
            n_series=12,
            capacity_Ah=4.0,
            continuous_c_rate_limit=20.0,
            v_cell_min_V=3.0,
            v_cell_nom_V=4.3,
            v_cell_full_V=4.2,
        )


def test_c_rate_required_rejects_negative_current():
    pack = BatteryPack(n_series=12, capacity_Ah=4.0, continuous_c_rate_limit=20.0)
    with pytest.raises(ValueError):
        pack.c_rate_required(-1.0)
