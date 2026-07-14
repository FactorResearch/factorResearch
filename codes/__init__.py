"""Graham Score Quant Platform.

Package initialization intentionally stays lightweight.  Application modules
must import their dependencies explicitly; legacy top-level names are resolved
on first access for backward compatibility.
"""

from importlib import import_module
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
import sys


_LEGACY_MODULES = {
    "cache": "codes.data.cache",
    "sec_data": "codes.data.sec_data",
    "api_fetcher": "codes.data.api_fetcher",
    "graham": "codes.models.graham",
    "buffett": "codes.models.buffett",
    "piotroski": "codes.models.piotroski",
    "altman": "codes.models.altman",
    "beneish": "codes.models.beneish",
    "dechow": "codes.models.dechow",
    "fraud_dashboard": "codes.models.fraud_dashboard",
    "greenblatt": "codes.models.greenblatt",
    "quality": "codes.models.quality",
    "momentum": "codes.models.momentum",
    "risk_metrics": "codes.models.risk_metrics",
    "earnings_revision": "codes.models.earnings_revision",
    "fcf_quality": "codes.models.fcf_quality",
    "capital_allocation": "codes.models.capital_allocation",
    "growth_quality": "codes.models.growth_quality",
    "accounting_quality": "codes.models.accounting_quality",
    "regime": "codes.models.regime",
    "insider_activity": "codes.models.insider_activity",
    "alternative_data": "codes.models.alternative_data",
    "spy_benchmark_model": "codes.models.spy_benchmark_model",
    "bias_engine": "codes.models.bias_engine",
    "scorer": "codes.engine.scorer",
    "screener": "codes.engine.screener",
    "universe": "codes.engine.universe",
}


class _LegacyAliasLoader(Loader):
    def __init__(self, target):
        self.target = target

    def create_module(self, spec):
        return import_module(self.target)

    def exec_module(self, module):
        return None


class _LegacyAliasFinder(MetaPathFinder):
    """Resolve imports such as ``codes.graham`` without eager registration."""

    def find_spec(self, fullname, path=None, target=None):
        prefix = f"{__name__}."
        if not fullname.startswith(prefix):
            return None
        legacy_name = fullname[len(prefix):]
        module_name = _LEGACY_MODULES.get(legacy_name)
        if module_name is None:
            return None
        return spec_from_loader(fullname, _LegacyAliasLoader(module_name))


if not any(isinstance(finder, _LegacyAliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _LegacyAliasFinder())


def __getattr__(name):
    """Load legacy package attributes only when callers request them."""
    target = _LEGACY_MODULES.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(target)
    globals()[name] = module
    return module


def __dir__():
    return sorted(set(globals()) | set(_LEGACY_MODULES))
