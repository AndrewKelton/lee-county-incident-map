# Infrastructure

Everything the pipeline runs on, and how to redeploy it. The application code is
environment-agnostic; this directory is the single place that knows about AWS.

## Inventory

| Resource | Purpose | Notes |
|---|---|---|
| Lambda: incidents fetch | `{"source": "lee_county"}` every 12 h (EventBridge) | handler `lambda_function.fetch_handler`; env `S3_BUFFER_BUCKET` |
| Lambda: traffic fetch | `{"source": "lee_county_traffic"}` every 5 min (EventBridge) | same artifact + handler; env `S3_BUFFER_BUCKET` |
| Lambda: flush | hourly (EventBridge); drains S3 buffer → Neon | handler `lambda_function.flush_handler`; env `S3_BUFFER_BUCKET`, `DATABASE_URL` |
| S3 buffer bucket | durable write buffer under `pending/<source>/` | fetch needs `s3:PutObject`; flush needs `s3:ListBucket/GetObject/DeleteObject` |
| Neon Postgres | `incidents`, `geocode_cache`, `crawl_queries` | pooled connection string in `.env` / Lambda env |
| EC2 `crawler-tolga_ec2_1` (`i-0d204316feb527199`) | crawl worker, id `tolga_ec2_1` | t4g.micro, us-east-1, AL2023 |
| EC2 `crawler-tolga_ec2_2` (`i-0a7606f7ff1b00f17`) | crawl worker, id `tolga_ec2_2` | t4g.micro, us-east-1, AL2023 |

Worker boxes: repo at `/home/ec2-user/sheriff_activity` with `.env` at its root;
`ssh -i ~/.ssh/tolga-ec2-crawler.pem ec2-user@<public-ip>` (IPs change on
stop/start; SSH is allowlisted to the owner IP in the security group).
Logs: `sudo journalctl -u leecad-crawl -f`.

## Lambda deploy

```bash
./infra/lambda/build.sh
aws lambda update-function-code --function-name <fn> \
    --zip-file fileb://build/lambda.zip        # repeat for all three functions
```

All three functions run the same zip; only the handler string and EventBridge
event differ. Set handlers to `lambda_function.fetch_handler` (both fetch
functions) and `lambda_function.flush_handler` (flush).

## Worker deploy

```bash
tar --exclude .venv --exclude build --exclude data --exclude .git -czf /tmp/leecad.tgz .
scp -i ~/.ssh/tolga-ec2-crawler.pem /tmp/leecad.tgz ec2-user@<ip>:
ssh -i ~/.ssh/tolga-ec2-crawler.pem ec2-user@<ip> \
    'cd sheriff_activity && tar xzf ~/leecad.tgz && uv sync && sudo systemctl restart leecad-crawl'
```

Unit files live in `infra/systemd/` (install instructions in their headers).
Safe to restart any time: workers buffer to a local SQLite outbox and re-sync on
the next hourly tick, and abandoned crawl leases self-heal after expiry.

## Package-layout cutover checklist (phase 2)

1. `./infra/lambda/build.sh`, upload to all three functions, switch their
   handler strings to `lambda_function.*`.
2. Watch one fetch cycle (traffic fires within 5 min) and the next hourly flush
   in CloudWatch; confirm `incidents` count advances in Neon.
3. On each EC2 box: deploy per "Worker deploy" above, install the new
   `leecad-crawl.service` (header instructions), disable old `crawler.service`.
4. Watch one full hourly sync on box 1 (`journalctl -u leecad-crawl -f`) before
   doing box 2.

Rollback: previous zip re-upload + old handler strings; boxes keep the old
tarball until step 3 overwrites it, so re-enabling `crawler.service` restores.
