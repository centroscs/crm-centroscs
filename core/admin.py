from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Agent,
    Contact,
    Property,
    PropertyImage,
    Appointment,
    TodoItem,
    GoogleAccount,
)


# =========================
# INLINE IMMAGINI IMMOBILE
# =========================
class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("thumb", "image", "is_primary")
    readonly_fields = ("thumb",)

    def thumb(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;" />',
                obj.image.url
            )
        return "—"

    thumb.short_description = "Preview"


# =======
# AGENTI
# =======
@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "user")
    search_fields = ("name", "email", "user__username")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)


# =========
# CONTATTI
# =========
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "phone", "updated_at")
    search_fields = ("full_name", "email", "phone")
    ordering = ("full_name",)


# ==========
# IMMOBILI
# ==========
@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "city", "thumb", "price", "updated_at")
    search_fields = ("code", "address", "city", "description")
    ordering = ("-updated_at",)
    inlines = [PropertyImageInline]

    def thumb(self, obj):
        url = obj.primary_image_url()
        if url:
            return format_html(
                '<img src="{}" style="width:50px;height:50px;object-fit:cover;border-radius:8px;" />',
                url
            )
        return "—"

    thumb.short_description = "Foto"


# =============
# APPUNTAMENTI
# =============
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "start", "end", "agent", "contact", "property")
    list_filter = ("agent",)
    search_fields = ("title", "notes", "contact__full_name", "property__code")


# =====
# TODO
# =====
@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ("id", "agent", "title", "is_done", "updated_at")
    list_filter = ("is_done", "agent")
    search_fields = ("title", "agent__name")
    ordering = ("is_done", "-updated_at")


# ===============
# GOOGLE ACCOUNT
# ===============
@admin.register(GoogleAccount)
class GoogleAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "updated_at")
    search_fields = ("user__username",)
    list_select_related = ("user",)
