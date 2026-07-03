"""Durable S3 staging buffer for fetched-but-not-yet-persisted incidents.

This is the Lambda's equivalent of the workers' local SQLite outbox: the fetch Lambdas
append one object per fetch under `pending/<source>/`, and the hourly flush Lambda drains
and deletes them. Lambdas have no persistent local disk, so the buffer must be external.

boto3 is imported lazily (it's provided by the Lambda runtime) so this module imports fine
locally and tests can inject a fake client / fake buffer.
"""
import json
from datetime import datetime, timezone


class S3Buffer:
    PREFIX = "pending/"

    def __init__(self, bucket: str, client=None):
        if client is None:
            import boto3
            client = boto3.client("s3")
        self.bucket = bucket
        self.s3 = client

    def put(self, source: str, incidents: list[dict]) -> str | None:
        """Write one fetch's normalized incidents (list of model_dump(mode='json') dicts) as a
        single timestamped object. No-op on an empty fetch. Returns the key (or None)."""
        if not incidents:
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        key = f"{self.PREFIX}{source}/{ts}.json"
        self.s3.put_object(
            Bucket=self.bucket, Key=key,
            Body=json.dumps(incidents).encode("utf-8"),
            ContentType="application/json",
        )
        return key

    def list_pending(self) -> list[str]:
        keys: list[str] = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.PREFIX):
            keys += [o["Key"] for o in page.get("Contents", [])]
        return keys

    def get(self, key: str) -> list[dict]:
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        return json.loads(obj["Body"].read())

    def delete(self, keys: list[str]) -> None:
        for i in range(0, len(keys), 1000):                 # delete_objects caps at 1000/call
            self.s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]], "Quiet": True},
            )
