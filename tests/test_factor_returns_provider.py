import io
import zipfile
from unittest.mock import patch

import pytest

from codes.data import factor_returns


def _zip_csv(name: str, text: str) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(name, text)
    return payload.getvalue()


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.payload


def test_get_us_monthly_factors_downloads_parses_and_caches(monkeypatch):
    ff5 = _zip_csv("ff5.csv", "Header\n, Mkt-RF, SMB, HML, RMW, CMA, RF\n202501, 1.0, 2.0, 3.0, 4.0, 5.0, 0.1\n202502, 2.0, 3.0, 4.0, 5.0, 6.0, 0.1\nAnnual Factors: January-December\n")
    mom = _zip_csv("mom.csv", "Header\n, Mom\n202501, 7.0\n202502, 8.0\nAnnual Factors: January-December\n")
    store = []

    def fake_read(*, source, period):
        assert source == "ken_french_us"
        assert period == "monthly"
        return store

    def fake_write(data, *, source, period):
        assert source == "ken_french_us"
        assert period == "monthly"
        store[:] = data
        return len(data)

    monkeypatch.setattr(factor_returns.db, "get_factor_returns", fake_read)
    monkeypatch.setattr(factor_returns.db, "upsert_factor_returns", fake_write)

    with patch.object(factor_returns, "urlopen", side_effect=[_Response(ff5), _Response(mom)]) as fetch:
        frame = factor_returns.get_us_monthly_factors(force_refresh=True)

    assert fetch.call_count == 2
    assert frame["Date"].tolist() == ["2025-01-31", "2025-02-28"]
    assert frame.loc[0, "mkt_rf"] == pytest.approx(0.01)
    assert frame.loc[0, "mom"] == pytest.approx(0.07)

    with patch.object(factor_returns, "urlopen") as fetch_again:
        cached = factor_returns.get_us_monthly_factors()

    fetch_again.assert_not_called()
    assert cached.loc[1, "cma"] == pytest.approx(0.06)
