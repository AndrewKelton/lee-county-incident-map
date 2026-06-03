from runner import run_source

def handler(event, context):
    source = event["source"]
    result = run_source(source)
    return {"statusCode": 200, "body": result}