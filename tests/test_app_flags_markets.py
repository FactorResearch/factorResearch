import json

from codes.core import app_flags


def test_enabled_markets_default_to_us_when_missing(monkeypatch, tmp_path):
    flag_file = tmp_path / "feature_flags.json"
    flag_file.write_text(json.dumps({"flag": "V1"}))
    monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)

    assert app_flags.get_enabled_markets() == {"US"}
    assert app_flags.is_market_enabled("US") is True
    assert app_flags.is_market_enabled("CA") is False


def test_enabled_markets_read_from_feature_flags_json(monkeypatch, tmp_path):
    flag_file = tmp_path / "feature_flags.json"
    flag_file.write_text(json.dumps({
        "flag": "INTERNAL",
        "markets": {"US": True, "CA": True, "GB": False},
    }))
    monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)

    assert app_flags.get_enabled_markets() == {"US", "CA"}
    assert app_flags.is_market_enabled("ca") is True
    assert app_flags.is_market_enabled("GB") is False
