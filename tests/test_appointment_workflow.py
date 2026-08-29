from appointment_alerts.workflow import AppointmentEvent, AppointmentRequest, plan_alert


def appointment(event: AppointmentEvent) -> AppointmentRequest:
    return AppointmentRequest(
        appointment_id="APT-1042",
        event_id="EVT-7",
        event=event,
        patient_phone="+14155550123",
        starts_at="2026-08-24 09:30",
        clinic_name="North Clinic",
        clinic_phone="+14155550199",
    )


def test_reschedule_becomes_a_patient_safe_operational_alert() -> None:
    alert = plan_alert(appointment(AppointmentEvent.RESCHEDULED))

    assert alert is not None
    assert alert.to == "+14155550123"
    assert alert.idempotency_key == "appointment:APT-1042:EVT-7"
    assert alert.body == (
        "North Clinic: Your appointment was rescheduled to 2026-08-24 09:30. "
        "Questions? Call +14155550199. Do not reply with medical details."
    )


def test_clinical_record_change_is_not_sent_by_sms() -> None:
    assert plan_alert(appointment(AppointmentEvent.CLINICAL_NOTE_UPDATED)) is None
