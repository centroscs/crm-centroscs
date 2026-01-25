# core/google_sync.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from django.utils import timezone

from core.google_calendar import _get_service_for_team, get_calendar_id
from core.models import Appointment


def _get_dt(obj, names):
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v:
                return v
    return None


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _to_google_dt(dt: datetime) -> Dict[str, str]:
    dt = _ensure_aware(dt)
    return {"dateTime": dt.isoformat()}


def _event_body_from_appt(appt: Appointment) -> Dict[str, Any]:
    start = _get_dt(appt, ["start_at", "start", "start_time", "starts_at"])
    end = _get_dt(appt, ["end_at", "end", "end_time", "ends_at"])

    start = _ensure_aware(start)
    end = _ensure_aware(end)

    title = getattr(appt, "title", "") or ""
    description = getattr(appt, "description", "") or ""
    location = getattr(appt, "location", "") or ""

    # GOOGLE: colorId deve essere stringa "1".."11"
    agent = getattr(appt, "agent", None)
    color_id = None
    if agent is not None and hasattr(agent, "google_color_id") and agent.google_color_id:
        color_id = str(agent.google_color_id)

    body: Dict[str, Any] = {
        "summary": title,
        "description": description,
        "location": location,
    }

    if start:
        body["start"] = _to_google_dt(start)
    if end:
        body["end"] = _to_google_dt(end)

    if color_id:
        body["colorId"] = color_id

    return body


def upsert_appointment_to_google(appt: Appointment) -> str:
    """
    Crea/aggiorna su Google l'evento dell'Appointment.
    Ritorna eventId.
    """
    service = _get_service_for_team()
    cal_id = get_calendar_id()

    body = _event_body_from_appt(appt)
    event_id = getattr(appt, "google_event_id", "") or ""

    if event_id:
        # PATCH: aggiorna solo i campi dati (noi includiamo colorId)
        ev = service.events().patch(calendarId=cal_id, eventId=event_id, body=body).execute()
    else:
        ev = service.events().insert(calendarId=cal_id, body=body).execute()

    new_event_id = ev.get("id") or event_id
    if new_event_id and new_event_id != event_id:
        appt.google_event_id = new_event_id

    if hasattr(appt, "sync_state"):
        appt.sync_state = "synced"
    if hasattr(appt, "last_synced_at"):
        appt.last_synced_at = timezone.now()
    if hasattr(appt, "sync_error"):
        appt.sync_error = ""

    appt.save()
    return new_event_id
