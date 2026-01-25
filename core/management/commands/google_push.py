# core/management/commands/google_push.py
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Appointment
from core.google_calendar import upsert_event_for_appointment


class Command(BaseCommand):
    help = "Push CRM → Google Calendar (solo Appointment con sync_state='local')"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Numero massimo di appuntamenti da processare",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        qs = (
            Appointment.objects
            .filter(sync_state="local")
            .select_related("agent")
            .order_by("id")[:limit]
        )

        pushed = 0
        errors = 0
        checked = 0

        for appt in qs:
            checked += 1
            try:
                upsert_event_for_appointment(appt)

                Appointment.objects.filter(pk=appt.pk).update(
                    sync_state="synced",
                    last_synced_at=timezone.now(),
                )
                pushed += 1
            except Exception as e:
                Appointment.objects.filter(pk=appt.pk).update(
                    sync_state="error",
                    last_synced_at=timezone.now(),
                )
                errors += 1

        self.stdout.write(
            str({
                "checked": checked,
                "pushed": pushed,
                "errors": errors,
            })
        )
