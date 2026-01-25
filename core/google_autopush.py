# core/google_autopush.py
from __future__ import annotations

from typing import Dict, Any

from django.db import transaction
from django.utils import timezone

from core.models import Appointment


def _concrete_field_names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}


def _safe_update(appt_id: int, **values):
    """
    Aggiorna solo i campi che esistono davvero nel modello (evita FieldDoesNotExist).
    """
    existing = _concrete_field_names(Appointment)
    clean = {k: v for k, v in values.items() if k in existing}
    if clean:
        Appointment.objects.filter(pk=appt_id).update(**clean)


@transaction.atomic
def push_local_appointments(*, limit: int = 50, verbosity: int = 1) -> Dict[str, Any]:
    """
    Push CRM → Google per Appointment con sync_state='local'.

    IMPORTANTISSIMO:
    - Qui usiamo SEMPRE core.google_calendar.upsert_event_for_appointment()
      così la description viene composta con immobile/indirizzo/orari/contatto/agente ecc.
    """
    # import lazy per evitare problemi di import all’avvio
    from core.google_calendar import upsert_event_for_appointment

    qs = (
        Appointment.objects.select_related("agent", "property", "contact")
        .filter(sync_state="local")
        .order_by("id")
    )

    checked = 0
    pushed = 0
    errors = 0

    for appt in qs[:limit]:
        checked += 1
        try:
            ev = upsert_event_for_appointment(appt)

            # segna synced (solo se i campi esistono)
            _safe_update(
                appt.pk,
                sync_state="synced",
                sync_error="",
                last_synced_at=timezone.now(),
                google_event_id=(ev.get("id") or getattr(appt, "google_event_id", "")),
                google_etag=(ev.get("etag") or getattr(appt, "google_etag", "")),
            )
            pushed += 1

            if verbosity >= 2:
                print(f"OK PUSH appt={appt.pk} title={getattr(appt,'title','')} event={ev.get('id')}")

        except Exception as ex:
            errors += 1
            _safe_update(
                appt.pk,
                sync_state="error",
                sync_error=f"PUSH ERROR: {ex}",
                last_synced_at=timezone.now(),
            )
            if verbosity >= 1:
                print(f"ERR PUSH appt={appt.pk} -> {ex}")

    return {"pushed": pushed, "errors": errors, "checked": checked}

