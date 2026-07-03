# Infrastructure

Everything the pipeline runs on, and how to redeploy it. The application code is
environment-agnostic; this directory is the single place that knows about AWS.

## Inventory (us-east-1)

| Resource | Purpose | Notes |
|---|---|---|
| Lambda `sheriff-activity-ingest` | fetch + normalize both feeds → S3 | handler `lambda_function.fetch_handler`; env `S3_BUFFER_BUCKET`, `USER_AGENT`; python3.12 x86_64 |
| Lambda `sheriff-activity-flush` | hourly S3 → Neon upsert | handler `lambda_function.flush_handler`; env `S3_BUFFER_BUCKET`, `DATABASE_URL` |
| Scheduler `sheriff-traffic-5min` | `rate(5 minutes)` → ingest, `{"source": "lee_county_traffic"}` | EventBridge **Scheduler** (identically named classic EventBridge *rules* exist but are DISABLED leftovers) |
| Scheduler `sheriff-incidents-12h` | `rate(12 hours)` → ingest, `{"source": "lee_county"}` | |
| Scheduler `lee-flush-hourly` | `cron(0 * * * ? *)` → flush | |
| S3 `lee-incidents-buffer-ucfsd` | write buffer under `pending/<source>/` | fetch needs `s3:PutObject`; flush needs `s3:ListBucket/GetObject/DeleteObject` |
| Neon Postgres | `incidents`, `geocode_cache`, `crawl_queries` | pooled connection string in `.env` / flush env |
| EC2 worker boxes | each runs `leecad-crawl` + `leecad-geocode` services | t4g.micro, AL2023; one crawl + one geocode worker per box, distinct worker ids (instance IDs/IPs kept in ops notes, not here) |

Worker boxes: repo at `/home/ec2-user/sheriff_activity` with `.env` at its root
(box-local `USER_AGENT`; never overwrite it);
`ssh -i ~/.ssh/<crawler-key>.pem ec2-user@<public-ip>` (IPs change on
stop/start; SSH allowlisted to the owner IP in the security group).
Logs: `sudo journalctl -u leecad-crawl -f`.

## Lambda deploy

```bash
./infra/lambda/build.sh
for fn in sheriff-activity-ingest sheriff-activity-flush; do
  aws lambda update-function-code --function-name $fn --zip-file fileb://build/lambda.zip
  aws lambda wait function-updated --function-name $fn
done
```

Both functions run the same zip; only the handler string and schedule differ.
Rollback: re-upload the previous zip.

## Worker deploy

```bash
git archive --format=tar.gz -o /tmp/leecad-deploy.tgz HEAD   # committed tree only: no .env, no data/
scp -i ~/.ssh/<crawler-key>.pem /tmp/leecad-deploy.tgz ec2-user@<ip>:
ssh -i ~/.ssh/<crawler-key>.pem ec2-user@<ip> \
    'cd sheriff_activity && tar xzf ~/leecad-deploy.tgz && ~/.local/bin/uv sync && sudo systemctl restart leecad-crawl'
```

Safe to restart any time: workers buffer to a local SQLite outbox and re-sync on
the next hourly tick, and abandoned leases (crawl and geocode) self-heal after
expiry. Roll one box, watch a sync in the journal, then do the other. Both
units (`leecad-crawl`, `leecad-geocode`) run on both boxes; restart both after
a deploy.
