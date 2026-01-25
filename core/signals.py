from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Appointment


def _appointment_has_field(name: str) -> bool:
    return name in {f.name for f in Appointment._meta.get_fields() if getattr(f, "name", None)}


@receiver(post_save, sender=Appointment)
def appointment_mark_local_on_change(sender, instance: Appointment, created: bool, **kwargs):
    """
    Compat: alcune versioni del model Appointment hanno sync_state/last_synced_at, altre no.
    Se i campi non esistono, non fare nulla (così non crasha mai).
    """
    if not _appointment_has_field("sync_state"):
        return

    # Se esiste, imposta sempre "local" quando viene modificato localmente
    if getattr(instance, "sync_state", None) != "local":
        instance.sync_state = "local"
        update_fields = ["sync_state"]

        if _appointment_has_field("last_synced_at"):
            instance.last_synced_at = None
            update_fields.append("last_synced_at")

        instance.save(update_fields=update_fields)
