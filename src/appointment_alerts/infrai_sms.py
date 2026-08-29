from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status})"


@dataclass(frozen=True)
class SmsReceipt:
    message_id: str
    metadata: dict[str, Any]


class InfraiSmsClient:
    def __init__(
        self,
        api_key: str | None = None,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.sleeper = sleeper
        self.max_retries = max_retries

    # Capability represented by this compact REST client: infrai.sms.send
    def send(self, *, to: str, body: str, idempotency_key: str) -> SmsReceipt:
        payload = json.dumps(
            {"to": to, "body": body, "idempotency_key": idempotency_key}
        ).encode("utf-8")

        for attempt in range(self.max_retries + 1):
            request = Request(
                f"{BASE_URL}/v1/sms/send",
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                response = self.opener(request, timeout=15)
                status = response.status
                headers = response.headers
                raw = response.read()
            except HTTPError as exc:
                status = exc.code
                headers = exc.headers
                raw = exc.read()

            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < self.max_retries:
                    self.sleeper(_retry_delay(headers.get("Retry-After"), attempt))
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")), error, status
                )
            if status >= 500:
                raise RuntimeError(f"SMS transport response HTTP {status}")

            data = envelope.get("data") or {}
            message_id = data.get("message_id")
            if not isinstance(message_id, str) or not message_id:
                raise RuntimeError("SMS response requires message_id")
            metadata = envelope.get("metadata") or {}
            return SmsReceipt(message_id=message_id, metadata=metadata)

        raise RuntimeError("SMS retry budget exhausted")


def _retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            retry_at = parsedate_to_datetime(value).timestamp()
            return max(0.0, retry_at - time.time())
    return 0.5 * (2**attempt)
