from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from core.models import Appointment


def _recipient_for_appointment(appt: Appointment) -> Optional[str]:
    agent = appt.agent
    if not agent:
        return None
    if getattr(agent, "email", ""):
        return agent.email.strip() or None
    user = getattr(agent, "user", None)
    if user and getattr(user, "email", ""):
        return user.email.strip() or None
    return None


class Command(BaseCommand):
    help = "Invia email di alert agli agenti 2 ore prima degli appuntamenti (evita doppioni)."

    def add_arguments(self, parser):
        parser.add_argument("--lead-minutes", type=int, default=120, help="Minuti prima dell’appuntamento (default 120)")
        parser.add_argument("--window-minutes", type=int, default=10, help="Finestra di ricerca (default 10)")
        parser.add_argument("--dry-run", action="store_true", help="Non inviare, stampa solo cosa farebbe")

    def handle(self, *args, **options):
        lead = int(options["lead_minutes"])
        window = int(options["window_minutes"])
        dry = bool(options["dry_run"])

        now = timezone.now()
        target_from = now + timedelta(minutes=lead)
        target_to = target_from + timedelta(minutes=window)

        qs = (
            Appointment.objects.select_related("agent", "agent__user", "contact", "property")
            .filter(start__gte=target_from, start__lt=target_to, alert_sent_at__isnull=True)
            .order_by("start")
        )

        count_total = qs.count()
        sent = 0
        skipped = 0

        self.stdout.write(f"[send_appointment_alerts] now={now.isoformat()} lead={lead}m window={window}m")
        self.stdout.write(f"[send_appointment_alerts] appointments in window: {count_total}")

        for appt in qs:
            to_email = _recipient_for_appointment(appt)
            if not to_email:
                skipped += 1
                continue

            when = timezone.localtime(appt.start).strftime("%d/%m/%Y %H:%M")
            subject = f"Promemoria appuntamento tra ~2 ore: {appt.title}"
            lines = [
                f"Ciao,",
                "",
                f"Promemoria: hai un appuntamento tra circa {lead} minuti.",
                "",
                f"Titolo: {appt.title}",
                f"Quando: {when}",
                f"Luogo: {appt.location or '—'}",
            ]

            if appt.contact:
                lines.append(f"Contatto: {appt.contact.full_name}")
                if appt.contact.phone:
                    lines.append(f"Telefono: {appt.contact.phone}")
                if appt.contact.email:
                    lines.append(f"Email: {appt.contact.email}")

            if appt.property:
                lines.append(f"Immobile: {appt.property.code} — {appt.property.city} — {appt.property.address}")

            if appt.notes:
                lines.extend(["", "Note:", appt.notes])

            lines.extend(["", "—", "MESH – WEB CRM SOFTWARE"])
            body = "\n".join(lines)

            if dry:
                self.stdout.write(f"DRY-RUN -> {to_email} | {subject}")
            else:
                # from_email: se non configurato, Django userà DEFAULT_FROM_EMAIL o fallback
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=None,
                    recipient_list=[to_email],
                    fail_silently=False,
                )

                appt.alert_sent_at = timezone.now()
                appt.save(update_fields=["alert_sent_at"])
                sent += 1

        self.stdout.write(f"[send_appointment_alerts] sent={sent} skipped(no email)={skipped}")
