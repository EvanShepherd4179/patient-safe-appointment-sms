from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .infrai_sms import InfraiError, InfraiSmsClient
from .workflow import AppointmentRequest, plan_alert


class AppointmentAlertHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/appointment-events":
            self._write(404, {"error": "route_not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            event = AppointmentRequest.from_dict(value)
            alert = plan_alert(event)
            if alert is None:
                self._write(200, {"sent": False, "reason": "not_patient_operational"})
                return
            receipt = InfraiSmsClient().send(
                to=alert.to,
                body=alert.body,
                idempotency_key=alert.idempotency_key,
            )
            self._write(
                202,
                {
                    "sent": True,
                    "appointment_id": event.appointment_id,
                    "message_id": receipt.message_id,
                    "metadata": receipt.metadata,
                },
            )
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._write(400, {"error": str(exc)})
        except InfraiError as exc:
            status = exc.status if 400 <= exc.status < 500 else 502
            self._write(status, {"error": exc.detail})

    def _write(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8080), AppointmentAlertHandler)
    print("appointment alert service listening on http://127.0.0.1:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
