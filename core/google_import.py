from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from core.models import Agent, Appointment, Contact, Property
from core.google_calendar import list_events_for_range


CRM_OPEN = "[REALESTATE_CRM]"
CRM_CLOSE = "[/REALESTATE_CRM]"

RE_KV = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*=\s*(.*?)\s*$")


@dataclass
class CrmBlock:
    appointment_id: Optional[int] = None
    property_code: Optional[str] = None
    property_address: Optional[str] = None
    agent_email: Optional[str] = None
    agent_label: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


def _extract_crm_block(description: str) -> Optional[str]:
    if not description:
        return None
    start = description.find(CRM_OPEN)
    end = description.find(CRM_CLOSE)
    if start == -1 or end == -1 or end <= start:
        return None
    return description[start + len(CRM_OPEN) : end].strip()


def _parse_crm_block(description: str) -> CrmBlock:
    block = _extract_crm_block(description)
    out = CrmBlock()
    if not block:
        return out

    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        m = RE_KV.match(line)
        if not m:
            continue
        k = m.group(1).strip()
        v = m.group(2).strip()

        if k == "appointment_id":
            try:
                out.appointment_id = int(v)
            except Exception:
                pass
        elif k == "property_code":
            out.property_code = v
        elif k == "property_address":
            out.property_address = v
        elif k == "agent_email":
            out.agent_email = v.lower()
        elif k == "agent_label":
            out.agent_label = v
        elif k == "contact_name":
            out.contact_name = v
        elif k == "contact_email":
            out.contact_email = v.lower()
        elif k == "contact_phone":
            out.contact_phone = v

    return out


def _ensure_agent(email: str) -> Agent:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("agent_email mancante nel blocco CRM dell'evento Google")
    agent, _ = Agent.objects.get_or_create(email=email, defaults={"name": email.split("@")[0]})
    return agent


def _ensure_property(code: Optional[str], address: Optional[str]) -> Property:
    code = (code or "").strip()
    address = (address or "").strip()
    if not code:
        # fallback minimo: se manca, creiamo un codice basato su address o su timestamp
        code = f"IMM-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    prop, _ = Property.objects.get_or_create(code=code, defaults={"address": address or code, "title": code})
    # aggiorna address se arriva e manca/è diversa
    if address and prop.address != address:
        prop.address = address
        prop.save(update_fields=["address"])
    return prop


def _ensure_contact(name: Optional[str], email: Optional[str], phone: Optional[str]) -> Optional[Contact]:
    name = (name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip()

    if not (name or email or phone):
        return None

    # chiave: email se c'è, altrimenti nome+telefono
    if email:
        c, _ = Contact.objects.get_or_create(email=email, defaults={"full_name": name or email, "phone": phone})
    else:
        c, _ = Contact.objects.get_or_create(full_name=name or "Contatto", phone=phone)

    # aggiorna campi mancanti
    updated = False
    if name and c.full_name != name:
        c.full_name = name
        updated = True
    if phone and c.phone != phone:
        c.phone = phone
        updated = True
    if email and c.email != email:
        c.email = email
        updated = True
    if updated:
        c.save()
    return c


def _dt_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalizza a naive UTC per confronti coerenti (indipendente da tz).
    """
    if not dt:
        return None
    if timezone.is_aware(dt):
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return dt


def _google_updated_from_event(ev: dict) -> Optional[datetime]:
    # Google event 'updated' è RFC3339
    upd = ev.get("updated")
    if not upd:
        return None
    try:
        # compatibile con '2026-01-13T11:32:01.123Z'
        if upd.endswith("Z"):
            upd = upd.replace("Z", "+00:00")
        dt = datetime.fromisoformat(upd)
        return _dt_utc_naive(dt)
    except Exception:
        return None


def _should_take_google(ev: dict, appt: Appointment) -> bool:
    """
    Decide se sovrascrivere CRM con Google:
    - se CRM è local → CRM vince (non tocchiamo)
    - altrimenti confrontiamo updated Google vs updated_at CRM
    """
    if appt.sync_state == "local":
        return False

    g_upd = _google_updated_from_event(ev)
    crm_upd = _dt_utc_naive(appt.updated_at)
    if not g_upd or not crm_upd:
        # se non ho dati robusti, preferisco NON sovrascrivere local
        # e per synced/error tengo CRM se non so
        return False

    return g_upd > crm_upd


@transaction.atomic
def import_agent_calendar(agent: Agent, days_back: int = 10, days_forward: int = 60, verbose: int = 0) -> Dict:
    """
    Importa eventi dal calendar unico CRM e li upserta su Appointment.
    REGOLA CHIAVE:
      - agent per l'Appointment viene SEMPRE dal blocco CRM: agent_email=
      - conflitto: vince il più recente tra Google(updated) e CRM(updated_at),
        ma se CRM è local, CRM vince sempre.
    """
    start = timezone.now() - timedelta(days=days_back)
    end = timezone.now() + timedelta(days=days_forward)

    events = list_events_for_range(start, end)

    created = 0
    updated = 0
    skipped = 0

    for ev in events:
        # processiamo solo eventi CRM (devono avere il blocco)
        desc = ev.get("description") or ""
        if CRM_OPEN not in desc or CRM_CLOSE not in desc:
            skipped += 1
            if verbose >= 2:
                print(f"[SKIP] event_id={ev.get('id')} (no CRM block)")
            continue

        crm = _parse_crm_block(desc)

        # agente SEMPRE dal blocco CRM
        try:
            ev_agent = _ensure_agent(crm.agent_email or "")
        except Exception as e:
            skipped += 1
            if verbose >= 1:
                print(f"[SKIP] event_id={ev.get('id')} missing agent_email -> {e}")
            continue

        prop = _ensure_property(crm.property_code, crm.property_address)
        contact = _ensure_contact(crm.contact_name, crm.contact_email, crm.contact_phone)

        google_event_id = ev.get("id")
        title = (ev.get("summary") or "").strip() or "Appuntamento"
        location = (ev.get("location") or "").strip()

        # date
        ev_start = ev.get("start", {})
        ev_end = ev.get("end", {})
        start_iso = ev_start.get("dateTime") or ev_start.get("date")
        end_iso = ev_end.get("dateTime") or ev_end.get("date")

        # parsing robusto: dateTime -> aware; date -> all-day (mettiamo mezzanotte UTC)
        def parse_iso(s: Optional[str]) -> Optional[datetime]:
            if not s:
                return None
            try:
                if "T" in s:
                    if s.endswith("Z"):
                        s2 = s.replace("Z", "+00:00")
                        return datetime.fromisoformat(s2).astimezone(dt_timezone.utc)
                    dt = datetime.fromisoformat(s)
                    if timezone.is_naive(dt):
                        dt = dt.replace(tzinfo=dt_timezone.utc)
                    return dt.astimezone(dt_timezone.utc)
                # all-day
                d = datetime.fromisoformat(s)
                return d.replace(tzinfo=dt_timezone.utc)
            except Exception:
                return None

        start_dt = parse_iso(start_iso)
        end_dt = parse_iso(end_iso)

        if not start_dt or not end_dt:
            skipped += 1
            if verbose >= 1:
                print(f"[SKIP] event_id={google_event_id} missing datetime")
            continue

        appt = Appointment.objects.filter(google_event_id=google_event_id).select_for_update().first()

        if not appt:
            appt = Appointment(
                agent=ev_agent,
                property=prop,
                contact=contact,
                title=title,
                location=location,
                start=start_dt,
                end=end_dt,
                google_event_id=google_event_id,
                sync_state="synced",
                last_synced_at=timezone.now(),
            )
            # IMPORT: non vogliamo che signals lo rimetta local
            appt._skip_mark_local = True
            appt.save()
            created += 1
            if verbose >= 2:
                print(f"[CREATE] id={appt.id} event_id={google_event_id} agent={ev_agent.email}")
            continue

        # già esiste: se CRM local -> non toccare
        if appt.sync_state == "local":
            skipped += 1
            if verbose >= 2:
                print(f"[SKIP] id={appt.id} event_id={google_event_id} (CRM local wins)")
            continue

        # conflitto: vince più recente
        take_google = _should_take_google(ev, appt)

        if not take_google:
            skipped += 1
            if verbose >= 2:
                g_upd = _google_updated_from_event(ev)
                print(f"[SKIP] id={appt.id} event_id={google_event_id} (CRM newer or unknown) g_upd={g_upd} crm_upd={appt.updated_at}")
            continue

        # aggiorna da google
        appt.agent = ev_agent
        appt.property = prop
        appt.contact = contact
        appt.title = title
        appt.location = location
        appt.start = start_dt
        appt.end = end_dt
        appt.sync_state = "synced"
        appt.last_synced_at = timezone.now()

        appt._skip_mark_local = True
        appt.save()
        updated += 1
        if verbose >= 2:
            print(f"[UPDATE] id={appt.id} event_id={google_event_id} agent={ev_agent.email}")

    return {"agent": agent.email, "created": created, "updated": updated, "skipped": skipped}
