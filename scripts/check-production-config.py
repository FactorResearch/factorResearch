"""Validate production environment names and relationships without outputting values."""

from codes.core.production_readiness import validate_production_environment

if __name__ == "__main__":
    failures = validate_production_environment()
    if failures:
        print("Production configuration invalid:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("Production configuration contract passed.")
