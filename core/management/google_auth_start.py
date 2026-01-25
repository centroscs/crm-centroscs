from django.core.management.base import BaseCommand, CommandError

from core.models import Agent
from core.google_oauth import start_oauth_for_agent


class Command(BaseCommand):
    help = "Avvia OAuth Google per un agente (salva refresh_token su GoogleAccount)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email agente (es: name@gmail.com)")
        parser.add_argument("--port", type=int, default=8765, help="Porta localhost per callback OAuth")

    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        port = opts["port"]

        try:
            agent = Agent.objects.get(email=email)
        except Agent.DoesNotExist:
            raise CommandError(f"Agent non trovato: {email}")

        ga = start_oauth_for_agent(agent, email=email, port=port)

        self.stdout.write(self.style.SUCCESS("OK: GoogleAccount salvato/aggiornato."))
        self.stdout.write(
            f"email={ga.email} agent={ga.agent.email} refresh_token={'YES' if ga.refresh_token else 'NO'}"
        )
