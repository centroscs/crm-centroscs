from django.urls import path
from . import views_crm
from django.db import models

urlpatterns = [
    path("crm/", views_crm.crm_dashboard, name="crm_dashboard"),

    # Contacts
    path("crm/contacts/", views_crm.contacts_list, name="contacts_list"),
    path("crm/contacts/new/", views_crm.contact_new, name="contact_new"),
    path("crm/contacts/<int:pk>/", views_crm.contact_detail, name="contact_detail"),
    path("crm/contacts/<int:pk>/edit/", views_crm.contact_edit, name="contact_edit"),

    # Appointments
    path("crm/appointments/", views_crm.appointments_list, name="appointments_list"),
    path("crm/appointments/new/", views_crm.appointment_new, name="appointment_new"),
    path("crm/appointments/<int:pk>/", views_crm.appointment_detail, name="appointment_detail"),
    path("crm/appointments/<int:pk>/edit/", views_crm.appointment_edit, name="appointment_edit"),
    path("crm/appointments/calendar/", views_crm.appointments_calendar, name="appointments_calendar"),
    path("crm/appointments/feed/", views_crm.appointments_feed, name="appointments_feed"),
    path("crm/appointments/sync/", views_crm.appointments_sync, name="appointments_sync"),

    # My calendar alias
    path("crm/my/calendar/", views_crm.my_calendar, name="my_calendar"),

    # Agents
    path("crm/agents/", views_crm.agents_list, name="agents_list"),
    path("crm/agents/add/", views_crm.agent_add, name="agent_add"),
    path("crm/agents/<int:pk>/", views_crm.agent_detail, name="agent_detail"),
    path("crm/agents/<int:pk>/calendar/", views_crm.agent_calendar, name="agent_calendar"),
    path("crm/agents/<int:pk>/feed/", views_crm.agent_appointments_feed, name="agent_appointments_feed"),
    path("crm/agents/new/", views_crm.agent_add, name="agent_new"),
    path("crm/agents/<int:pk>/edit/", views_crm.agent_edit, name="agent_edit"),

    # Properties
    path("crm/properties/", views_crm.properties_list, name="properties_list"),
    path("crm/properties/add/", views_crm.property_add, name="property_add"),
    path("crm/properties/<int:pk>/", views_crm.property_detail, name="property_detail"),
    path("crm/properties/<int:pk>/edit/", views_crm.property_edit, name="property_edit"),

    # Todos (se già li avevi nel menu)
    path("crm/my/todos/", views_crm.my_todos_alias, name="my_todos_alias"),
    path("crm/todos/admin/", views_crm.admin_todos, name="admin_todos"),
    path("crm/agents/<int:pk>/todos/", views_crm.agent_todos, name="agent_todos"),
    path("crm/agents/<int:pk>/todos/new/", views_crm.agent_todo_new, name="agent_todo_new"),
    path("crm/todos/<int:pk>/edit/", views_crm.todo_edit, name="todo_edit"),
    path("crm/todos/<int:pk>/toggle/", views_crm.todo_toggle, name="todo_toggle"),
]
