from __future__ import annotations

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Contact(models.Model):
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.full_name


class Agent(models.Model):
    # collegamento opzionale ad un utente Django (per login come agente)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent",
    )

    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True, default="")
    google_color_id = models.CharField(max_length=32, blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Property(models.Model):
    code = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def primary_image(self):
        """
        Ritorna:
        - prima una immagine primary (se esiste)
        - altrimenti la prima immagine disponibile
        Ordinamento: position, id
        """
        img = self.images.filter(is_primary=True).order_by("position", "id").first()
        return img or self.images.order_by("position", "id").first()

    def primary_image_url(self) -> str:
        img = self.primary_image()
        return img.image.url if img and img.image else ""

    def __str__(self) -> str:
        return self.code


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(upload_to="properties/%Y/%m/")
    is_primary = models.BooleanField(default=False)

    # ✅ per drag&drop (ordine persistente)
    position = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "-is_primary", "id"]

    def __str__(self) -> str:
        return f"Image #{self.id} for property {self.property_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Se questa è primary, le altre diventano non-primary
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property).exclude(pk=self.pk).update(is_primary=False)

        # Se non esiste nessuna primary (es: cancellata), promuovi la prima
        if not PropertyImage.objects.filter(property=self.property, is_primary=True).exists():
            first_img = PropertyImage.objects.filter(property=self.property).order_by("position", "id").first()
            if first_img and not first_img.is_primary:
                first_img.is_primary = True
                first_img.save(update_fields=["is_primary"])

class Appointment(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField()

    # ✅ QUESTO È IL CAMPO CHE DEVE ESISTERE
    location = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    agent = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )

    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class TodoItem(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="todos")
    title = models.CharField(max_length=255)
    due_at = models.DateTimeField("Scadenza", null=True, blank=True)

    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class GoogleAccount(models.Model):
    """Account Google per sync calendario (se usato)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="google_account")

    token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_uri = models.TextField(blank=True, default="")

    client_id = models.TextField(blank=True, default="")
    client_secret = models.TextField(blank=True, default="")
    scopes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"GoogleAccount({self.user.username})"
