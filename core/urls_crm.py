# core/urls_crm.py
from __future__ import annotations

from django.urls import path
from core import views_crm

urlpatterns = [
    path("appointments/", views_crm.appointment_list, name="crm_appointment_list"),
    path("appointments/new/", views_crm.appointment_create, name="crm_appointment_create"),
    path("appointments/<int:pk>/edit/", views_crm.appointment_edit, name="crm_appointment_edit"),
    path("appointments/<int:pk>/push/", views_crm.appointment_push_one, name="crm_appointment_push_one"),
    path("appointments/push/", views_crm.appointment_push_batch, name="crm_appointment_push_batch"),
]
