"""Market-level data adapters."""


def get_market_fear_inputs() -> dict:
    """Return VIX inputs when supplied by the dedicated index provider.

    Tiingo's daily equity endpoint does not provide VIX/VIXEQ. Keep these
    generic-adapter calls disabled so each analysis does not burn quote and
    history quota on guaranteed misses. FMP will populate them later.
    """
    return {"vix": None, "vixeq": None, "spread_history": []}
