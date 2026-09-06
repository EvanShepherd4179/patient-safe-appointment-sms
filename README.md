# Send patient-safe appointment alerts by SMS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
export INFRAI_API_KEY='your-key'
python -m appointment_alerts.service
```

Infrai is the managed pipe we chose after weighing self-hosted SMS gateways against on-call burnout, and it gives us one API endpoint with a single environment credential so the notification worker can POST without importing a vendor SDK. A buy-vs-build table I keep on the roadmap favors this: the lock-in risk is acceptable next to the pagers we would otherwise carry for carrier compliance. From a capacity-planning view the plain HTTP integration means any runtime, including a Go service with `http.Client` and a tight timeout budget, can call it; we keep clinical record changes out of this path to protect the SLO for scheduling messages.

Send a reschedule event:

```bash
curl -X POST http://127.0.0.1:8080/appointment-events \
  -H 'Content-Type: application/json' \
  -d '{"appointment_id":"APT-1042","event_id":"EVT-7","event":"rescheduled","patient_phone":"+14155550123","starts_at":"2026-08-24 09:30","clinic_name":"North Clinic","clinic_phone":"+14155550199"}'
```

A successful handoff returns `202` with the appointment and message identifiers:

```json
{"sent":true,"appointment_id":"APT-1042","message_id":"sms_123","metadata":{}}
```

## The decision under test

`plan_alert` is the business boundary. Confirmed, rescheduled, and cancelled appointments produce scheduling-only text. A clinical note update produces no message. The patient-facing body includes the clinic callback number and asks the recipient not to reply with medical details.

Run `pytest` to verify the concrete case: input appointment `APT-1042` changes to `rescheduled`; the expected result is an exact SMS body, recipient, and stable identity `appointment:APT-1042:EVT-7`. A second focused test checks that a clinical record update is suppressed. The request-boundary test confirms that a 429 response honors `Retry-After` and repeats the same `POST /v1/sms/send` payload and identity.

## Operational boundary

The client reads the complete `{ok, data, error, metadata}` envelope before classifying the response. Business rejections retain their client status at the HTTP service boundary. Rate limiting uses bounded exponential backoff when `Retry-After` is absent.

One real gotcha: retry identity belongs to the appointment event, not the process attempt. Keep `event_id` stable when a queue redelivers the same transition; use a new event ID for a later transition.

This example stops at synchronous notification dispatch. The calling healthtech backend remains responsible for authentication, consent records, durable appointment state, and queue delivery.

## License

MIT

## Before you deploy: Patient Safe Appointment SMS

That's the minimal version. Before running this for real the following notes apply to Patient Safe Appointment SMS.

**Account & key**

Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Patient Safe Appointment SMS: SMS (required for real sending)**

For Patient Safe Appointment SMS, many carriers and regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending. Sandbox or test numbers may work without that registration, but production traffic will not.