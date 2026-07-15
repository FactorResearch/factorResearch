import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "production-proof" / "07-observability"


def test_alert_catalog_is_actionable():
    catalog = json.loads((EVIDENCE / "alert-catalog.json").read_text())
    alerts = catalog["alerts"]
    assert catalog["schema_version"] == 1
    assert len(alerts) >= 10
    assert len({alert["id"] for alert in alerts}) == len(alerts)
    for alert in alerts:
        assert alert["severity"] in {"critical", "high"}
        assert alert["owner"] and alert["condition"]
        runbook = EVIDENCE / alert["runbook"]
        assert runbook.is_file(), f"missing runbook for {alert['id']}: {runbook}"
        assert len(runbook.read_text().splitlines()) >= 5


def test_critical_operational_domains_have_runbooks():
    expected = {
        "database.md", "redis.md", "provider.md", "queue.md",
        "authentication.md", "billing.md", "model-data.md", "cache-disk.md",
        "secret-compromise.md", "service-degradation.md",
    }
    assert expected <= {path.name for path in (EVIDENCE / "runbooks").glob("*.md")}
