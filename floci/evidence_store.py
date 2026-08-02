#!/usr/bin/env python3
"""Minimal evidence store using Floci S3 (boto3). Dev/CI only."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

try:
    import boto3
except ImportError:
    raise ImportError("pip install boto3")

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://127.0.0.1:4566")
BUCKET = os.environ.get("FLOCI_S3_EVIDENCE_BUCKET", "capability-evidence")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def put_evidence(capability_id: str, bundle: dict) -> str:
    key = f"evidence/{capability_id}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    body = json.dumps(bundle, indent=2).encode()
    client().put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json")
    return f"s3://{BUCKET}/{key}"
