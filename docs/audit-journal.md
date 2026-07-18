# Operational audit journal (ISSUE_048)

`codes.services.audit_journal.AuditJournal` is the append-only operational
timeline. Each event receives a unique ID, UTC timestamp, event type, action,
actor/user identifiers, request and correlation IDs, job/ticker/provider/
component dimensions, severity, outcome, and redacted details.

## Sources and search

Security access events, feature-policy changes, runtime configuration changes,
capability overrides, analysis-job enqueue/completion/retry/dead-letter, and
job recovery events are written through the journal. `search()` supports
bounded reverse-chronological filtering by user, ticker, provider, job,
component, and severity. Search returns copies and there is no update or
delete operation in the journal API.

## Privacy, retention, and operations

Sensitive keys such as passwords, tokens, secrets, API keys, credentials,
authorization headers, and cookies are replaced with `[REDACTED]`. Details are
depth- and size-bounded. Events use UTC and are retained according to the
journal deployment's configured retention policy; the default is 90 days.

The default development path is `/tmp/cenvarn-audit-events.jsonl`. Production
must provide an access-controlled durable `AUDIT_LOG_PATH`, include the file in
the operational backup/retention plan, and restrict journal search to
authorized operators. File append failures must be monitored because the
journal is required for incident reconstruction and recovery traceability.
