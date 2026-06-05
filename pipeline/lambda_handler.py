from pipeline.runner import run_source
from ingest import build_store, build_geocoding, geocode_pending

def handler(event: dict, context: object) -> dict:
    if event.get("action") == "geocode":
        result = geocode_pending(build_store(), build_geocoding(), worker_id=event.get("worker", "lambda"), limit=event.get("limit", 100))
    else:
        result = run_source(event["source"])
    return {"statusCode": 200, "body": result}