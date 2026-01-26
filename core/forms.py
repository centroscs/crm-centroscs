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

class PropertyAttachmentMultiUploadForm(forms.Form):
    attachments = forms.FileField(
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


class AppointmentForm(forms.ModelForm):
    """
    Usa datetime-local (menu) per start/end.
    Il campo "location" NON è nel model (altrimenti Django darebbe FieldError),
    quindi lo gestiamo in template+view.
    """
    start = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
    )
    end = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
    )

    class Meta:
        model = Appointment
        fields = [
            "title",
            "agent",
            "contact",
            "property",
            "start",
            "end",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and getattr(self.instance, "pk", None):
            if self.instance.start:
                self.fields["start"].initial = self.instance.start.strftime("%Y-%m-%dT%H:%M")
            if self.instance.end:
                self.fields["end"].initial = self.instance.end.strftime("%Y-%m-%dT%H:%M")

class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = "__all__"


class TodoItemForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = "__all__"	
