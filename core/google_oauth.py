from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.utils import timezone

from google_auth_oauthlib.flow import InstalledAppFlow

from core.models import Agent, GoogleAccount


SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _require(value: Optional[str], name: str) -> str:
    v = (value or "").strip()
    if not v:
        raise RuntimeError(f"Manca {name} in config/settings.py o .env")
    return v


def _client_config() -> dict:
    """
    Per InstalledAppFlow serve una config 'installed'.
    Anche se in Google Console hai creato credenziali 'Web', va bene lo stesso
    per l'OAuth locale con browser.
    """
    client_id = _require(getattr(settings, "GOOGLE_CLIENT_ID", None), "GOOGLE_CLIENT_ID")
    client_secret = _require(getattr(settings, "GOOGLE_CLIENT_SECRET", None), "GOOGLE_CLIENT_SECRET")
    token_uri = (getattr(settings, "GOOGLE_TOKEN_URI", "") or "https://oauth2.googleapis.com/token").strip()

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": token_uri,
            "redirect_uris": ["http://localhost"],
        }
    }


def start_oauth_for_agent(agent: Agent, email: str, port: int = 8765) -> GoogleAccount:
    """
    Avvia OAuth in locale e salva token/refresh_token nel GoogleAccount.
    """
    flow = InstalledAppFlow.from_client_config(_client_config(), scopes=SCOPES)

    creds = flow.run_local_server(
        host="localhost",
        port=port,
        authorization_prompt_message="Apri il browser per autorizzare Google Calendar",
        success_message="OK, autorizzazione completata. Puoi chiudere questa scheda.",
        open_browser=True,
    )

    ga, _ = GoogleAccount.objects.get_or_create(agent=agent, email=email)

    ga.access_token = creds.token or ""
    ga.refresh_token = creds.refresh_token or ga.refresh_token or ""
    ga.token_uri = getattr(creds, "token_uri", None) or getattr(settings, "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    ga.client_id = getattr(creds, "client_id", None) or getattr(settings, "GOOGLE_CLIENT_ID", "")
    ga.client_secret = getattr(creds, "client_secret", None) or getattr(settings, "GOOGLE_CLIENT_SECRET", "")

    # token_expiry: convertiamo a aware (UTC) se necessario
    exp = getattr(creds, "expiry", None)
    if exp is not None:
        if timezone.is_naive(exp):
            exp = timezone.make_aware(exp, timezone=timezone.utc)
        ga.token_expiry = exp

    ga.save()
    return ga
