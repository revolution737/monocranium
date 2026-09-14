from __future__ import annotations

import json

import pytest

from src.core.parameter_store import ParameterStore
from src.core.types import Parameter


@pytest.mark.asyncio
async def test_upsert_new_param(param_store: ParameterStore) -> None:
    """Verify upserting a new parameter and retrieving it."""
    param = Parameter(param_id="CRUISE_SPD", value=1.5, param_type=9, param_index=0)
    await param_store.upsert(2, param)

    retrieved = param_store.get(2, "CRUISE_SPD")
    assert retrieved == param


@pytest.mark.asyncio
async def test_upsert_update_existing(param_store: ParameterStore) -> None:
    """Verify upserting an existing parameter updates its value."""
    param1 = Parameter(param_id="CRUISE_SPD", value=1.5, param_type=9, param_index=0)
    await param_store.upsert(2, param1)

    param2 = Parameter(param_id="CRUISE_SPD", value=2.0, param_type=9, param_index=0)
    await param_store.upsert(2, param2)

    retrieved = param_store.get(2, "CRUISE_SPD")
    assert retrieved.value == 2.0


@pytest.mark.asyncio
async def test_bulk_load_replaces_all(param_store: ParameterStore) -> None:
    """Verify bulk_load replaces previous parameters entirely."""
    initial = [
        Parameter(param_id="P1", value=1.0, param_type=9, param_index=0),
        Parameter(param_id="P2", value=2.0, param_type=9, param_index=1),
        Parameter(param_id="P3", value=3.0, param_type=9, param_index=2),
    ]
    await param_store.bulk_load(2, initial)
    assert param_store.get_count(2) == 3

    replacement = [
        Parameter(param_id="NEW1", value=10.0, param_type=9, param_index=0),
        Parameter(param_id="NEW2", value=20.0, param_type=9, param_index=1),
    ]
    await param_store.bulk_load(2, replacement)
    assert param_store.get_count(2) == 2
    assert param_store.get(2, "NEW1").value == 10.0
    with pytest.raises(KeyError):
        param_store.get(2, "P1")


def test_get_nonexistent_raises(param_store: ParameterStore) -> None:
    """Verify get on nonexistent system or param raises KeyError."""
    with pytest.raises(KeyError, match="not found"):
        param_store.get(99, "NONEXISTENT")


@pytest.mark.asyncio
async def test_get_all_sorted_by_index(param_store: ParameterStore) -> None:
    """Verify get_all returns parameters sorted by param_index."""
    p_third = Parameter(param_id="P3", value=3.0, param_type=9, param_index=2)
    p_first = Parameter(param_id="P1", value=1.0, param_type=9, param_index=0)
    p_second = Parameter(param_id="P2", value=2.0, param_type=9, param_index=1)

    # Insert out of order
    await param_store.upsert(2, p_third)
    await param_store.upsert(2, p_first)
    await param_store.upsert(2, p_second)

    all_params = param_store.get_all(2)
    assert [p.param_id for p in all_params] == ["P1", "P2", "P3"]


def test_get_count_empty(param_store: ParameterStore) -> None:
    """Verify get_count returns 0 for untracked systems."""
    assert param_store.get_count(999) == 0


@pytest.mark.asyncio
async def test_clear(param_store: ParameterStore) -> None:
    """Verify clear removes all parameters for a system."""
    param = Parameter(param_id="P1", value=1.0, param_type=9, param_index=0)
    await param_store.upsert(2, param)
    assert param_store.get_count(2) == 1

    param_store.clear(2)
    assert param_store.get_count(2) == 0


@pytest.mark.asyncio
async def test_export_json(param_store: ParameterStore) -> None:
    """Verify export_json generates valid JSON representation of parameters."""
    params = [
        Parameter(param_id="WHEEL_DIA", value=130.0, param_type=9, param_index=0),
        Parameter(param_id="MOT_RPM", value=6000.0, param_type=9, param_index=1),
    ]
    await param_store.bulk_load(2, params)

    json_str = param_store.export_json(2)
    data = json.loads(json_str)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["param_id"] == "WHEEL_DIA"
    assert data[1]["param_id"] == "MOT_RPM"
