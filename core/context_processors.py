from django.apps import apps

def crm_agent(request):
    """
    Espone 'crm_agent' a tutti i template.
    Cerca l'agente collegato all'utente loggato (match per email).
    """
    agent = None
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        try:
            Agent = apps.get_model("core", "Agent")
            agent = Agent.objects.filter(email=user.email).first()
        except Exception:
            agent = None

    return {"crm_agent": agent}
