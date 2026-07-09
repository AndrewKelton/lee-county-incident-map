"""Lambda entry points for the live feeds.

  fetch_handler  -- both fetch Lambdas (traffic every 5 min, incidents every 12h): fetch one
                    source, normalize, stash to S3. No Neon.
  flush_handler  -- the flush Lambda (hourly): drain the S3 buffer into Neon in one batch.
  handler        -- single-entry dispatcher (action=flush -> flush, else -> fetch).

Deployed via infra/lambda/build.sh; functions point at the lambda_function.* shim
at the zip root. The fetch Lambdas pass {"source": "..."}.
Env: S3_BUFFER_BUCKET (both), DATABASE_URL (flush).
"""
import os

from leecad.pipeline.runner import fetch_source
from leecad.pipeline.s3_buffer import S3Buffer
from leecad.pipeline.flush import drain
from leecad.ingest import build_store


def _buffer() -> S3Buffer:
    return S3Buffer(os.environ["S3_BUFFER_BUCKET"])


def fetch_handler(event: dict, context: object) -> dict:
    source = event["source"]
    incidents = fetch_source(source)
    key = _buffer().put(source, [i.model_dump(mode="json") for i in incidents])
    return {"statusCode": 200, "body": {"source": source, "fetched": len(incidents), "key": key}}


def flush_handler(event: dict, context: object) -> dict:
    store = build_store()
    try:
        stats = drain(_buffer(), store)
    finally:
        store.close()
    return {"statusCode": 200, "body": stats}


def handler(event: dict, context: object) -> dict:
    if event.get("action") == "flush":
        return flush_handler(event, context)
    return fetch_handler(event, context)
