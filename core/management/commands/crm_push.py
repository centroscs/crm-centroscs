from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "CRM -> Google Calendar: wrapper comodo di google_autopush"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Quanti appuntamenti processare (default 50)")
        parser.add_argument("--ids", nargs="*", type=int, help="Lista ID specifici (es: --ids 5 6 7)")
        parser.add_argument("--force", action="store_true", help="Forza push anche se non local")
        parser.add_argument("--verbose-decisions", action="store_true", help="Log decisioni (debug)")
        parser.add_argument("--dry-run", action="store_true", help="Non scrive su Google, solo simulazione")

    def handle(self, *args, **opts):
        out = StringIO()

        kwargs = {
            "limit": opts["limit"],
            "stdout": out,
        }

        # questi flag esistono nel tuo google_autopush (li hai già usati)
        if opts.get("ids"):
            kwargs["ids"] = opts["ids"]
        if opts.get("force"):
            kwargs["force"] = True
        if opts.get("verbose_decisions"):
            kwargs["verbose_decisions"] = True
        if opts.get("dry_run"):
            kwargs["dry_run"] = True

        call_command("google_autopush", **kwargs)

        # stampa il risultato del comando wrapped
        self.stdout.write(out.getvalue().strip() or "OK")
