from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .forms import (
    AgentForm,
    AppointmentForm,
    ContactForm,
    PropertyAttachmentMultiUploadForm,
    PropertyForm,
    PropertyImageMultiUploadForm,
)
from .models import Agent, Appointment, Contact, Property, PropertyAttachment, PropertyImage, TodoItem


# ============================================================
# Helpers
# ============================================================

def _order_by_if_exists(qs, *fields: str):
    model_fields = {f.name for f in qs.model._meta.get_fields() if hasattr(f, "name")}
    for f in fields:
        name = f.lstrip("-")
        if name in model_fields:
            return qs.order_by(f)
    return qs


def _agents_qs():
    return Agent.objects.all().order_by("name")


def _contacts_qs():
    return Contact.objects.all().order_by("full_name")


def _properties_qs():
    return Property.objects.all().order_by("code")


def _parse_dt_local(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()

    dt = parse_datetime(s)
    if dt is None:
        d = parse_date(s)
        if d is None:
            return None
        dt = datetime.combine(d, time.min)

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _is_admin_user(user) -> bool:
    return bool(user and (user.is_staff or user.is_superuser))


def _current_agent_for_request(request: HttpRequest) -> Optional[Agent]:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None
    try:
        return request.user.agent
    except Exception:
        return None


def _forbid(request: HttpRequest, msg: str, fallback_url_name: str = "crm_dashboard") -> HttpResponse:
    messages.error(request, msg)
    return redirect(fallback_url_name)


def _can_edit_property(request: HttpRequest, prop: Property) -> bool:
    """Admin può sempre. Agente solo se è owner_agent."""
    if _is_admin_user(request.user):
        return True
    me = _current_agent_for_request(request)
    return bool(me and getattr(prop, "owner_agent_id", None) == me.id)


def _can_manage_images(request: HttpRequest, prop: Optional[Property]) -> bool:
    """Stesso criterio dell'edit: admin sempre, agente solo se proprietario."""
    if _is_admin_user(request.user):
        return True
    if prop is None:
        # in creazione: l'agente può caricare perché l'immobile sarà suo
        return _current_agent_for_request(request) is not None
    return _can_edit_property(request, prop)


def _set_appointment_location(obj: Appointment, request: HttpRequest) -> None:
    """
    Salva SEMPRE il luogo (anche se vuoto) leggendo dal POST 'location'.
    Il tuo campo reale è location.
    """
    obj.location = (request.POST.get("location") or "").strip()


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def crm_dashboard(request: HttpRequest) -> HttpResponse:
    # Date locali
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    # Visibilità: admin vede tutto, agente vede solo il suo
    qs_appt = Appointment.objects.select_related("agent").all()
    qs_todo = TodoItem.objects.select_related("agent").filter(is_done=False)

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if me:
            qs_appt = qs_appt.filter(agent=me)
            qs_todo = qs_todo.filter(agent=me)
        else:
            # utente non collegato ad agente: mostra vuoto (ma non esplode)
            qs_appt = qs_appt.none()
            qs_todo = qs_todo.none()

    appointments_today = qs_appt.filter(start__date=today).order_by("start")
    appointments_tomorrow = qs_appt.filter(start__date=tomorrow).order_by("start")

    todos_today = qs_todo.filter(due_at__date=today).order_by("due_at")
    todos_tomorrow = qs_todo.filter(due_at__date=tomorrow).order_by("due_at")

    ctx = {
        "today": today,
        "tomorrow": tomorrow,
        "appointments_today": appointments_today,
        "appointments_tomorrow": appointments_tomorrow,
        "todos_today": todos_today,
        "todos_tomorrow": todos_tomorrow,
    }
    return render(request, "core/dashboard.html", ctx)

# ============================================================
# CONTACTS
# ============================================================

@login_required
def contacts_list(request: HttpRequest) -> HttpResponse:
    contacts = _contacts_qs()
    return render(request, "core/contacts.html", {"contacts": contacts})


@login_required
def contact_new(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Contatto creato.")
            return redirect("contact_detail", pk=obj.pk)
        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = ContactForm()

    return render(request, "core/contact_form.html", {"form": form, "object": None})


@login_required
def contact_detail(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Contact, pk=pk)
    return render(request, "core/contact_detail.html", {"contact": obj, "object": obj})


@login_required
def contact_edit(request: HttpRequest, pk: int) -> HttpResponse:
    # come avevi: agenti non modificano contatti esistenti
    if not _is_admin_user(request.user):
        return _forbid(request, "Gli agenti possono creare contatti ma non modificare quelli esistenti.")

    obj = get_object_or_404(Contact, pk=pk)
    if request.method == "POST":
        form = ContactForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Contatto aggiornato.")
            return redirect("contact_detail", pk=obj.pk)
        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = ContactForm(instance=obj)

    return render(request, "core/contact_form.html", {"form": form, "object": obj, "contact": obj})


# ============================================================
# APPOINTMENTS
# ============================================================

@login_required
def appointments_list(request: HttpRequest) -> HttpResponse:
    qs = Appointment.objects.select_related("agent", "contact", "property").all()
    qs = _order_by_if_exists(qs, "-start", "-created_at")
    return render(
        request,
        "core/appointments.html",
        {
            "appointments": qs,
            "agents": _agents_qs(),
            "contacts": _contacts_qs(),
            "properties": _properties_qs(),
        },
    )


@login_required
def appointment_new(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)

            # Se non admin, forzo l'agente loggato
            if not _is_admin_user(request.user):
                me = _current_agent_for_request(request)
                if not me:
                    return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
                obj.agent = me

            # ✅ salva sempre location
            _set_appointment_location(obj, request)

            obj.save()
            form.save_m2m()
            messages.success(request, "Appuntamento creato.")
            return redirect("appointment_detail", pk=obj.pk)

        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = AppointmentForm()

    return render(request, "core/appointment_form.html", {"form": form, "object": None, "appointment": None})


@login_required
def appointment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(
        Appointment.objects.select_related("agent", "contact", "property"),
        pk=pk,
    )
    return render(request, "core/appointment_detail.html", {"appointment": obj, "object": obj})


@login_required
def appointment_edit(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Appointment, pk=pk)

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if not me:
            return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
        if obj.agent_id != me.pk:
            return _forbid(request, "Non puoi modificare gli appuntamenti di altri agenti.")

    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=obj)
        if form.is_valid():
            updated = form.save(commit=False)

            # Se non admin, ribadisco l'agente loggato (evita spoofing dal form)
            if not _is_admin_user(request.user):
                updated.agent = _current_agent_for_request(request)

            # ✅ salva sempre location
            _set_appointment_location(updated, request)

            updated.save()
            form.save_m2m()
            messages.success(request, "Appuntamento aggiornato.")
            return redirect("appointment_detail", pk=updated.pk)

        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = AppointmentForm(instance=obj)

    return render(request, "core/appointment_form.html", {"form": form, "object": obj, "appointment": obj})


@login_required
def appointments_calendar(request: HttpRequest) -> HttpResponse:
    return render(request, "core/appointments_calendar.html")


@login_required
def appointments_feed(request: HttpRequest) -> HttpResponse:
    start_q = _parse_dt_local(request.GET.get("start"))
    end_q = _parse_dt_local(request.GET.get("end"))

    qs = Appointment.objects.select_related("agent").all()

    # Visibilità: admin vede tutto, agente vede solo il suo
    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if me:
            qs = qs.filter(agent=me)
        else:
            qs = qs.none()

    if start_q:
        qs = qs.filter(end__gte=start_q)
    if end_q:
        qs = qs.filter(start__lte=end_q)

    qs = qs.order_by("start")

    # Palette “stabile” per agente (ripetibile)
    palette = [
        "#0d6efd",  # blu
        "#198754",  # verde
        "#dc3545",  # rosso
        "#fd7e14",  # arancio
        "#6f42c1",  # viola
        "#20c997",  # teal
        "#0dcaf0",  # cyan
        "#6c757d",  # grigio
    ]

    def color_for_agent(agent_id: int | None) -> str:
        if not agent_id:
            return "#343a40"  # default (dark)
        return palette[(agent_id - 1) % len(palette)]

    data = []
    for a in qs:
        c = color_for_agent(getattr(a, "agent_id", None))
        data.append(
            {
                "id": a.pk,
                "title": getattr(a, "title", "") or "(senza titolo)",
                "start": a.start.isoformat() if a.start else None,
                "end": a.end.isoformat() if a.end else None,
                "url": reverse("appointment_detail", kwargs={"pk": a.pk}),
                # FullCalendar colors
                "backgroundColor": c,
                "borderColor": c,
                "textColor": "#ffffff",
            }
        )
    return JsonResponse(data, safe=False)

@login_required
def appointments_sync(request: HttpRequest) -> HttpResponse:
    messages.info(request, "Sync non attivo.")
    return redirect("appointments_list")


# ============================================================
# MY
# ============================================================

@login_required
def my_calendar(request: HttpRequest) -> HttpResponse:
    if _is_admin_user(request.user):
        return redirect("appointments_calendar")
    me = _current_agent_for_request(request)
    if not me:
        return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
    return redirect("agent_calendar", pk=me.pk)


# ============================================================
# AGENTS
# ============================================================

@login_required
def agents_list(request: HttpRequest) -> HttpResponse:
    agents = _agents_qs()
    return render(request, "core/agents.html", {"agents": agents})


@login_required
def agent_add(request: HttpRequest) -> HttpResponse:
    if not _is_admin_user(request.user):
        return _forbid(request, "Operazione riservata all'amministratore.")

    if request.method == "POST":
        form = AgentForm(request.POST)
        if form.is_valid():
            agent = form.save()
            messages.success(request, "Agente creato.")
            return redirect("agent_detail", pk=agent.pk)
        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = AgentForm()

    return render(request, "core/agent_form.html", {"form": form, "object": None})


@login_required
def agent_new(request: HttpRequest) -> HttpResponse:
    return agent_add(request)


@login_required
def agent_detail(request: HttpRequest, pk: int) -> HttpResponse:
    agent = get_object_or_404(Agent, pk=pk)
    return render(request, "core/agent_detail.html", {"agent": agent, "object": agent})


@login_required
def agent_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not _is_admin_user(request.user):
        return _forbid(request, "Operazione riservata all'amministratore.")

    agent = get_object_or_404(Agent, pk=pk)

    if request.method == "POST":
        form = AgentForm(request.POST, instance=agent)
        if form.is_valid():
            form.save()
            messages.success(request, "Agente aggiornato.")
            return redirect("agent_detail", pk=agent.pk)
        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = AgentForm(instance=agent)

    return render(request, "core/agent_form.html", {"form": form, "agent": agent, "object": agent})


@login_required
def agent_calendar(request: HttpRequest, pk: int) -> HttpResponse:
    agent = get_object_or_404(Agent, pk=pk)
    return render(request, "core/agent_calendar.html", {"agent": agent})


@login_required
def agent_appointments_feed(request: HttpRequest, pk: int) -> HttpResponse:
    agent = get_object_or_404(Agent, pk=pk)

    start_q = _parse_dt_local(request.GET.get("start"))
    end_q = _parse_dt_local(request.GET.get("end"))

    qs = Appointment.objects.filter(agent=agent)
    if start_q:
        qs = qs.filter(end__gte=start_q)
    if end_q:
        qs = qs.filter(start__lte=end_q)

    qs = qs.order_by("start")

    data = []
    for a in qs:
        data.append(
            {
                "id": a.pk,
                "title": getattr(a, "title", "") or "(senza titolo)",
                "start": a.start.isoformat() if a.start else None,
                "end": a.end.isoformat() if a.end else None,
                "url": reverse("appointment_detail", kwargs={"pk": a.pk}),
            }
        )
    return JsonResponse(data, safe=False)


# ============================================================
# PROPERTIES (IMMAGINI + ALLEGATI)
# ============================================================

@login_required
def properties_list(request: HttpRequest) -> HttpResponse:
    props = _properties_qs()
    return render(request, "core/properties.html", {"properties": props})


@login_required
def property_add(request: HttpRequest) -> HttpResponse:
    can_manage_images = _can_manage_images(request, None)
    can_manage_attachments = can_manage_images  # stesso permesso

    image_form = PropertyImageMultiUploadForm()
    attachment_form = PropertyAttachmentMultiUploadForm()

    if request.method == "POST":
        form = PropertyForm(request.POST)
        image_form = PropertyImageMultiUploadForm(request.POST, request.FILES)
        attachment_form = PropertyAttachmentMultiUploadForm(request.POST, request.FILES)

        if form.is_valid():
            obj: Property = form.save(commit=False)

            # se non admin, assegna l'immobile all'agente loggato
            if not _is_admin_user(request.user):
                me = _current_agent_for_request(request)
                if not me:
                    return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
                obj.owner_agent = me

            obj.save()

            # upload immagini
            if can_manage_images:
                pos = 0
                created_any = False
                for f in request.FILES.getlist("images"):
                    PropertyImage.objects.create(property=obj, image=f, position=pos)
                    pos += 1
                    created_any = True

                if created_any and not obj.images.filter(is_primary=True).exists():
                    first_img = obj.images.order_by("position", "id").first()
                    if first_img:
                        first_img.is_primary = True
                        first_img.save(update_fields=["is_primary"])

            # upload allegati
            if can_manage_attachments:
                for f in request.FILES.getlist("attachments"):
                    PropertyAttachment.objects.create(property=obj, file=f)

            messages.success(request, "Immobile creato.")
            return redirect("property_edit", pk=obj.pk)

        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = PropertyForm()

    return render(
        request,
        "core/property_form.html",
        {
            "form": form,
            "image_form": image_form,
            "attachment_form": attachment_form,
            "object": None,
            "images": [],
            "attachments": [],
            "can_manage_images": can_manage_images,
            "can_manage_attachments": can_manage_attachments,
        },
    )


@login_required
def property_detail(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    images = list(prop.images.all().order_by("-is_primary", "position", "id"))
    attachments = list(prop.attachments.all().order_by("-created_at", "id"))
    return render(
        request,
        "core/property_detail.html",
        {"property": prop, "object": prop, "images": images, "attachments": attachments},
    )


@login_required
def property_edit(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Property, pk=pk)

    if not _can_edit_property(request, obj):
        return _forbid(request, "Non puoi modificare immobili di altri agenti.")

    can_manage_images = _can_manage_images(request, obj)
    can_manage_attachments = can_manage_images  # stesso permesso

    image_form = PropertyImageMultiUploadForm()
    attachment_form = PropertyAttachmentMultiUploadForm()

    # --- reorder immagini ---
    if request.method == "POST" and can_manage_images and request.POST.get("reorder_images") == "1":
        order_ids = (request.POST.get("order_ids") or "").strip()
        if order_ids:
            ids = []
            for part in order_ids.split(","):
                part = part.strip()
                if part.isdigit():
                    ids.append(int(part))

            imgs = {i.id: i for i in PropertyImage.objects.filter(property=obj, id__in=ids)}
            pos = 0
            for img_id in ids:
                if img_id in imgs:
                    PropertyImage.objects.filter(id=img_id).update(position=pos)
                    pos += 1

            messages.success(request, "Ordine foto salvato.")
        return redirect("property_edit", pk=obj.pk)

    # --- delete immagine ---
    if request.method == "POST" and can_manage_images and request.POST.get("delete_image"):
        img_id = request.POST.get("delete_image")
        img = get_object_or_404(PropertyImage, pk=img_id, property=obj)
        was_primary = bool(img.is_primary)

        try:
            if img.image:
                img.image.delete(save=False)
        except Exception:
            pass
        img.delete()

        if was_primary:
            next_img = obj.images.order_by("position", "id").first()
            if next_img:
                obj.images.update(is_primary=False)
                next_img.is_primary = True
                next_img.save(update_fields=["is_primary"])

        messages.success(request, "Foto eliminata.")
        return redirect("property_edit", pk=obj.pk)

    # --- set primary ---
    if request.method == "POST" and can_manage_images and request.POST.get("set_primary"):
        img_id = request.POST.get("set_primary")
        img = get_object_or_404(PropertyImage, pk=img_id, property=obj)
        obj.images.update(is_primary=False)
        img.is_primary = True
        img.save(update_fields=["is_primary"])
        messages.success(request, "Foto impostata come principale.")
        return redirect("property_edit", pk=obj.pk)

    # --- delete allegato ---
    if request.method == "POST" and can_manage_attachments and request.POST.get("delete_attachment"):
        att_id = request.POST.get("delete_attachment")
        att = get_object_or_404(PropertyAttachment, pk=att_id, property=obj)
        try:
            if att.file:
                att.file.delete(save=False)
        except Exception:
            pass
        att.delete()
        messages.success(request, "Allegato eliminato.")
        return redirect("property_edit", pk=obj.pk)

    # --- salvataggio immobile + upload (foto + allegati) ---
    if request.method == "POST":
        form = PropertyForm(request.POST, instance=obj)
        image_form = PropertyImageMultiUploadForm(request.POST, request.FILES)
        attachment_form = PropertyAttachmentMultiUploadForm(request.POST, request.FILES)

        if form.is_valid():
            prop = form.save()

            # nuove immagini
            if can_manage_images:
                last_pos = prop.images.aggregate(models.Max("position")).get("position__max")
                if last_pos is None:
                    last_pos = -1
                pos = last_pos + 1

                created_any = False
                for f in request.FILES.getlist("images"):
                    PropertyImage.objects.create(property=prop, image=f, position=pos)
                    pos += 1
                    created_any = True

                if created_any and not prop.images.filter(is_primary=True).exists():
                    first_img = prop.images.order_by("position", "id").first()
                    if first_img:
                        first_img.is_primary = True
                        first_img.save(update_fields=["is_primary"])

            # nuovi allegati
            if can_manage_attachments:
                for f in request.FILES.getlist("attachments"):
                    PropertyAttachment.objects.create(property=prop, file=f)

            messages.success(request, "Immobile aggiornato.")
            return redirect("property_edit", pk=prop.pk)

        messages.error(request, "Controlla i campi evidenziati.")
    else:
        form = PropertyForm(instance=obj)

    images = list(obj.images.all().order_by("-is_primary", "position", "id"))
    attachments = list(obj.attachments.all().order_by("-created_at", "id"))

    return render(
        request,
        "core/property_form.html",
        {
            "form": form,
            "image_form": image_form,
            "attachment_form": attachment_form,
            "object": obj,
            "images": images,
            "attachments": attachments,
            "can_manage_images": can_manage_images,
            "can_manage_attachments": can_manage_attachments,
        },
    )


@login_required
def my_properties(request: HttpRequest) -> HttpResponse:
    return properties_list(request)


# ============================================================
# TODOS
# ============================================================

@login_required
def my_todos(request: HttpRequest) -> HttpResponse:
    if _is_admin_user(request.user):
        agents = _agents_qs().prefetch_related("todos")
        return render(request, "core/my_todos_admin.html", {"agents": agents})

    me = _current_agent_for_request(request)
    if not me:
        return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
    return redirect("agent_todos", pk=me.pk)


@login_required
def my_todos_alias(request: HttpRequest) -> HttpResponse:
    return my_todos(request)


@login_required
def admin_todos(request: HttpRequest) -> HttpResponse:
    agents = _agents_qs()
    blocks = []
    for a in agents:
        open_qs = TodoItem.objects.filter(agent=a, is_done=False).order_by("due_at", "-updated_at")
        closed_qs = TodoItem.objects.filter(agent=a, is_done=True).order_by("due_at", "-updated_at")
        blocks.append({"agent": a, "open_todos": open_qs, "closed_todos": closed_qs})

    return render(request, "core/admin_todos.html", {"agent_blocks": blocks})


@login_required
def agent_todos(request: HttpRequest, pk: int) -> HttpResponse:
    agent = get_object_or_404(Agent, pk=pk)

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if not me:
            return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
        if agent.pk != me.pk:
            return _forbid(request, "Non puoi vedere i To-Do di altri agenti.")

    open_todos = TodoItem.objects.filter(agent=agent, is_done=False).order_by("due_at", "-updated_at")
    closed_todos = TodoItem.objects.filter(agent=agent, is_done=True).order_by("due_at", "-updated_at")

    return render(
        request,
        "core/agent_todos.html",
        {"agent": agent, "open_todos": open_todos, "closed_todos": closed_todos},
    )


def _parse_due_at_from_post(request: HttpRequest) -> Optional[datetime]:
    raw = (request.POST.get("due_at") or "").strip()
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@login_required
def agent_todo_new(request: HttpRequest, pk: int) -> HttpResponse:
    agent = get_object_or_404(Agent, pk=pk)

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if not me:
            return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
        if agent.pk != me.pk:
            return _forbid(request, "Non puoi creare To-Do per altri agenti.")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Titolo obbligatorio.")
            return render(request, "core/todo_form.html", {"agent": agent, "object": None})

        todo = TodoItem(agent=agent, title=title, due_at=_parse_due_at_from_post(request))
        todo.save()
        messages.success(request, "Todo creata.")
        return redirect("agent_todos", pk=agent.pk)

    return render(request, "core/todo_form.html", {"agent": agent, "object": None})


@login_required
def todo_edit(request: HttpRequest, pk: int) -> HttpResponse:
    todo = get_object_or_404(TodoItem, pk=pk)
    agent = todo.agent

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if not me:
            return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
        if todo.agent_id != me.pk:
            return _forbid(request, "Non puoi modificare i To-Do di altri agenti.")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Titolo obbligatorio.")
            return render(request, "core/todo_form.html", {"agent": agent, "object": todo})

        todo.title = title
        todo.due_at = _parse_due_at_from_post(request)
        todo.save(update_fields=["title", "due_at", "updated_at"])

        messages.success(request, "Todo aggiornata.")
        return redirect("agent_todos", pk=agent.pk)

    return render(request, "core/todo_form.html", {"agent": agent, "object": todo})


@login_required
def todo_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    todo = get_object_or_404(TodoItem, pk=pk)

    if not _is_admin_user(request.user):
        me = _current_agent_for_request(request)
        if not me:
            return _forbid(request, "Questo utente non è collegato ad alcun Agente.")
        if todo.agent_id != me.pk:
            return _forbid(request, "Non puoi modificare i To-Do di altri agenti.")

    todo.is_done = not bool(todo.is_done)
    todo.save(update_fields=["is_done", "updated_at"])
    return redirect(request.META.get("HTTP_REFERER") or reverse("admin_todos"))


# ============================================================
# GOOGLE (stub)
# ============================================================

@login_required
def google_sync(request: HttpRequest) -> HttpResponse:
    messages.info(request, "Google sync non configurato.")
    return redirect("crm_dashboard")
