from pipeline.runner import run_source

def handler(event: dict, context: object) -> dict:
    return {"statusCode": 200, "body": run_source(event["source"])}