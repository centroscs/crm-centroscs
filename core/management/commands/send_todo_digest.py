from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from core.models import TodoItem, Agent


def _agent_recipient(agent: Agent) -> str | None:
    # Priorità: Agent.email -> User.email
    if getattr(agent, "email", ""):
        e = agent.email.strip()
        if e:
            return e
    u = getattr(agent, "user", None)
    if u and getattr(u, "email", ""):
        e = u.email.strip()
        if e:
            return e
    return None


def _fmt_dt(dt):
    if not dt:
        return "—"
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


class Command(BaseCommand):
    help = "Invia un digest giornaliero delle TODO agli agenti (scadute/oggi/domani)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=1,
            help="Quanti giorni in avanti includere oltre a oggi (default: 1 = domani).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Non invia email, stampa solo cosa farebbe.",
        )

    def handle(self, *args, **opts):
        days_ahead = int(opts["days_ahead"])
        dry = bool(opts["dry_run"])

        now = timezone.now()
        tz = timezone.get_current_timezone()

        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        last_day = today + timedelta(days=days_ahead)

        # Consideriamo solo todo aperte e con scadenza valorizzata
        qs = (
            TodoItem.objects.select_related("agent", "agent__user")
            .filter(is_done=False, due_at__isnull=False)
            .order_by("agent_id", "due_at", "id")
        )

        # Raggruppo per agente
        by_agent = defaultdict(list)
        for t in qs:
            if t.agent_id:
                by_agent[t.agent_id].append(t)

        sent = 0
        skipped = 0

        self.stdout.write(f"[send_todo_digest] now={now.isoformat()} today={today} ahead={days_ahead} day(s)")

        for agent_id, items in by_agent.items():
            agent = items[0].agent
            to_email = _agent_recipient(agent)
            if not to_email:
                skipped += 1
                continue

            overdue = []
            due_today = []
            due_tomorrow = []
            due_next = []

            for t in items:
                due_local_date = timezone.localtime(t.due_at, tz).date()
                if due_local_date < today:
                    overdue.append(t)
                elif due_local_date == today:
                    due_today.append(t)
                elif due_local_date == tomorrow:
                    due_tomorrow.append(t)
                elif today < due_local_date <= last_day:
                    due_next.append(t)

            # Se non c’è nulla di rilevante, non inviare
            if not (overdue or due_today or due_tomorrow or due_next):
                continue

            subject = f"TODO Digest — {agent.name} — {today.strftime('%d/%m/%Y')}"

            def render_block(title, arr):
                if not arr:
                    return []
                lines = [f"{title} ({len(arr)}):"]
                for t in arr:
                    lines.append(f"• {_fmt_dt(t.due_at)} — {t.title}")
                lines.append("")  # riga vuota
                return lines

            lines = []
            lines.append(f"Ciao {agent.name},")
            lines.append("")
            lines.append("Ecco il riepilogo delle TODO aperte:")
            lines.append("")

            lines += render_block("⛔ Scadute", overdue)
            lines += render_block("📌 In scadenza oggi", due_today)
            lines += render_block("🟡 In scadenza domani", due_tomorrow)

            if due_next:
                lines += render_block(f"📅 In scadenza nei prossimi {days_ahead} giorni", due_next)

            lines.append("Apri il CRM per gestirle: /crm/my/todos/")
            lines.append("")
            lines.append("—")
            lines.append("MESH – WEB CRM SOFTWARE")

            body = "\n".join(lines)

            if dry:
                self.stdout.write(f"DRY-RUN -> {to_email} | {subject}")
            else:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=None,
                    recipient_list=[to_email],
                    fail_silently=False,
                )
                sent += 1

        self.stdout.write(f"[send_todo_digest] sent={sent} skipped(no email)={skipped}")
