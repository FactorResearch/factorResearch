"""Regression contracts for ISSUE_145 dependency and supply-chain controls."""

from __future__ import annotations

import importlib.metadata
import json
import re
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]


def _direct_python_names(pyproject: dict[str, object]) -> set[str]:
    """Return normalized direct Python names from runtime and development groups.

    Args:
        pyproject: Parsed `pyproject.toml` mapping with PEP 621 and PEP 735
            dependency declarations.

    Returns:
        Lower-case distribution names with extras and version constraints
        removed. The helper reads only the repository's constrained declaration
        format; it is not a general package requirement parser.
    """

    project = pyproject["project"]
    groups = pyproject["dependency-groups"]
    declarations = [*project["dependencies"], *groups["dev"]]
    return {
        re.split(r"[<>=!~\[]", declaration, maxsplit=1)[0].strip().lower()
        for declaration in declarations
    }


def test_python_dependencies_have_one_locked_declaration() -> None:
    """Require PEP metadata, explicit test tools, and a committed uv lockfile."""

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.14"
    assert (ROOT / ".python-version").read_text().strip() == "3.12"
    assert {"pytest", "hypothesis"} <= _direct_python_names(pyproject)
    assert pyproject["tool"]["uv"]["package"] is False
    assert (ROOT / "uv.lock").is_file()
    assert 'name = "factorresearch"' in (ROOT / "uv.lock").read_text()
    for legacy_manifest in (
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-proof.txt",
    ):
        assert not (ROOT / legacy_manifest).exists()


def test_node_dependencies_reproduce_without_unused_browser_drivers() -> None:
    """Require npm lock integrity and the narrow accessibility dependency."""

    package = json.loads((ROOT / "package.json").read_text())
    lock = json.loads((ROOT / "package-lock.json").read_text())
    assert package["devDependencies"].keys() == {"axe-core", "sass"}
    assert package["packageManager"] == "npm@11.13.0"
    assert package["engines"]["node"] == ">=22 <25"
    assert (ROOT / ".nvmrc").read_text().strip() == "24"
    assert lock["lockfileVersion"] >= 3
    assert "node_modules/axe-core" in lock["packages"]
    assert "node_modules/@axe-core/cli" not in lock["packages"]
    assert "node_modules/chromedriver" not in lock["packages"]


def test_every_direct_dependency_has_an_owner_and_disposition() -> None:
    """Keep the human dependency inventory synchronized with both manifests."""

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    inventory = (ROOT / "docs/issue-145-dependency-inventory.md").read_text().lower()
    direct_names = _direct_python_names(pyproject) | set(package["devDependencies"])
    for name in direct_names:
        assert f"| {name.lower()} |" in inventory
    assert "native dependency budget and compile time are\ntherefore exactly zero" in inventory


def test_repository_policy_is_mirrored_and_mechanically_reviewed() -> None:
    """Require the canonical policy mirrors and pull-request exception gate."""

    agents = (ROOT / "AGENTS.md").read_text()
    standards = (ROOT / "docs/standards/README.md").read_text()
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text()
    assert "Build-vs-Buy and No-Reinvention" in agents
    assert "3a34ef32c9f78126ba2bd57c1f050a2e" in standards
    assert "accepted ADR identifier" in template
    assert "did not self-approve" in template


def test_supply_chain_workflows_cover_current_ecosystems() -> None:
    """Require frozen audits, two SBOMs, license review, and grouped updates."""

    security = (ROOT / ".github/workflows/security-audit.yml").read_text().lower()
    review = (ROOT / ".github/workflows/dependency-review.yml").read_text().lower()
    updater = (ROOT / ".github/dependabot.yml").read_text().lower()
    for control in ("uv sync --frozen", "pip-audit", "npm audit", "sbom-python", "sbom-node"):
        assert control in security
    assert "license-check: true" in review
    assert "fail-on-severity: high" in review
    for ecosystem in ("pip", "npm", "github-actions"):
        assert f"package-ecosystem: {ecosystem}" in updater


def test_upgraded_financial_and_chart_major_surfaces_remain_compatible() -> None:
    """Exercise stable NumPy, pandas, and Plotly surfaces used by the product."""

    returns = pd.Series([100.0, 105.0, 102.9]).pct_change().dropna()
    np.testing.assert_allclose(returns.to_numpy(), np.array([0.05, -0.02]))
    figure = go.Figure(data=[go.Scatter(x=[1, 2], y=[3, 4])])
    assert figure.to_plotly_json()["data"][0]["type"] == "scatter"


def test_upgraded_infrastructure_sdk_surfaces_remain_available() -> None:
    """Exercise only the maintained SDK entry points consumed by application adapters."""

    import finnhub
    import psycopg
    import redis
    import stripe
    from flask_limiter import Limiter

    assert callable(finnhub.Client)
    assert callable(psycopg.connect)
    assert callable(redis.Redis)
    assert callable(Limiter)
    assert callable(stripe.checkout.Session.create)
    assert callable(stripe.Webhook.construct_event)
    assert importlib.metadata.version("gunicorn").startswith("26.")


def test_snapshot_storage_uses_only_the_declared_postgresql_driver() -> None:
    """Prevent the removed undeclared Psycopg 2 fallback from returning."""

    source = (ROOT / "codes/services/analysis_snapshot_service.py").read_text()
    assert "import psycopg" in source
    assert "psycopg2" not in source
