release: ./scripts/release-migrate.sh
web: gunicorn --bind 0.0.0.0:$PORT codes.app:server
worker: ANALYSIS_BACKGROUND_JOBS=1 PROCESS_ROLE=analysis-worker python -m codes.services.analysis_scheduler
