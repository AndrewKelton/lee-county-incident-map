#!/usr/bin/env bash
# Build the Lambda deployment zip -> build/lambda.zip
#
# One artifact serves all three live-feed functions; point their handlers at
#   lambda_function.fetch_handler / .flush_handler / .handler
#
# Dependencies come from uv.lock (single source of truth) and are installed as
# Linux x86_64 wheels to match the Lambda runtime. boto3 is runtime-provided and
# lives in the dev dependency group, so --no-dev keeps it out of the zip.
set -euo pipefail
cd "$(dirname "$0")/../.."

PKG=build/package
rm -rf "$PKG" build/lambda.zip
mkdir -p "$PKG"

uv export --no-dev --no-hashes --no-emit-project -o build/lambda-requirements.txt
uv pip install \
    --python-platform x86_64-manylinux2014 --python-version 3.12 \
    --target "$PKG" --only-binary :all: \
    -r build/lambda-requirements.txt

cp -r src/leecad "$PKG/"
cp infra/lambda/lambda_function.py "$PKG/"

(cd "$PKG" && zip -rq ../lambda.zip .)
echo "built build/lambda.zip ($(du -h build/lambda.zip | cut -f1))"
