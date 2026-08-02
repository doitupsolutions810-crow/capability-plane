"""Minimal AttestPipe bus: in-process + optional Floci SQS mirror."""
from __future__ import annotations

import json
import os
from typing import Callable, List

from .messages import Envelope

Subscriber = Callable[[dict], None]


class AttestPipeBus:
    def __init__(self) -> None:
        self._subs: List[Subscriber] = []

    def subscribe(self, fn: Subscriber) -> None:
        self._subs.append(fn)

    def publish(self, msg: Envelope | dict) -> dict:
        payload = json.loads(msg.to_json()) if isinstance(msg, Envelope) else msg
        for fn in self._subs:
            fn(payload)
        if os.environ.get("ATTESTPIPE_MIRROR_SQS", "1") == "1":
            try:
                self._mirror_sqs(payload)
            except Exception as e:  # noqa: BLE001
                payload.setdefault("_mirror_error", str(e))
        return payload

    def _mirror_sqs(self, payload: dict) -> None:
        try:
            import boto3
        except ImportError:
            return
        endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://127.0.0.1:4566")
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        qname = os.environ.get("FLOCI_SQS_AUDIT_QUEUE", "capability-audit")
        client = boto3.client(
            "sqs",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        )
        url = client.get_queue_url(QueueName=qname)["QueueUrl"]
        client.send_message(QueueUrl=url, MessageBody=json.dumps(payload))


BUS = AttestPipeBus()
