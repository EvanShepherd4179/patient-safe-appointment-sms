import io
import json

from appointment_alerts.infrai_sms import InfraiSmsClient


class Response:
    def __init__(self, status: int, payload: dict[str, object], retry_after: str | None = None):
        self.status = status
        self.headers = {"Retry-After": retry_after} if retry_after else {}
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._body.read()


def test_rate_limit_retry_keeps_method_body_and_identity() -> None:
    requests = []
    responses = iter(
        [
            Response(429, {"ok": False, "error": {"code": "RATE_LIMIT"}}, "2"),
            Response(
                200,
                {
                    "ok": True,
                    "data": {"message_id": "sms_123"},
                    "metadata": {"vendor": "selected"},
                },
            ),
        ]
    )
    sleeps = []

    def open_request(request, timeout):
        requests.append(request)
        assert timeout == 15
        return next(responses)

    client = InfraiSmsClient(
        api_key="test-key", opener=open_request, sleeper=sleeps.append, max_retries=1
    )
    receipt = client.send(
        to="+14155550123",
        body="Appointment reminder",
        idempotency_key="appointment:APT-1042:EVT-7",
    )

    assert receipt.message_id == "sms_123"
    assert sleeps == [2.0]
    assert [request.method for request in requests] == ["POST", "POST"]
    assert requests[0].data == requests[1].data
    assert requests[0].headers["Idempotency-key"] == requests[1].headers["Idempotency-key"]
