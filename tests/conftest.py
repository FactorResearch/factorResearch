import os


# Importing codes.app must not connect to databases or providers during test
# collection. Tests that exercise startup call it explicitly with mocks.
os.environ["APP_SKIP_STARTUP"] = "1"
os.environ["APP_FEATURE_FLAG"] = "V1"
