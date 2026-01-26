from django import forms

from .models import Agent, Appointment, Contact, Property, TodoItem


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class PropertyImageMultiUploadForm(forms.Form):
    images = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"multiple": True}),
        label="",
    )


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = "__all__"


from django import forms
from .models import Appointment

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = "__all__"
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # se in futuro Django cambia widget, lo forziamo qui
        self.fields["start"].widget.input_type = "datetime-local"
        self.fields["end"].widget.input_type = "datetime-local"

        # Precompila correttamente in edit
        for f in ("start", "end"):
            dt = getattr(self.instance, f, None)
            if dt:
                self.initial[f] = dt.strftime("%Y-%m-%dT%H:%M")

class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = "__all__"


class TodoItemForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = "__all__"
