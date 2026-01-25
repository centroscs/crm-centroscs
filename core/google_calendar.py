# core/google_calendar.py
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any, Iterable

from django.conf import settings
from django.utils import timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from core.models import GoogleAccount, Appointment


CRM_BLOCK_START = "[REALESTATE_CRM]"
CRM_BLOCK_END = "[/REALESTATE_CRM]"


# -----------------------------
# Utils: campi esistenti nel Model
# -----------------------------
def _model_field_names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}


_APPT_FIELDS = _model_field_names(Appointment)


def _safe_update_appointment(pk: int, **kwargs) -> None:
    """
    Aggiorna solo i campi che esistono DAVVERO sul modello Appointment.
    Evita FieldDoesNotExist quando in DB/codice i campi differiscono.
    """
    safe = {k: v for k, v in kwargs.items() if k in _APPT_FIELDS}
    if safe:
        Appointment.objects.filter(pk=pk).update(**safe)


# -----------------------------
# Google account / service
# -----------------------------
def _get_team_google_account() -> GoogleAccount:
    team_email = getattr(settings, "GOOGLE_TEAM_ACCOUNT_EMAIL", "").strip().lower()
    if not team_email:
        raise RuntimeError("Manca GOOGLE_TEAM_ACCOUNT_EMAIL in settings/.env")

    ga = GoogleAccount.objects.filter(email=team_email).first()
    if not ga:
        raise RuntimeError(f"GoogleAccount team non trovato in DB: {team_email}. Esegui google_auth_start.")
    return ga


def _expiry_db_to_creds(expiry_db: Optional[datetime]) -> Optional[datetime]:
    """
    DB (Django USE_TZ=True) -> datetime aware UTC.
    google-auth si aspetta expiry *naive UTC*.
    """
    if not expiry_db:
        return None
    if timezone.is_aware(expiry_db):
        expiry_db = expiry_db.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return expiry_db


def _expiry_creds_to_db(expiry_creds: Optional[datetime]) -> Optional[datetime]:
    """
    google-auth -> expiry naive UTC
    DB -> aware UTC
    """
    if not expiry_creds:
        return None
    if timezone.is_naive(expiry_creds):
        return timezone.make_aware(expiry_creds, dt_timezone.utc)
    return expiry_creds


def _creds_from_google_account(ga: GoogleAccount) -> Credentials:
    if not (
        ga.refresh_token
        and ga.client_id
        and ga.client_secret
        and (ga.token_uri or getattr(settings, "GOOGLE_TOKEN_URI", ""))
    ):
        raise RuntimeError("Credenziali non refreshabili: servono refresh_token, token_uri, client_id, client_secret.")

    return Credentials(
        token=ga.access_token or None,
        refresh_token=ga.refresh_token,
        token_uri=ga.token_uri or settings.GOOGLE_TOKEN_URI,
        client_id=ga.client_id,
        client_secret=ga.client_secret,
        expiry=_expiry_db_to_creds(getattr(ga, "token_expiry", None)),
        scopes=["https://www.googleapis.com/auth/calendar"],
    )


def _save_creds_to_google_account(ga: GoogleAccount, creds: Credentials) -> None:
    ga.access_token = creds.token or ""
    ga.token_expiry = _expiry_creds_to_db(getattr(creds, "expiry", None))
    ga.save(update_fields=["access_token", "token_expiry", "updated_at"])


def _ensure_fresh_token(ga: GoogleAccount) -> Credentials:
    creds = _creds_from_google_account(ga)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_creds_to_google_account(ga, creds)
        else:
            raise RuntimeError("Token non valido e non refreshabile (rifai OAuth).")
    return creds


def _get_service_for_team():
    ga = _get_team_google_account()
    creds = _ensure_fresh_token(ga)
    return build("calendar", "v3", credentials=creds)


def get_calendar_id() -> str:
    cal_id = getattr(settings, "GOOGLE_CALENDAR_ID", "").strip()
    if not cal_id:
        raise RuntimeError("Manca GOOGLE_CALENDAR_ID in settings/.env")
    return cal_id


def build_calendar_service(ga: GoogleAccount):
    """
    Compat: usata da google_import (se presente nel progetto).
    """
    creds = _ensure_fresh_token(ga)
    return build("calendar", "v3", credentials=creds)


# -----------------------------
# Description helpers
# -----------------------------
def _compose_human_description(appt: Appointment) -> str:
    """
    Testo leggibile in Google Calendar:
    immobile, indirizzo, ora, contatto, dettagli contatto, agente.
    """
    lines: list[str] = []

    # Agente
    agent = getattr(appt, "agent", None)
    agent_email = getattr(agent, "email", "") or ""
    if agent_email:
        lines.append(f"Agente: {agent_email}")

    # Orari
    start_val = getattr(appt, "start_at", None) or getattr(appt, "start", None)
    end_val = getattr(appt, "end_at", None) or getattr(appt, "end", None)
    if start_val:
        local_start = timezone.localtime(start_val) if timezone.is_aware(start_val) else start_val
        if end_val:
            local_end = timezone.localtime(end_val) if timezone.is_aware(end_val) else end_val
            lines.append(f"Orario: {local_start.strftime('%d/%m/%Y %H:%M')} - {local_end.strftime('%H:%M')}")
        else:
            lines.append(f"Orario: {local_start.strftime('%d/%m/%Y %H:%M')}")

    # Immobile / indirizzo
    prop = getattr(appt, "property", None)
    if prop:
        prop_code = getattr(prop, "code", "") or getattr(prop, "ref", "") or getattr(prop, "codice", "")
        addr = getattr(prop, "address", "") or getattr(prop, "indirizzo", "") or getattr(prop, "street", "")
        city = getattr(prop, "city", "") or getattr(prop, "town", "") or getattr(prop, "comune", "")
        if prop_code:
            lines.append(f"Immobile: {prop_code}")
        if addr or city:
            indirizzo = (addr + (f", {city}" if city else "")).strip().strip(",")
            lines.append(f"Indirizzo: {indirizzo}")

    # Contatto
    c = getattr(appt, "contact", None)
    if c:
        name = getattr(c, "name", "") or getattr(c, "full_name", "")
        if not name:
            fn = getattr(c, "first_name", "") or getattr(c, "nome", "")
            ln = getattr(c, "last_name", "") or getattr(c, "cognome", "")
            name = (fn + " " + ln).strip()

        email = getattr(c, "email", "") or getattr(c, "mail", "")
        phone = getattr(c, "phone", "") or getattr(c, "mobile", "") or getattr(c, "telefono", "")

        if name:
            lines.append(f"Contatto: {name}")
        if phone:
            lines.append(f"Telefono: {phone}")
        if email:
            lines.append(f"Email: {email}")

    # Luogo
    loc = getattr(appt, "location", "") or ""
    if loc:
        lines.append(f"Luogo: {loc}")

    # Dettagli (description del tuo model)
    desc = getattr(appt, "description", "") or ""
    if desc:
        lines.append("")
        lines.append("Dettagli:")
        lines.append(desc.strip())

    return "\n".join(lines).strip()


def _compose_google_description(user_text: str, *, agent_email: str = "") -> str:
    """
    Testo umano sopra, blocco tecnico CRM sotto.
    """
    user_text = (user_text or "").strip()

    meta = f"agent={agent_email}".strip() if agent_email else ""
    if meta:
        crm_block = f"{CRM_BLOCK_START}\n{meta}\n{CRM_BLOCK_END}"
    else:
        crm_block = f"{CRM_BLOCK_START}\n{CRM_BLOCK_END}"

    if user_text:
        return f"{user_text}\n\n{crm_block}".strip()

    return f"RealEstate CRM\n\n{crm_block}".strip()


# -----------------------------
# Upsert single appointment (CRM -> Google)
# -----------------------------
def upsert_event_for_appointment(appt: Appointment) -> Dict[str, Any]:
    """
    Crea/Aggiorna evento su Google Calendar per Appointment.
    - account TEAM
    - colorId da appt.agent.google_color_id (se presente)
    - description: testo umano + blocco CRM
    - salva solo campi esistenti su Appointment (no crash)
    """
    service = _get_service_for_team()
    cal_id = get_calendar_id()

    agent = getattr(appt, "agent", None)
    agent_email = getattr(agent, "email", "") or ""
    color_id = getattr(agent, "google_color_id", None)

    start_dt = getattr(appt, "start_at", None) or getattr(appt, "start", None)
    end_dt = getattr(appt, "end_at", None) or getattr(appt, "end", None)
    if not start_dt or not end_dt:
        raise RuntimeError("Appointment senza start/end: non posso pushare su Google.")

    # normalizza aware
    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())

    human = _compose_human_description(appt)
    description = _compose_google_description(human, agent_email=agent_email)

    body: Dict[str, Any] = {
        "summary": getattr(appt, "title", "") or "Appuntamento",
        "description": description,
        "location": getattr(appt, "location", "") or "",
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }
    if color_id:
        body["colorId"] = str(color_id)

    google_event_id = getattr(appt, "google_event_id", "") or ""

    if google_event_id:
        ev = service.events().patch(calendarId=cal_id, eventId=google_event_id, body=body).execute()
    else:
        ev = service.events().insert(calendarId=cal_id, body=body).execute()

    # salva back (solo campi esistenti)
    _safe_update_appointment(
        appt.pk,
        google_event_id=(ev.get("id") or google_event_id),
        google_etag=(ev.get("etag") or ""),  # ignorato se non esiste
        last_synced_at=timezone.now(),
        sync_state="synced",
        sync_error="",  # ignorato se non esiste
    )

    return ev

