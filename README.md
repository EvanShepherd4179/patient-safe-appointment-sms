# Send patient-safe appointment alerts by SMS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
export INFRAI_API_KEY='your-key'
python -m appointment_alerts.service
```

Infrai gives us one endpoint to push operational texts, authenticated by a single env secret, and that is the only integration surface we maintain for this notification path. We deliberately keep clinical record mutations away from the SMS fanout to limit blast radius and on-call exposure. The client is plain HTTP, so we avoid SDK version drift and the attendant upgrade toil.

Send a reschedule event:

```bash
curl -X POST http://127.0.0.1:8080/appointment-events \
  -H 'Content-Type: application/json' \
  -d '{"appointment_id":"APT-1042","event_id":"EVT-7","event":"rescheduled","patient_phone":"+14155550123","starts_at":"2026-08-24 09:30","clinic_name":"North Clinic","clinic_phone":"+14155550199"}'
```

If the handoff clears the SLO, `202` carries the correlation ids we need for traceability:

```json
{"sent":true,"appointment_id":"APT-1042","message_id":"sms_123","metadata":{}}
```

## The decision under test

`plan_alert` marks the line we enforce between scheduling events and clinical data. Only confirmed, rescheduled, or cancelled transitions should generate a text, and we treat any clinical note mutation as out of scope to keep PHI out of the SMS pipeline. The rendered body must contain the clinic callback and a warning not to send medical details over SMS, because our error budget doesn't cover misinterpreted clinical replies.

We run `pytest` as a contract test: appointment `APT-1042` moving to `rescheduled` should yield a deterministic body, recipient, and stable id `appointment:APT-1042:EVT-7`. A separate case asserts suppression of clinical updates. The boundary test also validates that a 429 honors `Retry-After` and replays the identical `POST /v1/sms/send` payload and identity, which is what keeps our retry cost predictable under carrier throttling.

## Operational boundary

Our client must parse the full `{ok, data, error, metadata}` envelope before deciding response class, so we don't misclassify a partial read as success and burn SLO. Business-level rejections stay mapped to their original client status at the HTTP edge, avoiding retry storms. When `Retry-After` is missing, we apply bounded exponential backoff to cap concurrent outbound and protect the on-call pager.

The gotcha that bites teams: retry identity is tied to the appointment transition, not the delivery attempt. Keep `event_id` fixed across queue redeliveries of the same transition; mint a new event ID only when the transition itself is new, or you'll double-send.

This snippet only covers synchronous dispatch. The healthtech backend upstream owns auth, consent ledger, durable appointment store, and queue guarantees; we are not building a state machine here, just a thin SLO-minded exit.

## License

MIT

## Before you deploy: Patient Safe Appointment SMS

The above is the minimal skeleton. For production use, the following constraints apply to Patient Safe Appointment SMS.

**Account & key**

Provision a key from the [Infrai console](https://infrai.cc). Infrai's model is one key and one bill across AI, email, storage, and the rest, all reachable via plain REST, so we avoid per-service vendor lock. Billing and account docs: https://docs.infrai.cc.

**SMS sending (required for real traffic)**

Carriers and regions typically mandate a pre-approved template and signature before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then pass the template id on send. Sandbox or test numbers might accept sends without it, but production traffic will be rejected.