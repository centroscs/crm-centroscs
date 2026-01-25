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


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = "__all__"


class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = "__all__"


class TodoItemForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = "__all__"
