"""Canonical Lambda entry point, copied to the zip root by infra/lambda/build.sh.

Handler strings:
    lambda_function.fetch_handler   -- both fetch functions (event: {"source": "..."})
    lambda_function.flush_handler   -- hourly S3 -> Neon flush
    lambda_function.handler         -- single-entry dispatcher (action=flush -> flush)
"""
from leecad.pipeline.lambda_handler import fetch_handler, flush_handler, handler  # noqa: F401