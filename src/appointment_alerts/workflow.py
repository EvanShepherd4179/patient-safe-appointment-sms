from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AppointmentEvent(StrEnum):
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    CLINICAL_NOTE_UPDATED = "clinical_note_updated"


@dataclass(frozen=True)
class AppointmentRequest:
    appointment_id: str
    event_id: str
    event: AppointmentEvent
    patient_phone: str
    starts_at: str
    clinic_name: str
    clinic_phone: str

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> AppointmentRequest:
        required = (
            "appointment_id",
            "event_id",
            "event",
            "patient_phone",
            "starts_at",
            "clinic_name",
            "clinic_phone",
        )
        fields: dict[str, str] = {}
        for name in required:
            item = value.get(name)
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{name} must be a non-empty string")
            fields[name] = item.strip()
        return cls(
            appointment_id=fields["appointment_id"],
            event_id=fields["event_id"],
            event=AppointmentEvent(fields["event"]),
            patient_phone=fields["patient_phone"],
            starts_at=fields["starts_at"],
            clinic_name=fields["clinic_name"],
            clinic_phone=fields["clinic_phone"],
        )


@dataclass(frozen=True)
class PlannedAlert:
    to: str
    body: str
    idempotency_key: str


def plan_alert(request: AppointmentRequest) -> PlannedAlert | None:
    """Return an operational alert; clinical record changes stay off SMS."""
    wording = {
        AppointmentEvent.CONFIRMED: "is confirmed for",
        AppointmentEvent.RESCHEDULED: "was rescheduled to",
        AppointmentEvent.CANCELLED: "was cancelled for",
    }.get(request.event)
    if wording is None:
        return None

    body = (
        f"{request.clinic_name}: Your appointment {wording} {request.starts_at}. "
        f"Questions? Call {request.clinic_phone}. Do not reply with medical details."
    )
    return PlannedAlert(
        to=request.patient_phone,
        body=body,
        idempotency_key=f"appointment:{request.appointment_id}:{request.event_id}",
    )
