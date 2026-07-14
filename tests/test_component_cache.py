from unittest.mock import Mock

from codes.services import component_cache


def test_input_hash_is_stable_across_dict_order():
    assert component_cache.input_hash({"a": 1, "b": 2}) == component_cache.input_hash({"b": 2, "a": 1})


def test_component_cache_reuses_identical_inputs(monkeypatch):
    monkeypatch.setattr(component_cache, "get_redis", lambda: None)
    monkeypatch.setattr(component_cache, "_memory", {})
    compute = Mock(return_value={"score": 80})

    first, first_hit = component_cache.get_or_compute("quality", "AAPL", "1", {"facts": 1}, compute)
    second, second_hit = component_cache.get_or_compute("quality", "AAPL", "1", {"facts": 1}, compute)

    assert first == second == {"score": 80}
    assert first_hit is False
    assert second_hit is True
    compute.assert_called_once()


def test_component_cache_invalidates_changed_inputs(monkeypatch):
    monkeypatch.setattr(component_cache, "get_redis", lambda: None)
    monkeypatch.setattr(component_cache, "_memory", {})
    compute = Mock(side_effect=[{"score": 70}, {"score": 71}])

    component_cache.get_or_compute("quality", "AAPL", "1", {"facts": 1}, compute)
    component_cache.get_or_compute("quality", "AAPL", "1", {"facts": 2}, compute)

    assert compute.call_count == 2
